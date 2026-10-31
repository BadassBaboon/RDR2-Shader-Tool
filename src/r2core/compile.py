"""Compilation engine for RDR2 shaders: HLSL/GLSL to Vulkan (SPIR-V) and DirectX 12 (DXIL)."""

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from . import paths
from .toolchain import get_toolchain

_STAGE_PATTERNS = [
    (re.compile(r"(?:[._-]vs(?:[._-]|$)|\bvs/)", re.I), "vs", "vs_6_0"),
    (re.compile(r"(?:[._-]ps(?:[._-]|$)|\bps/)", re.I), "ps", "ps_6_0"),
    (re.compile(r"(?:[._-]cs(?:[._-]|$)|\bcs/)", re.I), "cs", "cs_6_0"),
    (re.compile(r"(?:[._-]gs(?:[._-]|$)|\bgs/)", re.I), "gs", "gs_6_0"),
    (re.compile(r"(?:[._-]ds(?:[._-]|$)|\bds/)", re.I), "ds", "ds_6_0"),
    (re.compile(r"(?:[._-]hs(?:[._-]|$)|\bhs/)", re.I), "hs", "hs_6_0"),
]


@dataclass
class CompileResult:
    ok: bool
    target_api: str
    stage: str
    profile: str
    bytecode: bytes
    error: str = ""
    warnings: str = ""
    steps: List[str] = None


def detect_stage(path_or_name: Union[str, Path], content: Optional[str] = None) -> Tuple[str, str]:
    """Detect shader stage ('vs', 'ps', etc.) and default SM 6.0 profile ('vs_6_0')."""
    s = str(path_or_name).replace("\\", "/")

    for pat, stage, prof in _STAGE_PATTERNS:
        if pat.search(s):
            return stage, prof

    # Check content if available
    if content:
        if "SV_Position" in content and "SV_Target" not in content and "numthreads" not in content:
            return "vs", "vs_6_0"
        elif "SV_Target" in content:
            return "ps", "ps_6_0"
        elif "numthreads" in content:
            return "cs", "cs_6_0"

    # Default fallback to pixel shader
    return "ps", "ps_6_0"


