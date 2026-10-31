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
    """Compute standard IEEE 802.3 CRC32 (RenoDX convention)."""
    return zlib.crc32(data) & 0xFFFFFFFF


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


def parse_hash(text: str) -> Optional[int]:
    """Parse '0x4C793B07' or '4c793b07' into an integer."""
    if not text:
        return None
    s = str(text).strip()
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
