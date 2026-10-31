"""Lenny's Mod Loader (LML) packager and deployment engine for RDR2 shaders."""

import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Union

from . import paths
from .settings import settings

RPF_HASH_MAP = {
    # DX12
    "sga_win32_60_final_init.fxdb": "0x2A25B571.bin",
    "sga_win32_60_final.fxdb": "0x8068F4F9.bin",
    # Vulkan
    "sga_vulkan_final_init.fxdb": "0xA8C90D00.bin",
    "sga_vulkan_final.fxdb": "0xFEEB1B85.bin",
}


def get_rpf_bin_name(filename_or_path: Union[str, Path]) -> str:
    """Map .fxdb filename to its shaders_x64.rpf internal hash filename."""
    name = Path(filename_or_path).name.lower()
    return RPF_HASH_MAP.get(name, name)


def generate_install_xml(mod_name: str, file_mappings: List[Dict[str, str]], author: str = "RealityV", version: str = "1.0.0") -> str:
    """Generate Lenny's Mod Loader install.xml string."""
    easy_install = ET.Element("EasyInstall")

    name_el = ET.SubElement(easy_install, "Name")
    name_el.text = mod_name

    author_el = ET.SubElement(easy_install, "Author")
    author_el.text = author

    ver_el = ET.SubElement(easy_install, "Version")
    ver_el.text = version

    link_el = ET.SubElement(easy_install, "Link")
    link_el.text = ""

    meta_el = ET.SubElement(easy_install, "Metadata")
    meta_el.text = ""

    resources_el = ET.SubElement(easy_install, "Resources")
    res_el = ET.SubElement(resources_el, "Resource")

    for m in file_mappings:
        fr = ET.SubElement(res_el, "FileReplacement")
        gp = ET.SubElement(fr, "GamePath")
        gp.text = m["game_path"]
        fp = ET.SubElement(fr, "FilePath")
        fp.text = m["file_path"]

    # Format pretty XML
    ET.indent(easy_install, space="  ")
    xml_str = ET.tostring(easy_install, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return xml_str


def deploy_to_lml(
    modified_fxdb_files: List[Union[str, Path]],
    mod_name: Optional[str] = None,
    lml_dir: Optional[Path] = None
) -> Dict[str, Union[bool, str, List[str]]]:
    """Deploy modified FXDB files directly to game's lml/<ModName>/ folder."""
    cfg = settings()
    name = mod_name or cfg.get("Paths", "lml_mod_name", "RealityV_Shaders")
    target_lml = lml_dir or cfg.lml_dir

    if not target_lml.exists():
        # Create lml folder if it doesn't exist
        target_lml.mkdir(parents=True, exist_ok=True)

    mod_folder = target_lml / name
    shaders_folder = mod_folder / "shaders_x64"
    shaders_folder.mkdir(parents=True, exist_ok=True)

    file_mappings = []
    deployed_files = []

    for f in modified_fxdb_files:
        src = Path(f)
        if not src.exists():
            continue

        bin_name = get_rpf_bin_name(src)
        dst = shaders_folder / bin_name
        shutil.copy2(src, dst)
        deployed_files.append(str(dst))

        # Add mapping for both the hash name and the loose name
        file_mappings.append({
            "game_path": f"shaders_x64:/{bin_name}",
            "file_path": f"shaders_x64/{bin_name}"
        })
        if bin_name != src.name:
            file_mappings.append({
                "game_path": f"shaders_x64:/{src.name}",
                "file_path": f"shaders_x64/{bin_name}"
            })

    # Write install.xml
    install_xml = generate_install_xml(name, file_mappings)
    install_xml_path = mod_folder / "install.xml"
    install_xml_path.write_text(install_xml, encoding="utf-8")

    return {
        "ok": True,
        "mod_name": name,
        "mod_dir": str(mod_folder),
        "install_xml": str(install_xml_path),
        "deployed_files": deployed_files
    }


def list_installed_mods(lml_dir: Optional[Path] = None) -> List[Dict[str, Union[str, bool]]]:
    """List installed LML mods and check for shader replacements."""
    target_lml = lml_dir or settings().lml_dir
    mods = []
    if target_lml and target_lml.exists():
        for d in sorted(target_lml.iterdir()):
            if d.is_dir() and (d / "install.xml").exists():
                has_shaders = (d / "shaders_x64").exists()
                mods.append({
                    "name": d.name,
                    "has_shaders": has_shaders,
                    "path": str(d)
                })
    return mods