def compile_to_vulkan(
    source_file_or_code: Union[str, Path],
    stage: Optional[str] = None,
    entry_point: str = "main",
    target_env: str = "vulkan1.1",
    optimize: bool = False,
    defines: Optional[Dict[str, str]] = None
) -> CompileResult:
    """Compile HLSL or GLSL source to Vulkan SPIR-V binary."""
    tc = get_toolchain()
    steps = []

    with tempfile.TemporaryDirectory(prefix="r2_compile_vk_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        if isinstance(source_file_or_code, Path) or (isinstance(source_file_or_code, str) and os.path.isfile(source_file_or_code)):
            src_path = Path(source_file_or_code).resolve()
            code_text = src_path.read_text(encoding="utf-8", errors="replace")
        else:
            code_text = str(source_file_or_code)
            src_path = (tmp_path / "shader.hlsl").resolve()
            src_path.write_text(code_text, encoding="utf-8")

        det_stage, profile = detect_stage(src_path, code_text)
        actual_stage = stage or det_stage

        spv_out = tmp_path / "output.spv"

        # Check if source is GLSL or HLSL
        is_glsl = src_path.suffix.lower() in (".glsl", ".frag", ".vert", ".comp")

        if is_glsl:
            # Compile via glslc
            args = [str(src_path), "-o", str(spv_out), f"--target-env={target_env}"]
            if defines:
                for k, v in defines.items():
                    args.append(f"-D{k}={v}")
            r = tc.run("glslc", args, cwd=tmp_path)
            steps.append("glslc")
        else:
            # Compile via dxc -spirv
            prof = f"{actual_stage.lower()}_6_0"
            args = [
                str(src_path),
                "-spirv",
                "-T", prof,
                "-E", entry_point,
                "-Fo", str(spv_out),
                f"-fspv-target-env={target_env}",
                "-fvk-use-dx-layout"
            ]
            if defines:
                for k, v in defines.items():
                    args.append(f"-D{k}={v}")
            r = tc.run("dxc", args, cwd=tmp_path)
            steps.append("dxc -spirv")

        if not r.ok or not spv_out.exists():
            return CompileResult(
                ok=False,
                target_api="vulkan",
                stage=actual_stage,
                profile=profile,
                bytecode=b"",
                error=r.tail(10),
                steps=steps
            )

        # Validate with spirv-val
        val_res = tc.run("spirv_val", [str(spv_out)], cwd=tmp_path)
        if not val_res.ok:
            return CompileResult(
                ok=False,
                target_api="vulkan",
                stage=actual_stage,
                profile=profile,
                bytecode=b"",
                error=f"SPIR-V validation failed:\n{val_res.tail(10)}",
                steps=steps
            )
        steps.append("spirv-val")

        # Optional optimize
        if optimize:
            opt_out = tmp_path / "opt.spv"
            opt_res = tc.run("spirv_opt", ["-O", str(spv_out), "-o", str(opt_out)], cwd=tmp_path)
            if opt_res.ok and opt_out.exists():
                spv_out = opt_out
                steps.append("spirv-opt")

        compiled_bytes = spv_out.read_bytes()
        return CompileResult(
            ok=True,
            target_api="vulkan",
            stage=actual_stage,
            profile=profile,
            bytecode=compiled_bytes,
            warnings=r.stderr if r.ok else "",
            steps=steps
        )


def compile_to_dx12(
    source_file_or_code: Union[str, Path],
    stage: Optional[str] = None,
    entry_point: str = "main",
    profile: Optional[str] = None,
    defines: Optional[Dict[str, str]] = None
) -> CompileResult:
    """Compile HLSL source to DirectX 12 DXIL CSO binary."""
    tc = get_toolchain()
    steps = []

    with tempfile.TemporaryDirectory(prefix="r2_compile_dx12_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        if isinstance(source_file_or_code, Path) or (isinstance(source_file_or_code, str) and os.path.isfile(source_file_or_code)):
            src_path = Path(source_file_or_code).resolve()
            code_text = src_path.read_text(encoding="utf-8", errors="replace")
        else:
            code_text = str(source_file_or_code)
            src_path = (tmp_path / "shader.hlsl").resolve()
            src_path.write_text(code_text, encoding="utf-8")

        det_stage, det_prof = detect_stage(src_path, code_text)
        actual_stage = stage or det_stage
        actual_prof = profile or f"{actual_stage.lower()}_6_0"

        cso_out = tmp_path / "output.cso"

        args = [
            str(src_path),
            "-T", actual_prof,
            "-E", entry_point,
            "-Fo", str(cso_out),
            "-O3"
        ]
        if defines:
            for k, v in defines.items():
                args.append(f"-D{k}={v}")

        r = tc.run("dxc", args, cwd=tmp_path)
        steps.append("dxc (DX12)")

        if not r.ok or not cso_out.exists():
            return CompileResult(
                ok=False,
                target_api="dx12",
                stage=actual_stage,
                profile=actual_prof,
                bytecode=b"",
                error=r.tail(10),
                steps=steps
            )

        compiled_bytes = cso_out.read_bytes()
        return CompileResult(
            ok=True,
            target_api="dx12",
            stage=actual_stage,
            profile=actual_prof,
            bytecode=compiled_bytes,
            warnings=r.stderr if r.ok else "",
            steps=steps
        )


def compile_shader(
    source_file_or_code: Union[str, Path],
    target_api: str = "vulkan",
    stage: Optional[str] = None,
    entry_point: str = "main",
    defines: Optional[Dict[str, str]] = None
) -> CompileResult:
    """Unified entry point to compile shader source to either Vulkan or DX12."""
    if target_api.lower() == "vulkan":
        return compile_to_vulkan(source_file_or_code, stage=stage, entry_point=entry_point, defines=defines)
    else:
        return compile_to_dx12(source_file_or_code, stage=stage, entry_point=entry_point, defines=defines)
