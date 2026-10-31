"""Audit unit tests for decompile, recompile, FXDB repacking, modified shader filtering, and UI alignment."""

import sys
import tempfile
import unittest
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from r2core import catalog, compile, decompile, fxdb_parser, hashing, paths, replacements


class TestAuditEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = catalog.get_default_catalog()

    def test_decompile_vulkan(self):
        entries = self.cat.find(query="VS_Clear_Wrapped", api="vulkan")
        self.assertGreater(len(entries), 0)
        e = entries[0]

        fxdb = fxdb_parser.get_cached_fxdb(e.fxdb_path, decompress_bytecode=False)
        rec = fxdb.shaders[e.stage][e.index]
        rec.get_decompressed_bytecode()

        res = decompile.decompile_shader(rec, api="vulkan", target_lang="hlsl")
        self.assertTrue(res.ok, f"Vulkan decompile failed: {res.error}")
        self.assertEqual(res.method, "spirv-cross")
        self.assertIn("main", res.source_code)
        self.assertTrue(len(res.source_code) > 0)

    def test_decompile_dx12(self):
        entries = self.cat.find(query="VS_Clear_Wrapped", api="dx12")
        self.assertGreater(len(entries), 0)
        e = entries[0]

        fxdb = fxdb_parser.get_cached_fxdb(e.fxdb_path, decompress_bytecode=False)
        rec = fxdb.shaders[e.stage][e.index]
        rec.get_decompressed_bytecode()

        res = decompile.decompile_shader(rec, api="dx12", target_lang="hlsl")
        self.assertTrue(res.ok, f"DX12 decompile failed: {res.error}")
        self.assertIn(res.method, ("dxbc2dxil+spirv-cross", "3dmigoto", "decomp.exe"))
        self.assertTrue(len(res.source_code) > 0)
        self.assertTrue(len(res.disassembly) > 0)

    def test_compile_vulkan(self):
        hlsl_code = """
        struct VS_INPUT { float3 pos : POSITION; };
        struct PS_INPUT { float4 pos : SV_Position; };
        PS_INPUT main(VS_INPUT input) {
            PS_INPUT output;
            output.pos = float4(input.pos, 1.0f);
            return output;
        }
        """
        res = compile.compile_to_vulkan(hlsl_code, stage="vs", entry_point="main")
        self.assertTrue(res.ok, f"Vulkan compile failed: {res.error}")
        self.assertEqual(res.target_api, "vulkan")
        self.assertGreater(len(res.bytecode), 0)
        # Check SPIR-V magic
        self.assertEqual(res.bytecode[:4], b"\x03\x02\x23\x07")

    def test_compile_dx12(self):
        hlsl_code = """
        struct VS_INPUT { float3 pos : POSITION; };
        struct PS_INPUT { float4 pos : SV_Position; };
        PS_INPUT main(VS_INPUT input) {
            PS_INPUT output;
            output.pos = float4(input.pos, 1.0f);
            return output;
        }
        """
        res = compile.compile_to_dx12(hlsl_code, stage="vs", entry_point="main")
        self.assertTrue(res.ok, f"DX12 compile failed: {res.error}")
        self.assertEqual(res.target_api, "dx12")
        self.assertGreater(len(res.bytecode), 0)
        # Check DXBC/DXIL container magic
        self.assertEqual(res.bytecode[:4], b"DXBC")

    def test_repack_fxdb(self):
        entries = self.cat.find(query="VS_Clear_Wrapped", api="vulkan")
        self.assertGreater(len(entries), 0)
        e = entries[0]
        src_fxdb = Path(e.fxdb_path)

        with tempfile.TemporaryDirectory() as td:
            dst_fxdb = Path(td) / src_fxdb.name
            dummy_bytecode = b"\x03\x02\x23\x07" + b"\x00" * 256
            replacements = {(e.stage, e.index): dummy_bytecode}

            count = fxdb_parser.repack_fxdb(src_fxdb, dst_fxdb, replacements)
            self.assertEqual(count, 1)
            self.assertTrue(dst_fxdb.exists())

            # Verify repacked file parses and contains the replacement CRC
            reparsed = fxdb_parser.parse_file(dst_fxdb, decompress_bytecode=False)
            repacked_rec = reparsed.shaders[e.stage][e.index]
            self.assertEqual(repacked_rec.crc, hashing.crc32(dummy_bytecode))

    def test_modified_shader_detection_and_filtering(self):
        mods = replacements.scan_modified_shaders("vulkan", cat=self.cat)
        # We know VS_Clear_Wrapped is compiled in compiled/vulkan and belongs to sga_vulkan_final_init.fxdb
        self.assertIn(("sga_vulkan_final_init.fxdb", "VS", 0), mods)
        self.assertNotIn(("sga_vulkan_final.fxdb", "VS", 0), mods)

        mod_info = mods[("sga_vulkan_final_init.fxdb", "VS", 0)]
        self.assertEqual(mod_info["name"], "VS_Clear_Wrapped")
        self.assertNotEqual(mod_info["old_crc"], mod_info["new_crc"])

        clear_entries = self.cat.find(query="VS_Clear_Wrapped", api="vulkan")
        passthrough_entries = self.cat.find(query="VS_PassthroughComposite_Wrapped", api="vulkan")
        self.assertTrue(replacements.is_entry_modified(clear_entries[0], mods))
        self.assertFalse(replacements.is_entry_modified(passthrough_entries[0], mods))
