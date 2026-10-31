"""Shader Browser page: Search, inspect, view registers/cbuffers, RenoDX interop, and decompile."""

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

        self.search = SearchEntry(toolbar, self.fonts, placeholder="Search shader name, RenoDX 0xHash, or dump filename...", on_search=self._on_search)
        self.search.pack(side="left", fill="x", expand=True, padx=(0, T.px(10)), pady=T.px(6))

        # Stage filter
        self.stage_var = tk.StringVar(value="ALL")
        stages = ["ALL", "VS", "PS", "CS", "GS", "DS", "HS"]
        stage_menu = ttk.Combobox(toolbar, textvariable=self.stage_var, values=stages, width=7, state="readonly")
        stage_menu.pack(side="left", padx=(0, T.px(10)), pady=T.px(6))
        stage_menu.bind("<<ComboboxSelected>>", lambda e: self._on_search(self.search.get()))

        btn_reload = tk.Button(
            toolbar, text="Reload", bg=T.BG_PANEL, fg=T.TEXT_MAIN, activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["header_small"], relief="flat", padx=T.px(12), pady=T.px(4), command=self.refresh, cursor="hand2"
        )
        btn_reload.pack(side="right", padx=T.px(6), pady=T.px(6))

        # Main split container
        paned = tk.PanedWindow(self, orient="horizontal", bg=T.BORDER, sashwidth=4)
        paned.pack(fill="both", expand=True, padx=T.px(10), pady=T.px(10))

        # Left: TreeView list of shaders
        left_frame = tk.Frame(paned, bg=T.BG_INPUT)
        paned.add(left_frame, minsize=T.px(490))

        cols = ("stage", "index", "name", "renodx_hash", "size")
        self.tree = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("stage", text="Stage")
        self.tree.heading("index", text="#")
        self.tree.heading("name", text="Shader Name")
        self.tree.heading("renodx_hash", text="RenoDX Hash")
        self.tree.heading("size", text="Size")

        self.tree.column("stage", width=T.px(55), anchor="center")
        self.tree.column("index", width=T.px(50), anchor="center")
        self.tree.column("name", width=T.px(230), anchor="w")
        self.tree.column("renodx_hash", width=T.px(105), anchor="center")
        self.tree.column("size", width=T.px(70), anchor="e")

        # Alternating row colors
        self.tree.tag_configure("odd", background=T.BG_INPUT)
        self.tree.tag_configure("even", background=T.BG_ALT)

        tree_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Right: Detail Inspector
        right_frame = tk.Frame(paned, bg=T.BG_ALT)
        paned.add(right_frame, minsize=T.px(530))

        # Inspector Title Bar
        header_bar = tk.Frame(right_frame, bg=T.BG_ALT)
        header_bar.pack(fill="x", padx=T.px(14), pady=(T.px(10), T.px(4)))

        self.detail_header = tk.Label(
            header_bar, text="Select a shader to inspect reflection",
            font=self.fonts["header"], fg=T.TEXT_MAIN, bg=T.BG_ALT, anchor="w"
        )
        self.detail_header.pack(side="left")

        # Action Buttons
        act_bar = tk.Frame(right_frame, bg=T.BG_ALT)
        act_bar.pack(fill="x", padx=T.px(14), pady=(0, T.px(8)))

        self.btn_decompile = tk.Button(
            act_bar, text="Decompile to HLSL", bg=T.ACCENT, fg=T.ON_ACCENT,
            activebackground=T.ACCENT_HOVER, activeforeground=T.ON_ACCENT,
            font=self.fonts["header_small"], relief="flat", padx=T.px(14), pady=T.px(5),
            command=self._decompile_selected, state="disabled", cursor="hand2"
        )
        self.btn_decompile.pack(side="left", padx=(0, T.px(6)))

        self.btn_view_source = tk.Button(
            act_bar, text="Open in Editor", bg=T.BG_PANEL, fg=T.TEXT_MAIN,
            activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["header_small"], relief="flat", padx=T.px(12), pady=T.px(5),
            command=self._open_in_editor, state="disabled", cursor="hand2"
        )
        self.btn_view_source.pack(side="left", padx=(0, T.px(6)))

        self.btn_copy_hash = tk.Button(
            act_bar, text="Copy RenoDX Hash", bg=T.BG_PANEL, fg=T.GOLD,
            activebackground=T.BG_ALT, activeforeground=T.GOLD,
            font=self.fonts["small"], relief="flat", padx=T.px(10), pady=T.px(5),
            command=self._copy_renodx_hash, state="disabled", cursor="hand2"
        )
        self.btn_copy_hash.pack(side="left", padx=(0, T.px(4)))

        self.btn_copy_name = tk.Button(
            act_bar, text="Copy Dump Name", bg=T.BG_PANEL, fg=T.TEXT_MUTED,
            activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["small"], relief="flat", padx=T.px(10), pady=T.px(5),
            command=self._copy_renodx_filename, state="disabled", cursor="hand2"
        )
        self.btn_copy_name.pack(side="left")

        # Detail text widget (Registers, CBuffers, Reflection)
        detail_container = tk.Frame(right_frame, bg=T.BG_INPUT, bd=1, relief="solid")
        detail_container.pack(fill="both", expand=True, padx=T.px(14), pady=(0, T.px(12)))

        self.detail_text = tk.Text(
            detail_container, bg=T.BG_INPUT, fg=T.TEXT_MAIN, font=self.fonts["mono_small"],
            selectbackground=T.ACCENT_ACTIVE, selectforeground="#FFFFFF",
            relief="flat", bd=0, padx=T.px(12), pady=T.px(10), state="disabled"
        )
        detail_scroll = ttk.Scrollbar(detail_container, orient="vertical", command=self.detail_text.yview)
        self.detail_text.config(yscrollcommand=detail_scroll.set)
        self.detail_text.pack(side="left", fill="both", expand=True)
        detail_scroll.pack(side="right", fill="y")

        # Text tag styles for syntax coloring in reflection dump
        self.detail_text.tag_configure("title", font=self.fonts["header_small"], foreground=T.GOLD)
        self.detail_text.tag_configure("meta_key", font=self.fonts["mono_small"], foreground=T.TEXT_MUTED)
        self.detail_text.tag_configure("meta_val", font=self.fonts["mono_small"], foreground=T.TEXT_MAIN)
        self.detail_text.tag_configure("cb_head", font=self.fonts["mono_bold"], foreground=T.GOLD)
        self.detail_text.tag_configure("var_type", font=self.fonts["mono_small"], foreground=T.CYAN)
        self.detail_text.tag_configure("var_offset", font=self.fonts["mono_small"], foreground=T.TEXT_DIM)
        self.detail_text.tag_configure("var_name", font=self.fonts["mono_small"], foreground=T.TEXT_MAIN)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        cat = catalog.get_default_catalog()
        api = self.app.active_api
        stage_filter = self.stage_var.get()
        st = None if stage_filter == "ALL" else stage_filter

        entries = cat.find(query=self.search.get(), stage=st, api=api)
        for idx, e in enumerate(entries[:400]):
            row_tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", "end", iid=f"{e.stage}_{e.index}_{e.crc}", values=(
                e.stage, e.index, e.name, e.renodx_hash, f"{e.byte_size:,} B"
            ), tags=(row_tag,))

        self.app.set_status(f"Loaded {len(entries)} shaders for {api.upper()}")

    def _on_search(self, query: str):
        self.refresh()

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return

        item = self.tree.item(sel[0])
        st, idx_str, _, renodx_hash_str, _ = item["values"]
        idx = int(idx_str)

        cat = catalog.get_default_catalog()
        entries = cat.find(query=renodx_hash_str, stage=st, api=self.app.active_api)
        if not entries:
            entries = [e for e in cat.entries if e.stage == st and e.index == idx and e.api.lower() == self.app.active_api.lower()]
        if not entries:
            return

        entry = entries[0]
        self.selected_entry = entry

        self.btn_decompile.config(state="normal")
        self.btn_view_source.config(state="normal")
        self.btn_copy_hash.config(state="normal")
        self.btn_copy_name.config(state="normal")

        self.detail_header.config(text=f"{entry.name}  [{entry.stage}:{entry.index}]  ({entry.api.upper()})")

        # Load reflection
        try:
            fxdb = parse_file(entry.fxdb_path, decompress_bytecode=True)
            rec = fxdb.shaders[entry.stage][entry.index]

            self.detail_text.config(state="normal")
            self.detail_text.delete("1.0", "end")

            def append(txt: str, tag: str = None):
                if tag:
                    self.detail_text.insert("end", txt, tag)
                else:
                    self.detail_text.insert("end", txt)

            append("RENODX SHADER INTEROP\n", "title")
            append("----------------------------------------------------------------------\n", "meta_key")
            append("RenoDX Hash: ", "meta_key"); append(f"{entry.renodx_hash}\n", "cb_head")
            append("Dump Name:   ", "meta_key"); append(f"{entry.renodx_filename}\n", "var_type")

            append("\nSHADER METADATA\n", "title")
            append("----------------------------------------------------------------------\n", "meta_key")
            append("Name:        ", "meta_key"); append(f"{rec.name}\n", "meta_val")
            append("Stage:       ", "meta_key"); append(f"{rec.stage} (Index {rec.index})\n", "meta_val")
            append("API:         ", "meta_key"); append(f"{entry.api.upper()}\n", "meta_val")
            append("CRC32:       ", "meta_key"); append(f"{entry.crc_hex}\n", "meta_val")
            append("Signature:   ", "meta_key"); append(f"{entry.sig_hex}\n", "meta_val")
            append("Size:        ", "meta_key"); append(f"{len(rec.bytecode):,} B (Raw disk: {len(rec.raw_bytecode):,} B, Compressed: {rec.is_compressed})\n", "meta_val")
            append("Effects:     ", "meta_key"); append(f"{', '.join(entry.effects) or 'None'}\n", "meta_val")

            append("\nCONSTANT BUFFERS & REGISTERS (RAGE SGA v1 Reflection)\n", "title")
            append("----------------------------------------------------------------------\n", "meta_key")

            if not rec.data.resources:
                append("  No direct constant buffer or resource bindings in this stage.\n", "meta_key")
            else:
                for r in rec.data.resources:
                    append(f"\n[Slot {r.bind_point:02d}] {r.resource_class.name} :: {r.name}", "cb_head")
                    append(f" ({r.resource_type.name}, Size={r.byte_size} B)\n", "meta_key")
                    for el in r.elements:
                        arr = f"[{el.array_size}]" if el.array_size > 0 else ""
                        append(f"    +{el.start_offset:04d}: ", "var_offset")
                        append(f"{el.var_type.name:<12} ", "var_type")
                        append(f"{el.name}{arr}\n", "var_name")

            self.detail_text.config(state="disabled")

        except Exception as ex:
            self.detail_text.config(state="normal")
            self.detail_text.delete("1.0", "end")
            self.detail_text.insert("1.0", f"Error loading reflection metadata:\n{ex}")
            self.detail_text.config(state="disabled")

    def _copy_renodx_hash(self):
        if self.selected_entry:
            self.clipboard_clear()
            self.clipboard_append(self.selected_entry.renodx_hash)
            self.app.set_status(f"Copied RenoDX hash {self.selected_entry.renodx_hash} to clipboard")

    def _copy_renodx_filename(self):
        if self.selected_entry:
            self.clipboard_clear()
            self.clipboard_append(self.selected_entry.renodx_filename)
            self.app.set_status(f"Copied RenoDX dump name {self.selected_entry.renodx_filename} to clipboard")

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

            out_path = paths.SOURCE_DIR / entry.api / rec.stage / f"{rec.name}.{rec.stage.lower()}_6_0.hlsl"
            paths.ensure(out_path.parent)
            out_path.write_text(res.source_code, encoding="utf-8")

            self.app.pages["source"].load_file(out_path)
            self.app.show_page("source")
            self.app.set_status(f"Decompiled {entry.name} to {out_path.name}")

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
