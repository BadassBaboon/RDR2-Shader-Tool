"""Lenny's Mod Loader (LML) UI page: 1-click deployment, install.xml generation, and mod status."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from r2core import lml, paths, settings
from .. import theme as T


class LmlPage(tk.Frame):
    def __init__(self, parent, app, fonts: dict):
        super().__init__(parent, bg=T.BG)
        self.app = app
        self.fonts = fonts

        self._build_ui()

    def _build_ui(self):
        cfg = settings.settings()

        # Top Info Card
        card = tk.Frame(self, bg=T.BG_ALT, bd=1, relief="solid")
        card.pack(fill="x", padx=T.px(20), pady=(T.px(16), T.px(10)))

        tk.Label(
            card, text="Lenny's Mod Loader (LML) Integration",
            font=self.fonts["header"], fg=T.TEXT_MAIN, bg=T.BG_ALT, anchor="w", padx=T.px(16)
        ).pack(fill="x", pady=(T.px(12), T.px(4)))

        desc = (
            "Load custom shaders into Red Dead Redemption 2 without modifying .rpf archives.\n"
            "The tool packages your modified .fxdb files into LML's virtual filesystem and writes an install.xml."
        )
        tk.Label(
            card, text=desc, font=self.fonts["small"], fg=T.TEXT_MUTED, bg=T.BG_ALT, justify="left", anchor="w", padx=T.px(16)
        ).pack(fill="x", pady=(0, T.px(12)))

        # Config row
        row = tk.Frame(self, bg=T.BG)
        row.pack(fill="x", padx=T.px(20), pady=T.px(6))

        tk.Label(row, text="LML Mod Folder Name:", font=self.fonts["body"], fg=T.TEXT_MAIN, bg=T.BG).pack(side="left", padx=(0, T.px(8)))

        self.mod_name_var = tk.StringVar(value=cfg.get("Paths", "lml_mod_name", "RealityV_Shaders"))
        self.mod_name_entry = tk.Entry(
            row, textvariable=self.mod_name_var, font=self.fonts["body"],
            bg=T.BG_PANEL, fg=T.TEXT_MAIN, insertbackground=T.TEXT_MAIN, relief="flat", width=25
        )
        self.mod_name_entry.pack(side="left", padx=T.px(8))

        # Game directory row
        g_row = tk.Frame(self, bg=T.BG)
        g_row.pack(fill="x", padx=T.px(20), pady=T.px(6))

        tk.Label(g_row, text="Game Directory:", font=self.fonts["body"], fg=T.TEXT_MAIN, bg=T.BG).pack(side="left", padx=(0, T.px(8)))
        self.game_lbl = tk.Label(g_row, text=str(cfg.game_dir), font=self.fonts["small"], fg=T.CYAN, bg=T.BG)
        self.game_lbl.pack(side="left", padx=T.px(8))

        btn_ch_game = tk.Button(g_row, text="Change...", bg=T.BG_PANEL, fg=T.TEXT_MAIN, relief="flat", padx=T.px(8), command=self._change_game_dir)
        btn_ch_game.pack(side="left", padx=T.px(8))

        # Deploy Button (Prominent)
        btn_box = tk.Frame(self, bg=T.BG)
        btn_box.pack(fill="x", padx=T.px(20), pady=T.px(16))

        self.btn_deploy = tk.Button(
            btn_box, text="🚀 Deploy to Game via Lenny's Mod Loader (1-Click)",
            bg=T.GREEN, fg="#000000", activebackground="#28A745", activeforeground="#FFFFFF",
            font=self.fonts["header"], relief="flat", padx=T.px(20), pady=T.px(10),
            command=self._deploy_mod
        )
        self.btn_deploy.pack(side="left")

        # Installed Mods List
        lbl_installed = tk.Label(
            self, text="Currently Installed LML Mods:",
            font=self.fonts["header"], fg=T.TEXT_MAIN, bg=T.BG, anchor="w", padx=T.px(20)
        )
        lbl_installed.pack(fill="x", pady=(T.px(10), T.px(4)))

        list_frame = tk.Frame(self, bg=T.BG)
        list_frame.pack(fill="both", expand=True, padx=T.px(20), pady=(0, T.px(20)))

        cols = ("name", "status", "path")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings")
        self.tree.heading("name", text="Mod Name")
        self.tree.heading("status", text="Has Shaders")
        self.tree.heading("path", text="Folder Path")

        self.tree.column("name", width=T.px(200), anchor="w")
        self.tree.column("status", width=T.px(100), anchor="center")
        self.tree.column("path", width=T.px(400), anchor="w")

        self.tree.pack(fill="both", expand=True)

        self.refresh_mods()

    def refresh_mods(self):
        self.tree.delete(*self.tree.get_children())
        cfg = settings.settings()
        lml_dir = cfg.lml_dir

        if not lml_dir.exists():
            return

        for d in lml_dir.iterdir():
            if d.is_dir() and (d / "install.xml").exists():
                has_sh = (d / "shaders_x64").exists()
                self.tree.insert("", "end", values=(d.name, "YES" if has_sh else "NO", str(d)))

    def _change_game_dir(self):
        d = filedialog.askdirectory(title="Select Red Dead Redemption 2 Installation Folder", initialdir=str(settings.settings().game_dir))
        if d:
            p = Path(d)
            if not (p / "RDR2.exe").exists():
                if not messagebox.askyesno("Warning", "RDR2.exe was not found in this folder. Are you sure?"):
                    return
            settings.settings().set("General", "game_dir", str(p))
            self.game_lbl.config(text=str(p))
            self.refresh_mods()

    def _deploy_mod(self):
        cfg = settings.settings()
        mod_name = self.mod_name_var.get().strip()
        if not mod_name:
            messagebox.showerror("Error", "Please specify a mod name.")
            return

        # Find any _modified.fxdb files in dump folder or fxdb_files
        dump_dir = Path(cfg.get("Paths", "rdr2_shaders_dump", str(paths.DEFAULT_DUMP_DIR)))
        fxdb_dir = dump_dir / "fxdb"

        modified_files = []
        if fxdb_dir.exists():
            for f in fxdb_dir.glob("*_modified.fxdb"):
                modified_files.append(f)
        if paths.FXDB_FILES_DIR.exists():
            for f in paths.FXDB_FILES_DIR.glob("*_modified.fxdb"):
                if f not in modified_files:
                    modified_files.append(f)

        if not modified_files:
            # Check if any repacked files exist
            if messagebox.askyesno("No Modified Files", "No *_modified.fxdb files found. Would you like to select a file manually?"):
                selected = filedialog.askopenfilenames(
                    title="Select Modified .fxdb Libraries to Deploy",
                    filetypes=[("FXDB Files", "*.fxdb *.bin"), ("All Files", "*.*")]
                )
                if selected:
                    modified_files = [Path(x) for x in selected]
                else:
                    return
            else:
                return

        self.app.set_busy(True, f"Deploying to LML: {mod_name}...")

        def work():
            return lml.deploy_to_lml(modified_files, mod_name=mod_name)

        def done(res):
            self.app.set_busy(False, "")
            messagebox.showinfo("LML Deployment Succeeded", f"Mod successfully installed to:\n{res['mod_dir']}\n\nFiles installed: {len(res['deployed_files'])}\ninstall.xml generated!")
            self.app.set_status(f"Deployed {mod_name} to Lenny's Mod Loader")
            self.refresh_mods()

        self.app.tasks.run(work, done=done, label=f"Deploy {mod_name}")
