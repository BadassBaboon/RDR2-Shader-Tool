"""Filesystem layout for RDR2 Shader Tool.

Every path is anchored to ROOT (the repository directory). Data directories (source, compiled,
decompiled, fxdb_files, lml_mods) live at ROOT; code lives in src/.
"""

import os
import sys
from pathlib import Path

# Repository root (where sm.bat / main.py live)
ROOT = Path(__file__).resolve().parent.parent.parent

# Subdirectories
SRC_DIR = ROOT / "src"
COMPILERS_DIR = ROOT / "compilers"
CACHE_DIR = ROOT / ".r2cache"

SOURCE_DIR = ROOT / "source"
COMPILED_DIR = ROOT / "compiled"
DECOMPILED_DIR = ROOT / "decompiled"
FXDB_FILES_DIR = ROOT / "fxdb_files"
LML_EXPORT_DIR = ROOT / "lml_export"

# Default game installation
DEFAULT_GAME_DIR = Path(r"G:\Red Dead Redemption 2")
DEFAULT_DUMP_DIR = Path(r"E:\RealityVAddon\RDR2_Shaders")
SETTINGS_FILE = ROOT / "settings.ini"


def ensure(path: Path) -> Path:
    """Ensure directory exists and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def init_workspace():
    """Create all working directories if they do not exist."""
    for p in (CACHE_DIR, SOURCE_DIR / "vulkan", SOURCE_DIR / "dx12",
              COMPILED_DIR / "vulkan", COMPILED_DIR / "dx12",
              DECOMPILED_DIR / "vulkan", DECOMPILED_DIR / "dx12",
              FXDB_FILES_DIR, LML_EXPORT_DIR):
        ensure(p)
