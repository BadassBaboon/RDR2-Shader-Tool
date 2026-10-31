"""Decompilation engine for RDR2 shaders: Vulkan (SPIR-V) and DirectX 12 (DXIL/DXBC)."""

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

from . import paths
from .fxdb_models import ShaderData, ShaderRecord
from .toolchain import get_toolchain


@dataclass
class DecompileResult:
    ok: bool
    method: str
    source_code: str
    disassembly: str = ""
    error: str = ""
    steps: List[str] = field(default_factory=list)


def decompile_spirv(
    spv_bytes: bytes,
    target_lang: str = "hlsl",
    stage: Optional[str] = None,
    shader_data: Optional[ShaderData] = None,
    disassemble: bool = True
) -> DecompileResult:
    """Decompile Vulkan SPIR-V bytecode using spirv-cross and spirv-dis."""
    tc = get_toolchain()
    steps = []

    with tempfile.TemporaryDirectory(prefix="r2_spv_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        spv_file = tmp_path / "shader.spv"
        spv_file.write_bytes(spv_bytes)

        # 1. Disassemble via spirv-dis if requested
        disasm_text = ""
        if disassemble:
            dis_res = tc.run("spirv_dis", [spv_file], cwd=tmp_path)
            if dis_res.ok:
                disasm_text = dis_res.stdout
                steps.append("spirv-dis")

        # 2. Decompile via spirv-cross
        args = [str(spv_file)]
        if target_lang.lower() == "hlsl":
            args.extend(["--hlsl", "--shader-model", "60"])
        else:
            args.extend(["--version", "450", "--vulkan-semantics"])

        if stage:
            s_lower = stage.lower()
            if "vs" in s_lower:
                args.extend(["--stage", "vert"])
            elif "ps" in s_lower:
                args.extend(["--stage", "frag"])
            elif "cs" in s_lower:
                args.extend(["--stage", "comp"])
            elif "gs" in s_lower:
                args.extend(["--stage", "geom"])
            elif "ds" in s_lower:
                args.extend(["--stage", "tese"])
            elif "hs" in s_lower:
                args.extend(["--stage", "tesc"])

        res = tc.run("spirv_cross", args, cwd=tmp_path)
        if not res.ok:
            return DecompileResult(
                ok=False,
                method="spirv-cross",
                source_code="",
                disassembly=disasm_text,
                error=res.tail(),
                steps=steps
            )

        steps.append("spirv-cross")
        code = res.stdout

        # 3. Post-process: Annotate with metadata from FXDB ShaderData if available
        if shader_data and shader_data.resources:
            code = _annotate_with_reflection(code, shader_data)

        return DecompileResult(
            ok=True,
            method="spirv-cross",
            source_code=code,
            disassembly=disasm_text,
            steps=steps
        )


def decompile_dx12(
    cso_bytes: bytes,
    stage: Optional[str] = None,
    preferred_method: str = "decomp",
    disassemble: bool = True
) -> DecompileResult:
    """Decompile DirectX 12 DXIL/DXBC bytecode using RenoDX decomp.exe or dxil-spirv."""
    tc = get_toolchain()
    steps = []

    with tempfile.TemporaryDirectory(prefix="r2_dx12_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        cso_file = tmp_path / "shader.cso"
        cso_file.write_bytes(cso_bytes)

        # 1. Disassemble using dxc -dumpbin
        disasm_text = ""
        if disassemble:
            dxc_res = tc.run("dxc", ["-dumpbin", cso_file], cwd=tmp_path)
            if dxc_res.ok:
                disasm_text = dxc_res.stdout
                steps.append("dxc -dumpbin")

        out_hlsl = tmp_path / "decompiled.hlsl"

        # 2. Primary Route: decomp.exe (RenoDX)
        if preferred_method == "decomp":
            decomp_res = tc.run("decomp", [cso_file, out_hlsl], cwd=paths.COMPILERS_DIR)
            if decomp_res.ok and out_hlsl.exists() and out_hlsl.stat().st_size > 0:
                steps.append("decomp.exe")
                return DecompileResult(
                    ok=True,
                    method="decomp.exe",
                    source_code=out_hlsl.read_text(encoding="utf-8", errors="replace"),
                    disassembly=disasm_text,
                    steps=steps
                )

        # 3. Fallback Route: dxil-spirv + spirv-cross
        spv_out = tmp_path / "from_dxil.spv"
        dxil_res = tc.run("dxil_spirv", [cso_file, "-o", spv_out], cwd=tmp_path)
        if dxil_res.ok and spv_out.exists():
            steps.append("dxil-spirv")
            cross_res = tc.run("spirv_cross", [str(spv_out), "--hlsl", "--shader-model", "60"], cwd=tmp_path)
            if cross_res.ok:
                steps.append("spirv-cross")
                return DecompileResult(
                    ok=True,
                    method="dxil-spirv+spirv-cross",
                    source_code=cross_res.stdout,
                    disassembly=disasm_text,
                    steps=steps
                )

        # Both failed
        return DecompileResult(
            ok=False,
            method="decomp",
            source_code="",
            disassembly=disasm_text,
            error="Both decomp.exe and dxil-spirv failed to decompile the shader.",
            steps=steps
        )


def decompile_shader(
    shader_or_bytes: Union[ShaderRecord, bytes],
    api: str = "vulkan",
    target_lang: str = "hlsl",
    stage: Optional[str] = None
) -> DecompileResult:
    """Unified entry point to decompile a shader record or raw bytecode."""
    if isinstance(shader_or_bytes, ShaderRecord):
        rec = shader_or_bytes
        st = rec.stage
        sdata = rec.data
        bc = rec.bytecode  # already decompressed
        if rec.is_spirv or api.lower() == "vulkan":
            return decompile_spirv(bc, target_lang=target_lang, stage=st, shader_data=sdata)
        else:
            return decompile_dx12(bc, stage=st)
    else:
        bc = shader_or_bytes
        is_spv = len(bc) >= 4 and bc[:4] == b'\x03\x02#\x07'
        if is_spv or api.lower() == "vulkan":
            return decompile_spirv(bc, target_lang=target_lang, stage=stage)
        else:
            return decompile_dx12(bc, stage=stage)


def _annotate_with_reflection(source: str, sdata: ShaderData) -> str:
    """Prepend reflection comments to decompiler output with CBuffer layouts and resources."""
    lines = [
        "// ===========================================================================",
        "// RDR2 Shader Reflection Metadata (from RAGE SGA v1)",
        "// ===========================================================================",
    ]

    for res in sdata.resources:
        lines.append(f"// Resource: {res.name} (Type={res.resource_type.name}, Class={res.resource_class.name}, Slot={res.bind_point}, Size={res.byte_size}B)")
        if res.elements:
            lines.append("//   CBuffer Fields:")
            for elem in res.elements:
                arr = f"[{elem.array_size}]" if elem.array_size > 0 else ""
                lines.append(f"//     +{elem.start_offset:04d}: {elem.var_type.name} {elem.name}{arr};")

    lines.append("// ===========================================================================\n")
    return "\n".join(lines) + source
