"""FXDB Archive Builder: Unpack libraries, inspect modified shaders, and repack."""

import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

from r2core import fxdb_parser, hashing, paths, settings
from .. import theme as T


class BuilderPage(tk.Frame):
    def __init__(self, parent, app, fonts: dict):
        super().__init__(parent, bg=T.BG)
        self.app = app
        self.fonts = fonts
        self.fxdb_files = []

        self._build_ui()

    def _build_ui(self):
        # Top toolbar
        toolbar = tk.Frame(self, bg=T.BG_ALT, height=T.px(54))
        toolbar.pack(fill="x", padx=T.px(10), pady=(T.px(10), 0))

        tk.Label(
            toolbar, text="FXDB Library:", bg=T.BG_ALT, fg=T.GOLD_MUTED, font=self.fonts["mono_small"]
        ).pack(side="left", padx=(T.px(12), T.px(6)), pady=T.px(8))

        self.lib_var = tk.StringVar()
        self.combo_lib = ttk.Combobox(toolbar, textvariable=self.lib_var, width=32, state="readonly")
        self.combo_lib.pack(side="left", padx=T.px(4), pady=T.px(8))
        self.combo_lib.bind("<<ComboboxSelected>>", lambda e: self._on_lib_change())

        btn_browse = tk.Button(
            toolbar, text="Browse...", bg=T.BG_PANEL, fg=T.TEXT_MAIN,
            activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["header_small"], relief="flat", padx=T.px(10), pady=T.px(4),
            command=self._browse_fxdb, cursor="hand2"
        )
        btn_browse.pack(side="left", padx=T.px(4))

        self.btn_unpack = tk.Button(
            toolbar, text="Unpack Shaders", bg=T.BG_PANEL, fg=T.TEXT_MAIN,
            activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["header_small"], relief="flat", padx=T.px(14), pady=T.px(4),
            command=self._unpack_library, cursor="hand2"
        )
        self.btn_unpack.pack(side="left", padx=(T.px(10), T.px(4)))

        self.btn_repack = tk.Button(
            toolbar, text="Repack Modified Shaders", bg=T.ACCENT, fg=T.ON_ACCENT,
            activebackground=T.ACCENT_HOVER, activeforeground=T.ON_ACCENT,
            font=self.fonts["header_small"], relief="flat", padx=T.px(16), pady=T.px(4),
            command=self._repack_library, cursor="hand2"
        )
        self.btn_repack.pack(side="left", padx=T.px(4))

        # Main content
        main_frame = tk.Frame(self, bg=T.BG)
        main_frame.pack(fill="both", expand=True, padx=T.px(10), pady=T.px(10))

        # Modified shaders panel
        head_panel = tk.Frame(main_frame, bg=T.BG)
        head_panel.pack(fill="x", pady=(0, T.px(6)))

        lbl_changed = tk.Label(
            head_panel, text="MODIFIED SHADERS DETECTED FOR INJECTION",
            font=self.fonts["mono_small"], fg=T.GOLD_MUTED, bg=T.BG, anchor="w"
        )
        lbl_changed.pack(side="left")

        btn_scan = tk.Button(
            head_panel, text="Rescan compiled/", bg=T.BG_PANEL, fg=T.TEXT_MUTED,
            activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["small"], relief="flat", padx=T.px(8), pady=1,
            command=self._detect_changes, cursor="hand2"
        )
        btn_scan.pack(side="right")

        table_box = tk.Frame(main_frame, bg=T.BG_INPUT, bd=1, relief="solid")
        table_box.pack(fill="both", expand=True)

        cols = ("stage", "index", "name", "old_crc", "new_crc", "file")
        self.tree = ttk.Treeview(table_box, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("stage", text="Stage")
        self.tree.heading("index", text="#")
        self.tree.heading("name", text="Shader Name")
        self.tree.heading("old_crc", text="Stock CRC")
        self.tree.heading("new_crc", text="Modified CRC")
        self.tree.heading("file", text="Compiled Source")

        self.tree.column("stage", width=T.px(60), anchor="center")
        self.tree.column("index", width=T.px(50), anchor="center")
        self.tree.column("name", width=T.px(240), anchor="w")
        self.tree.column("old_crc", width=T.px(100), anchor="center")
        self.tree.column("new_crc", width=T.px(100), anchor="center")
        self.tree.column("file", width=T.px(300), anchor="w")

        self.tree.tag_configure("odd", background=T.BG_INPUT)
        self.tree.tag_configure("even", background=T.BG_ALT)

        scroll = ttk.Scrollbar(table_box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.refresh_libraries()

    def refresh_libraries(self):
        dump_dir = Path(settings.settings().get("Paths", "rdr2_shaders_dump", str(paths.DEFAULT_DUMP_DIR)))
        fxdb_dir = dump_dir / "fxdb"
        found = []

        if fxdb_dir.exists():
            for f in fxdb_dir.glob("*.fxdb"):
                found.append(f)

        if paths.FXDB_FILES_DIR.exists():
            for f in paths.FXDB_FILES_DIR.glob("*.fxdb"):
                if f not in found:
                    found.append(f)

        self.fxdb_files = found
        names = [f.name for f in found]
        self.combo_lib["values"] = names

        if names:
            preferred = "sga_vulkan_final.fxdb" if self.app.active_api == "vulkan" else "sga_win32_60_final.fxdb"
            if preferred in names:
                self.combo_lib.set(preferred)
            else:
                self.combo_lib.current(0)
            self._detect_changes()

    def _browse_fxdb(self):
        f = filedialog.askopenfilename(
            title="Select FXDB Shader Database",
            initialdir=str(paths.DEFAULT_DUMP_DIR),
            filetypes=[("FXDB Databases", "*.fxdb;*.bin"), ("All Files", "*.*")]
        )
        if f:
            p = Path(f)
            if p not in self.fxdb_files:
                self.fxdb_files.append(p)
                self.combo_lib["values"] = [x.name for x in self.fxdb_files]
            self.combo_lib.set(p.name)
            self._detect_changes()

    def _on_lib_change(self):
        self._detect_changes()

    def _get_selected_fxdb_path(self) -> Optional[Path]:
        name = self.lib_var.get()
        for f in self.fxdb_files:
            if f.name == name:
                return f
        return None

    def _detect_changes(self):
        self.tree.delete(*self.tree.get_children())
        fxdb_path = self._get_selected_fxdb_path()
        if not fxdb_path or not fxdb_path.exists():
            return

        def work():
            fxdb = fxdb_parser.parse_file(fxdb_path, decompress_bytecode=True)
            modified = []
            compiled_dir = paths.COMPILED_DIR

            for stage_name, list_records in fxdb.shaders.items():
                for rec in list_records:
                    patterns = [
                        f"{rec.name}.spv",
                        f"{rec.name}.cso",
                        f"{rec.name}.{stage_name.lower()}_6_0.spv",
                        f"{rec.name}.{stage_name.lower()}_6_0.cso",
                        f"{stage_name.lower()}_{rec.index:08d}.spv",
                        f"{stage_name.lower()}_{rec.index:08d}.cso",
                    ]
                    for pat in patterns:
                        candidate = compiled_dir / pat
                        if candidate.exists():
                            new_bytes = candidate.read_bytes()
                            new_crc = hashing.crc32(new_bytes)
                            if new_crc != rec.crc32:
                                modified.append({
                                    "stage": rec.stage,
                                    "index": rec.index,
                                    "name": rec.name,
                                    "old_crc": f"0x{rec.crc32:08X}",
                                    "new_crc": f"0x{new_crc:08X}",
                                    "file": str(candidate.relative_to(paths.ROOT_DIR)),
                                    "path": candidate,
                                    "data": new_bytes,
                                })
                            break
            return modified

        def done(modified_list):
            for idx, m in enumerate(modified_list):
                row_tag = "even" if idx % 2 == 0 else "odd"
                self.tree.insert("", "end", values=(
                    m["stage"], m["index"], m["name"], m["old_crc"], m["new_crc"], m["file"]
                ), tags=(row_tag,))

            count = len(modified_list)
            self.app.set_status(f"Found {count} modified shaders ready to repack")

        self.app.tasks.run(work, done=done, label="Detecting modified shaders")

    def _unpack_library(self):
        fxdb_path = self._get_selected_fxdb_path()
        if not fxdb_path:
            messagebox.showinfo("Select Library", "Select an FXDB library to unpack.")
            return

        dest_dir = paths.DECOMPILED_DIR / fxdb_path.stem
        self.app.set_busy(True, f"Unpacking {fxdb_path.name}...")

        def work():
            fxdb = fxdb_parser.parse_file(fxdb_path, decompress_bytecode=True)
            total = sum(len(v) for v in fxdb.shaders.values())
            count = 0
            for stage_name, list_records in fxdb.shaders.items():
                stage_dir = dest_dir / stage_name
                paths.ensure(stage_dir)
                for rec in list_records:
                    ext = "spv" if rec.bytecode[:4] == b"\x03\x02\x23\x07" else "cso"
                    fn = stage_dir / f"{rec.index:04d}_{rec.name}.{ext}"
                    fn.write_bytes(rec.bytecode)
                    count += 1
            return count, dest_dir

        def done(res):
            self.app.set_busy(False, "")
            count, out_dir = res
            messagebox.showinfo("Unpack Complete", f"Unpacked {count} shaders to:\n{out_dir}")
            self.app.set_status(f"Unpacked {count} shaders -> {out_dir.name}")

        self.app.tasks.run(work, done=done, label=f"Unpack {fxdb_path.name}")

    def _repack_library(self):
        fxdb_path = self._get_selected_fxdb_path()
        if not fxdb_path:
            messagebox.showinfo("Select Library", "Select an FXDB library to repack.")
            return

        out_fxdb = paths.COMPILED_DIR / fxdb_path.name
        self.app.set_busy(True, f"Repacking into {out_fxdb.name}...")

        def work():
            fxdb = fxdb_parser.parse_file(fxdb_path, decompress_bytecode=True)
            compiled_dir = paths.COMPILED_DIR
            replacements = {}

            for stage_name, list_records in fxdb.shaders.items():
                for rec in list_records:
                    patterns = [
                        f"{rec.name}.spv",
                        f"{rec.name}.cso",
                        f"{rec.name}.{stage_name.lower()}_6_0.spv",
                        f"{rec.name}.{stage_name.lower()}_6_0.cso",
                        f"{stage_name.lower()}_{rec.index:08d}.spv",
                        f"{stage_name.lower()}_{rec.index:08d}.cso",
                    ]
                    for pat in patterns:
                        candidate = compiled_dir / pat
                        if candidate.exists():
                            new_bytes = candidate.read_bytes()
                            replacements[(rec.stage, rec.index)] = new_bytes
                            break

            count = fxdb_parser.repack_fxdb(fxdb_path, out_fxdb, replacements=replacements)
            return count, out_fxdb

        def done(res):
            self.app.set_busy(False, "")
            count, target_file = res
            messagebox.showinfo("Repack Complete", f"Successfully repacked {count} modified shaders.\nOutput written to:\n{target_file}")
            self.app.set_status(f"Repacked {count} shaders -> {target_file.name}")
            self._detect_changes()

        self.app.tasks.run(work, done=done, label=f"Repack {fxdb_path.name}")
