"""CLI commands for decompilation, compilation, and verification."""

import argparse
from pathlib import Path

from r2core import catalog, compile, decompile, hashing, paths, settings
from r2core.fxdb_parser import parse_file
from .common import CliError, Ctx


def register(subparsers):
    # decompile
    p_dec = subparsers.add_parser("decompile", help="Decompile shader to editable HLSL/GLSL")
    p_dec.add_argument("target", help="Shader name, 0xCRC32 hash, or path to .spv/.cso binary file")
    p_dec.add_argument("-o", "--output", help="Output file path (default: source/<api>/<shader_name>.hlsl)")
    p_dec.add_argument("-a", "--api", choices=["vulkan", "dx12"], help="Specify API")
    p_dec.add_argument("-l", "--lang", choices=["hlsl", "glsl"], default="hlsl", help="Target source language")
    p_dec.set_defaults(func=cmd_decompile)

    # compile
    p_comp = subparsers.add_parser("compile", help="Compile HLSL/GLSL source to SPIR-V or DXIL CSO")
    p_comp.add_argument("source", help="Path to .hlsl or .glsl source file")
    p_comp.add_argument("-o", "--output", help="Output .spv or .cso file path")
    p_comp.add_argument("-a", "--api", choices=["vulkan", "dx12"], help="Target API (default: auto or active API)")
    p_comp.add_argument("-s", "--stage", choices=["vs", "ps", "gs", "ds", "hs", "cs"], help="Shader stage")
    p_comp.add_argument("-e", "--entry", default="main", help="Shader entry point")
    p_comp.add_argument("-O", "--optimize", action="store_true", help="Run optimizer (spirv-opt)")
    p_comp.set_defaults(func=cmd_compile)


def cmd_decompile(ctx: Ctx, args):
    target_path = Path(args.target)
    api = args.api or settings.settings().active_api

    # Case 1: Raw file on disk (.spv or .cso)
    if target_path.exists() and target_path.is_file():
        bytecode = target_path.read_bytes()
        res = decompile.decompile_shader(bytecode, api=api, target_lang=args.lang)
        if not res.ok:
            raise CliError(f"Decompilation failed: {res.error}")

        out_path = Path(args.output) if args.output else paths.DECOMPILED_DIR / api / f"{target_path.stem}.{args.lang}"
        paths.ensure(out_path.parent)
        out_path.write_text(res.source_code, encoding="utf-8")

        res_data = {
            "ok": True,
            "method": res.method,
            "output_file": str(out_path),
            "lines": len(res.source_code.splitlines()),
            "steps": res.steps
        }
        ctx.emit(res_data, f"Successfully decompiled via {res.method} -> {out_path} ({len(res.source_code.splitlines())} lines)")
        return

    # Case 2: Target is in the catalog (name or hash)
    cat = catalog.get_default_catalog()
    entries = cat.find(query=args.target, api=api)
    if not entries:
        raise CliError(f"Shader '{args.target}' not found for API '{api}'.")

    entry = entries[0]
    fxdb = parse_file(entry.fxdb_path, decompress_bytecode=True)
    rec = fxdb.shaders[entry.stage][entry.index]

    res = decompile.decompile_shader(rec, api=entry.api, target_lang=args.lang)
    if not res.ok:
        raise CliError(f"Decompilation failed: {res.error}")

    # Output to editable source directory
    ext = "glsl" if args.lang.lower() == "glsl" else "hlsl"
    out_path = Path(args.output) if args.output else paths.SOURCE_DIR / entry.api / rec.stage / f"{rec.name}.{rec.stage.lower()}_6_0.{ext}"
    paths.ensure(out_path.parent)
    out_path.write_text(res.source_code, encoding="utf-8")

    # Also save disassembly to decompiled folder
    if res.disassembly:
        dis_path = paths.DECOMPILED_DIR / entry.api / rec.stage / f"{rec.name}.spvasm"
        paths.ensure(dis_path.parent)
        dis_path.write_text(res.disassembly, encoding="utf-8")

    res_data = {
        "ok": True,
        "shader": rec.name,
        "stage": rec.stage,
        "method": res.method,
        "output_file": str(out_path),
        "steps": res.steps
    }
    ctx.emit(res_data, f"Decompiled {rec.name} ({rec.stage}[{rec.index}]) -> {out_path} [{res.method}]")


def cmd_compile(ctx: Ctx, args):
    src_file = Path(args.source)
    if not src_file.exists():
        raise CliError(f"Source file not found: {src_file}")

    api = args.api
    if not api:
        # Infer API from file path
        if "vulkan" in str(src_file).lower():
            api = "vulkan"
        elif "dx12" in str(src_file).lower():
            api = "dx12"
        else:
            api = settings.settings().active_api

    res = compile.compile_shader(
        source_file_or_code=src_file,
        target_api=api,
        stage=args.stage,
        entry_point=args.entry
    )

    if not res.ok:
        raise CliError(f"Compilation failed:\n{res.error}")

    ext = "spv" if api == "vulkan" else "cso"
    out_file = Path(args.output) if args.output else paths.COMPILED_DIR / api / f"{src_file.stem}.{ext}"
    paths.ensure(out_file.parent)
    out_file.write_bytes(res.bytecode)

    res_data = {
        "ok": True,
        "target_api": res.target_api,
        "stage": res.stage,
        "profile": res.profile,
        "bytecode_size": len(res.bytecode),
        "output_file": str(out_file),
        "steps": res.steps
    }
    ctx.emit(res_data, f"Successfully compiled {src_file.name} -> {out_file} ({len(res.bytecode):,} bytes) [{', '.join(res.steps or [])}]")
