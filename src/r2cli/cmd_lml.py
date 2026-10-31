"""CLI commands for Lenny's Mod Loader (LML) integration."""

import argparse
from pathlib import Path

from r2core import lml, settings
from .common import CliError, Ctx


def register(subparsers):
    p_lml = subparsers.add_parser("lml", help="Manage Lenny's Mod Loader shader mod deployment")
    lml_subs = p_lml.add_subparsers(dest="lml_cmd", metavar="<lml-subcommand>")

    # deploy
    p_dep = lml_subs.add_parser("deploy", help="Deploy modified .fxdb files directly to LML")
    p_dep.add_argument("files", nargs="+", help="Modified .fxdb files to install to LML")
    p_dep.add_argument("-n", "--name", help="Mod folder name (default from settings.ini: RealityV_Shaders)")
    p_dep.set_defaults(func=cmd_lml_deploy)

    # status
    p_stat = lml_subs.add_parser("status", help="Check LML installation status and active shader mods")
    p_stat.set_defaults(func=cmd_lml_status)


def cmd_lml_deploy(ctx: Ctx, args):
    file_paths = [Path(f) for f in args.files]
    for f in file_paths:
        if not f.exists():
            raise CliError(f"File not found: {f}")

    res = lml.deploy_to_lml(file_paths, mod_name=args.name)

    lines = [
        "============================================================",
        f"  Deployed to Lenny's Mod Loader: {res['mod_name']}",
        "============================================================",
        f"Directory:    {res['mod_dir']}",
        f"install.xml:  {res['install_xml']}",
        "Installed Files:",
    ]
    for df in res["deployed_files"]:
        lines.append(f"  • {Path(df).name}")

    ctx.emit(res, "\n".join(lines))


def cmd_lml_status(ctx: Ctx, args):
    cfg = settings.settings()
    lml_dir = cfg.lml_dir

    status_data = {
        "lml_path": str(lml_dir),
        "exists": lml_dir.exists(),
        "mods": []
    }

    if lml_dir.exists():
        for d in lml_dir.iterdir():
            if d.is_dir() and (d / "install.xml").exists():
                has_shaders = (d / "shaders_x64").exists()
                status_data["mods"].append({
                    "name": d.name,
                    "path": str(d),
                    "has_shaders": has_shaders
                })

    lines = [
        "============================================================",
        "  Lenny's Mod Loader Status",
        "============================================================",
        f"LML Root:   {lml_dir} ({'Ready' if lml_dir.exists() else 'Missing'})",
        "\nInstalled Mods:",
    ]
    for m in status_data["mods"]:
        tag = "[SHADERS]" if m["has_shaders"] else ""
        lines.append(f"  • {m['name']:<30} {tag}")

    ctx.emit(status_data, "\n".join(lines))
