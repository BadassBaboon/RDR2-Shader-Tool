"""Unit tests for the Model Context Protocol (MCP) server."""

import json
import os
import sys
import unittest
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from r2mcp.server import Server


class TestMCPServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = Server()

    def test_initialize(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        resp = self.server.handle(req)
        self.assertIsNotNone(resp)
        self.assertEqual(resp["id"], 1)
        res = resp["result"]
        self.assertEqual(res["serverInfo"]["name"], "rdr2-shader-tool")
        self.assertIn("tools", res["capabilities"])

    def test_tools_list(self):
        req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        resp = self.server.handle(req)
        self.assertIsNotNone(resp)
        tools = resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        expected_tools = [
            "r2sm_status",
            "r2sm_find",
            "r2sm_info",
            "r2sm_effects",
            "r2sm_decompile",
            "r2sm_compile",
            "r2sm_unpack",
            "r2sm_repack",
            "r2sm_inject",
            "r2sm_lml_deploy",
            "r2sm_lml_status",
        ]
        for exp in expected_tools:
            self.assertIn(exp, tool_names)

    def test_mcp_find_and_info(self):
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "r2sm_find",
                "arguments": {"query": "0x2FFB1EF2"}
            }
        }
        resp = self.server.handle(req)
        self.assertFalse(resp["result"].get("isError", False))
        results = json.loads(resp["result"]["content"][0]["text"])
        self.assertGreater(len(results), 0)
        first = results[0]
        self.assertEqual(first["name"], "VS_Clear_Wrapped")

        # Test info
        info_req = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "r2sm_info",
                "arguments": {"target": "0x2FFB1EF2"}
            }
        }
        info_resp = self.server.handle(info_req)
        self.assertFalse(info_resp["result"].get("isError", False))
        info = json.loads(info_resp["result"]["content"][0]["text"])
        self.assertEqual(info["name"], "VS_Clear_Wrapped")
        self.assertIn("fxdb_path", info)
        self.assertTrue(os.path.exists(info["fxdb_path"]))


if __name__ == "__main__":
    unittest.main()
