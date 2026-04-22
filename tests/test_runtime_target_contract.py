from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repowise.server.app import _resolve_target_runtime
from repowise.server.mcp_server._server import _resolve_mcp_runtime_target


class RuntimeTargetContractTests(unittest.TestCase):
    def test_fastapi_runtime_keeps_target_repo_when_db_url_env_is_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "target"
            (repo_path / ".git").mkdir(parents=True)

            target_paths, db_url = _resolve_target_runtime(
                target_repo_path=str(repo_path),
                configured_db_url="sqlite+aiosqlite:////tmp/unrelated.db",
            )

            self.assertEqual(target_paths.repo_path, repo_path.resolve())
            self.assertEqual(db_url, _resolve_target_runtime(None, None)[1])

    def test_mcp_runtime_ignores_env_db_override_when_repo_path_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "target"
            (repo_path / ".git").mkdir(parents=True)

            target_paths, db_url = _resolve_mcp_runtime_target(
                repo_path=str(repo_path),
                configured_db_url="sqlite+aiosqlite:////tmp/unrelated.db",
            )

            self.assertEqual(target_paths.repo_path, repo_path.resolve())
            self.assertEqual(db_url, _resolve_mcp_runtime_target(None, None)[1])


if __name__ == "__main__":
    unittest.main()
