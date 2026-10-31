"""Main window application for Red Dead Redemption 2 Shader Tool."""

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from r2core import catalog, paths, settings
from . import tasks, theme as T, widgets as W
from .pages import BrowserPage, BuilderPage, LmlPage, SourcePage

PAGES = [
    ("browser", "Shaders", "Browse shaders, reflection metadata, and constant buffers"),
    ("source", "Code Editor", "Edit and compile HLSL/GLSL to SPIR-V or DXIL with watch mode"),
    ("builder", "FXDB Builder", "Extract and repack RAGE SGD1 shader libraries"),
    ("lml", "LML Deployer", "Deploy modified shaders directly to Lenny's Mod Loader VFS"),
]


class App:
    def __init__(self):
        T.dpi_aware()
        self.root = tk.Tk()
        self.fonts = T.setup_fonts(self.root)
        self.cfg = settings.settings()

        # Apply global dark theme to all TTK widgets (Treeview, Scrollbar, Combobox)
        T.apply_ttk_theme(self.root, self.fonts)

        self.root.title("Red Dead Redemption 2 Shader Tool")
        self.root.geometry(self.cfg.get("Window", "geometry", f"{T.px(1380)}x{T.px(880)}"))
        self.root.minsize(T.px(1100), T.px(700))
        self.root.configure(bg=T.BG)

        self.active_api = self.cfg.active_api
        self.tasks = tasks.Tasks(self.root, on_busy=self.set_busy, on_log=self.log)

        self.pages = {}
        self.current_page_name = None

        self._build_layout()
        self.show_page(self.cfg.get("Window", "page", "browser"))

        # Preload catalog in background
        self.tasks.run(catalog.get_default_catalog, done=self._catalog_ready, label="indexing shaders")

    def _build_layout(self):
        # 1. Top Header Band
        active_lib = "sga_vulkan_final.fxdb" if self.active_api == "vulkan" else "sga_win32_60_final.fxdb"
        self.header = W.HeaderBand(
            self.root, self.fonts,
            title="SHADER TOOL",
            subtitle=f"Active API: {self.active_api.upper()} ({active_lib})"
        )
        self.header.pack(side="top", fill="x")

        # API Switcher on top right of header band
        self.api_switch = W.Segmented(
            self.header.right,
            self.fonts,
            options=[("vulkan", "VULKAN"), ("dx12", "DIRECTX 12")],
            value=self.active_api,
            command=self.set_api
        )
        self.api_switch.pack(side="left", padx=(0, T.px(16)), pady=T.px(14))

        # 2. Bottom Status Bar (Created before middle area to guarantee correct layout packing)
        f_sep = tk.Frame(self.root, bg=T.BORDER, height=1)
        f_sep.pack(side="bottom", fill="x")

        self.footer = tk.Frame(self.root, bg=T.BG_ALT, height=T.px(28))
        self.footer.pack(side="bottom", fill="x")
        self.footer.pack_propagate(False)

        # Game & LML status label (permanently snapped to bottom-right corner)
        game_ok = self.cfg.game_dir.exists()
        lml_ok = (self.cfg.game_dir / "lml").exists()
        info_str = f"Game: {'Found' if game_ok else 'Not Set'}  |  LML: {'Ready' if lml_ok else 'Not Installed'}"
        self.info_lbl = tk.Label(
            self.footer, text=info_str, font=self.fonts["mono_small"],
            fg=T.TEXT_DIM, bg=T.BG_ALT, anchor="e"
        )
        self.info_lbl.pack(side="right", padx=(T.px(8), T.px(16)), fill="y")

        self.busy_lbl = tk.Label(
            self.footer, text="", font=self.fonts["small"],
            fg=T.GOLD, bg=T.BG_ALT, anchor="e", padx=T.px(8)
        )
        self.busy_lbl.pack(side="right", fill="y")

        self.status_lbl = tk.Label(
            self.footer, text="Ready", font=self.fonts["small"],
            fg=T.TEXT_MUTED, bg=T.BG_ALT, anchor="w", padx=T.px(12)
        )
        self.status_lbl.pack(side="left", fill="both", expand=True)

        # 3. Main Middle Area (Sidebar Navigation + Page Container)
        middle = tk.Frame(self.root, bg=T.BG)
        middle.pack(fill="both", expand=True)

        # Sidebar navigation
        sidebar = tk.Frame(middle, bg=T.BG_ALT, width=T.px(210))
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Hairline separator between sidebar and content
        sep = tk.Frame(middle, bg=T.BORDER, width=1)
        sep.pack(side="left", fill="y")

        self.nav_buttons = {}
        tk.Label(
            sidebar, text="WORKBENCH", font=self.fonts["mono_small"],
            fg=T.GOLD_MUTED, bg=T.BG_ALT, anchor="w", padx=T.px(18)
        ).pack(fill="x", pady=(T.px(14), T.px(8)))

        for page_id, label, desc in PAGES:
            btn = tk.Button(
                sidebar, text=f"  {label}", font=self.fonts["header_small"],
                bg=T.BG_ALT, fg=T.TEXT_MUTED, activebackground=T.BG_PANEL, activeforeground=T.TEXT_MAIN,
                relief="flat", bd=0, anchor="w", padx=T.px(14), pady=T.px(9), cursor="hand2",
                command=lambda pid=page_id: self.show_page(pid)
            )
            btn.pack(fill="x", padx=T.px(8), pady=2)
            self.nav_buttons[page_id] = btn

        # Page container
        self.container = tk.Frame(middle, bg=T.BG)
        self.container.pack(side="left", fill="both", expand=True)

        # Instantiate pages
        self.pages["browser"] = BrowserPage(self.container, self, self.fonts)
        self.pages["source"] = SourcePage(self.container, self, self.fonts)
        self.pages["builder"] = BuilderPage(self.container, self, self.fonts)
        self.pages["lml"] = LmlPage(self.container, self, self.fonts)

        for p in self.pages.values():
            p.pack_forget()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def show_page(self, page_id: str):
        if page_id not in self.pages:
            return

        if self.current_page_name and self.current_page_name in self.pages:
            self.pages[self.current_page_name].pack_forget()
            self.nav_buttons[self.current_page_name].config(bg=T.BG_ALT, fg=T.TEXT_MUTED)

        self.current_page_name = page_id
        page = self.pages[page_id]
        page.pack(fill="both", expand=True)

        self.nav_buttons[page_id].config(bg=T.ACCENT_ACTIVE, fg="#FFFFFF")

        # Update header subtitle
        active_lib = "sga_vulkan_final.fxdb" if self.active_api == "vulkan" else "sga_win32_60_final.fxdb"
        for pid, label, desc in PAGES:
            if pid == page_id:
                if pid == "browser":
                    cat = catalog.get_default_catalog()
                    total_count = len(cat.entries)
                    api_count = len(cat.by_api.get(self.active_api, []))
                    self.header.set_title("SHADER TOOL", f"Active API: {self.active_api.upper()} ({active_lib}) • {api_count:,} shaders ({total_count:,} total)")
                else:
                    self.header.set_title("SHADER TOOL", f"{label}: {desc} ({active_lib})")
                break

        if hasattr(page, "refresh"):
            page.refresh()

        self.cfg.set("Window", "page", page_id)

    def set_api(self, api: str):
        self.active_api = api.lower()
        self.cfg.active_api = self.active_api
        active_lib = "sga_vulkan_final.fxdb" if self.active_api == "vulkan" else "sga_win32_60_final.fxdb"
        cat = catalog.get_default_catalog()
        total_count = len(cat.entries)
        api_count = len(cat.by_api.get(self.active_api, []))
        self.header.set_title("SHADER TOOL", f"Active API: {self.active_api.upper()} ({active_lib}) • {api_count:,} shaders ({total_count:,} total)")

        cur_page = self.pages.get(self.current_page_name)
        if cur_page and hasattr(cur_page, "refresh"):
            cur_page.refresh()

    def set_status(self, msg: str):
        self.status_lbl.config(text=msg)

    def set_busy(self, is_busy: bool, msg: str = ""):
        self.busy_lbl.config(text=f"● {msg}" if is_busy else "")

    def log(self, text: str):
        pass

    def _catalog_ready(self, cat):
        total_count = len(cat.entries)
        api_count = len(cat.by_api.get(self.active_api, []))
        active_lib = "sga_vulkan_final.fxdb" if self.active_api == "vulkan" else "sga_win32_60_final.fxdb"
        self.header.set_title("SHADER TOOL", f"Active API: {self.active_api.upper()} ({active_lib}) • {api_count:,} shaders ({total_count:,} total)")
        if self.current_page_name == "browser":
            self.pages["browser"].refresh()

    def on_close(self):
        self.cfg.set("Window", "geometry", f"{self.root.winfo_width()}x{self.root.winfo_height()}")
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    paths.init_workspace()
    app = App()
    app.run()


if __name__ == "__main__":
    main()
