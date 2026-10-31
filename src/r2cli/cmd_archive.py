"""CLI commands for archive management: unpack, repack, and inject."""

import argparse
from pathlib import Path
from typing import Dict, Tuple

from r2core import fxdb_parser, hashing, paths, settings
from .common import CliError, Ctx


def register(subparsers):
    # unpack
    p_unp = subparsers.add_parser("unpack", help="Unpack all shaders from an FXDB library into stage folders")
    p_unp.add_argument("fxdb", help="Path to .fxdb library file")
    p_unp.add_argument("-o", "--output", help="Output directory")
    p_unp.set_defaults(func=cmd_unpack)

    # repack
    p_rep = subparsers.add_parser("repack", help="Repack modified shaders back into FXDB library")
    p_rep.add_argument("fxdb", help="Path to original .fxdb library file")
    p_rep.add_argument("-o", "--output", help="Output .fxdb file path")
    p_rep.add_argument("-d", "--compiled-dir", help="Directory containing modified .spv or .cso files")
    p_rep.set_defaults(func=cmd_repack)

    # inject
    p_inj = subparsers.add_parser("inject", help="Inject a single compiled shader into an FXDB library")
    p_inj.add_argument("fxdb", help="Path to .fxdb file")
    p_inj.add_argument("target", help="Shader stage and index (e.g. VS[0] or VS_Clear_Wrapped)")
    p_inj.add_argument("bytecode_file", help="Path to new .spv or .cso file")
    p_inj.add_argument("-o", "--output", help="Output .fxdb path")
    p_inj.set_defaults(func=cmd_inject)


def cmd_unpack(ctx: Ctx, args):
    fxdb_path = Path(args.fxdb)
    if not fxdb_path.exists():
        raise CliError(f"FXDB file not found: {fxdb_path}")

    parsed = fxdb_parser.parse_file(fxdb_path, decompress_bytecode=True)

    is_vulkan = "vulkan" in fxdb_path.name.lower() or "vk" in fxdb_path.name.lower()
    api = "vulkan" if is_vulkan else "dx12"
    ext = "spv" if is_vulkan else "cso"

    out_base = Path(args.output) if args.output else paths.COMPILED_DIR / api / fxdb_path.stem
    paths.ensure(out_base)

    unpacked = []
    for st, records in parsed.shaders.items():
        stage_dir = out_base / st
        paths.ensure(stage_dir)
        for r in records:
            out_file = stage_dir / f"{r.index:04d}_{r.name}.{ext}"
            out_file.write_bytes(r.bytecode)
            unpacked.append(str(out_file))

    res_data = {
        "ok": True,
        "archive": fxdb_path.name,
        "total_unpacked": len(unpacked),
        "output_dir": str(out_base)
    }
    ctx.emit(res_data, f"Successfully unpacked {len(unpacked)} shaders from {fxdb_path.name} -> {out_base}")


def cmd_repack(ctx: Ctx, args):
    fxdb_path = Path(args.fxdb)
    if not fxdb_path.exists():
        raise CliError(f"Source FXDB file not found: {fxdb_path}")

    is_vulkan = "vulkan" in fxdb_path.name.lower() or "vk" in fxdb_path.name.lower()
    api = "vulkan" if is_vulkan else "dx12"
    ext = "spv" if is_vulkan else "cso"

    search_dir = Path(args.compiled_dir) if args.compiled_dir else paths.COMPILED_DIR / api / fxdb_path.stem
    if not search_dir.exists():
        raise CliError(f"Compiled directory not found: {search_dir}")

    # Parse source to map (stage, index) and name
    parsed = fxdb_parser.parse_file(fxdb_path, decompress_bytecode=True)

    replacements: Dict[Tuple[str, int], bytes] = {}

    # Scan for compiled files in search_dir
    for f in search_dir.rglob(f"*.{ext}"):
        # Match pattern: 0004_ShaderName.spv or ShaderName.spv
        fname = f.stem
        # Check if stage is in parent folder
        st = f.parent.name.upper()
        if st not in fxdb_parser.STAGES:
            continue

        matched_record = None
        # Check index prefix e.g. 0004_...
        parts = fname.split("_", 1)
        if len(parts) == 2 and parts[0].isdigit():
            idx = int(parts[0])
            recs = parsed.shaders.get(st, [])
            if 0 <= idx < len(recs):
                matched_record = recs[idx]

        if not matched_record:
            # Match by name
            for r in parsed.shaders.get(st, []):
                if r.name.lower() == fname.lower() or r.name.lower() in fname.lower():
                    matched_record = r
                    break

        if matched_record:
            new_bytes = f.read_bytes()
            if hashing.crc32(new_bytes) != matched_record.crc:
                replacements[(st, matched_record.index)] = new_bytes

    if not replacements:
        ctx.emit({"ok": True, "repacked": 0, "message": "No modified shaders detected to inject."})
        return

    out_path = Path(args.output) if args.output else fxdb_path.with_name(f"{fxdb_path.stem}_modified.fxdb")
    res = fxdb_parser.inject_shaders(fxdb_path, out_path, replacements)

    ctx.emit(res, f"Repacked {res['injected_count']} changed shader(s) into -> {out_path}")


def cmd_inject(ctx: Ctx, args):
    fxdb_path = Path(args.fxdb)
    bc_path = Path(args.bytecode_file)
    if not fxdb_path.exists():
        raise CliError(f"FXDB file not found: {fxdb_path}")
    if not bc_path.exists():
        raise CliError(f"Bytecode file not found: {bc_path}")

    parsed = fxdb_parser.parse_file(fxdb_path, decompress_bytecode=False)

    # Resolve target e.g. "VS[0]" or "VS_Clear_Wrapped"
    target_str = args.target.strip()
    target_rec = None

    import re
    m = re.match(r"^([A-Z]{2})\[(\d+)\]$", target_str, re.I)
    if m:
        st = m.group(1).upper()
        idx = int(m.group(2))
        recs = parsed.shaders.get(st, [])
        if 0 <= idx < len(recs):
            target_rec = recs[idx]
    else:
        for st, records in parsed.shaders.items():
            for r in records:
                if r.name.lower() == target_str.lower():
                    target_rec = r
                    break
            if target_rec:
                break

    if not target_rec:
        raise CliError(f"Could not find shader '{target_str}' in {fxdb_path.name}")

    out_path = Path(args.output) if args.output else fxdb_path.with_name(f"{fxdb_path.stem}_injected.fxdb")
    new_bc = bc_path.read_bytes()

    res = fxdb_parser.inject_shaders(fxdb_path, out_path, {(target_rec.stage, target_rec.index): new_bc})
    ctx.emit(res, f"Injected {bc_path.name} into {target_rec.stage}[{target_rec.index}] ({target_rec.name}) -> {out_path}")
