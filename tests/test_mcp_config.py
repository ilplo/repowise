from __future__ import annotations

import sys
import tempfile
import unittest
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repowise.cli.mcp_config import generate_mcp_config


class McpConfigTests(unittest.TestCase):
    def test_generate_mcp_config_uses_explicit_python_and_target_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "target"
            repo_path.mkdir()

            config = generate_mcp_config(repo_path)
            server = config["mcpServers"]["repowise"]

            self.assertEqual(server["command"], sys.executable)
            self.assertEqual(server["args"][:3], ["-m", "repowise", "mcp"])
            self.assertEqual(server["args"][3], str(repo_path.resolve()).replace("\\", "/"))
            self.assertEqual(server["args"][4:], ["--transport", "stdio"])
            self.assertIn("PYTHONPATH", server["env"])
            self.assertTrue(server["env"]["PYTHONPATH"].split(os.pathsep)[0].endswith("/src"))


if __name__ == "__main__":
    unittest.main()
