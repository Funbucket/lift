from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lift.interfaces.mcp import handle_json_rpc


class McpTest(unittest.TestCase):
    def test_initialize(self) -> None:
        response = handle_json_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertIsNotNone(response)
        self.assertEqual(response["result"]["serverInfo"]["name"], "lift")

    def test_tools_list(self) -> None:
        response = handle_json_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertIsNotNone(response)
        names = {tool["name"] for tool in response["result"]["tools"]}
        self.assertIn("inspect_dataset", names)
        self.assertIn("validate_dataset", names)
        self.assertIn("validate_causal_assumptions", names)
        self.assertIn("analyze_campaign", names)
        self.assertIn("export_targets", names)

    def test_inspect_dataset_tool(self) -> None:
        response = handle_json_rpc(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "inspect_dataset",
                    "arguments": {"dataset": "fixtures/randomized_coupon.csv"},
                },
            }
        )
        self.assertIsNotNone(response)
        text = response["result"]["content"][0]["text"]
        payload = json.loads(text)
        self.assertEqual(payload["rows"], 12)

    def test_validate_causal_assumptions_tool(self) -> None:
        response = handle_json_rpc(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "validate_causal_assumptions",
                    "arguments": {"dataset": "fixtures/observational_coupon.csv"},
                },
            }
        )
        self.assertIsNotNone(response)
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertIn(payload["trust"]["trust_level"], {"medium", "low"})

    def test_analyze_and_export_targets_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = str(Path(temp_dir) / "outputs")
            analyze_response = handle_json_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {
                        "name": "analyze_campaign",
                        "arguments": {
                            "dataset": "fixtures/randomized_coupon.csv",
                            "config": {
                                "output_root": output_root,
                                "seed": 7,
                                "budget": 5,
                                "min_roi": 0.1,
                            },
                        },
                    },
                }
            )
            self.assertIsNotNone(analyze_response)
            analyzed = json.loads(analyze_response["result"]["content"][0]["text"])
            export_response = handle_json_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "tools/call",
                    "params": {
                        "name": "export_targets",
                        "arguments": {
                            "run_id": analyzed["run_id"],
                            "output_root": output_root,
                            "budget": 3,
                            "min_roi": 0.1,
                        },
                    },
                }
            )
            self.assertIsNotNone(export_response)
            exported = json.loads(export_response["result"]["content"][0]["text"])
            self.assertTrue(Path(exported["targets_path"]).exists())


if __name__ == "__main__":
    unittest.main()
