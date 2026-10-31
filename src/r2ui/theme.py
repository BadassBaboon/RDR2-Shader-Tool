"""Visual design tokens, DPI scaling, and font configuration for RDR2 Shader Tool."""

import ctypes
import os
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# Red Dead Redemption 2 Inspired Dark Palette
# Deep soot & aged iron surfaces, weathered parchment typography, and outlaw crimson red accents.
BG = "#111113"           # Deepest background (soot charcoal)
BG_ALT = "#18181B"       # Secondary dark surface (aged iron)
BG_PANEL = "#212126"     # Elevated cards, toolbar bands
BG_INPUT = "#151518"     # Input boxes, list backgrounds, code viewers
BORDER = "#2E2D33"       # Hairline dividers
BORDER_LIGHT = "#3D3C45" # Hover borders
BORDER_FOCUS = "#B81D20" # RDR2 Red active border

# Typography Colors (Weathered paper & warm bone)
TEXT_MAIN = "#EDE7DB"    # Bone white / warm parchment (readable without glare)
TEXT_MUTED = "#A39C90"   # Weathered newspaper grey
TEXT_DIM = "#6B665E"     # Metadata / dim commentary

# RDR2 Outlaw Crimson Accent
ACCENT = "#B81D20"       # Rockstar RDR2 Blood Red
ACCENT_HOVER = "#D1282B" # Lighter crimson
ACCENT_ACTIVE = "#8C1215"# Deep dark crimson
ON_ACCENT = "#FFFFFF"

# Frontier Brass / Gold (Secondary Accent for badges and stage tags)
GOLD = "#C29336"
GOLD_MUTED = "#8A6926"

# Stage & Status Indicators
STAGE_VS = "#C29336"     # Vertex Shader (Brass/Gold)
STAGE_PS = "#B81D20"     # Pixel Shader (Crimson Red)
STAGE_CS = "#3C78B0"     # Compute Shader (Steel Blue)
STAGE_OTHER = "#786896"  # Geometry / Domain / Hull (Muted Indigo)

GREEN = "#3E9C4F"        # Muted sage green (compile success)
YELLOW = "#D49826"       # Amber / warning
BLUE = "#3C78B0"         # Cold steel blue
CYAN = "#4CA8AF"         # Muted turquoise

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
    """Create typography scales with frontier print aesthetic."""
    base_family = "Segoe UI"
    title_family = "Georgia" if "Georgia" in tkfont.families() else base_family
    mono_family = "Consolas"

    return {
        "brand": tkfont.Font(family=title_family, size=px(15), weight="bold"),
        "title": tkfont.Font(family=base_family, size=px(13), weight="bold"),
        "header": tkfont.Font(family=base_family, size=px(11), weight="bold"),
        "header_small": tkfont.Font(family=base_family, size=px(9), weight="bold"),
        "body": tkfont.Font(family=base_family, size=px(10)),
        "small": tkfont.Font(family=base_family, size=px(8)),
        "mono": tkfont.Font(family=mono_family, size=px(10)),
        "mono_small": tkfont.Font(family=mono_family, size=px(9)),
        "mono_bold": tkfont.Font(family=mono_family, size=px(9), weight="bold"),
    }


def apply_ttk_theme(root: tk.Tk, fonts: dict):
    """Apply RDR2 dark theme to TTK widgets (Treeview, Scrollbars, Combobox)."""
    style = ttk.Style(root)
    style.theme_use("clam")

    # Treeview (Shader list table)
    style.configure(
        "Treeview",
        background=BG_INPUT,
        foreground=TEXT_MAIN,
        fieldbackground=BG_INPUT,
        borderwidth=0,
        rowheight=px(26),
        font=fonts["mono_small"]
    )
    style.map(
        "Treeview",
        background=[("selected", ACCENT_ACTIVE)],
        foreground=[("selected", "#FFFFFF")]
    )

    # Treeview Headings
    style.configure(
        "Treeview.Heading",
        background=BG_ALT,
        foreground=TEXT_MUTED,
        borderwidth=1,
        relief="flat",
        font=fonts["header_small"]
    )
    style.map(
        "Treeview.Heading",
        background=[("active", BG_PANEL)],
        foreground=[("active", TEXT_MAIN)]
    )

    # Scrollbars
    style.configure(
        "Vertical.TScrollbar",
        background=BG_PANEL,
        troughcolor=BG,
        bordercolor=BG,
        arrowcolor=TEXT_MUTED,
        relief="flat",
        borderwidth=0
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("active", BORDER_LIGHT)]
    )

    style.configure(
        "Horizontal.TScrollbar",
        background=BG_PANEL,
        troughcolor=BG,
        bordercolor=BG,
        arrowcolor=TEXT_MUTED,
        relief="flat",
        borderwidth=0
    )
    style.map(
        "Horizontal.TScrollbar",
        background=[("active", BORDER_LIGHT)]
    )

    # Combobox
    style.configure(
        "TCombobox",
        background=BG_PANEL,
        foreground=TEXT_MAIN,
        fieldbackground=BG_INPUT,
        darkcolor=BORDER,
        lightcolor=BORDER,
        bordercolor=BORDER,
        arrowcolor=GOLD,
        relief="flat",
        font=fonts["body"]
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", BG_INPUT)],
        foreground=[("readonly", TEXT_MAIN)],
        selectbackground=[("readonly", BG_INPUT)],
        selectforeground=[("readonly", TEXT_MAIN)]
    )
