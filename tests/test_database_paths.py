from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repowise.app_runtime import get_app_db_path
from repowise.core.persistence.database import get_repo_db_path, resolve_db_url


class DatabasePathTests(unittest.TestCase):
    def test_resolve_db_url_uses_central_app_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "target"
            (repo_path / ".git").mkdir(parents=True)

            db_path = get_repo_db_path(repo_path)
            db_url = resolve_db_url(repo_path)

            self.assertEqual(db_path, repo_path.resolve() / ".repowise" / "wiki.db")
            self.assertEqual(db_url, f"sqlite+aiosqlite:///{get_app_db_path().as_posix()}")

    def test_resolve_db_url_does_not_create_repowise_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "target"
            (repo_path / ".git").mkdir(parents=True)

            resolve_db_url(repo_path)

            self.assertFalse((repo_path / ".repowise").exists())


if __name__ == "__main__":
    unittest.main()
