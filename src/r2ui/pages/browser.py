"""Shader Browser page: Search, inspect, view registers/cbuffers, and decompile."""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from r2core import catalog, decompile, hashing, paths, settings
from r2core.fxdb_parser import parse_file
from .. import theme as T
from ..widgets import CodeViewer, SearchEntry


class BrowserPage(tk.Frame):
    def __init__(self, parent, app, fonts: dict):
        super().__init__(parent, bg=T.BG)
        self.app = app
        self.fonts = fonts
        self.selected_entry: Optional[catalog.CatalogEntry] = None

        self._build_ui()

    def _build_ui(self):
        # Top toolbar
        toolbar = tk.Frame(self, bg=T.BG_ALT, height=T.px(48))
        toolbar.pack(fill="x", padx=T.px(10), pady=(T.px(10), 0))

        self.search = SearchEntry(toolbar, placeholder="Search shader name, hash, or effect...", on_search=self._on_search)
        self.search.pack(side="left", fill="x", expand=True, padx=(0, T.px(10)), pady=T.px(6))

        # Stage filter
        self.stage_var = tk.StringVar(value="ALL")
        stages = ["ALL", "VS", "PS", "CS", "GS", "DS", "HS"]
        stage_menu = ttk.Combobox(toolbar, textvariable=self.stage_var, values=stages, width=6, state="readonly")
        stage_menu.pack(side="left", padx=(0, T.px(10)))
        stage_menu.bind("<<ComboboxSelected>>", lambda e: self._on_search(self.search.get()))

        btn_reload = tk.Button(toolbar, text="↻ Refresh", bg=T.BG_PANEL, fg=T.TEXT_MAIN, relief="flat", padx=T.px(10), command=self.refresh)
        btn_reload.pack(side="right")

        # Main split container
        paned = tk.PanedWindow(self, orient="horizontal", bg=T.BORDER, sashwidth=4)
        paned.pack(fill="both", expand=True, padx=T.px(10), pady=T.px(10))

        # Left: TreeView list of shaders
        left_frame = tk.Frame(paned, bg=T.BG)
        paned.add(left_frame, minsize=T.px(450))

        cols = ("stage", "index", "name", "crc", "size")
        self.tree = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("stage", text="Stage")
        self.tree.heading("index", text="#")
        self.tree.heading("name", text="Shader Name")
        self.tree.heading("crc", text="CRC32")
        self.tree.heading("size", text="Size")

        self.tree.column("stage", width=T.px(55), anchor="center")
        self.tree.column("index", width=T.px(50), anchor="center")
        self.tree.column("name", width=T.px(220), anchor="w")
        self.tree.column("crc", width=T.px(90), anchor="center")
        self.tree.column("size", width=T.px(70), anchor="e")

        tree_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Right: Detail Inspector
        right_frame = tk.Frame(paned, bg=T.BG_ALT)
        paned.add(right_frame, minsize=T.px(500))

        self.detail_header = tk.Label(
            right_frame, text="Select a shader to inspect details",
            font=self.fonts["header"], fg=T.TEXT_MAIN, bg=T.BG_ALT, anchor="w", padx=T.px(12), pady=T.px(10)
        )
        self.detail_header.pack(fill="x")

        # Action Buttons
        act_bar = tk.Frame(right_frame, bg=T.BG_ALT)
        act_bar.pack(fill="x", padx=T.px(12), pady=(0, T.px(10)))

        self.btn_decompile = tk.Button(
            act_bar, text="▼ Decompile to HLSL", bg=T.ACCENT, fg=T.ON_ACCENT,
            font=self.fonts["body"], relief="flat", padx=T.px(14), pady=T.px(4),
            command=self._decompile_selected, state="disabled"
        )
        self.btn_decompile.pack(side="left", padx=(0, T.px(8)))

        self.btn_view_source = tk.Button(
            act_bar, text="Open in Editor Page", bg=T.BG_PANEL, fg=T.TEXT_MAIN,
            font=self.fonts["body"], relief="flat", padx=T.px(12), pady=T.px(4),
            command=self._open_in_editor, state="disabled"
        )
        self.btn_view_source.pack(side="left")

        # Detail text widget (Registers, CBuffers, Reflection)
        self.detail_text = tk.Text(
            right_frame, bg=T.BG, fg=T.TEXT_MAIN, font=self.fonts["mono"],
            relief="flat", bd=0, padx=T.px(12), pady=T.px(10), state="disabled"
        )
        self.detail_text.pack(fill="both", expand=True, padx=T.px(12), pady=(0, T.px(12)))

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        cat = catalog.get_default_catalog()
        api = self.app.active_api
        stage_filter = self.stage_var.get()
        st = None if stage_filter == "ALL" else stage_filter

        entries = cat.find(query=self.search.get(), stage=st, api=api)
        for e in entries[:300]:
            self.tree.insert("", "end", iid=f"{e.stage}_{e.index}_{e.crc}", values=(
                e.stage, e.index, e.name, e.crc_hex, f"{e.byte_size:,} B"
            ))

        self.app.set_status(f"Loaded {len(entries)} shaders for {api.upper()}")

    def _on_search(self, query: str):
        self.refresh()

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return

        item = self.tree.item(sel[0])
        st, idx_str, _, crc_hex, _ = item["values"]
        idx = int(idx_str)

        cat = catalog.get_default_catalog()
        entries = cat.find(query=crc_hex, stage=st, api=self.app.active_api)
        if not entries:
            return

        entry = entries[0]
        self.selected_entry = entry

        # Enable buttons
        self.btn_decompile.config(state="normal")
        self.btn_view_source.config(state="normal")

        self.detail_header.config(text=f"{entry.name} ({entry.stage}[{entry.index}]) — {entry.api.upper()}")

        # Load reflection
        try:
            fxdb = parse_file(entry.fxdb_path, decompress_bytecode=True)
            rec = fxdb.shaders[entry.stage][entry.index]

            lines = [
                f"Shader:      {rec.name}",
                f"Stage:       {rec.stage}[{rec.index}]",
                f"API:         {entry.api.upper()}",
                f"CRC32:       {entry.crc_hex}",
                f"Signature:   {entry.sig_hex}",
                f"Size:        {len(rec.bytecode):,} bytes (On-Disk: {len(rec.raw_bytecode):,} bytes, Compressed: {rec.is_compressed})",
                f"Belongs to:  {', '.join(entry.effects) or 'General'}",
                "\n" + "=" * 60,
                "REGISTERS & CONSTANT BUFFERS (RAGE SGA v1 Reflection):",
                "=" * 60,
            ]

            if not rec.data.resources:
                lines.append("  (No direct constant buffer or resource bindings)")
            else:
                for r in rec.data.resources:
                    lines.append(f"\n[Slot {r.bind_point}] {r.resource_class.name} :: {r.name} ({r.resource_type.name}, Size={r.byte_size}B)")
                    for el in r.elements:
                        arr = f"[{el.array_size}]" if el.array_size > 0 else ""
                        lines.append(f"    +{el.start_offset:04d}: {el.var_type.name:<10} {el.name}{arr}")

            self.detail_text.config(state="normal")
            self.detail_text.delete("1.0", "end")
            self.detail_text.insert("1.0", "\n".join(lines))
            self.detail_text.config(state="disabled")

        except Exception as ex:
            self.detail_text.config(state="normal")
            self.detail_text.delete("1.0", "end")
            self.detail_text.insert("1.0", f"Error loading reflection metadata:\n{ex}")
            self.detail_text.config(state="disabled")

    def _decompile_selected(self):
        if not self.selected_entry:
            return

        entry = self.selected_entry
        self.app.set_busy(True, f"Decompiling {entry.name}...")

        def work():
            fxdb = parse_file(entry.fxdb_path, decompress_bytecode=True)
            rec = fxdb.shaders[entry.stage][entry.index]
            res = decompile.decompile_shader(rec, api=entry.api, target_lang="hlsl")
            return res, rec

        def done(result_tuple):
            self.app.set_busy(False, "")
            res, rec = result_tuple
            if not res.ok:
                messagebox.showerror("Decompile Error", f"Failed to decompile {entry.name}:\n{res.error}")
                return

            # Save to source/
            out_path = paths.SOURCE_DIR / entry.api / rec.stage / f"{rec.name}.{rec.stage.lower()}_6_0.hlsl"
            paths.ensure(out_path.parent)
            out_path.write_text(res.source_code, encoding="utf-8")

            # Switch to Editor page
            self.app.pages["source"].load_file(out_path)
            self.app.show_page("source")
            self.app.set_status(f"Decompiled {entry.name} -> {out_path.name}")

        self.app.tasks.run(work, done=done, label=f"Decompile {entry.name}")

    def _open_in_editor(self):
        if not self.selected_entry:
            return
        entry = self.selected_entry
        out_path = paths.SOURCE_DIR / entry.api / entry.stage / f"{entry.name}.{entry.stage.lower()}_6_0.hlsl"
        if out_path.exists():
            self.app.pages["source"].load_file(out_path)
            self.app.show_page("source")
        else:
            self._decompile_selected()
