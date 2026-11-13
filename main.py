"""Main entry point for Red Dead Redemption 2 Shader Tool.

If run with CLI arguments (e.g. `python main.py status`), runs the CLI.
If run with no arguments (e.g. `python main.py`), opens the modern GUI.
"""

import sys

# Minimum supported Python is 3.9
MIN_PYTHON = (3, 9)
if sys.version_info < MIN_PYTHON:
    current = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    msg = (
        f"Python 3.9 or newer is required to run RDR2 Shader Tool.\n"
        f"Detected Python {current} at:\n{sys.executable}\n\n"
        f"Please run with Python 3.9+ (e.g. 'py -3.9 main.py' or update your default Python installation)."
    )
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "RDR2 Shader Tool - Unsupported Python Version", 0x10)
    except Exception:
        pass
    sys.stderr.write(msg + "\n")
    sys.exit(1)

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
