"""Entry point for RDR2 Shader Tool MCP Server."""

import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from r2mcp.server import main

if __name__ == "__main__":
    main()
