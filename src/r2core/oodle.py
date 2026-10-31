"""Oodle compression and decompression wrapper for RDR2 shader bytecodes.

Uses oo2core_5_win64.dll via ctypes. Handles the 12-byte FxdbCompressedDataHeader (magic 0xDCE7).
"""

import ctypes
import os
import struct
from pathlib import Path
from typing import Optional, Tuple

from . import paths

COMPRESSED_MAGIC = 0xDCE7
COMPRESSED_HEADER_SIZE = 12

# Oodle format constants
OODLE_FORMAT_KRAKEN = 8
OODLE_LEVEL_OPTIMAL5 = 9

_oodle_dll: Optional[ctypes.CDLL] = None


def _load_oodle() -> Optional[ctypes.CDLL]:
    global _oodle_dll
    if _oodle_dll is not None:
        return _oodle_dll

    search_paths = [
        paths.COMPILERS_DIR / "oo2core_5_win64.dll",
        paths.DEFAULT_GAME_DIR / "oo2core_5_win64.dll",
        Path("oo2core_5_win64.dll"),
    ]

    for p in search_paths:
        if p.exists():
            try:
                dll = ctypes.CDLL(str(p))
                # Configure argtypes and restype
                dll.OodleLZ_Decompress.argtypes = [
                    ctypes.c_char_p, ctypes.c_size_t,
                    ctypes.c_char_p, ctypes.c_size_t,
                    ctypes.c_int, ctypes.c_int, ctypes.c_int,
                    ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int
                ]
                dll.OodleLZ_Decompress.restype = ctypes.c_int

                dll.OodleLZ_Compress.argtypes = [
                    ctypes.c_int,
                    ctypes.c_char_p, ctypes.c_size_t,
                    ctypes.c_char_p, ctypes.c_int,
                    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
                ]
                dll.OodleLZ_Compress.restype = ctypes.c_int

                _oodle_dll = dll
                return dll
            except Exception:
                continue

    return None


def is_compressed(bytecode: bytes) -> bool:
    """Returns True if the bytecode starts with the 0xDCE7 Oodle header."""
    if len(bytecode) < COMPRESSED_HEADER_SIZE:
        return False
    magic = struct.unpack_from("<H", bytecode, 0)[0]
    return magic == COMPRESSED_MAGIC


def decompress(bytecode: bytes) -> bytes:
    """Decompress shader bytecode if Oodle compressed; returns raw bytecode otherwise."""
    if not is_compressed(bytecode):
        return bytecode

    dll = _load_oodle()
    if dll is None:
        raise RuntimeError("oo2core_5_win64.dll not found in compilers/ or game folder")

    magic, format_id, pad, comp_size_hdr, decomp_size = struct.unpack_from("<HBBii", bytecode, 0)
    in_data = bytecode[COMPRESSED_HEADER_SIZE:]

    out_buf = ctypes.create_string_buffer(decomp_size)
    res = dll.OodleLZ_Decompress(
        in_data, len(in_data),
        out_buf, decomp_size,
        0, 0, 0,
        None, 0, None,
        None, None, 0, 0
    )

    if res != decomp_size:
        raise RuntimeError(f"Oodle decompression failed: got {res} bytes, expected {decomp_size}")

    return out_buf.raw[:res]


def compress(decompressed_bytes: bytes, level: int = OODLE_LEVEL_OPTIMAL5) -> bytes:
    """Compress raw bytecode into Oodle Kraken with the 12-byte FxdbCompressedDataHeader."""
    dll = _load_oodle()
    if dll is None:
        raise RuntimeError("oo2core_5_win64.dll not found in compilers/ or game folder")

    decomp_size = len(decompressed_bytes)
    # Conservative buffer bound
    max_out = decomp_size + 274 * ((decomp_size + 0x3FFFF) // 0x400000) + 4096
    out_buf = ctypes.create_string_buffer(max_out)

    comp_size = dll.OodleLZ_Compress(
        OODLE_FORMAT_KRAKEN,
        decompressed_bytes, decomp_size,
        out_buf, level,
        None, None, None
    )

    if comp_size <= 0:
        raise RuntimeError(f"Oodle compression failed with error code {comp_size}")

    # Build 12-byte header
    hdr = struct.pack(
        "<HBBii",
        COMPRESSED_MAGIC,
        OODLE_FORMAT_KRAKEN,
        0,                                   # padding
        comp_size + COMPRESSED_HEADER_SIZE,  # total compressed size with header
        decomp_size                          # decompressed target size
    )

    return hdr + out_buf.raw[:comp_size]
