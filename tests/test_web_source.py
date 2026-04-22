from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repowise.cli.commands.serve_cmd import _find_local_web


class WebSourceTests(unittest.TestCase):
    def test_repo_contains_local_web_source(self) -> None:
        web_dir = _find_local_web()

        self.assertIsNotNone(web_dir)
        assert web_dir is not None
        self.assertEqual(web_dir.resolve(), (Path(__file__).resolve().parents[1] / "packages" / "web").resolve())
        self.assertTrue((web_dir / "package.json").exists())
        self.assertTrue((web_dir / "src").is_dir())
        self.assertTrue((web_dir / "public").is_dir())


if __name__ == "__main__":
    unittest.main()
