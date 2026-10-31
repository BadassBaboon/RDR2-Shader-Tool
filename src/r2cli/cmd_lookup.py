"""CLI commands for lookup and inspection: status, find, info, effects."""

import argparse
from pathlib import Path

from r2core import catalog, hashing, paths, settings, toolchain
from r2core.fxdb_parser import parse_file
from .common import CliError, Ctx


def register(subparsers):
    # status
    p_stat = subparsers.add_parser("status", help="Inspect toolchain status, game directories and active API")
    p_stat.set_defaults(func=cmd_status)

    # find
    p_find = subparsers.add_parser("find", help="Search shaders by name, hash, stage or effect")
    p_find.add_argument("query", nargs="?", default="", help="Search query (name, 0xCRC, 0xSignature)")
    p_find.add_argument("-s", "--stage", choices=["vs", "ps", "gs", "ds", "hs", "cs"], help="Filter by stage")
    p_find.add_argument("-a", "--api", choices=["vulkan", "dx12"], help="Filter by API")
    p_find.add_argument("-e", "--effect", help="Filter by effect name")
    p_find.set_defaults(func=cmd_find)

    # info
    p_info = subparsers.add_parser("info", help="Display full metadata, registers and cbuffers for a shader")
    p_info.add_argument("target", help="Shader name, CRC32, or Signature")
    p_info.add_argument("-a", "--api", choices=["vulkan", "dx12"], help="Specify API")
    p_info.set_defaults(func=cmd_info)

    # effects
    p_eff = subparsers.add_parser("effects", help="List all effects present in the shader database")
    p_eff.add_argument("-a", "--api", choices=["vulkan", "dx12"], help="Filter by API")
    p_eff.set_defaults(func=cmd_effects)


def cmd_status(ctx: Ctx, args):
    tc = toolchain.get_toolchain()
    tc_status = tc.status()
    cfg = settings.settings()

    status_data = {
        "version": "1.0.0",
        "active_api": cfg.active_api,
        "game_dir": str(cfg.game_dir),
        "game_installed": cfg.game_dir.exists(),
        "lml_dir": str(cfg.lml_dir),
        "lml_available": cfg.lml_dir.exists(),
        "dump_dir": str(paths.DEFAULT_DUMP_DIR),
        "dump_available": paths.DEFAULT_DUMP_DIR.exists(),
        "tools": tc_status,
    }

    lines = [
        "============================================================",
        "  Red Dead Redemption 2 Shader Tool: System Status",
        "============================================================",
        f"Active API:        {cfg.active_api.upper()} (default for RDR2 is Vulkan)",
        f"Game Directory:    {cfg.game_dir} ({'Found' if cfg.game_dir.exists() else 'Missing'})",
        f"LML Directory:     {cfg.lml_dir} ({'Found' if cfg.lml_dir.exists() else 'Missing'})",
        f"Shaders Dump:      {paths.DEFAULT_DUMP_DIR} ({'Found' if paths.DEFAULT_DUMP_DIR.exists() else 'Missing'})",
        "\nCompilers & Toolchain:",
    ]
    for tid, tinfo in tc_status.items():
        mark = "✓" if tinfo["available"] else "✗"
        lines.append(f"  [{mark}] {tid:<15} {tinfo['version']}")

    ctx.emit(status_data, "\n".join(lines))


def cmd_find(ctx: Ctx, args):
    cat = catalog.get_default_catalog()
    api = args.api or settings.settings().active_api
    entries = cat.find(query=args.query, stage=args.stage, api=api, effect=args.effect)

    data = [e.to_dict() for e in entries]
    lines = [
        f"Found {len(entries)} shader(s) for API={api}:",
        f"{'Stage':<6} {'Index':<6} {'RenoDX Hash':<14} {'Signature':<20} {'Size':<8} {'Name':<35} {'Effects'}",
        "-" * 115,
    ]
    for e in entries[:100]:
        eff_str = ", ".join(e.effects[:2])
        lines.append(f"{e.stage:<6} {e.index:<6} {e.renodx_hash:<14} {e.sig_hex:<20} {e.byte_size:<8} {e.name[:34]:<35} {eff_str}")

    if len(entries) > 100:
        lines.append(f"... and {len(entries) - 100} more (use --json to see all)")

    ctx.emit(data, "\n".join(lines))


def cmd_info(ctx: Ctx, args):
    cat = catalog.get_default_catalog()
    api = args.api or settings.settings().active_api
    entries = cat.find(query=args.target, api=api)
    if not entries:
        raise CliError(f"Shader '{args.target}' not found in catalog for API '{api}'.")

    entry = entries[0]
    fxdb = parse_file(entry.fxdb_path, decompress_bytecode=True)
    records = fxdb.shaders.get(entry.stage, [])
    if entry.index >= len(records):
        raise CliError(f"Shader index {entry.index} out of range in {entry.fxdb_path}")

    rec = records[entry.index]

    info_data = {
        "name": rec.name,
        "stage": rec.stage,
        "index": rec.index,
        "api": entry.api,
        "crc32": entry.crc_hex,
        "renodx_hash": entry.renodx_hash,
        "renodx_dump_filename": entry.renodx_filename,
        "signature": entry.sig_hex,
        "bytecode_size": len(rec.bytecode),
        "raw_size": len(rec.raw_bytecode),
        "is_compressed": rec.is_compressed,
        "effects": entry.effects,
        "resources": [
            {
                "name": r.name,
                "type": r.resource_type.name,
                "class": r.resource_class.name,
                "slot": r.bind_point,
                "elements": [
                    {"name": el.name, "type": el.var_type.name, "offset": el.start_offset, "array_size": el.array_size}
                    for el in r.elements
                ]
            }
            for r in rec.data.resources
        ]
    }

    lines = [
        "============================================================",
        f"Shader: {rec.name} ({rec.stage}[{rec.index}])",
        "============================================================",
        f"API:          {entry.api.upper()}",
        f"RenoDX Hash:  {entry.renodx_hash}",
        f"RenoDX Dump:  {entry.renodx_filename}",
        f"CRC32:        {entry.crc_hex}",
        f"Signature:    {entry.sig_hex}",
        f"Size:         {len(rec.bytecode):,} bytes (raw on disk: {len(rec.raw_bytecode):,} bytes, compressed: {rec.is_compressed})",
        f"Belongs to:   {', '.join(entry.effects) or 'None'}",
        "\nRegisters & Constant Buffers:",
    ]

    for res in rec.data.resources:
        lines.append(f"  • {res.name} (Type={res.resource_type.name}, Class={res.resource_class.name}, Slot={res.bind_point})")
        for el in res.elements:
            arr = f"[{el.array_size}]" if el.array_size > 0 else ""
            lines.append(f"      +{el.start_offset:04d}: {el.var_type.name} {el.name}{arr}")

    ctx.emit(info_data, "\n".join(lines))


def cmd_effects(ctx: Ctx, args):
    cat = catalog.get_default_catalog()
    api = args.api or settings.settings().active_api
    effs = cat.list_effects(api=api)

    ctx.emit(effs, f"Effects ({len(effs)} total for {api}):\n" + "\n".join(f"  • {e}" for e in effs))
