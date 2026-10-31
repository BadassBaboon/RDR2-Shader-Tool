"""r2sm -- Red Dead Redemption 2 Shader Manager CLI.

Commands:
  r2sm status                      Inspect compilers, game folders, and active API
  r2sm find <query>                Search shaders by name, hash, stage or effect
  r2sm info <name_or_hash>         View registers, cbuffers and metadata
  r2sm decompile <shader>          Decompile to editable HLSL or GLSL
  r2sm compile <source.hlsl>       Compile to SPIR-V (Vulkan) or DXIL CSO (DX12)
  r2sm unpack <library.fxdb>       Unpack all shaders into stage folders
  r2sm repack <library.fxdb>       Repack modified shaders into library
  r2sm lml deploy <files>          Deploy modified libraries directly to LML
"""

import argparse
import sys

from r2core import paths
from . import cmd_archive, cmd_build, cmd_lml, cmd_lookup
from .common import CliError, Ctx

_MODULES = [cmd_lookup, cmd_build, cmd_archive, cmd_lml]


def build_parser():
    ap = argparse.ArgumentParser(
        prog="r2sm",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--version", action="version", version="RDR2 Shader Tool 1.0.0")
    ap.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    ap.add_argument("-a", "--api", choices=["vulkan", "dx12"], help="Override active API (default: settings.ini)")

    sub = ap.add_subparsers(dest="cmd", metavar="<command>")
    for m in _MODULES:
        m.register(sub)

    return ap


def main(argv=None):
    paths.init_workspace()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass

    ap = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)

    as_json = "--json" in argv
    if as_json:
        argv.remove("--json")

    api_override = None
    if "-a" in argv:
        idx = argv.index("-a")
        if idx + 1 < len(argv):
            api_override = argv[idx + 1]
            del argv[idx:idx + 2]
    elif "--api" in argv:
        idx = argv.index("--api")
        if idx + 1 < len(argv):
            api_override = argv[idx + 1]
            del argv[idx:idx + 2]

    args = ap.parse_args(argv)
    args.json = as_json
    if api_override:
        args.api = api_override

    if not getattr(args, "func", None):
        ap.print_help()
        return 1

    ctx = Ctx(args)
    try:
        rc = args.func(ctx, args)
        return rc or 0
    except (CliError, FileNotFoundError, ValueError) as e:
        ctx.error(str(e))
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
