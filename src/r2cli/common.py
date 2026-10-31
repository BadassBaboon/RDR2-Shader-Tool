"""Common context and helpers for RDR2 Shader Tool CLI."""

import json
import sys
from typing import Any, Optional


class CliError(Exception):
    """User-facing CLI failure."""
    pass


class Ctx:
    """CLI execution context."""

    def __init__(self, args):
        self.args = args
        self.as_json = getattr(args, "json", False)

    def emit(self, data: Any, text: Optional[str] = None):
        """Emit data as JSON if requested, otherwise print human-readable text."""
        if self.as_json:
            print(json.dumps(data, indent=2, default=str))
        elif text is not None:
            print(text)
        elif isinstance(data, str):
            print(data)
        else:
            print(json.dumps(data, indent=2, default=str))

    def error(self, msg: str):
        print(f"Error: {msg}", file=sys.stderr)
