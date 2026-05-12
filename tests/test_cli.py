from __future__ import annotations

import sys
import tempfile
import subprocess
import types
import unittest
import os
from pathlib import Path
from unittest.mock import patch

import click
from click.testing import CliRunner
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repowise.cli.main import cli
from repowise.cli.commands.init_cmd import init_command
from repowise.cli.helpers import resolve_provider
from repowise.cli.runtime import determine_local_runtime_python, ensure_local_cli_runtime
from repowise.cli.commands.start_cmd import clear_server_state, restart_server, _sync_frontend_assets
from repowise.cli.ui import interactive_provider_select
from repowise.core.providers import get_provider, list_providers
from repowise.server.provider_config import get_active_provider, list_provider_status, set_active_provider


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

    def test_serve_command_is_not_registered(self) -> None:
        result = self.runner.invoke(cli, ["serve", "--help"])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("No such command 'serve'", result.output)

    def test_init_interactive_provider_select_defaults_to_xai_grok(self) -> None:
        with patch.dict("os.environ", {"XAI_API_KEY": "test-key"}, clear=True):
            with patch("repowise.cli.ui.Prompt.ask", return_value="1"):
                with patch("repowise.cli.ui.click.prompt", return_value="grok-4-1-fast-reasoning") as prompt:
                    provider, model = interactive_provider_select(
                        Console(record=True),
                        None,
                    )

        self.assertEqual(provider, "xai")
        self.assertEqual(model, "grok-4-1-fast-reasoning")
        prompt.assert_called_once()

    def test_resolve_provider_defaults_to_xai_grok(self) -> None:
        with patch.dict("os.environ", {"XAI_API_KEY": "test-key"}, clear=True):
            provider = resolve_provider(None, None, None)

        self.assertEqual(provider.provider_name, "xai")
        self.assertEqual(provider.model_name, "grok-4-1-fast-reasoning")

    def test_resolve_provider_allows_explicit_xai(self) -> None:
        with patch.dict("os.environ", {"XAI_API_KEY": "test-key"}, clear=True):
            provider = resolve_provider("xai", None, None)

        self.assertEqual(provider.provider_name, "xai")
        self.assertEqual(provider.model_name, "grok-4-1-fast-reasoning")

    def test_public_provider_registry_exposes_only_xai(self) -> None:
        self.assertEqual(list_providers(), ["xai"])
        with self.assertRaises(ValueError):
            get_provider("ollama")

    def test_server_provider_status_defaults_to_xai_grok(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"REPOWISE_CONFIG_DIR": temp_dir}, clear=True):
                status = list_provider_status()
                provider, model = get_active_provider()

        self.assertEqual(provider, "xai")
        self.assertEqual(model, "grok-4-1-fast-reasoning")
        self.assertEqual([p["id"] for p in status["providers"]], ["xai"])
        self.assertEqual(status["providers"][0]["default_model"], "grok-4-1-fast-reasoning")

    def test_server_provider_status_allows_xai_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"REPOWISE_CONFIG_DIR": temp_dir}, clear=True):
                set_active_provider("xai")
                provider, model = get_active_provider()

        self.assertEqual(provider, "xai")
        self.assertEqual(model, "grok-4-1-fast-reasoning")

    def test_server_provider_status_replaces_stale_active_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "provider_config.json"
            config_path.write_text(
                '{"active_provider":"xai","active_model":"legacy-model"}',
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"REPOWISE_CONFIG_DIR": temp_dir}, clear=True):
                provider, model = get_active_provider()
                status = list_provider_status()

        self.assertEqual(provider, "xai")
        self.assertEqual(model, "grok-4-1-fast-reasoning")
        self.assertEqual(status["active"]["model"], "grok-4-1-fast-reasoning")

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

    def test_runtime_reexec_adds_checkout_src_to_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "pyproject.toml").write_text("[project]\nname='repowise'\n", encoding="utf-8")
            (root / "src" / "repowise" / "cli").mkdir(parents=True)
            (root / "src" / "repowise" / "cli" / "main.py").write_text("", encoding="utf-8")
            (root / ".venv" / "bin").mkdir(parents=True)
            venv_python = root / ".venv" / "bin" / "python"
            venv_python.write_text("", encoding="utf-8")

            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                with patch("repowise.cli.runtime.sys.executable", "/usr/bin/python3"):
                    with patch("repowise.cli.runtime.sys.argv", ["repowise", "start"]):
                        with patch("repowise.cli.runtime.os.execve") as execve:
                            ensure_local_cli_runtime()
            finally:
                os.chdir(previous_cwd)

        execve.assert_called_once()
        executable, argv, env = execve.call_args.args
        self.assertEqual(executable, str(venv_python.resolve()))
        self.assertEqual(argv, [str(venv_python.resolve()), "-m", "repowise", "start"])
        self.assertEqual(env["PYTHONPATH"].split(os.pathsep)[0], str((root / "src").resolve()))
        self.assertEqual(env["VIRTUAL_ENV"], str((root / ".venv").resolve()))
        self.assertEqual(env["PATH"].split(os.pathsep)[0], str((root / ".venv" / "bin").resolve()))

    def test_runtime_sets_activation_env_when_already_using_project_venv_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "pyproject.toml").write_text("[project]\nname='repowise'\n", encoding="utf-8")
            (root / "src" / "repowise" / "cli").mkdir(parents=True)
            (root / "src" / "repowise" / "cli" / "main.py").write_text("", encoding="utf-8")
            (root / ".venv" / "bin").mkdir(parents=True)
            venv_python = root / ".venv" / "bin" / "python"
            venv_python.write_text("", encoding="utf-8")

            previous_cwd = Path.cwd()
            previous_env = dict(os.environ)
            os.chdir(root)
            try:
                with patch("repowise.cli.runtime.sys.executable", str(venv_python)):
                    with patch("repowise.cli.runtime.os.execve") as execve:
                        ensure_local_cli_runtime()
                    self.assertEqual(os.environ["VIRTUAL_ENV"], str((root / ".venv").resolve()))
                    self.assertEqual(os.environ["PATH"].split(os.pathsep)[0], str((root / ".venv" / "bin").resolve()))
                    self.assertEqual(os.environ["PYTHONPATH"].split(os.pathsep)[0], str((root / "src").resolve()))
            finally:
                os.environ.clear()
                os.environ.update(previous_env)
                os.chdir(previous_cwd)

        execve.assert_not_called()

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
                "printf '%s\\n' \"$0 $*\"\n"
                "printf 'VIRTUAL_ENV=%s\\n' \"$VIRTUAL_ENV\"\n"
                "printf 'PATH_HEAD=%s\\n' \"${PATH%%:*}\"\n",
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
        self.assertIn(f"VIRTUAL_ENV={(root / '.venv').resolve()}", result.stdout)
        self.assertIn(f"PATH_HEAD={(root / '.venv' / 'bin').resolve()}", result.stdout)

    def test_root_wrapper_runs_from_checkout_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "bin").mkdir(parents=True)
            (root / ".venv" / "bin").mkdir(parents=True)

            source_bin_wrapper = Path(__file__).resolve().parents[1] / "bin" / "repowise"
            source_root_wrapper = Path(__file__).resolve().parents[1] / "repowise"
            (root / "bin" / "repowise").write_text(source_bin_wrapper.read_text(encoding="utf-8"), encoding="utf-8")
            (root / "bin" / "repowise").chmod(0o755)
            (root / "repowise").write_text(source_root_wrapper.read_text(encoding="utf-8"), encoding="utf-8")
            (root / "repowise").chmod(0o755)

            fake_python = root / ".venv" / "bin" / "python"
            fake_python.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$0 $*\"\n"
                "printf 'VIRTUAL_ENV=%s\\n' \"$VIRTUAL_ENV\"\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            result = subprocess.run(
                [str(root / "repowise"), "start"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(fake_python), result.stdout)
        self.assertIn("-m repowise start", result.stdout)
        self.assertIn(f"VIRTUAL_ENV={(root / '.venv').resolve()}", result.stdout)

    def test_make_start_all_uses_root_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_makefile = Path(__file__).resolve().parents[1] / "Makefile"
            (root / "Makefile").write_text(source_makefile.read_text(encoding="utf-8"), encoding="utf-8")

            result = subprocess.run(
                ["make", "-n", "start-all"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("./repowise start", result.stdout)

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

    def test_frontend_asset_sync_replaces_stale_standalone_static_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local_web = root / "packages" / "web"
            standalone = local_web / ".next" / "standalone"
            source_static = local_web / ".next" / "static"
            stale_static = standalone / ".next" / "static"
            source_public = local_web / "public"
            stale_public = standalone / "public"

            (source_static / "chunks").mkdir(parents=True)
            (source_static / "chunks" / "new.js").write_text("new", encoding="utf-8")
            (source_public).mkdir(parents=True)
            (source_public / "logo.svg").write_text("new logo", encoding="utf-8")
            (stale_static / "chunks").mkdir(parents=True)
            (stale_static / "chunks" / "old.js").write_text("old", encoding="utf-8")
            (stale_public).mkdir(parents=True)
            (stale_public / "old-logo.svg").write_text("old logo", encoding="utf-8")

            _sync_frontend_assets(local_web, standalone)

            self.assertTrue((stale_static / "chunks" / "new.js").exists())
            self.assertFalse((stale_static / "chunks" / "old.js").exists())
            self.assertTrue((stale_public / "logo.svg").exists())
            self.assertFalse((stale_public / "old-logo.svg").exists())

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
