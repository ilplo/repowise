from __future__ import annotations

import sys
import tempfile
import subprocess
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import click
from click.testing import CliRunner
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repowise.cli.main import cli
from repowise.cli.commands.init_cmd import init_command
from repowise.cli.runtime import determine_local_runtime_python
from repowise.cli.commands.start_cmd import clear_server_state, restart_server
from repowise.cli.ui import interactive_provider_select


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()
        self.runtime_patch = patch("repowise.cli.main.ensure_local_cli_runtime")
        self.runtime_patch.start()

    def tearDown(self) -> None:
        self.runtime_patch.stop()

    def test_init_defaults_to_current_directory(self) -> None:
        path_param = next(param for param in init_command.params if param.name == "path")

        self.assertEqual(path_param.default, ".")

    def test_mcp_requires_explicit_target_repo_path(self) -> None:
        result = self.runner.invoke(cli, ["mcp"])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing argument 'PATH'", result.output)

    def test_start_supports_running_without_target_repo_path(self) -> None:
        fake_uvicorn = types.SimpleNamespace(run=lambda *args, **kwargs: None)
        with patch("repowise.cli.commands.start_cmd._setup_embedder"):
            with patch("repowise.cli.commands.start_cmd._find_listening_pids", return_value=[]):
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

    def test_bin_wrapper_resolves_repo_root_when_invoked_via_venv_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "bin").mkdir(parents=True)
            (root / ".venv" / "bin").mkdir(parents=True)

            source_wrapper = Path(__file__).resolve().parents[1] / "bin" / "repowise"
            (root / "bin" / "repowise").write_text(source_wrapper.read_text(encoding="utf-8"), encoding="utf-8")
            (root / "bin" / "repowise").chmod(0o755)
            (root / ".venv" / "bin" / "repowise").symlink_to(root / "bin" / "repowise")

            fake_python = root / ".venv" / "bin" / "python"
            fake_python.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$0 $*\"\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            result = subprocess.run(
                [str(root / ".venv" / "bin" / "repowise"), "stop"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(fake_python), result.stdout)
        self.assertIn("-m repowise stop", result.stdout)

    def test_start_refuses_busy_port_before_writing_state(self) -> None:
        fake_uvicorn = types.SimpleNamespace(run=lambda *args, **kwargs: None)
        with patch("repowise.cli.commands.start_cmd._setup_embedder"):
            with patch("repowise.cli.commands.start_cmd._find_listening_pids", return_value=[117]):
                with patch("repowise.cli.commands.start_cmd._write_server_state") as write_state:
                    with patch.dict(sys.modules, {"uvicorn": fake_uvicorn}):
                        result = self.runner.invoke(cli, ["start", "--no-ui"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("already in use", result.output)
        write_state.assert_not_called()

    def test_clear_server_state_preserves_different_server_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_path = root / ".repowise" / "server.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text('{"pid": 117}\n', encoding="utf-8")

            with patch("repowise.cli.commands.start_cmd.get_server_state_path", return_value=state_path):
                clear_server_state(expected_pid=999)

            self.assertTrue(state_path.exists())

    def test_stop_command_terminates_listener_when_state_missing(self) -> None:
        with patch("repowise.cli.commands.stop_cmd.load_server_state", return_value=None):
            with patch("repowise.cli.commands.stop_cmd.stop_server", return_value=[117, 92346]) as stop_server:
                result = self.runner.invoke(cli, ["stop"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Stopped repowise processes", result.output)
        stop_server.assert_called_once()

    def test_logs_command_is_registered(self) -> None:
        result = self.runner.invoke(cli, ["logs", "--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("--follow", result.output)
        self.assertIn("--lines", result.output)

    def test_logs_command_prints_recent_server_log_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "server.log"
            log_path.write_text("one\ntwo\nthree\n", encoding="utf-8")

            with patch("repowise.cli.commands.logs_cmd.get_server_log_path", return_value=log_path):
                result = self.runner.invoke(cli, ["logs", "--lines", "2"])

        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("one", result.output)
        self.assertIn("two", result.output)
        self.assertIn("three", result.output)

    def test_logs_follow_streams_from_server_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "server.log"
            log_path.write_text("ready\n", encoding="utf-8")

            with patch("repowise.cli.commands.logs_cmd.get_server_log_path", return_value=log_path):
                with patch("repowise.cli.commands.logs_cmd.follow_log") as follow_log:
                    result = self.runner.invoke(cli, ["logs", "--follow", "--lines", "5", "--interval", "0.25"])

        self.assertEqual(result.exit_code, 0)
        follow_log.assert_called_once_with(log_path, 5, 0.25)

    def test_restart_server_waits_for_listener_not_transient_state_file(self) -> None:
        class FakeProc:
            pid = 456
            returncode = 1

            def poll(self) -> int:
                return self.returncode

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "server.log"
            log_path.write_text("", encoding="utf-8")

            with patch("repowise.cli.commands.start_cmd.stop_server"):
                with patch("repowise.cli.commands.start_cmd.ensure_app_data_dir"):
                    with patch("repowise.cli.commands.start_cmd.get_server_log_path", return_value=log_path):
                        with patch("repowise.cli.commands.start_cmd.load_server_state", side_effect=[{}, {"pid": 456}]):
                            with patch("repowise.cli.commands.start_cmd._find_listening_pids", return_value=[]):
                                with patch("repowise.cli.commands.start_cmd.time.sleep"):
                                    with patch("repowise.cli.commands.start_cmd.subprocess.Popen", return_value=FakeProc()):
                                        with self.assertRaises(click.ClickException):
                                            restart_server()


if __name__ == "__main__":
    unittest.main()
