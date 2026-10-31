"""Entry point for RDR2 Shader Tool MCP Server."""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent
src_dir = root_dir / "src"

while str(root_dir) in sys.path:
    sys.path.remove(str(root_dir))
while "" in sys.path:
    sys.path.remove("")

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

if "r2mcp" in sys.modules and not hasattr(sys.modules["r2mcp"], "__path__"):
    del sys.modules["r2mcp"]

from r2mcp.server import main

if __name__ == "__main__":
    main()
