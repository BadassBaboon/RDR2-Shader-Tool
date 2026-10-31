"""Custom reusable UI widgets for RDR2 Shader Tool."""

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional, Tuple

from . import theme as T


class HeaderBand(tk.Frame):
    """Top header band with title, page description, and right-aligned controls."""

    def __init__(self, parent, fonts: dict, title: str, subtitle: str, **kwargs):
        super().__init__(parent, bg=T.BG_ALT, height=T.px(64), **kwargs)
        self.pack_propagate(False)

        left = tk.Frame(self, bg=T.BG_ALT)
        left.pack(side="left", padx=T.px(20), fill="y")

        self.title_lbl = tk.Label(
            left, text=title, font=fonts["title"],
            fg=T.TEXT_MAIN, bg=T.BG_ALT, anchor="w"
        )
        self.title_lbl.pack(anchor="w", pady=(T.px(8), 0))

        self.sub_lbl = tk.Label(
            left, text=subtitle, font=fonts["small"],
            fg=T.TEXT_MUTED, bg=T.BG_ALT, anchor="w"
        )
        self.sub_lbl.pack(anchor="w")

        self.right = tk.Frame(self, bg=T.BG_ALT)
        self.right.pack(side="right", padx=T.px(20), fill="y")

        # Bottom border line
        sep = tk.Frame(self, bg=T.BORDER, height=1)
        sep.pack(side="bottom", fill="x")

    def set_title(self, title: str, subtitle: str):
        self.title_lbl.config(text=title)
        self.sub_lbl.config(text=subtitle)


class Segmented(tk.Frame):
    """Pill-style segmented button switch (e.g. Vulkan / DX12)."""

    def __init__(self, parent, options: List[Tuple[str, str]], value: str, command: Optional[Callable[[str], None]] = None):
        super().__init__(parent, bg=T.BG_PANEL, bd=1, relief="solid")
        self.options = options
        self.current = value
        self.command = command
        self.buttons = {}

        for val, label in options:
            btn = tk.Button(
                self, text=label, font=tk.font.nametofont("TkDefaultFont"),
                relief="flat", bd=0, padx=T.px(12), pady=T.px(4),
                command=lambda v=val: self.select(v)
            )
            btn.pack(side="left", padx=1, pady=1)
            self.buttons[val] = btn

        self._refresh()

    def select(self, val: str):
        if self.current != val:
            self.current = val
            self._refresh()
            if self.command:
                self.command(val)

    def _refresh(self):
        for val, btn in self.buttons.items():
            if val == self.current:
                btn.config(bg=T.ACCENT, fg=T.ON_ACCENT, activebackground=T.ACCENT_HOVER, activeforeground=T.ON_ACCENT)
            else:
                btn.config(bg=T.BG_PANEL, fg=T.TEXT_MUTED, activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN)


class SearchEntry(tk.Frame):
    """Search box with placeholder and clear button."""

    def __init__(self, parent, placeholder: str = "Search...", on_search: Optional[Callable[[str], None]] = None):
        super().__init__(parent, bg=T.BG_PANEL, bd=1, relief="solid")
        self.on_search = on_search
        self.placeholder = placeholder

        self.var = tk.StringVar()
        self.var.trace_add("write", lambda *args: self._on_change())

        lbl = tk.Label(self, text="🔍", bg=T.BG_PANEL, fg=T.TEXT_DIM, font=("Segoe UI", T.px(9)))
        lbl.pack(side="left", padx=(T.px(8), T.px(4)))

        self.entry = tk.Entry(
            self, textvariable=self.var, bg=T.BG_PANEL, fg=T.TEXT_MAIN,
            insertbackground=T.TEXT_MAIN, relief="flat", bd=0, font=("Segoe UI", T.px(10))
        )
        self.entry.pack(side="left", fill="both", expand=True, padx=T.px(4), pady=T.px(6))

        self.clear_btn = tk.Button(
            self, text="✕", bg=T.BG_PANEL, fg=T.TEXT_DIM, relief="flat", bd=0,
            command=self.clear, cursor="hand2"
        )
        self.clear_btn.pack(side="right", padx=T.px(6))

    def _on_change(self):
        if self.on_search:
            self.on_search(self.var.get())

    def clear(self):
        self.var.set("")

    def get(self) -> str:
        return self.var.get()


class CodeViewer(tk.Frame):
    """Scrollable code viewer/editor with line numbers."""

    def __init__(self, parent, fonts: dict, **kwargs):
        super().__init__(parent, bg=T.BG, **kwargs)

        self.line_nums = tk.Text(
            self, width=5, bg=T.BG_ALT, fg=T.TEXT_DIM,
            font=fonts["mono"], bd=0, relief="flat", state="disabled", padx=4
        )
        self.line_nums.pack(side="left", fill="y")

        self.text = tk.Text(
            self, bg=T.BG, fg=T.TEXT_MAIN, insertbackground=T.TEXT_MAIN,
            font=fonts["mono"], bd=0, relief="flat", wrap="none", padx=8
        )
        self.text.pack(side="left", fill="both", expand=True)

        scroll_y = tk.Scrollbar(self, orient="vertical", command=self._scroll_both)
        scroll_y.pack(side="right", fill="y")
        self.text.config(yscrollcommand=scroll_y.set)

        scroll_x = tk.Scrollbar(parent, orient="horizontal", command=self.text.xview)
        self.text.config(xscrollcommand=scroll_x.set)

        self.text.bind("<KeyRelease>", lambda e: self._update_line_numbers())
        self.text.bind("<MouseWheel>", lambda e: self._sync_lines())

    def _scroll_both(self, *args):
        self.text.yview(*args)
        self.line_nums.yview(*args)

    def _sync_lines(self):
        self.line_nums.yview_moveto(self.text.yview()[0])

    def set_content(self, content: str):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self._update_line_numbers()

    def get_content(self) -> str:
        return self.text.get("1.0", "end-1c")

    def _update_line_numbers(self):
        count = int(self.text.index("end-1c").split(".")[0])
        nums = "\n".join(str(i) for i in range(1, count + 1))
        self.line_nums.config(state="normal")
        self.line_nums.delete("1.0", "end")
        self.line_nums.insert("1.0", nums)
        self.line_nums.config(state="disabled")
        self._sync_lines()
