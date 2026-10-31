"""Unit tests for RDR2 Shader Tool catalog, library filtering, and sorting."""

import unittest
from pathlib import Path
import sys

# Ensure src is on sys.path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from r2core import catalog, hashing


class TestCatalogAndSorting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = catalog.get_default_catalog(force_rebuild=False)

    def test_catalog_counts(self):
        vulkan_count = len(self.cat.by_api.get("vulkan", []))
        dx12_count = len(self.cat.by_api.get("dx12", []))

        # Full RDR2 database indexing check
        self.assertGreaterEqual(vulkan_count, 13000, f"Expected at least 13,000 Vulkan shaders, got {vulkan_count}")
        self.assertGreaterEqual(dx12_count, 12000, f"Expected at least 12,000 DX12 shaders, got {dx12_count}")

    def test_catalog_libraries(self):
        vk_libs = self.cat.get_libraries("vulkan")
        self.assertIn("sga_vulkan_final.fxdb", vk_libs)
        self.assertIn("sga_vulkan_final_init.fxdb", vk_libs)

        dx_libs = self.cat.get_libraries("dx12")
        self.assertIn("sga_win32_60_final.fxdb", dx_libs)
        self.assertIn("sga_win32_60_final_init.fxdb", dx_libs)

    def test_library_filtering(self):
        init_shaders = self.cat.find(api="vulkan", library="sga_vulkan_final_init.fxdb")
        self.assertEqual(len(init_shaders), 369)

        main_shaders = self.cat.find(api="vulkan", library="sga_vulkan_final.fxdb")
        self.assertEqual(len(main_shaders), 12883)

        total_vulkan = self.cat.find(api="vulkan")
        self.assertEqual(len(total_vulkan), 13252)

    def test_sorting_by_size(self):
        shaders = self.cat.find(api="vulkan", library="sga_vulkan_final_init.fxdb")

        # Ascending sort
        sorted_asc = sorted(shaders, key=lambda e: e.byte_size, reverse=False)
        self.assertLessEqual(sorted_asc[0].byte_size, sorted_asc[-1].byte_size)

        # Descending sort
        sorted_desc = sorted(shaders, key=lambda e: e.byte_size, reverse=True)
        self.assertGreaterEqual(sorted_desc[0].byte_size, sorted_desc[-1].byte_size)

    def test_sorting_by_index_and_stage(self):
        shaders = self.cat.find(api="vulkan", stage="VS", library="sga_vulkan_final_init.fxdb")

        sorted_asc = sorted(shaders, key=lambda e: (e.index, e.stage), reverse=False)
        indices = [s.index for s in sorted_asc]
        self.assertEqual(indices, sorted(indices))

    def test_renodx_hash_lookup(self):
        matches = self.cat.find(query="0x2FFB1EF2", api="vulkan")
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0].renodx_hash.lower(), "0x2ffb1ef2")


if __name__ == "__main__":
    unittest.main()
