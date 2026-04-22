from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repowise.cli.main import cli
from repowise.cli.runtime import determine_local_runtime_python
from repowise.cli.ui import interactive_provider_select


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_init_requires_explicit_target_repo_path(self) -> None:
        result = self.runner.invoke(cli, ["init"])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing argument 'PATH'", result.output)

    def test_mcp_requires_explicit_target_repo_path(self) -> None:
        result = self.runner.invoke(cli, ["mcp"])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing argument 'PATH'", result.output)

    def test_start_supports_running_without_target_repo_path(self) -> None:
        fake_uvicorn = types.SimpleNamespace(run=lambda *args, **kwargs: None)
        with patch("repowise.cli.commands.start_cmd._setup_embedder"):
            with patch.dict(sys.modules, {"uvicorn": fake_uvicorn}):
                result = self.runner.invoke(cli, ["start", "--no-ui"])

        self.assertEqual(result.exit_code, 0)

    def test_init_interactive_provider_select_defaults_to_xai(self) -> None:
        with patch.dict("os.environ", {"XAI_API_KEY": "test-key"}, clear=True):
            with patch("repowise.cli.ui.Prompt.ask", return_value="1"):
                with patch("repowise.cli.ui.click.prompt", return_value="grok-4-1-fast-reasoning"):
                    provider, model = interactive_provider_select(
                        Console(record=True),
                        None,
                    )

        self.assertEqual(provider, "xai")
        self.assertEqual(model, "grok-4-1-fast-reasoning")

    def test_runtime_prefers_project_venv_python_when_running_from_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "pyproject.toml").write_text("[project]\nname='repowise'\n", encoding="utf-8")
            (root / "src" / "repowise" / "cli").mkdir(parents=True)
            (root / "src" / "repowise" / "cli" / "main.py").write_text("", encoding="utf-8")
            (root / ".venv" / "bin").mkdir(parents=True)
            venv_python = root / ".venv" / "bin" / "python"
            venv_python.write_text("", encoding="utf-8")

            resolved = determine_local_runtime_python(
                start_dir=root / "src",
                executable="/usr/bin/python3",
            )

        self.assertEqual(resolved, venv_python.resolve())

    def test_runtime_skips_reexec_when_already_using_project_venv_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "pyproject.toml").write_text("[project]\nname='repowise'\n", encoding="utf-8")
            (root / "src" / "repowise" / "cli").mkdir(parents=True)
            (root / "src" / "repowise" / "cli" / "main.py").write_text("", encoding="utf-8")
            (root / ".venv" / "bin").mkdir(parents=True)
            venv_python = root / ".venv" / "bin" / "python"
            venv_python.write_text("", encoding="utf-8")

            resolved = determine_local_runtime_python(
                start_dir=root,
                executable=venv_python,
            )

        self.assertIsNone(resolved)


if __name__ == "__main__":
    unittest.main()
