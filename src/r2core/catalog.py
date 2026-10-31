"""In-memory fast shader catalog and indexer for RDR2 shaders."""

import os
import pickle
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

from . import hashing, paths
from .fxdb_models import FXDBFile, ShaderRecord
from .fxdb_parser import parse_file
from .settings import settings


@dataclass
class CatalogEntry:
    api: str                 # "vulkan" or "dx12"
    stage: str               # "VS", "PS", etc.
    index: int               # Index in stage array
    name: str                # e.g. "VS_Clear_Wrapped"
    crc: int                 # CRC32 of decompressed bytecode
    signature: int           # 64-bit signature in FXDB
    fxdb_path: str           # Source .fxdb file path
    blob_offset: int         # Offset in file
    byte_size: int           # Decompressed bytecode size
    raw_size: int            # On-disk size
    is_compressed: bool      # Oodle compressed
    effects: List[str] = field(default_factory=list)

    @property
    def crc_hex(self) -> str:
        return hashing.fmt(self.crc)

    @property
    def sig_hex(self) -> str:
        return hashing.fmt64(self.signature)

    @property
    def renodx_hash(self) -> str:
        """32-bit RenoDX shader hash matching RenoDX OSD and live replacement."""
        return self.crc_hex

    @property
    def renodx_filename(self) -> str:
        """Expected filename when dumped by RenoDX."""
        return hashing.renodx_dump_filename(self.crc, self.stage, self.api)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["crc_hex"] = self.crc_hex
        d["sig_hex"] = self.sig_hex
        d["renodx_hash"] = self.renodx_hash
        d["renodx_filename"] = self.renodx_filename
        return d


class Catalog:
    """Indexed database of all RDR2 shaders across Vulkan and DX12."""

    def __init__(self):
        self.entries: List[CatalogEntry] = []
        self.by_crc: Dict[int, List[CatalogEntry]] = {}
        self.by_name: Dict[str, List[CatalogEntry]] = {}
        self.by_api: Dict[str, List[CatalogEntry]] = {"vulkan": [], "dx12": []}
        self.by_effect: Dict[str, List[CatalogEntry]] = {}
        self.loaded_files: Set[str] = set()

    def add_fxdb(self, fxdb_path: Union[str, Path], api: Optional[str] = None):
        p = Path(fxdb_path)
        if str(p) in self.loaded_files:
            return

        # Infer API from path or argument
        if api is None:
            name_lower = p.name.lower()
            if "vulkan" in name_lower or "vk" in name_lower:
                api = "vulkan"
            else:
                api = "dx12"

        parsed = parse_file(p, decompress_bytecode=True)
        self.loaded_files.add(str(p))

        # Build effect to shader mapping
        # parsed.effects has stage_indices dict
        eff_map: Dict[Tuple[str, int], List[str]] = {}
        for eff in parsed.effects:
            for st, indices in eff.stage_indices.items():
                for idx in indices:
                    eff_map.setdefault((st, idx), []).append(eff.name)

        for st, records in parsed.shaders.items():
            for r in records:
                effs = eff_map.get((st, r.index), [])
                entry = CatalogEntry(
                    api=api,
                    stage=st,
                    index=r.index,
                    name=r.name,
                    crc=r.crc,
                    signature=r.signature,
                    fxdb_path=str(p),
                    blob_offset=r.blob_offset,
                    byte_size=len(r.bytecode),
                    raw_size=len(r.raw_bytecode),
                    is_compressed=r.is_compressed,
                    effects=effs
                )
                self.entries.append(entry)
                self.by_crc.setdefault(entry.crc, []).append(entry)
                self.by_name.setdefault(entry.name.lower(), []).append(entry)
                self.by_api[api].append(entry)
                for e in effs:
                    self.by_effect.setdefault(e.lower(), []).append(entry)

    def find(self, query: str = "", stage: Optional[str] = None, api: Optional[str] = None, effect: Optional[str] = None) -> List[CatalogEntry]:
        results = self.entries
        if api:
            results = [e for e in results if e.api.lower() == api.lower()]
        if stage:
            results = [e for e in results if e.stage.lower() == stage.lower()]
        if effect:
            eff_q = effect.lower()
            results = [e for e in results if any(eff_q in eff.lower() for eff in e.effects)]

        if query:
            q = query.strip().lower()
            # Check if query is a hex hash
            h = hashing.parse_hash(q)
            if h is not None:
                return [e for e in results if e.crc == h or (e.signature & 0xFFFFFFFF) == (h & 0xFFFFFFFF)]

            # Text substring search in name and effects
            results = [e for e in results if q in e.name.lower() or any(q in eff.lower() for eff in e.effects)]

        return results

    def get_by_crc(self, crc: int, api: Optional[str] = None) -> List[CatalogEntry]:
        entries = self.by_crc.get(crc, [])
        if api:
            entries = [e for e in entries if e.api.lower() == api.lower()]
        return entries

    def get_by_name(self, name: str, stage: Optional[str] = None, api: Optional[str] = None) -> List[CatalogEntry]:
        entries = self.by_name.get(name.lower(), [])
        if api:
            entries = [e for e in entries if e.api.lower() == api.lower()]
        if stage:
            entries = [e for e in entries if e.stage.lower() == stage.lower()]
        return entries

    def list_effects(self, api: Optional[str] = None) -> List[str]:
        if api:
            effs = set()
            for e in self.by_api.get(api.lower(), []):
                for eff in e.effects:
                    effs.add(eff)
            return sorted(effs)
        return sorted(self.by_effect.keys())

    def save_cache(self, cache_file: Optional[Path] = None):
        target = cache_file or (paths.CACHE_DIR / "catalog.pkl")
        paths.ensure(target.parent)
        with open(target, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load_cache(cls, cache_file: Optional[Path] = None) -> Optional["Catalog"]:
        target = cache_file or (paths.CACHE_DIR / "catalog.pkl")
        if target.exists():
            try:
                with open(target, "rb") as f:
                    cat = pickle.load(f)
                    if isinstance(cat, cls):
                        return cat
            except Exception:
                pass
        return None


def get_default_catalog(force_rebuild: bool = False) -> Catalog:
    """Load or build the catalog from user dump folder, fxdb_files/, or shaders_dump/."""
    if not force_rebuild:
        cached = Catalog.load_cache()
        if cached:
            return cached

    cat = Catalog()
    dump_dir = Path(settings().get("Paths", "rdr2_shaders_dump", str(paths.DEFAULT_DUMP_DIR)))

    # Collect search directories for .fxdb files
    search_dirs = [
        dump_dir / "fxdb",
        dump_dir,
        paths.FXDB_FILES_DIR,
        paths.SHADERS_DUMP_DIR,
    ]

    indexed_paths = set()
    for s_dir in search_dirs:
        if s_dir and s_dir.exists():
            for f in sorted(s_dir.glob("*.fxdb")):
                if f.resolve() not in indexed_paths:
                    try:
                        cat.add_fxdb(f)
                        indexed_paths.add(f.resolve())
                    except Exception as e:
                        print(f"Warning: Failed to index {f.name}: {e}")

    cat.save_cache()
    return cat
