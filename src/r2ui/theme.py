"""Visual design tokens, DPI scaling, and font configuration for RDR2 Shader Tool."""

import ctypes
import os
import sys
import tkinter as tk
from tkinter import font as tkfont

# Brand Palette (RDR2 Red & Dark Charcoal)
BG = "#141416"
BG_ALT = "#1C1C1F"
BG_PANEL = "#232328"
BORDER = "#2E2E35"
BORDER_FOCUS = "#C41E22"

TEXT_MAIN = "#F2F2F5"
TEXT_MUTED = "#9E9EA8"
TEXT_DIM = "#6B6B75"

# RDR2 Outlaw Crimson Accent
ACCENT = "#C41E22"
ACCENT_HOVER = "#D92D31"
ACCENT_ACTIVE = "#A0171A"
ON_ACCENT = "#FFFFFF"

# Status Colors
GREEN = "#34C759"
YELLOW = "#FF9F0A"
BLUE = "#0A84FF"
CYAN = "#64D2FF"

# Global DPI scale factor
_SCALE = 1.0


def dpi_aware():
    """Enable Windows per-monitor DPI awareness."""
    global _SCALE
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        try:
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
            ctypes.windll.user32.ReleaseDC(0, hdc)
            _SCALE = max(1.0, dpi / 96.0)
        except Exception:
            _SCALE = 1.0


def px(n: int) -> int:
    """Scale pixel dimension according to monitor DPI."""
    return int(round(n * _SCALE))


def setup_fonts(root: tk.Tk) -> dict:
    """Create typography scales."""
    base_family = "Segoe UI"
    mono_family = "Consolas"

    return {
        "title": tkfont.Font(family=base_family, size=px(14), weight="bold"),
        "header": tkfont.Font(family=base_family, size=px(11), weight="bold"),
        "body": tkfont.Font(family=base_family, size=px(10)),
        "small": tkfont.Font(family=base_family, size=px(8)),
        "mono": tkfont.Font(family=mono_family, size=px(10)),
        "mono_small": tkfont.Font(family=mono_family, size=px(9)),
    }
