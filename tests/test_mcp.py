from __future__ import annotations

import json
import unittest

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
        self.assertIn("analyze_campaign", names)

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


if __name__ == "__main__":
    unittest.main()
