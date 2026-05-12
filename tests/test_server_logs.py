from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repowise.server.routers.logs import get_server_logs


class ServerLogsTests(unittest.TestCase):
    def test_server_logs_returns_empty_lines_when_log_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "missing.log"

            with patch("repowise.server.routers.logs.get_server_log_path", return_value=log_path):
                response = get_server_logs(lines=100)

        self.assertEqual(response.path, str(log_path))
        self.assertEqual(response.lines, [])

    def test_server_logs_returns_requested_tail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "server.log"
            log_path.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")

            with patch("repowise.server.routers.logs.get_server_log_path", return_value=log_path):
                response = get_server_logs(lines=2)

        self.assertEqual(response.path, str(log_path))
        self.assertEqual(response.lines, ["three", "four"])


if __name__ == "__main__":
    unittest.main()
