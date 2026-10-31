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
        self._displayed_entries: list = []
        self.sort_col = "index"
        self.sort_desc = False
        self.col_titles = {
            "stage": "Stage",
            "index": "#",
            "name": "Shader Name",
            "renodx_hash": "RenoDX Hash",
            "size": "Size"
        }

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

        # Library filter
        self.lib_var = tk.StringVar(value="All Databases")
        self.lib_menu = ttk.Combobox(toolbar, textvariable=self.lib_var, values=["All Databases"], width=24, state="readonly")
        self.lib_menu.pack(side="left", padx=(0, T.px(10)), pady=T.px(6))
        self.lib_menu.bind("<<ComboboxSelected>>", lambda e: self._on_search(self.search.get()))

        btn_reload = tk.Button(
            toolbar, text="Reload", bg=T.BG_PANEL, fg=T.TEXT_MAIN, activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["header_small"], relief="flat", padx=T.px(10), pady=T.px(4), command=self.refresh, cursor="hand2"
        )
        btn_reload.pack(side="right", padx=T.px(4), pady=T.px(6))

        btn_folder = tk.Button(
            toolbar, text="Folder...", bg=T.BG_PANEL, fg=T.TEXT_MAIN, activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["header_small"], relief="flat", padx=T.px(10), pady=T.px(4), command=self._change_dump_folder, cursor="hand2"
        )
        btn_folder.pack(side="right", padx=T.px(4), pady=T.px(6))

        btn_guide = tk.Button(
            toolbar, text="Extraction Guide", bg=T.BG_PANEL, fg=T.GOLD, activebackground=T.BG_ALT, activeforeground=T.GOLD,
            font=self.fonts["header_small"], relief="flat", padx=T.px(10), pady=T.px(4), command=self._open_guide, cursor="hand2"
        )
        btn_guide.pack(side="right", padx=T.px(4), pady=T.px(6))

        # Main split container
        paned = tk.PanedWindow(self, orient="horizontal", bg=T.BORDER, sashwidth=4)
        paned.pack(fill="both", expand=True, padx=T.px(10), pady=T.px(10))

        # Left: TreeView list of shaders
        left_frame = tk.Frame(paned, bg=T.BG_INPUT)
        paned.add(left_frame, minsize=T.px(490))

        cols = ("stage", "index", "name", "renodx_hash", "size")
        self.tree = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="browse")
        for col, title in self.col_titles.items():
            self.tree.heading(col, text=title, command=lambda c=col: self._sort_by_column(c))

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

        self._update_headings()

    def _open_guide(self):
        from r2core import rpf_reader
        from pathlib import Path
        import os

        guide = tk.Toplevel(self)
        guide.title("RDR2 Game Shaders & CodeX Extraction Guide")
        guide.geometry(f"{T.px(920)}x{T.px(640)}")
        guide.minsize(T.px(800), T.px(540))
        guide.configure(bg=T.BG)
        guide.transient(self.winfo_toplevel())
        guide.grab_set()

        # Top Red Accent Stripe
        tk.Frame(guide, bg=T.ACCENT, height=T.px(3)).pack(fill="x")

        # Top Header Bar
        top_bar = tk.Frame(guide, bg=T.BG_PANEL)
        top_bar.pack(fill="x", padx=T.px(16), pady=(T.px(14), T.px(8)))

        tk.Label(
            top_bar, text="GAME SHADER EXTRACTION REFERENCE", font=self.fonts["title"],
            fg=T.GOLD, bg=T.BG_PANEL
        ).pack(anchor="w", padx=T.px(14), pady=(T.px(10), T.px(2)))

        tk.Label(
            top_bar,
            text="Extract shaders from shaders_x64.rpf using your own copy of CodeX, then point the tool to your folder.",
            font=self.fonts["body"], fg=T.TEXT_MUTED, bg=T.BG_PANEL
        ).pack(anchor="w", padx=T.px(14), pady=(0, T.px(10)))

        # Step-by-Step Workflow Cards
        steps_frame = tk.Frame(guide, bg=T.BG)
        steps_frame.pack(fill="x", padx=T.px(16), pady=(0, T.px(8)))

        steps = [
            ("1. Open Game Archive", "shaders_x64.rpf in your RDR2 folder\n(and update_1.rpf\\common\\shaders)."),
            ("2. Export in CodeX", "Export shader files to any folder.\nKeep .bin hashes or rename them."),
            ("3. Point Shader Tool", "Select your folder below or put\nfiles inside fxdb_files/ in this tool."),
        ]
        for idx, (stitle, sdesc) in enumerate(steps):
            scard = tk.Frame(steps_frame, bg=T.BG_ALT, bd=1, relief="solid")
            scard.pack(side="left", fill="both", expand=True, padx=(0 if idx == 0 else T.px(6), 0))
            tk.Label(scard, text=stitle, font=self.fonts["body_bold"], fg=T.GOLD, bg=T.BG_ALT).pack(anchor="w", padx=T.px(10), pady=(T.px(8), T.px(2)))
            tk.Label(scard, text=sdesc, font=self.fonts["small"], fg=T.TEXT_MUTED, bg=T.BG_ALT, justify="left").pack(anchor="w", padx=T.px(10), pady=(0, T.px(8)))

        # Middle: Structured Table of Shaders
        table_label_frame = tk.Frame(guide, bg=T.BG)
        table_label_frame.pack(fill="x", padx=T.px(16), pady=(T.px(6), T.px(2)))
        tk.Label(table_label_frame, text="SHADER DATABASES REFERENCE MAPPING", font=self.fonts["header_small"], fg=T.TEXT_MAIN, bg=T.BG).pack(side="left")

        table_frame = tk.Frame(guide, bg=T.BG_INPUT, bd=1, relief="solid")
        table_frame.pack(fill="both", expand=True, padx=T.px(16), pady=(0, T.px(10)))

        tcols = ("status", "hash", "target", "api", "count", "size", "desc")
        gtree = ttk.Treeview(table_frame, columns=tcols, show="headings", selectmode="browse", height=5)
        gtree.heading("status", text="Status")
        gtree.heading("hash", text="CodeX Export (.bin)")
        gtree.heading("target", text="Target File (.fxdb)")
        gtree.heading("api", text="API")
        gtree.heading("count", text="Shaders")
        gtree.heading("size", text="Expected Size")
        gtree.heading("desc", text="Role / Content")

        gtree.column("status", width=T.px(80), anchor="center")
        gtree.column("hash", width=T.px(130), anchor="w")
        gtree.column("target", width=T.px(190), anchor="w")
        gtree.column("api", width=T.px(80), anchor="center")
        gtree.column("count", width=T.px(70), anchor="e")
        gtree.column("size", width=T.px(95), anchor="e")
        gtree.column("desc", width=T.px(220), anchor="w")

        gtree.tag_configure("even", background=T.BG_INPUT)
        gtree.tag_configure("odd", background=T.BG_ALT)

        gscroll = ttk.Scrollbar(table_frame, orient="vertical", command=gtree.yview)
        gtree.configure(yscrollcommand=gscroll.set)
        gtree.pack(side="left", fill="both", expand=True)
        gscroll.pack(side="right", fill="y")

        def populate_table():
            gtree.delete(*gtree.get_children())
            statuses = rpf_reader.check_folder_shader_status()
            for idx, s in enumerate(statuses):
                tag = "even" if idx % 2 == 0 else "odd"
                stat_text = "Detected" if s["found"] else "Missing"
                size_str = f"{s['expected_size'] / 1_000_000:.1f} MB" if s['expected_size'] >= 1_000_000 else f"{s['expected_size'] // 1_000} KB"
                gtree.insert("", "end", values=(
                    stat_text,
                    s["hash_file"],
                    s["fxdb_name"],
                    s["api"].upper(),
                    f"{s['shader_count']:,}",
                    size_str,
                    s["description"]
                ), tags=(tag,))

        populate_table()

        # Folder config card
        folder_card = tk.Frame(guide, bg=T.BG_PANEL, bd=1, relief="solid")
        folder_card.pack(fill="x", padx=T.px(16), pady=(0, T.px(10)))

        fc_top = tk.Frame(folder_card, bg=T.BG_PANEL)
        fc_top.pack(fill="x", padx=T.px(12), pady=(T.px(8), T.px(4)))

        tk.Label(fc_top, text="Current Shaders Folder:", font=self.fonts["body_bold"], fg=T.GOLD, bg=T.BG_PANEL).pack(side="left")

        curr_dump_val = tk.StringVar(value=settings.settings().get("Paths", "rdr2_shaders_dump", str(paths.DEFAULT_DUMP_DIR)))
        lbl_path = tk.Label(folder_card, textvariable=curr_dump_val, font=self.fonts["mono_small"], fg=T.TEXT_MAIN, bg=T.BG_PANEL, anchor="w")
        lbl_path.pack(fill="x", padx=T.px(12), pady=(0, T.px(8)))

        # Bottom Action Bar
        btn_bar = tk.Frame(guide, bg=T.BG)
        btn_bar.pack(fill="x", padx=T.px(16), pady=(0, T.px(14)))

        def choose_folder():
            from tkinter import filedialog
            chosen = filedialog.askdirectory(initialdir=curr_dump_val.get(), title="Select RDR2 Shaders / FXDB Folder")
            if chosen:
                settings.settings().set("Paths", "rdr2_shaders_dump", chosen)
                settings.settings().save()
                curr_dump_val.set(chosen)
                catalog.get_default_catalog(force_rebuild=True)
                populate_table()
                self.refresh()
                self.app.set_status(f"Updated shaders directory to: {chosen}")

        def open_folder():
            p = curr_dump_val.get()
            if p and Path(p).exists():
                os.startfile(p)

        tk.Button(
            btn_bar, text="Select Shaders Folder...", bg=T.ACCENT, fg=T.ON_ACCENT,
            activebackground=T.ACCENT_HOVER, activeforeground=T.ON_ACCENT,
            font=self.fonts["header_small"], relief="flat", padx=T.px(14), pady=T.px(6),
            command=choose_folder, cursor="hand2"
        ).pack(side="left", padx=(0, T.px(8)))

        tk.Button(
            btn_bar, text="Open in Explorer", bg=T.BG_PANEL, fg=T.TEXT_MAIN,
            activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["header_small"], relief="flat", padx=T.px(12), pady=T.px(6),
            command=open_folder, cursor="hand2"
        ).pack(side="left")

        tk.Button(
            btn_bar, text="Close", bg=T.BG_PANEL, fg=T.TEXT_MUTED,
            activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["header_small"], relief="flat", padx=T.px(16), pady=T.px(6),
            command=guide.destroy, cursor="hand2"
        ).pack(side="right")

    def _change_dump_folder(self):
        from tkinter import filedialog
        curr = settings.settings().get("Paths", "rdr2_shaders_dump", str(paths.DEFAULT_DUMP_DIR))
        chosen = filedialog.askdirectory(initialdir=curr, title="Select RDR2 Shaders / FXDB Folder")
        if chosen:
            settings.settings().set("Paths", "rdr2_shaders_dump", chosen)
            settings.settings().save()
            catalog.get_default_catalog(force_rebuild=True)
            self.refresh()
            self.app.set_status(f"Updated shaders directory to: {chosen}")

    def _update_headings(self):
        arrow = " \u25BC" if self.sort_desc else " \u25B2"
        for col, title in self.col_titles.items():
            if col == self.sort_col:
                self.tree.heading(col, text=f"{title}{arrow}")
            else:
                self.tree.heading(col, text=title)

    def _sort_by_column(self, col: str):
        selected_crc = self.selected_entry.crc if self.selected_entry else None
        if self.sort_col == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col = col
            self.sort_desc = True if col == "size" else False
        self._update_headings()
        self.refresh()
        if selected_crc is not None:
            for idx, e in enumerate(self._displayed_entries):
                if e.crc == selected_crc:
                    iid = str(idx)
                    self.tree.selection_set(iid)
                    self.tree.see(iid)
                    break

    def _sort_entries(self, entries: list) -> list:
        col = self.sort_col
        desc = self.sort_desc

        if col == "stage":
            return sorted(entries, key=lambda e: (e.stage, e.index), reverse=desc)
        elif col == "index":
            return sorted(entries, key=lambda e: (e.index, e.stage), reverse=desc)
        elif col == "name":
            return sorted(entries, key=lambda e: e.name.lower(), reverse=desc)
        elif col == "renodx_hash":
            return sorted(entries, key=lambda e: e.renodx_hash.lower(), reverse=desc)
        elif col == "size":
            return sorted(entries, key=lambda e: e.byte_size, reverse=desc)
        return entries

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        cat = catalog.get_default_catalog()
        api = self.app.active_api

        # Update library selector for current API
        libs = ["All Databases"] + cat.get_libraries(api)
        self.lib_menu["values"] = libs
        if self.lib_var.get() not in libs:
            self.lib_var.set("All Databases")

        stage_filter = self.stage_var.get()
        st = None if stage_filter == "ALL" else stage_filter
        lib_filter = None if self.lib_var.get() == "All Databases" else self.lib_var.get()

        entries = cat.find(query=self.search.get(), stage=st, api=api, library=lib_filter)
        entries = self._sort_entries(entries)
        self._displayed_entries = entries

        for idx, e in enumerate(entries):
            row_tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", "end", iid=str(idx), values=(
                e.stage, e.index, e.name, e.renodx_hash, f"{e.byte_size:,} B"
            ), tags=(row_tag,))

        lib_info = f" ({lib_filter})" if lib_filter else ""
        self.app.set_status(f"Loaded {len(entries):,} shaders for {api.upper()}{lib_info}")

    def _on_search(self, query: str):
        self.refresh()

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return

        try:
            row_idx = int(sel[0])
            entry = self._displayed_entries[row_idx]
        except (ValueError, IndexError):
            return

        self.selected_entry = entry

        self.btn_decompile.config(state="normal")
        self.btn_view_source.config(state="normal")
        self.btn_copy_hash.config(state="normal")
        self.btn_copy_name.config(state="normal")

        self.detail_header.config(text=f"{entry.name}  [{entry.stage}:{entry.index}]  ({entry.api.upper()})")

        # Load reflection
        try:
            from pathlib import Path
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
            from r2core import rpf_reader
            fxdb_disp = rpf_reader.resolve_fxdb_name(Path(entry.fxdb_path).name)
            if fxdb_disp.lower() != Path(entry.fxdb_path).name.lower():
                fxdb_disp = f"{fxdb_disp} ({Path(entry.fxdb_path).name})"
            append("Library:     ", "meta_key"); append(f"{fxdb_disp}\n", "meta_val")
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
