"""Model Context Protocol (MCP) server for RDR2 Shader Tool (stdio JSON-RPC 2.0).

Exposes all CLI commands as structured tools so AI coding agents can inspect,
decompile, patch, compile, repack, and deploy RDR2 shaders automatically.
"""

import argparse
import io
import json
import sys
import traceback
from typing import Any, Dict, List, Optional, Tuple

from r2cli.common import CliError, Ctx
from r2cli.main import build_parser

PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
MAX_TEXT = 60_000

INSTRUCTIONS = (
    "Red Dead Redemption 2 shader management toolkit (Vulkan SPIR-V & DirectX 12 DXIL). "
    "Shaders are keyed by 0xCRC32 or name; default API is Vulkan. "
    "Use find / info to explore shaders, registers, and cbuffers; "
    "decompile / compile to convert between binaries and HLSL/GLSL; "
    "unpack / repack to modify .fxdb libraries; "
    "lml to deploy directly to Lenny's Mod Loader without modifying .rpf files."
)


class _CaptureCtx(Ctx):
    """Context that captures emit data for MCP response."""

    def __init__(self, args):
        super().__init__(args)
        self.data = None

    def emit(self, data: Any, text: Optional[str] = None):
        self.data = data


def _prop(action):
    if isinstance(action, argparse._StoreTrueAction):
        p = {"type": "boolean"}
    elif action.nargs in ("+", "*", "...") or isinstance(action, argparse._AppendAction):
        item = {"type": "integer"} if action.type is int else {"type": "string"}
        if action.choices:
            item["enum"] = list(action.choices)
        p = {"type": "array", "items": item}
    else:
        p = {"type": "integer"} if action.type is int else {"type": "string"}
        if action.choices:
            p["enum"] = list(action.choices)
    if action.help and action.help != argparse.SUPPRESS:
        p["description"] = action.help
    if action.default not in (None, argparse.SUPPRESS, False) and not isinstance(action.default, list):
        p["default"] = action.default
    return p


class Tool:
    def __init__(self, name: str, path: Tuple[str, ...], parser: argparse.ArgumentParser, help_text: str):
        self.name = name
        self.path = path
        self.parser = parser
        props, required = {}, []
        self.actions = []
        for act in parser._actions:
            if isinstance(act, (argparse._HelpAction, argparse._SubParsersAction, argparse._VersionAction)):
                continue
            key = act.dest
            props[key] = _prop(act)
            self.actions.append(act)
            if not act.option_strings and act.nargs not in ("?", "*", "..."):
                required.append(key)
            elif act.option_strings and act.required:
                required.append(key)
        self.schema = {"type": "object", "properties": props, "required": required}
        self.description = (help_text or parser.description or name).strip()

    def argv(self, arguments: dict) -> List[str]:
        out = list(self.path)
        positional = []
        for act in self.actions:
            if act.dest not in arguments or arguments[act.dest] is None:
                continue
            v = arguments[act.dest]
            if not act.option_strings:
                if isinstance(v, list):
                    positional.extend(str(x) for x in v)
                else:
                    positional.append(str(v))
            elif isinstance(act, argparse._StoreTrueAction):
                if v:
                    out.append(act.option_strings[0])
            elif isinstance(v, list):
                for item in v:
                    out.extend([act.option_strings[0], str(item)])
            else:
                out.extend([act.option_strings[0], str(v)])
        return out + positional


def collect_tools() -> Dict[str, Tool]:
    root_parser = build_parser()
    tools = {}

    def walk(subparser_action, prefix=()):
        for name, sub in subparser_action.choices.items():
            path = prefix + (name,)
            tool_name = "r2sm_" + "_".join(path)
            help_text = getattr(sub, "description", "") or sub.format_help()
            # Check for nested subparsers
            nested = [a for a in sub._actions if isinstance(a, argparse._SubParsersAction)]
            if nested:
                for n in nested:
                    walk(n, path)
            else:
                tools[tool_name] = Tool(tool_name, path, sub, help_text)

    for action in root_parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            walk(action)

    return tools


class Server:
    def __init__(self):
        self.tools = collect_tools()
        self.parser = build_parser()

    def handle(self, request: dict) -> Optional[dict]:
        method = request.get("method")
        msg_id = request.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": PROTOCOLS[0],
                    "serverInfo": {"name": "rdr2-shader-tool", "version": "1.0.0"},
                    "instructions": INSTRUCTIONS,
                    "capabilities": {"tools": {}}
                }
            }
        elif method == "notifications/initialized":
            return None
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {"name": t.name, "description": t.description, "inputSchema": t.schema}
                        for t in self.tools.values()
                    ]
                }
            }
        elif method == "tools/call":
            params = request.get("params", {})
            name = params.get("name")
            arguments = params.get("arguments", {})
            if name not in self.tools:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {name}"}
                }

            tool = self.tools[name]
            argv = tool.argv(arguments)
            try:
                args = self.parser.parse_args(argv)
                args.json = True
                ctx = _CaptureCtx(args)
                rc = args.func(ctx, args)
                data = ctx.data if ctx.data is not None else {"ok": rc == 0}
                text = json.dumps(data, indent=2, default=str)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": text}],
                        "isError": (rc is not None and rc != 0)
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
                        "isError": True
                    }
                }

        elif msg_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }
        return None

    def run(self):
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except AttributeError:
                pass

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except Exception:
                continue
            resp = self.handle(req)
            if resp is not None:
                print(json.dumps(resp), flush=True)


def main():
    server = Server()
    server.run()


if __name__ == "__main__":
    main()
