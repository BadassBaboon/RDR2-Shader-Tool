"""User settings and configuration persistence (settings.ini)."""

import configparser
from pathlib import Path
from typing import Optional

from . import paths

_DEFAULT_SETTINGS = {
    "General": {
        "active_api": "vulkan",       # "vulkan" (default for RDR2) or "dx12"
        "game_dir": str(paths.DEFAULT_GAME_DIR),
        "editor_path": "",
        "auto_recompile": "true",
    },
    "Paths": {
        "rdr2_shaders_dump": str(paths.DEFAULT_DUMP_DIR),
        "compilers_dir": str(paths.COMPILERS_DIR),
        "lml_mod_name": "RealityV_Shaders",
    },
    "Window": {
        "geometry": "1360x880",
        "theme": "darkly",
        "page": "browser",
    },
    "Vulkan": {
        "target_env": "vulkan1.1",
        "spirv_opt": "false",
        "decompile_target": "hlsl",   # "hlsl" or "glsl"
    },
    "DirectX12": {
        "shader_model": "6_0",
        "decompiler": "decomp",       # "decomp" or "dxil_spirv"
    }
}


class Settings:
    """Manages reading and updating settings.ini."""

    def __init__(self, ini_path: Optional[Path] = None):
        self.path = ini_path or paths.SETTINGS_FILE
        self.cfg = configparser.ConfigParser()
        self.load()

    def load(self):
        # Populate defaults first
        for section, kv in _DEFAULT_SETTINGS.items():
            if not self.cfg.has_section(section):
                self.cfg.add_section(section)
            for k, v in kv.items():
                self.cfg.set(section, k, str(v))

        if self.path.exists():
            try:
                self.cfg.read(self.path, encoding="utf-8")
            except Exception:
                pass
        else:
            self.save()

    def save(self):
        paths.ensure(self.path.parent)
        with open(self.path, "w", encoding="utf-8") as f:
            self.cfg.write(f)

    def get(self, section: str, key: str, fallback: str = "") -> str:
        return self.cfg.get(section, key, fallback=fallback)

    def get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        val = self.get(section, key, str(fallback)).lower()
        return val in ("true", "1", "yes", "on")

    def set(self, section: str, key: str, value: str):
        if not self.cfg.has_section(section):
            self.cfg.add_section(section)
        self.cfg.set(section, key, str(value))
        self.save()

    @property
    def active_api(self) -> str:
        return self.get("General", "active_api", "vulkan").lower()

    @active_api.setter
    def active_api(self, value: str):
        self.set("General", "active_api", value.lower())

    @property
    def game_dir(self) -> Path:
        return Path(self.get("General", "game_dir", str(paths.DEFAULT_GAME_DIR)))

    @property
    def lml_dir(self) -> Path:
        return self.game_dir / "lml"


_instance: Optional[Settings] = None


def settings() -> Settings:
    global _instance
    if _instance is None:
        _instance = Settings()
    return _instance
