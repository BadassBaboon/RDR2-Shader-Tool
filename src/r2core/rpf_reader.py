"""Direct RPF archive reader for RDR2 using CodeX Rpf8 interop."""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Union

from . import paths
from .settings import settings


def extract_from_shaders_rpf(
    rpf_path: Optional[Union[str, Path]] = None,
    output_dir: Optional[Union[str, Path]] = None,
    game_dir: Optional[Union[str, Path]] = None
) -> Dict[str, Union[bool, str, List[str]]]:
    """Extract files from shaders_x64.rpf using rpf_probe tool."""
    cfg = settings()
    g_dir = Path(game_dir or cfg.game_dir)
    r_path = Path(rpf_path or (g_dir / "shaders_x64.rpf"))
    out_d = Path(output_dir or paths.FXDB_FILES_DIR)
    out_d.mkdir(parents=True, exist_ok=True)

    if not r_path.exists():
        return {
            "ok": False,
            "error": f"RPF file not found: {r_path}",
            "extracted_files": []
        }

    # Use dotnet probe helper if present in tools/rpf_probe
    probe_dir = paths.ROOT / "tools" / "rpf_probe"
    if not probe_dir.exists():
        return {
            "ok": False,
            "error": "Direct RPF extractor is not configured. Place extracted .fxdb files into fxdb_files/ or shaders_dump/.",
            "extracted_files": []
        }

    # Run extraction script
    extract_script = f"""
using System;
using System.IO;
using CodeX.Games.RDR2.RPF8;
using CodeX.Core.Engine;

class Program {{
    static void Main(string[] args) {{
        string gameDir = @\"{g_dir}\";
        Rpf8Crypto.Init(gameDir);
        string rpfPath = @\"{r_path}\";
        string outDir = @\"{out_d}\";
        var rpf = new Rpf8File(rpfPath, \"shaders_x64.rpf\");
        using (var fs = File.OpenRead(rpfPath))
        using (var br = new BinaryReader(fs)) {{
            var method = typeof(Rpf8File).GetMethod(\"ReadHeader\", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            method?.Invoke(rpf, new object[] {{ br }});
        }}
        foreach (var entry in rpf.AllEntries) {{
            if (entry is GameArchiveFileInfo fi) {{
                byte[] data = rpf.ExtractFile(fi);
                if (data != null) {{
                    string outPath = Path.Combine(outDir, entry.Name);
                    File.WriteAllBytes(outPath, data);
                    Console.WriteLine(\"EXTRACTED:\" + outPath);
                }}
            }}
        }}
    }}
}}
"""
    prog_cs = probe_dir / "Program.cs"
    prog_cs.write_text(extract_script, encoding="utf-8")

    res = subprocess.run(
        ["dotnet", "run", "-c", "Release"],
        cwd=str(probe_dir),
        capture_output=True,
        text=True
    )

    extracted = []
    for line in res.stdout.splitlines():
        if line.startswith("EXTRACTED:"):
            extracted.append(line.replace("EXTRACTED:", "").strip())

    return {
        "ok": res.returncode == 0,
        "extracted_files": extracted,
        "stdout": res.stdout,
        "stderr": res.stderr
    }
