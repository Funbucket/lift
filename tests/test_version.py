from __future__ import annotations

import json
import unittest

from typer.testing import CliRunner

from lift import __version__
from lift.interfaces.cli import app


class VersionTest(unittest.TestCase):
    def test_version_command(self) -> None:
        result = CliRunner().invoke(app, ["version"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["version"], __version__)


if __name__ == "__main__":
    unittest.main()
