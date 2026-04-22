from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repowise.target_repo import (
    TargetRepoResolutionError,
    ensure_repowise_dir,
    require_repowise_dir,
    resolve_target_repo_paths,
)


class TargetRepoResolverTests(unittest.TestCase):
    def test_rejects_missing_target_repo(self) -> None:
        missing_path = Path(tempfile.gettempdir()) / "repowise-missing-target-repo"

        with self.assertRaises(TargetRepoResolutionError):
            resolve_target_repo_paths(missing_path)

    def test_rejects_file_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "target.txt"
            file_path.write_text("not a repo", encoding="utf-8")

            with self.assertRaises(TargetRepoResolutionError):
                resolve_target_repo_paths(file_path)

    def test_rejects_directory_without_git_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "target"
            repo_path.mkdir()

            with self.assertRaises(TargetRepoResolutionError):
                resolve_target_repo_paths(repo_path)

    def test_derives_repowise_paths_without_creating_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "target"
            (repo_path / ".git").mkdir(parents=True)

            paths = resolve_target_repo_paths(repo_path)

            self.assertEqual(paths.repo_path, repo_path.resolve())
            self.assertEqual(paths.repowise_dir, repo_path.resolve() / ".repowise")
            self.assertEqual(paths.db_path, repo_path.resolve() / ".repowise" / "wiki.db")
            self.assertEqual(paths.config_path, repo_path.resolve() / ".repowise" / "config.yaml")
            self.assertEqual(paths.state_path, repo_path.resolve() / ".repowise" / "state.json")
            self.assertFalse(paths.repowise_dir.exists())

    def test_creates_repowise_directory_only_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "target"
            (repo_path / ".git").mkdir(parents=True)

            paths = resolve_target_repo_paths(repo_path)
            ensure_repowise_dir(paths)

            self.assertTrue(paths.repowise_dir.is_dir())

    def test_requires_existing_repowise_directory_for_read_only_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "target"
            (repo_path / ".git").mkdir(parents=True)

            paths = resolve_target_repo_paths(repo_path)

            with self.assertRaises(TargetRepoResolutionError):
                require_repowise_dir(paths)

    def test_accepts_git_file_marker_for_worktree_style_repos(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "target"
            repo_path.mkdir()
            (repo_path / ".git").write_text("gitdir: /tmp/worktrees/target", encoding="utf-8")

            paths = resolve_target_repo_paths(repo_path)

            self.assertEqual(paths.repo_path, repo_path.resolve())


if __name__ == "__main__":
    unittest.main()
