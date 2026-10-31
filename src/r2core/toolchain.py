"""Subprocess runner and tool discovery for RDR2 Shader Tool."""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from . import paths

_KNOWN_TOOLS = {
    # Vulkan
    "spirv_cross": "spirv-cross.exe",
    "spirv_dis": "spirv-dis.exe",
    "spirv_as": "spirv-as.exe",
    "spirv_val": "spirv-val.exe",
    "spirv_opt": "spirv-opt.exe",
    "glslc": "glslc.exe",
    "glslang": "glslangValidator.exe",
    # DX12
    "decomp": "decomp.exe",
    "dxc": "dxc.exe",
    "dxil_spirv": "dxil-spirv.exe",
    "dxbc2dxil": "dxbc2dxil.exe",
    "dxil_extract": "dxil-extract.exe",
    "fxc": "fxc.exe",
}


@dataclass
class ToolResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    cmd: List[str]

    def tail(self, lines: int = 5) -> str:
        text = self.stderr.strip() or self.stdout.strip()
        parts = text.splitlines()
        return "\n".join(parts[-lines:]) if parts else ""


class Toolchain:
    """Manages compilers and decompilers."""

    def __init__(self, compilers_dir: Optional[Path] = None):
        self.compilers_dir = compilers_dir or paths.COMPILERS_DIR

    def find_tool(self, tool_id: str) -> Optional[Path]:
        exe_name = _KNOWN_TOOLS.get(tool_id, tool_id if tool_id.endswith(".exe") else f"{tool_id}.exe")
        local_path = self.compilers_dir / exe_name
        if local_path.exists():
            return local_path

        # Fallback to system PATH
        which = shutil.which(exe_name)
        return Path(which) if which else None

    def status(self) -> Dict[str, Dict[str, Union[bool, str]]]:
        """Check availability and version of all known tools."""
        res = {}
        for tool_id in _KNOWN_TOOLS:
            path = self.find_tool(tool_id)
            if not path or not path.exists():
                res[tool_id] = {"available": False, "path": "", "version": "Not found"}
                continue

            ver = "Available"
            try:
                # Try running version check
                flag = "-help" if tool_id == "decomp" else "--version"
                r = subprocess.run([str(path), flag], capture_output=True, text=True, timeout=5)
                out = (r.stdout or r.stderr or "").strip().splitlines()
                if out:
                    ver = out[0][:60]
            except Exception:
                pass

            res[tool_id] = {"available": True, "path": str(path), "version": ver}

        return res

    def run(self, tool_id: str, args: List[Union[str, Path]], cwd: Optional[Path] = None, timeout: int = 120) -> ToolResult:
        tool_path = self.find_tool(tool_id)
        if not tool_path:
            raise FileNotFoundError(f"Compiler/Decompiler tool '{tool_id}' not found in {self.compilers_dir}")

        cmd = [str(tool_path)] + [str(a) for a in args]
        work_dir = cwd or self.compilers_dir

        try:
            p = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace"
            )
            return ToolResult(
                ok=(p.returncode == 0),
                returncode=p.returncode,
                stdout=p.stdout,
                stderr=p.stderr,
                cmd=cmd
            )
        except subprocess.TimeoutExpired as e:
            return ToolResult(
                ok=False,
                returncode=-1,
                stdout=e.stdout or "" if isinstance(e.stdout, str) else "",
                stderr=f"Timed out after {timeout}s",
                cmd=cmd
            )
        except Exception as ex:
            return ToolResult(
                ok=False,
                returncode=-2,
                stdout="",
                stderr=str(ex),
                cmd=cmd
            )


_toolchain_instance: Optional[Toolchain] = None


def get_toolchain() -> Toolchain:
    global _toolchain_instance
    if _toolchain_instance is None:
        _toolchain_instance = Toolchain()
    return _toolchain_instance
