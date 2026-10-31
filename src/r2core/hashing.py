"""Hashing algorithms for RDR2 shaders: Jenkins One-at-a-time (joaat), CRC32, FNV-64."""

import re
import zlib
from typing import Optional

_HASH32_RE = re.compile(r"^(?:0x)?([0-9a-fA-F]{8})$")
_HASH64_RE = re.compile(r"^(?:0x)?([0-9a-fA-F]{16})$")
_HASH_IN_NAME = re.compile(r"0x([0-9a-fA-F]{8,16})")


def joaat(s: str) -> int:
    """Rage / Jenkins one-at-a-time hash of lowercased string (u32)."""
    h = 0
    for c in s.encode("latin-1").lower():
        h = (h + c) & 0xFFFFFFFF
        h = (h + ((h << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + ((h << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + ((h << 15) & 0xFFFFFFFF)) & 0xFFFFFFFF
    return h


def joaat_case(s: str) -> int:
    """Jenkins one-at-a-time hash preserving exact case (u32)."""
    h = 0
    for c in s.encode("latin-1"):
        h = (h + c) & 0xFFFFFFFF
        h = (h + ((h << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + ((h << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + ((h << 15) & 0xFFFFFFFF)) & 0xFFFFFFFF
    return h


def crc32(data: bytes) -> int:
    """Compute standard IEEE 802.3 CRC32 (identical to RenoDX ComputeCRC32)."""
    return zlib.crc32(data) & 0xFFFFFFFF


def renodx_hash(data: bytes) -> int:
    """Compute 32-bit RenoDX shader hash (standard CRC32 over uncompressed bytecode)."""
    return crc32(data)


def renodx_hash_hex(data: bytes) -> str:
    """Format 32-bit RenoDX shader hash as uppercase hex: 0x12345678."""
    return fmt(crc32(data))


def renodx_dump_filename(shader_hash: int, stage: str, api: str) -> str:
    """Generate expected RenoDX shader dump filename based on API and stage.
    
    DX12:   0x12345678.ps_6_0.cso / 0x12345678.vs_6_0.cso
    Vulkan: 0x12345678.frag.spv / 0x12345678.vert.spv
    """
    h_str = fmt(shader_hash)
    st = str(stage).upper()
    api_clean = str(api).lower()

    if api_clean == "dx12":
        stage_map = {
            "VS": "vs_6_0", "PS": "ps_6_0", "CS": "cs_6_0",
            "GS": "gs_6_0", "DS": "ds_6_0", "HS": "hs_6_0"
        }
        abbr = stage_map.get(st, "ps_6_0")
        return f"{h_str}.{abbr}.cso"
    else:
        stage_map = {
            "VS": "vert", "PS": "frag", "CS": "comp",
            "GS": "geom", "DS": "tese", "HS": "tesc"
        }
        abbr = stage_map.get(st, "spv")
        return f"{h_str}.{abbr}.spv"


def fnv1a_64(data: bytes) -> int:
    """64-bit FNV-1a hash."""
    h = 0xCBF29CE484222325
    prime = 0x00000100000001B3
    for b in data:
        h = ((h ^ b) * prime) & 0xFFFFFFFFFFFFFFFF
    return h


def fmt(h: int) -> str:
    """Format 32-bit hash as 0x12345678."""
    return f"0x{h & 0xFFFFFFFF:08X}"


def fmt64(h: int) -> str:
    """Format 64-bit hash as 0x123456789ABCDEF0."""
    return f"0x{h & 0xFFFFFFFFFFFFFFFF:016X}"


_RENODX_FILE_RE = re.compile(r"^(?:0x)?([0-9a-fA-F]{8})(?:\.[a-zA-Z0-9_]+)+$")


def parse_hash(text: str) -> Optional[int]:
    """Parse '0x4C793B07', '4c793b07', or RenoDX filename '0x4C793B07.ps_6_0.cso' into an integer."""
    if not text:
        return None
    s = str(text).strip()
    m_reno = _RENODX_FILE_RE.match(s)
    if m_reno:
        return int(m_reno.group(1), 16)
    m32 = _HASH32_RE.match(s)
    if m32:
        return int(m32.group(1), 16)
    m64 = _HASH64_RE.match(s)
    if m64:
        return int(m64.group(1), 16)
    return None


def extract_hash_from_name(name: str) -> Optional[int]:
    """Extract first 0xHASH pattern from filename."""
    m = _HASH_IN_NAME.search(str(name))
    if m:
        return int(m.group(1), 16)
    return None
