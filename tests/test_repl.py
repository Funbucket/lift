from __future__ import annotations

import json
import unittest

from lift.interfaces.repl import handle_repl_command


class ReplTest(unittest.TestCase):
    def test_help(self) -> None:
        output = handle_repl_command("/help")
        self.assertIsNotNone(output)
        self.assertIn("/analyze", output)

    def test_doctor_returns_json(self) -> None:
        output = handle_repl_command("/doctor")
        self.assertIsNotNone(output)
        payload = json.loads(output)
        self.assertIn(payload["status"], {"ok", "warning"})

    def test_inspect_fixture(self) -> None:
        output = handle_repl_command("/inspect fixtures/randomized_coupon.csv")
        self.assertIsNotNone(output)
        payload = json.loads(output)
        self.assertEqual(payload["rows"], 12)


if __name__ == "__main__":
    unittest.main()
