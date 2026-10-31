"""Main entry point for Red Dead Redemption 2 Shader Tool.

If run with CLI arguments (e.g. `python main.py status`), runs the CLI.
If run with no arguments (e.g. `python main.py`), opens the modern GUI.
"""

import sys
from pathlib import Path

# Add src to python path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        from r2cli.main import main as cli_main
        sys.exit(cli_main())
    else:
        from r2ui.app import main as gui_main
        gui_main()
