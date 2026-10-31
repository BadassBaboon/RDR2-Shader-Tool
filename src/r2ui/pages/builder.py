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
        toolbar = tk.Frame(self, bg=T.BG_ALT, height=T.px(56))
        toolbar.pack(fill="x", padx=T.px(10), pady=(T.px(10), 0))

        tk.Label(toolbar, text="FXDB Library:", bg=T.BG_ALT, fg=T.TEXT_MAIN, font=self.fonts["body"]).pack(side="left", padx=(T.px(10), T.px(6)))

        self.lib_var = tk.StringVar()
        self.combo_lib = ttk.Combobox(toolbar, textvariable=self.lib_var, width=35, state="readonly")
        self.combo_lib.pack(side="left", padx=T.px(6))
        self.combo_lib.bind("<<ComboboxSelected>>", lambda e: self._on_lib_change())

        btn_browse = tk.Button(toolbar, text="Browse...", bg=T.BG_PANEL, fg=T.TEXT_MAIN, relief="flat", padx=T.px(8), command=self._browse_fxdb)
        btn_browse.pack(side="left", padx=T.px(6))

        self.btn_unpack = tk.Button(
            toolbar, text="📦 Unpack All Shaders", bg=T.BG_PANEL, fg=T.TEXT_MAIN,
            font=self.fonts["body"], relief="flat", padx=T.px(12), pady=T.px(4),
            command=self._unpack_library
        )
        self.btn_unpack.pack(side="left", padx=T.px(10))

        self.btn_repack = tk.Button(
            toolbar, text="📤 Repack (Inject Changed)", bg=T.ACCENT, fg=T.ON_ACCENT,
            font=self.fonts["body"], relief="flat", padx=T.px(14), pady=T.px(4),
            command=self._repack_library
        )
        self.btn_repack.pack(side="left", padx=T.px(6))

        # Main content
        main_frame = tk.Frame(self, bg=T.BG)
        main_frame.pack(fill="both", expand=True, padx=T.px(10), pady=T.px(10))

        # Changed shaders detection panel
        lbl_changed = tk.Label(
            main_frame, text="Modified Shaders Detected for Repack:",
            font=self.fonts["header"], fg=T.TEXT_MAIN, bg=T.BG, anchor="w", pady=T.px(6)
        )
        lbl_changed.pack(fill="x")

        cols = ("stage", "index", "name", "old_crc", "new_crc", "file")
        self.tree = ttk.Treeview(main_frame, columns=cols, show="headings", selectmode="browse")
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

        scroll = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
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
            # Prefer active API file
            api = self.app.active_api
            preferred = [n for n in names if api in n.lower()]
            self.combo_lib.set(preferred[0] if preferred else names[0])
            self._on_lib_change()

    def _browse_fxdb(self):
        f = filedialog.askopenfilename(
            title="Select RDR2 FXDB Shader Library",
            filetypes=[("FXDB Shader Libraries", "*.fxdb *.bin"), ("All Files", "*.*")]
        )
        if f:
            p = Path(f)
            if p not in self.fxdb_files:
                self.fxdb_files.append(p)
                self.combo_lib["values"] = [f.name for f in self.fxdb_files]
            self.combo_lib.set(p.name)
            self._on_lib_change()

    def _get_selected_fxdb(self) -> Optional[Path]:
        name = self.lib_var.get()
        for f in self.fxdb_files:
            if f.name == name:
                return f
        return None

    def _on_lib_change(self):
        fxdb = self._get_selected_fxdb()
        if not fxdb:
            return
        self._scan_modified_shaders(fxdb)

    def _scan_modified_shaders(self, fxdb_path: Path):
        self.tree.delete(*self.tree.get_children())
        is_vulkan = "vulkan" in fxdb_path.name.lower() or "vk" in fxdb_path.name.lower()
        api = "vulkan" if is_vulkan else "dx12"
        ext = "spv" if is_vulkan else "cso"

        search_dir = paths.COMPILED_DIR / api / fxdb_path.stem
        if not search_dir.exists():
            return

        try:
            parsed = fxdb_parser.parse_file(fxdb_path, decompress_bytecode=True)
            for f in search_dir.rglob(f"*.{ext}"):
                st = f.parent.name.upper()
                if st not in fxdb_parser.STAGES:
                    continue

                fname = f.stem
                matched_record = None
                parts = fname.split("_", 1)
                if len(parts) == 2 and parts[0].isdigit():
                    idx = int(parts[0])
                    recs = parsed.shaders.get(st, [])
                    if 0 <= idx < len(recs):
                        matched_record = recs[idx]

                if not matched_record:
                    for r in parsed.shaders.get(st, []):
                        if r.name.lower() == fname.lower():
                            matched_record = r
                            break

                if matched_record:
                    new_bytes = f.read_bytes()
                    new_crc = hashing.crc32(new_bytes)
                    if new_crc != matched_record.crc:
                        self.tree.insert("", "end", values=(
                            st, matched_record.index, matched_record.name,
                            hashing.fmt(matched_record.crc), hashing.fmt(new_crc),
                            str(f.relative_to(paths.ROOT))
                        ))
        except Exception as ex:
            print(f"Error scanning modified shaders: {ex}")

    def _unpack_library(self):
        fxdb = self._get_selected_fxdb()
        if not fxdb:
            return

        self.app.set_busy(True, f"Unpacking {fxdb.name}...")

        def work():
            parsed = fxdb_parser.parse_file(fxdb, decompress_bytecode=True)
            is_vulkan = "vulkan" in fxdb.name.lower() or "vk" in fxdb.name.lower()
            api = "vulkan" if is_vulkan else "dx12"
            ext = "spv" if is_vulkan else "cso"
            out_base = paths.COMPILED_DIR / api / fxdb.stem
            paths.ensure(out_base)

            cnt = 0
            for st, records in parsed.shaders.items():
                sdir = out_base / st
                paths.ensure(sdir)
                for r in records:
                    ofile = sdir / f"{r.index:04d}_{r.name}.{ext}"
                    ofile.write_bytes(r.bytecode)
                    cnt += 1
            return cnt, out_base

        def done(tup):
            self.app.set_busy(False, "")
            cnt, out_base = tup
            messagebox.showinfo("Unpack Complete", f"Successfully unpacked {cnt:,} shaders to:\n{out_base}")
            self.app.set_status(f"Unpacked {cnt} shaders from {fxdb.name}")
            self._scan_modified_shaders(fxdb)

        self.app.tasks.run(work, done=done, label=f"Unpack {fxdb.name}")

    def _repack_library(self):
        fxdb = self._get_selected_fxdb()
        if not fxdb:
            return

        is_vulkan = "vulkan" in fxdb.name.lower() or "vk" in fxdb.name.lower()
        api = "vulkan" if is_vulkan else "dx12"
        ext = "spv" if is_vulkan else "cso"
        search_dir = paths.COMPILED_DIR / api / fxdb.stem

        if not search_dir.exists():
            messagebox.showwarning("Repack", f"No compiled shaders found in {search_dir}")
            return

        self.app.set_busy(True, f"Repacking {fxdb.name}...")

        def work():
            parsed = fxdb_parser.parse_file(fxdb, decompress_bytecode=True)
            replacements = {}
            for f in search_dir.rglob(f"*.{ext}"):
                st = f.parent.name.upper()
                if st not in fxdb_parser.STAGES:
                    continue
                parts = f.stem.split("_", 1)
                if len(parts) == 2 and parts[0].isdigit():
                    idx = int(parts[0])
                    recs = parsed.shaders.get(st, [])
                    if 0 <= idx < len(recs):
                        nb = f.read_bytes()
                        if hashing.crc32(nb) != recs[idx].crc:
                            replacements[(st, idx)] = nb

            if not replacements:
                return None, 0

            # Backup original
            bdir = paths.ensure(fxdb.parent / "backups")
            shutil.copy2(fxdb, bdir / f"{fxdb.name}.bak")

            out_path = fxdb.with_name(f"{fxdb.stem}_modified.fxdb")
            res = fxdb_parser.inject_shaders(fxdb, out_path, replacements)
            return res, len(replacements)

        def done(tup):
            self.app.set_busy(False, "")
            res, count = tup
            if count == 0:
                messagebox.showinfo("Repack", "No modified shaders were detected to inject.")
            else:
                messagebox.showinfo("Repack Complete", f"Successfully injected {count} shader(s) into:\n{res['output_path']}\n(Backup created in backups/)")
                self.app.set_status(f"Repacked {count} shader(s) into {Path(res['output_path']).name}")
                self._scan_modified_shaders(fxdb)

        self.app.tasks.run(work, done=done, label=f"Repack {fxdb.name}")
