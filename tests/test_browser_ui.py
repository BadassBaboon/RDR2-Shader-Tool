"""Unit tests for BrowserPage sorting, treeview population, and row selection."""

import unittest
from pathlib import Path
import sys
import tkinter as tk

src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from r2ui.pages.browser import BrowserPage
from r2core import catalog


class MockApp:
    def __init__(self):
        self.active_api = "vulkan"
        self.status_msg = ""

    def set_status(self, msg: str):
        self.status_msg = msg


class TestBrowserUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()
        cls.mock_fonts = {
            "title": ("Arial", 16),
            "header": ("Arial", 13),
            "header_small": ("Arial", 10),
            "body": ("Arial", 9),
            "body_bold": ("Arial", 9, "bold"),
            "small": ("Arial", 8),
            "mono": ("Consolas", 9),
            "mono_bold": ("Consolas", 9, "bold"),
            "mono_small": ("Consolas", 8),
        }
        cls.mock_app = MockApp()
        cls.page = BrowserPage(cls.root, cls.mock_app, cls.mock_fonts)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def test_page_population(self):
        self.page.refresh()
        displayed = self.page._displayed_entries
        self.assertGreater(len(displayed), 13000, "Should display all 13,000+ Vulkan shaders")
        self.assertIn("Loaded", self.mock_app.status_msg)

    def test_sorting_columns(self):
        # Sort by size (first click on size sets descending=True)
        self.page._sort_by_column("size")
        entries = self.page._displayed_entries
        self.assertGreaterEqual(entries[0].byte_size, entries[-1].byte_size)

        # Toggle to size ascending
        self.page._sort_by_column("size")
        entries = self.page._displayed_entries
        self.assertLessEqual(entries[0].byte_size, entries[-1].byte_size)

        # Sort by name
        self.page._sort_by_column("name")
        entries = self.page._displayed_entries
        self.assertLessEqual(entries[0].name.lower(), entries[-1].name.lower())

        # Sort by renodx_hash
        self.page._sort_by_column("renodx_hash")
        entries = self.page._displayed_entries
        self.assertLessEqual(entries[0].renodx_hash.lower(), entries[-1].renodx_hash.lower())

    def test_row_selection_inspection(self):
        self.page.refresh()
        # Select row 0
        self.page.tree.selection_set("0")
        self.page._on_select(None)

        self.assertIsNotNone(self.page.selected_entry)
        detail_content = self.page.detail_text.get("1.0", "end")
        self.assertIn("RENODX SHADER INTEROP", detail_content)
        self.assertIn("SHADER METADATA", detail_content)
        self.assertIn("Library:", detail_content)

    def test_extraction_guide_modal(self):
        from tkinter import ttk
        self.page._open_guide()
        guides = [w for w in self.page.winfo_children() if isinstance(w, tk.Toplevel)]
        self.assertGreaterEqual(len(guides), 1)
        guide_win = guides[-1]

        treeviews = []
        def find_tv(w):
            for c in w.winfo_children():
                if isinstance(c, ttk.Treeview):
                    treeviews.append(c)
                find_tv(c)
        find_tv(guide_win)

        self.assertEqual(len(treeviews), 1)
        tv = treeviews[0]
        rows = [tv.item(item)["values"] for item in tv.get_children()]
        self.assertEqual(len(rows), 4, "Extraction guide should list all 4 shader packages")

        hashes = [r[1] for r in rows]
        self.assertIn("0xFEEB1B85.bin", hashes)
        self.assertIn("0x8068F4F9.bin", hashes)
        self.assertIn("0xA8C90D00.bin", hashes)
        self.assertIn("0x2A25B571.bin", hashes)

        targets = [r[2] for r in rows]
        self.assertIn("sga_vulkan_final.fxdb", targets)
        self.assertIn("sga_win32_60_final.fxdb", targets)

        guide_win.destroy()

    def test_replaced_filter_and_tag(self):
        # Set filter to REPLACED
        self.page.stage_var.set("REPLACED")
        self.page.refresh()
        displayed = self.page._displayed_entries
        self.assertGreaterEqual(len(displayed), 1, "Should show at least 1 modified shader")
        names = [e.name for e in displayed]
        self.assertIn("VS_Clear_Wrapped", names)

        # Verify row tag in treeview is "modified"
        first_item = self.page.tree.get_children()[0]
        tags = self.page.tree.item(first_item, "tags")
        self.assertIn("modified", tags)
        values = self.page.tree.item(first_item, "values")
        self.assertIn("[MOD]", values[0])

        # Reset filter
        self.page.stage_var.set("ALL")
        self.page.refresh()

    def test_app_footer_status_bar_alignment(self):
        from r2ui.app import App
        app = App()
        app.root.withdraw()
        try:
            # Check packing info of info_lbl
            pinfo = app.info_lbl.pack_info()
            self.assertEqual(pinfo["side"], "right", "info_lbl should be snapped to side='right'")
            self.assertIn("16", str(pinfo["padx"]), "info_lbl should have right margin padding")
        finally:
            app.root.destroy()


if __name__ == "__main__":
    unittest.main()
