"""Filesystem layout and auto-detection for RDR2 Shader Tool.

Every path is anchored to ROOT (the repository directory). Data directories (source, compiled,
decompiled, fxdb_files, lml_mods) live at ROOT; code lives in src/.
Includes automatic registry and filesystem discovery for Red Dead Redemption 2 installations.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Repository root (where r2sm.bat / main.py live)
ROOT = Path(__file__).resolve().parent.parent.parent

# Subdirectories inside the repository
SRC_DIR = ROOT / "src"
COMPILERS_DIR = ROOT / "compilers"
CACHE_DIR = ROOT / ".r2cache"

SOURCE_DIR = ROOT / "source"
COMPILED_DIR = ROOT / "compiled"
DECOMPILED_DIR = ROOT / "decompiled"
FXDB_FILES_DIR = ROOT / "fxdb_files"
SHADERS_DUMP_DIR = ROOT / "shaders_dump"
LML_EXPORT_DIR = ROOT / "lml_export"
SETTINGS_FILE = ROOT / "settings.ini"


def detect_game_dir() -> Path:
    """Auto-detect Red Dead Redemption 2 installation directory via Registry or common paths."""
    candidates = []

    # 1. Windows Registry (Rockstar Games Launcher)
    if sys.platform == "win32":
        import winreg

        reg_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Rockstar Games\Red Dead Redemption 2", "InstallFolder"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Rockstar Games\Red Dead Redemption 2", "InstallFolder"),
            (winreg.HKEY_CURRENT_USER, r"Software\Rockstar Games\Red Dead Redemption 2", "InstallFolder"),
        ]
        for hive, subkey, val_name in reg_keys:
            try:
                with winreg.OpenKey(hive, subkey) as k:
                    val, _ = winreg.QueryValueEx(k, val_name)
                    if val and Path(val).exists():
                        candidates.append(Path(val))
            except Exception:
                pass

        # 2. Steam Library Detection
        steam_keys = [
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        ]
        for hive, subkey, val_name in steam_keys:
            try:
                with winreg.OpenKey(hive, subkey) as k:
                    val, _ = winreg.QueryValueEx(k, val_name)
                    if val:
                        steam_rdr2 = Path(val) / "steamapps" / "common" / "Red Dead Redemption 2"
                        if steam_rdr2.exists():
                            candidates.append(steam_rdr2)
            except Exception:
                pass

    # 3. Known common install locations across drives
    for drive in ["C", "D", "E", "F", "G"]:
        d_path = Path(f"{drive}:/")
        if not d_path.exists():
            continue
        candidates.extend([
            d_path / "Red Dead Redemption 2",
            d_path / "Games" / "Red Dead Redemption 2",
            d_path / "Program Files" / "Rockstar Games" / "Red Dead Redemption 2",
            d_path / "Program Files (x86)" / "Steam" / "steamapps" / "common" / "Red Dead Redemption 2",
            d_path / "SteamLibrary" / "steamapps" / "common" / "Red Dead Redemption 2",
        ])

    for c in candidates:
        if c.exists() and (c / "RDR2.exe").exists():
            return c

    for c in candidates:
        if c.exists():
            return c

    return Path("")


def detect_dump_dir() -> Path:
    """Auto-detect directory containing extracted shaders/fxdb files."""
    # 1. Local workspace directories
    if FXDB_FILES_DIR.exists() and any(FXDB_FILES_DIR.glob("*.fxdb")):
        return FXDB_FILES_DIR

    if SHADERS_DUMP_DIR.exists():
        return SHADERS_DUMP_DIR

    # 2. Check sibling directory named RDR2_Shaders
    sibling_dump = ROOT.parent / "RDR2_Shaders"
    if sibling_dump.exists():
        return sibling_dump

    return SHADERS_DUMP_DIR


DEFAULT_GAME_DIR = detect_game_dir()
DEFAULT_DUMP_DIR = detect_dump_dir()


def ensure(path: Path) -> Path:
    """Ensure directory exists and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def init_workspace():
    """Create all working directories if they do not exist."""
    for p in (CACHE_DIR, SOURCE_DIR / "vulkan", SOURCE_DIR / "dx12",
              COMPILED_DIR / "vulkan", COMPILED_DIR / "dx12",
              DECOMPILED_DIR / "vulkan", DECOMPILED_DIR / "dx12",
              FXDB_FILES_DIR, SHADERS_DUMP_DIR, LML_EXPORT_DIR):
        ensure(p)
