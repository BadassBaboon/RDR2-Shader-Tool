"""Lenny's Mod Loader (LML) UI page: VFS deployment, install.xml generation, and mod status."""

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

        # Target Specification Card
        card = tk.Frame(self, bg=T.BG_ALT, bd=1, relief="solid")
        card.pack(fill="x", padx=T.px(20), pady=(T.px(16), T.px(10)))

        tk.Label(
            card, text="VFS REPLACEMENT TARGETS (Lenny's Mod Loader)",
            font=self.fonts["header_small"], fg=T.GOLD, bg=T.BG_ALT, anchor="w", padx=T.px(16)
        ).pack(fill="x", pady=(T.px(12), T.px(4)))

        specs = (
            "Vulkan shader archive target:   shaders_x64:/0xFEEB1B85.bin (sga_vulkan_final.fxdb)\n"
            "DirectX 12 archive target:      shaders_x64:/0x8068F4F9.bin (sga_win32_60_final.fxdb)\n"
            "Method: Direct VFS replacement via install.xml. No .rpf archive modification required."
        )
        tk.Label(
            card, text=specs, font=self.fonts["mono_small"], fg=T.TEXT_MUTED, bg=T.BG_ALT, justify="left", anchor="w", padx=T.px(16)
        ).pack(fill="x", pady=(0, T.px(12)))

        # Config row: Mod Folder Name
        row = tk.Frame(self, bg=T.BG)
        row.pack(fill="x", padx=T.px(20), pady=T.px(6))

        tk.Label(row, text="Mod Folder Name:", font=self.fonts["body"], fg=T.TEXT_MAIN, bg=T.BG).pack(side="left", padx=(0, T.px(8)))

        self.mod_name_var = tk.StringVar(value=cfg.get("Paths", "lml_mod_name", "RealityV_Shaders"))
        self.mod_name_entry = tk.Entry(
            row, textvariable=self.mod_name_var, font=self.fonts["body"],
            bg=T.BG_INPUT, fg=T.TEXT_MAIN, insertbackground=T.TEXT_MAIN,
            selectbackground=T.ACCENT_ACTIVE, selectforeground="#FFFFFF",
            relief="solid", bd=1, width=28
        )
        self.mod_name_entry.pack(side="left", padx=T.px(8), ipady=T.px(3))

        # Game directory row
        g_row = tk.Frame(self, bg=T.BG)
        g_row.pack(fill="x", padx=T.px(20), pady=T.px(6))

        tk.Label(g_row, text="Game Directory:", font=self.fonts["body"], fg=T.TEXT_MAIN, bg=T.BG).pack(side="left", padx=(0, T.px(8)))
        self.game_lbl = tk.Label(g_row, text=str(cfg.game_dir), font=self.fonts["mono_small"], fg=T.GOLD, bg=T.BG)
        self.game_lbl.pack(side="left", padx=T.px(8))

        btn_ch_game = tk.Button(
            g_row, text="Browse...", bg=T.BG_PANEL, fg=T.TEXT_MAIN,
            activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["small"], relief="flat", padx=T.px(8), pady=T.px(2),
            command=self._change_game_dir, cursor="hand2"
        )
        btn_ch_game.pack(side="left", padx=T.px(8))

        # Deploy Button
        btn_box = tk.Frame(self, bg=T.BG)
        btn_box.pack(fill="x", padx=T.px(20), pady=T.px(14))

        self.btn_deploy = tk.Button(
            btn_box, text="Deploy Mod to Lenny's Mod Loader",
            bg=T.ACCENT, fg="#FFFFFF", activebackground=T.ACCENT_HOVER, activeforeground="#FFFFFF",
            font=self.fonts["header"], relief="flat", padx=T.px(22), pady=T.px(9),
            command=self._deploy_mod, cursor="hand2"
        )
        self.btn_deploy.pack(side="left")

        # Installed Mods List
        mod_head = tk.Frame(self, bg=T.BG)
        mod_head.pack(fill="x", padx=T.px(20), pady=(T.px(10), T.px(4)))

        lbl_installed = tk.Label(
            mod_head, text="INSTALLED LML MODS",
            font=self.fonts["mono_small"], fg=T.GOLD_MUTED, bg=T.BG, anchor="w"
        )
        lbl_installed.pack(side="left")

        btn_refresh = tk.Button(
            mod_head, text="Refresh", bg=T.BG_PANEL, fg=T.TEXT_MUTED,
            activebackground=T.BG_ALT, activeforeground=T.TEXT_MAIN,
            font=self.fonts["small"], relief="flat", padx=T.px(8), pady=1,
            command=self.refresh_mods, cursor="hand2"
        )
        btn_refresh.pack(side="right")

        list_frame = tk.Frame(self, bg=T.BG_INPUT, bd=1, relief="solid")
        list_frame.pack(fill="both", expand=True, padx=T.px(20), pady=(0, T.px(20)))

        cols = ("name", "status", "path")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings")
        self.tree.heading("name", text="Mod Name")
        self.tree.heading("status", text="Has Shaders")
        self.tree.heading("path", text="Folder Path")

        self.tree.column("name", width=T.px(220), anchor="w")
        self.tree.column("status", width=T.px(110), anchor="center")
        self.tree.column("path", width=T.px(440), anchor="w")

        self.tree.tag_configure("odd", background=T.BG_INPUT)
        self.tree.tag_configure("even", background=T.BG_ALT)

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.refresh_mods()

    def refresh_mods(self):
        self.tree.delete(*self.tree.get_children())
        cfg = settings.settings()
        lml_dir = cfg.game_dir / "lml"

        if not lml_dir.exists():
            return

        mods = lml.list_installed_mods(lml_dir)
        for idx, m in enumerate(mods):
            has_sh = "Yes" if m["has_shaders"] else "No"
            row_tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", "end", values=(m["name"], has_sh, m["path"]), tags=(row_tag,))

    def _change_game_dir(self):
        d = filedialog.askdirectory(title="Select Red Dead Redemption 2 Game Directory", initialdir=str(settings.settings().game_dir))
        if d:
            settings.settings().set("Paths", "game_dir", str(Path(d)))
            self.game_lbl.config(text=d)
            self.refresh_mods()

    def _deploy_mod(self):
        mod_name = self.mod_name_var.get().strip()
        if not mod_name:
            messagebox.showerror("Error", "Enter a mod folder name.")
            return

        settings.settings().set("Paths", "lml_mod_name", mod_name)
        cfg = settings.settings()

        # Check compiled/
        compiled_dir = paths.COMPILED_DIR
        candidates = list(compiled_dir.glob("*.fxdb"))
        if not candidates:
            messagebox.showwarning(
                "No Repacked Shaders Found",
                "No repacked .fxdb files found in compiled/.\n"
                "Please compile your modified shaders and repack an .fxdb library first."
            )
            return

        target_fxdb = candidates[0]
        self.app.set_busy(True, f"Deploying {mod_name} to LML...")

        def work():
            res = lml.deploy_to_lml([target_fxdb], mod_name=mod_name, lml_dir=cfg.lml_dir)
            return res

        def done(res):
            self.app.set_busy(False, "")
            if res.get("ok"):
                messagebox.showinfo(
                    "Deploy Succeeded",
                    f"Mod successfully deployed to:\n{res['mod_dir']}\n\n"
                    f"Files copied: {len(res['deployed_files'])}\n"
                    f"install.xml: {Path(res['install_xml']).name}"
                )
                self.app.set_status(f"Deployed {mod_name} to LML")
                self.refresh_mods()
            else:
                messagebox.showerror("Deploy Failed", f"Failed to deploy mod:\n{res.get('error', 'Unknown error')}")

        self.app.tasks.run(work, done=done, label=f"Deploy {mod_name}")
