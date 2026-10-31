"""Source & Compile page: Edit shader code, recompile, and watch for file modifications."""

import os
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from r2core import compile, paths, settings
from .. import theme as T
from ..widgets import CodeViewer


class SourcePage(tk.Frame):
    def __init__(self, parent, app, fonts: dict):
        super().__init__(parent, bg=T.BG)
        self.app = app
        self.fonts = fonts
        self.current_file: Optional[Path] = None
        self.watch_active = False
        self.last_mtime = 0

        self._build_ui()

    def _build_ui(self):
        # Action Bar
        act_bar = tk.Frame(self, bg=T.BG_ALT, height=T.px(48))
        act_bar.pack(fill="x", padx=T.px(10), pady=(T.px(10), 0))

        btn_open = tk.Button(
            act_bar, text="📁 Open File...", bg=T.BG_PANEL, fg=T.TEXT_MAIN,
            font=self.fonts["body"], relief="flat", padx=T.px(10), pady=T.px(4),
            command=self._on_open_file
        )
        btn_open.pack(side="left", padx=(T.px(6), T.px(6)), pady=T.px(6))

        self.btn_compile = tk.Button(
            act_bar, text="▶ Compile Selected", bg=T.ACCENT, fg=T.ON_ACCENT,
            font=self.fonts["body"], relief="flat", padx=T.px(14), pady=T.px(4),
            command=self._compile_current
        )
        self.btn_compile.pack(side="left", padx=T.px(6))

        # Watch mode toggle
        self.watch_var = tk.BooleanVar(value=True)
        chk_watch = tk.Checkbutton(
            act_bar, text="Auto-Compile on Save (Watch Mode)", variable=self.watch_var,
            bg=T.BG_ALT, fg=T.TEXT_MAIN, selectcolor=T.BG_PANEL, activebackground=T.BG_ALT,
            font=self.fonts["small"], command=self._toggle_watch
        )
        chk_watch.pack(side="left", padx=T.px(12))

        self.file_lbl = tk.Label(
            act_bar, text="No file open", font=self.fonts["small"],
            fg=T.TEXT_MUTED, bg=T.BG_ALT, anchor="w"
        )
        self.file_lbl.pack(side="left", padx=T.px(10))

        # Main editor area
        paned = tk.PanedWindow(self, orient="vertical", bg=T.BORDER, sashwidth=4)
        paned.pack(fill="both", expand=True, padx=T.px(10), pady=T.px(10))

        # Editor
        self.editor = CodeViewer(paned, self.fonts)
        paned.add(self.editor, minsize=T.px(350))

        # Build log
        log_frame = tk.Frame(paned, bg=T.BG_ALT)
        paned.add(log_frame, minsize=T.px(120))

        log_lbl = tk.Label(
            log_frame, text="Compiler Output & Diagnostics:",
            font=self.fonts["small"], fg=T.TEXT_MUTED, bg=T.BG_ALT, anchor="w", padx=T.px(8), pady=T.px(4)
        )
        log_lbl.pack(fill="x")

        self.log_text = tk.Text(
            log_frame, bg=T.BG, fg=T.TEXT_MAIN, font=self.fonts["mono_small"],
            relief="flat", bd=0, padx=T.px(8), pady=T.px(4), height=6
        )
        self.log_text.pack(fill="both", expand=True, padx=T.px(8), pady=(0, T.px(8)))

        self._start_watcher()

    def load_file(self, file_path: Path):
        self.current_file = Path(file_path)
        content = self.current_file.read_text(encoding="utf-8", errors="replace")
        self.editor.set_content(content)
        self.last_mtime = self.current_file.stat().st_mtime
        self.file_lbl.config(text=f"Editing: {self.current_file.name} ({self.current_file})")

    def _on_open_file(self):
        f = filedialog.askopenfilename(
            title="Open HLSL / GLSL Shader Source",
            initialdir=str(paths.SOURCE_DIR),
            filetypes=[("Shader Sources", "*.hlsl *.glsl"), ("All Files", "*.*")]
        )
        if f:
            self.load_file(Path(f))

    def _compile_current(self):
        if not self.current_file or not self.current_file.exists():
            # Save unsaved buffer to temp
            content = self.editor.get_content()
            if not content.strip():
                return
            temp_hlsl = paths.SOURCE_DIR / self.app.active_api / "temp_shader.hlsl"
            paths.ensure(temp_hlsl.parent)
            temp_hlsl.write_text(content, encoding="utf-8")
            self.load_file(temp_hlsl)

        # Save buffer to disk before compiling
        self.current_file.write_text(self.editor.get_content(), encoding="utf-8")
        self.last_mtime = self.current_file.stat().st_mtime

        api = self.app.active_api
        self.app.set_busy(True, f"Compiling {self.current_file.name}...")

        def work():
            return compile.compile_shader(self.current_file, target_api=api)

        def done(res: compile.CompileResult):
            self.app.set_busy(False, "")
            self.log_text.delete("1.0", "end")

            if res.ok:
                ext = "spv" if api == "vulkan" else "cso"
                out_path = paths.COMPILED_DIR / api / f"{self.current_file.stem}.{ext}"
                paths.ensure(out_path.parent)
                out_path.write_bytes(res.bytecode)

                msg = f"✓ Build Succeeded!\nOutput: {out_path} ({len(res.bytecode):,} bytes)\nProfile: {res.profile} [{', '.join(res.steps or [])}]"
                if res.warnings:
                    msg += f"\nWarnings:\n{res.warnings}"
                self.log_text.insert("1.0", msg)
                self.app.set_status(f"Compiled {self.current_file.name} -> {out_path.name}")
            else:
                self.log_text.insert("1.0", f"✗ Compilation Failed:\n{res.error}")
                self.app.set_status(f"Compilation failed for {self.current_file.name}")

        self.app.tasks.run(work, done=done, label=f"Compile {self.current_file.name}")

    def _toggle_watch(self):
        pass

    def _start_watcher(self):
        def watcher():
            while True:
                time.sleep(0.8)
                if self.watch_var.get() and self.current_file and self.current_file.exists():
                    try:
                        mtime = self.current_file.stat().st_mtime
                        if mtime > self.last_mtime:
                            self.last_mtime = mtime
                            # Reload and auto-compile
                            content = self.current_file.read_text(encoding="utf-8", errors="replace")
                            self.after(0, lambda c=content: self.editor.set_content(c))
                            self.after(50, self._compile_current)
                    except Exception:
                        pass

        t = threading.Thread(target=watcher, daemon=True)
        t.start()
