"""RDR2 game shader package reference and CodeX extraction map.

In Red Dead Redemption 2, shaders are stored inside shaders_x64.rpf in the game
installation directory. Because CodeX exports unmapped entries using Rage hash
filenames, this module maps those raw .bin hashes to their respective .fxdb names.
"""

from typing import Dict, List, Optional


GAME_SHADER_PACKAGES = [
    {
        "archive": "shaders_x64.rpf",
        "hash_file": "0xFEEB1B85.bin",
        "fxdb_name": "sga_vulkan_final.fxdb",
        "api": "vulkan",
        "shader_count": 12883,
        "description": "Main Vulkan game shaders (world, lighting, materials, post-processing)",
        "expected_size": 119244896,
    },
    {
        "archive": "shaders_x64.rpf",
        "hash_file": "0x8068F4F9.bin",
        "fxdb_name": "sga_win32_60_final.fxdb",
        "api": "dx12",
        "shader_count": 12255,
        "description": "Main DirectX 12 game shaders (world, lighting, materials, post-processing)",
        "expected_size": 112837792,
    },
    {
        "archive": "shaders_x64.rpf (and update_1.rpf)",
        "hash_file": "0xA8C90D00.bin",
        "fxdb_name": "sga_vulkan_final_init.fxdb",
        "api": "vulkan",
        "shader_count": 369,
        "description": "Vulkan engine initialization shaders",
        "expected_size": 945552,
    },
    {
        "archive": "shaders_x64.rpf (and update_1.rpf)",
        "hash_file": "0x2A25B571.bin",
        "fxdb_name": "sga_win32_60_final_init.fxdb",
        "api": "dx12",
        "shader_count": 367,
        "description": "DirectX 12 engine initialization shaders",
        "expected_size": 892592,
    },
]

HASH_TO_FXDB: Dict[str, str] = {
    "0xfeeb1b85.bin": "sga_vulkan_final.fxdb",
    "feeb1b85.bin": "sga_vulkan_final.fxdb",
    "0x8068f4f9.bin": "sga_win32_60_final.fxdb",
    "8068f4f9.bin": "sga_win32_60_final.fxdb",
    "0xa8c90d00.bin": "sga_vulkan_final_init.fxdb",
    "a8c90d00.bin": "sga_vulkan_final_init.fxdb",
    "0x2a25b571.bin": "sga_win32_60_final_init.fxdb",
    "2a25b571.bin": "sga_win32_60_final_init.fxdb",
}


def resolve_fxdb_name(filename: str) -> str:
    """Return canonical .fxdb name if the file is a raw CodeX hash export, else return unchanged."""
    clean = filename.strip().lower()
    return HASH_TO_FXDB.get(clean, filename)


def check_folder_shader_status(folder_path: Optional[str] = None) -> List[Dict]:
    """Inspect folder and subfolders to determine which shader packages are present."""
    from pathlib import Path
    from . import paths, settings

    if not folder_path:
        folder_path = settings.settings().get("Paths", "rdr2_shaders_dump", str(paths.DEFAULT_DUMP_DIR))

    base_dir = Path(folder_path)
    search_dirs = [base_dir / "fxdb", base_dir, paths.FXDB_FILES_DIR, paths.SHADERS_DUMP_DIR]

    statuses = []
    for pkg in GAME_SHADER_PACKAGES:
        fxdb_name = pkg["fxdb_name"]
        hash_file = pkg["hash_file"]

        found = False
        found_file = None
        for s_dir in search_dirs:
            if s_dir and s_dir.exists():
                for cand in (fxdb_name, hash_file, hash_file.lower(), hash_file.upper()):
                    target = s_dir / cand
                    if target.exists():
                        found = True
                        found_file = target
                        break
            if found:
                break

        statuses.append({
            "archive": pkg["archive"],
            "hash_file": pkg["hash_file"],
            "fxdb_name": pkg["fxdb_name"],
            "api": pkg["api"],
            "shader_count": pkg["shader_count"],
            "expected_size": pkg["expected_size"],
            "description": pkg["description"],
            "found": found,
            "path": str(found_file) if found_file else "",
        })

    return statuses
