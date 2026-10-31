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
            act_bar, text="Open Shader...", bg=T.BG_PANEL, fg=T.TEXT_MAIN,
            activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["header_small"], relief="flat", padx=T.px(12), pady=T.px(5),
            command=self._on_open_file, cursor="hand2"
        )
        btn_open.pack(side="left", padx=(T.px(6), T.px(6)), pady=T.px(6))

        self.btn_compile = tk.Button(
            act_bar, text="Compile Shader", bg=T.ACCENT, fg=T.ON_ACCENT,
            activebackground=T.ACCENT_HOVER, activeforeground=T.ON_ACCENT,
            font=self.fonts["header_small"], relief="flat", padx=T.px(14), pady=T.px(5),
            command=self._compile_current, cursor="hand2"
        )
        self.btn_compile.pack(side="left", padx=T.px(6))

        btn_save = tk.Button(
            act_bar, text="Save File", bg=T.BG_PANEL, fg=T.TEXT_MAIN,
            activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["header_small"], relief="flat", padx=T.px(12), pady=T.px(5),
            command=self._save_current, cursor="hand2"
        )
        btn_save.pack(side="left", padx=T.px(6))

        # Watch mode toggle
        self.watch_var = tk.BooleanVar(value=True)
        chk_watch = tk.Checkbutton(
            act_bar, text="Auto-compile on save (Watch Mode)", variable=self.watch_var,
            bg=T.BG_ALT, fg=T.TEXT_MAIN, selectcolor=T.BG_INPUT, activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["small"], command=self._toggle_watch
        )
        chk_watch.pack(side="left", padx=T.px(14))

        self.file_lbl = tk.Label(
            act_bar, text="No file loaded", font=self.fonts["mono_small"],
            fg=T.TEXT_MUTED, bg=T.BG_ALT, anchor="w"
        )
        self.file_lbl.pack(side="left", padx=T.px(10))

        # Main editor area
        paned = tk.PanedWindow(self, orient="vertical", bg=T.BORDER, sashwidth=4)
        paned.pack(fill="both", expand=True, padx=T.px(10), pady=T.px(10))

        # Code Editor
        self.editor = CodeViewer(paned, self.fonts)
        paned.add(self.editor, minsize=T.px(360))

        # Compiler output console
        log_frame = tk.Frame(paned, bg=T.BG_ALT)
        paned.add(log_frame, minsize=T.px(130))

        log_head = tk.Frame(log_frame, bg=T.BG_ALT)
        log_head.pack(fill="x", padx=T.px(8), pady=(T.px(6), T.px(2)))

        log_lbl = tk.Label(
            log_head, text="COMPILER OUTPUT & DIAGNOSTICS",
            font=self.fonts["mono_small"], fg=T.GOLD_MUTED, bg=T.BG_ALT, anchor="w"
        )
        log_lbl.pack(side="left")

        btn_clear_log = tk.Button(
            log_head, text="Clear", bg=T.BG_PANEL, fg=T.TEXT_MUTED,
            activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["small"], relief="flat", padx=T.px(8), pady=1,
            command=lambda: self.log_text.delete("1.0", "end"), cursor="hand2"
        )
        btn_clear_log.pack(side="right")

        log_container = tk.Frame(log_frame, bg=T.BG_INPUT, bd=1, relief="solid")
        log_container.pack(fill="both", expand=True, padx=T.px(8), pady=(0, T.px(8)))

        self.log_text = tk.Text(
            log_container, bg=T.BG_INPUT, fg=T.TEXT_MAIN, font=self.fonts["mono_small"],
            selectbackground=T.ACCENT_ACTIVE, selectforeground="#FFFFFF",
            relief="flat", bd=0, padx=T.px(8), pady=T.px(6), height=6
        )
        log_scroll = ttk.Scrollbar(log_container, orient="vertical", command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        self.log_text.tag_configure("error", foreground=T.ACCENT)
        self.log_text.tag_configure("success", foreground=T.GREEN)
        self.log_text.tag_configure("info", foreground=T.GOLD)

        self._start_watcher()

    def load_file(self, file_path: Path):
        self.current_file = Path(file_path)
        content = self.current_file.read_text(encoding="utf-8", errors="replace")
        self.editor.set_content(content)
        self.last_mtime = self.current_file.stat().st_mtime
        self.file_lbl.config(text=f"{self.current_file.name} ({self.current_file})")

    def _on_open_file(self):
        f = filedialog.askopenfilename(
            title="Open HLSL / GLSL Shader Source",
            initialdir=str(paths.SOURCE_DIR),
            filetypes=[("Shader Sources", "*.hlsl *.glsl"), ("All Files", "*.*")]
        )
        if f:
            self.load_file(Path(f))

    def _save_current(self):
        if not self.current_file:
            f = filedialog.asksaveasfilename(
                title="Save Shader Source",
                initialdir=str(paths.SOURCE_DIR),
                defaultextension=".hlsl",
                filetypes=[("HLSL File", "*.hlsl"), ("GLSL File", "*.glsl")]
            )
            if not f:
                return
            self.current_file = Path(f)

        content = self.editor.get_content()
        self.current_file.write_text(content, encoding="utf-8")
        self.last_mtime = self.current_file.stat().st_mtime
        self.app.set_status(f"Saved {self.current_file.name}")
        self._log(f"Saved {self.current_file.name} to disk\n", "info")

    def _compile_current(self):
        if not self.current_file:
            messagebox.showinfo("No File", "Open or save a shader file before compiling.")
            return

        # Save buffer to disk before compiling
        self._save_current()

        api = self.app.active_api
        self.app.set_busy(True, f"Compiling {self.current_file.name} for {api.upper()}...")
        self._log(f"Compiling {self.current_file.name} (API: {api.upper()})...\n", "info")

        def work():
            return compile.compile_shader_file(self.current_file, api=api)

        def done(res):
            self.app.set_busy(False, "")
            if res.ok:
                msg = f"Compilation Succeeded: {len(res.bytecode):,} bytes written to {res.output_path.name}\n"
                self._log(msg, "success")
                self.app.set_status(f"Compiled successfully -> {res.output_path.name}")
            else:
                msg = f"Compilation Failed:\n{res.error}\n"
                self._log(msg, "error")
                self.app.set_status(f"Compilation error in {self.current_file.name}")

        self.app.tasks.run(work, done=done, label=f"Compile {self.current_file.name}")

    def _log(self, text: str, tag: str = None):
        if tag:
            self.log_text.insert("end", text, tag)
        else:
            self.log_text.insert("end", text)
        self.log_text.see("end")

    def _toggle_watch(self):
        pass

    def _start_watcher(self):
        self.watch_active = True

        def loop():
            while self.watch_active:
                time.sleep(1.0)
                try:
                    if not self.winfo_exists():
                        break
                    if not self.watch_var.get() or not self.current_file or not self.current_file.exists():
                        continue

                    mtime = self.current_file.stat().st_mtime
                    if mtime > self.last_mtime:
                        self.last_mtime = mtime
                        # Reload content and compile
                        content = self.current_file.read_text(encoding="utf-8", errors="replace")
                        self.after(0, lambda c=content: self.editor.set_content(c))
                        self.after(0, self._compile_current)
                except Exception:
                    break

        t = threading.Thread(target=loop, daemon=True)
        t.start()
