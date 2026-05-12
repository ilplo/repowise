from __future__ import annotations

import sys
import tempfile
import unittest
import os
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repowise.cli.mcp_config import (
    generate_codex_mcp_config_toml,
    generate_mcp_config,
    save_codex_mcp_config,
)


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

    def test_generate_codex_mcp_config_toml_uses_project_scoped_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "target"
            repo_path.mkdir()

            parsed = tomllib.loads(generate_codex_mcp_config_toml(repo_path))
            server = parsed["mcp_servers"]["repowise"]

            self.assertEqual(server["command"], sys.executable)
            self.assertEqual(server["args"][:3], ["-m", "repowise", "mcp"])
            self.assertEqual(server["args"][3], str(repo_path.resolve()).replace("\\", "/"))
            self.assertEqual(server["args"][4:], ["--transport", "stdio"])
            self.assertEqual(server["startup_timeout_sec"], 30)
            self.assertIn("PYTHONPATH", server["env"])

    def test_save_codex_mcp_config_merges_repowise_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "target"
            config_path = repo_path / ".codex" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                'model = "gpt-5.5"\n\n'
                "[mcp_servers.other]\n"
                'url = "https://example.test/mcp"\n\n'
                "[mcp_servers.repowise]\n"
                'command = "old"\n\n'
                "[mcp_servers.repowise.env]\n"
                'PYTHONPATH = "old"\n',
                encoding="utf-8",
            )

            written = save_codex_mcp_config(repo_path)
            parsed = tomllib.loads(written.read_text(encoding="utf-8"))

            self.assertEqual(written, config_path)
            self.assertEqual(parsed["model"], "gpt-5.5")
            self.assertEqual(parsed["mcp_servers"]["other"]["url"], "https://example.test/mcp")
            self.assertEqual(parsed["mcp_servers"]["repowise"]["command"], sys.executable)
            self.assertNotEqual(parsed["mcp_servers"]["repowise"]["env"]["PYTHONPATH"], "old")


if __name__ == "__main__":
    unittest.main()
