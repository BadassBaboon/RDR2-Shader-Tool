"""Custom reusable UI widgets for RDR2 Shader Tool with RDR2 dark styling."""

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional, Tuple

from . import theme as T


class HeaderBand(tk.Frame):
    """Top header band with RDR2 frontier styling, status line, and API toggle."""

    def __init__(self, parent, fonts: dict, title: str, subtitle: str, **kwargs):
        super().__init__(parent, bg=T.BG_ALT, height=T.px(66), **kwargs)
        self.pack_propagate(False)

        left = tk.Frame(self, bg=T.BG_ALT)
        left.pack(side="left", padx=T.px(20), fill="y")

        title_row = tk.Frame(left, bg=T.BG_ALT)
        title_row.pack(anchor="w", pady=(T.px(10), 0))

        # RDR2 Outlaw Crimson Tag
        badge = tk.Label(
            title_row, text=" RDR2 ", font=fonts["header_small"],
            fg="#FFFFFF", bg=T.ACCENT, padx=T.px(4), pady=T.px(1)
        )
        badge.pack(side="left", padx=(0, T.px(10)))

        self.title_lbl = tk.Label(
            title_row, text=title, font=fonts["brand"],
            fg=T.TEXT_MAIN, bg=T.BG_ALT, anchor="w"
        )
        self.title_lbl.pack(side="left")

        self.sub_lbl = tk.Label(
            left, text=subtitle, font=fonts["small"],
            fg=T.TEXT_MUTED, bg=T.BG_ALT, anchor="w"
        )
        self.sub_lbl.pack(anchor="w", pady=(T.px(2), 0))

        self.right = tk.Frame(self, bg=T.BG_ALT)
        self.right.pack(side="right", padx=T.px(20), fill="y")

        # Bottom hairline border
        sep = tk.Frame(self, bg=T.BORDER, height=1)
        sep.pack(side="bottom", fill="x")

    def set_title(self, title: str, subtitle: str):
        self.title_lbl.config(text=title)
        self.sub_lbl.config(text=subtitle)


class Segmented(tk.Frame):
    """Pill-style segmented button switch for API selection."""

    def __init__(self, parent, fonts: dict, options: List[Tuple[str, str]], value: str, command: Optional[Callable[[str], None]] = None):
        super().__init__(parent, bg=T.BG_PANEL, bd=1, relief="solid", highlightthickness=0)
        self.options = options
        self.current = value
        self.command = command
        self.fonts = fonts
        self.buttons = {}

        for val, label in options:
            btn = tk.Button(
                self, text=label, font=fonts["header_small"],
                relief="flat", bd=0, padx=T.px(14), pady=T.px(5), cursor="hand2",
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
                btn.config(bg=T.ACCENT, fg="#FFFFFF", activebackground=T.ACCENT_HOVER, activeforeground="#FFFFFF")
            else:
                btn.config(bg=T.BG_PANEL, fg=T.TEXT_MUTED, activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN)


class SearchEntry(tk.Frame):
    """Clean search input with placeholder, clear button, debounced typing, and dark input styling."""

    def __init__(self, parent, fonts: dict, placeholder: str = "Search shader name or 0xHash...", on_search: Optional[Callable[[str], None]] = None):
        super().__init__(parent, bg=T.BG_INPUT, bd=1, relief="solid", highlightthickness=0)
        self.on_search = on_search
        self.placeholder = placeholder
        self.fonts = fonts
        self._after_id = None

        self.var = tk.StringVar()
        self.var.trace_add("write", lambda *args: self._schedule_search())

        lbl = tk.Label(self, text="FILTER:", bg=T.BG_INPUT, fg=T.GOLD_MUTED, font=fonts["mono_small"])
        lbl.pack(side="left", padx=(T.px(10), T.px(4)))

        self.entry = tk.Entry(
            self, textvariable=self.var, bg=T.BG_INPUT, fg=T.TEXT_MAIN,
            insertbackground=T.TEXT_MAIN, selectbackground=T.ACCENT_ACTIVE, selectforeground="#FFFFFF",
            relief="flat", bd=0, font=fonts["body"]
        )
        self.entry.pack(side="left", fill="both", expand=True, padx=T.px(4), pady=T.px(6))
        self.entry.bind("<Return>", lambda e: self._trigger_search())

        self.clear_btn = tk.Button(
            self, text="Clear", bg=T.BG_PANEL, fg=T.TEXT_MUTED, activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=fonts["small"], relief="flat", bd=0, padx=T.px(8), pady=T.px(2),
            command=self.clear, cursor="hand2"
        )
        self.clear_btn.pack(side="right", padx=T.px(6), pady=T.px(4))

    def _schedule_search(self):
        # Debounce typing by 120ms to allow smooth typing without stutter
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.after(120, self._trigger_search)

    def _trigger_search(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self.on_search:
            self.on_search(self.var.get().strip())

    def clear(self):
        self.var.set("")
        self._trigger_search()

    def get(self) -> str:
        return self.var.get().strip()


class CodeViewer(tk.Frame):
    """Scrollable code viewer/editor with line numbers, dark styling, and TTK scrollbars."""

    def __init__(self, parent, fonts: dict, **kwargs):
        super().__init__(parent, bg=T.BG_INPUT, bd=1, relief="solid", **kwargs)

        self.line_nums = tk.Text(
            self, width=5, bg=T.BG_ALT, fg=T.TEXT_DIM,
            font=fonts["mono_small"], bd=0, relief="flat", state="disabled", padx=T.px(6)
        )
        self.line_nums.pack(side="left", fill="y")

        sep = tk.Frame(self, bg=T.BORDER, width=1)
        sep.pack(side="left", fill="y")

        self.text = tk.Text(
            self, bg=T.BG_INPUT, fg=T.TEXT_MAIN, insertbackground=T.TEXT_MAIN,
            selectbackground=T.ACCENT_ACTIVE, selectforeground="#FFFFFF",
            font=fonts["mono"], bd=0, relief="flat", wrap="none", padx=T.px(8)
        )
        self.text.pack(side="left", fill="both", expand=True)

        scroll_y = ttk.Scrollbar(self, orient="vertical", command=self._scroll_both)
        scroll_y.pack(side="right", fill="y")
        self.text.config(yscrollcommand=scroll_y.set)

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
