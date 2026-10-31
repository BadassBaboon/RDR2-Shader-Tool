"""Detection and resolution of modified compiled shaders for injection."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from . import catalog, hashing, paths, rpf_reader


def _strip_profile_suffix(stem: str) -> str:
    for suff in (".vs_6_0", ".ps_6_0", ".cs_6_0", ".gs_6_0", ".ds_6_0", ".hs_6_0",
                 ".vs_5_0", ".ps_5_0", ".cs_5_0", ".gs_5_0", ".ds_5_0", ".hs_5_0",
                 "_vs_6_0", "_ps_6_0", "_cs_6_0", "_gs_6_0", "_ds_6_0", "_hs_6_0"):
        if stem.lower().endswith(suff):
            return stem[:-len(suff)]
    return stem


def scan_modified_shaders(
    api: str, cat: Optional[catalog.Catalog] = None
) -> Dict[Tuple[str, str, int], Dict[str, Any]]:
    """Scan compiled/ directory and map modified shaders to their target (db_name, stage, index) slot.
    
    Returns a dict mapping (fxdb_filename_lower, stage, index) to metadata about the replacement file.
    """
    if cat is None:
        cat = catalog.get_default_catalog()

    api_lower = api.lower()
    ext = "spv" if api_lower == "vulkan" else "cso"

    # Search in api-specific folder and flat compiled/
    search_dirs = [
        paths.COMPILED_DIR / api_lower,
        paths.COMPILED_DIR,
    ]

    candidate_files: List[Path] = []
    seen_paths = set()
    for s_dir in search_dirs:
        if s_dir.exists():
            for f in sorted(s_dir.rglob(f"*.{ext}")):
                if f not in seen_paths:
                    seen_paths.add(f)
                    candidate_files.append(f)

    if not candidate_files:
        return {}

    modified: Dict[Tuple[str, str, int], Dict[str, Any]] = {}

    for f in candidate_files:
        stem = f.stem
        clean_stem = _strip_profile_suffix(stem)

        matched_entries: List[catalog.CatalogEntry] = []

        # 1. Match by exact CRC / RenoDX Hash if filename looks like a hex hash
        parsed_hash = hashing.parse_hash(clean_stem)
        if parsed_hash is not None:
            entries_by_crc = cat.get_by_crc(parsed_hash, api=api_lower)
            if entries_by_crc:
                matched_entries.extend(entries_by_crc)

        # 2. Match by stage and index prefix (e.g. 0004_VS_Clear_Wrapped or vs_00000004)
        if not matched_entries:
            m_idx = re.match(r"^([a-z]{2})_(\d+)", clean_stem, re.I)
            if m_idx:
                st = m_idx.group(1).upper()
                idx = int(m_idx.group(2))
                entry_candidates = [e for e in cat.by_api.get(api_lower, []) if e.stage == st and e.index == idx]
                if entry_candidates:
                    matched_entries.extend(entry_candidates)
            else:
                parts = clean_stem.split("_", 1)
                if len(parts) == 2 and parts[0].isdigit():
                    idx = int(parts[0])
                    parent_stage = f.parent.name.upper()
                    st = parent_stage if parent_stage in ("VS", "PS", "CS", "GS", "DS", "HS") else None
                    for e in cat.by_api.get(api_lower, []):
                        if e.index == idx and (st is None or e.stage == st):
                            matched_entries.append(e)

        # 3. Match by shader name
        if not matched_entries:
            by_name = cat.get_by_name(clean_stem, api=api_lower)
            if by_name:
                matched_entries.extend(by_name)
            else:
                by_full = cat.get_by_name(stem, api=api_lower)
                if by_full:
                    matched_entries.extend(by_full)

        if not matched_entries:
            continue

        try:
            new_bytes = f.read_bytes()
        except Exception:
            continue

        new_crc = hashing.crc32(new_bytes)

        for entry in matched_entries:
            # If replacement bytecode differs from stock FXDB bytecode, it is modified
            if new_crc != entry.crc:
                db_name = Path(entry.fxdb_path).name.lower()
                slot_key = (db_name, entry.stage, entry.index)
                rel = str(f.relative_to(paths.ROOT)) if f.is_relative_to(paths.ROOT) else str(f)
                modified[slot_key] = {
                    "fxdb_name": db_name,
                    "stage": entry.stage,
                    "index": entry.index,
                    "name": entry.name,
                    "old_crc": entry.crc,
                    "new_crc": new_crc,
                    "old_crc_hex": entry.crc_hex,
                    "new_crc_hex": f"0x{new_crc:08X}",
                    "path": f,
                    "rel_path": rel,
                    "entry": entry,
                    "data": new_bytes,
                }

    return modified


def is_entry_modified(
    entry: catalog.CatalogEntry, mods: Dict[Tuple[str, str, int], Dict[str, Any]]
) -> bool:
    """Return True if the specific catalog entry has a modified replacement ready."""
    db_name = Path(entry.fxdb_path).name.lower()
    return (db_name, entry.stage, entry.index) in mods


def get_entry_mod_info(
    entry: catalog.CatalogEntry, mods: Dict[Tuple[str, str, int], Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Return replacement metadata for a specific catalog entry, or None if unmodified."""
    db_name = Path(entry.fxdb_path).name.lower()
    return mods.get((db_name, entry.stage, entry.index))


def get_replacements_for_fxdb(
    fxdb_path: Union[str, Path], api: Optional[str] = None
) -> Dict[Tuple[str, int], bytes]:
    """Return dictionary of (stage, index) -> bytecode for all modified shaders matching an FXDB file."""
    p = Path(fxdb_path)
    target_db = p.name.lower()
    canonical_target = rpf_reader.resolve_fxdb_name(target_db).lower()

    if api is None:
        api = "vulkan" if "vulkan" in canonical_target or "feeb1b85" in canonical_target else "dx12"

    mods = scan_modified_shaders(api)
    result: Dict[Tuple[str, int], bytes] = {}

    for (db, st, idx), m in mods.items():
        canonical_db = rpf_reader.resolve_fxdb_name(db).lower()
        if db == target_db or canonical_db == canonical_target:
            result[(st, idx)] = m["data"]

    return result
