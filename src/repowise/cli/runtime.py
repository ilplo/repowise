"""CLI runtime helpers for preferring the local project `.venv` when available."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable


def _iter_search_roots(start_dir: Path) -> Iterable[Path]:
    current = start_dir.resolve()
    yield current
    yield from current.parents


def _is_repowise_checkout(root: Path) -> bool:
    return (root / "pyproject.toml").exists() and (root / "src" / "repowise" / "cli" / "main.py").exists()


def _project_venv_python(root: Path) -> Path | None:
    candidates = (
        root / ".venv" / "bin" / "python",
        root / ".venv" / "bin" / "python3",
        root / ".venv" / "Scripts" / "python.exe",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def determine_local_runtime_python(
    *,
    start_dir: str | Path | None = None,
    executable: str | Path | None = None,
) -> Path | None:
    """Return the checkout `.venv` Python when the current runtime is stale.

    The lookup walks upward from ``start_dir`` and detects a Repowise source
    checkout by looking for ``pyproject.toml`` plus ``src/repowise/cli/main.py``.
    If such a checkout also has a local ``.venv`` and the current executable is
    not already that interpreter, the `.venv` Python path is returned.
    """
    search_start = Path(start_dir or Path.cwd()).resolve()
    current_executable = Path(executable or sys.executable).resolve()

    for root in _iter_search_roots(search_start):
        if not _is_repowise_checkout(root):
            continue

        venv_python = _project_venv_python(root)
        if venv_python is None:
            return None

        if current_executable == venv_python:
            return None

        return venv_python

    return None


def ensure_local_cli_runtime() -> None:
    """Re-exec the CLI through the checkout `.venv` when needed.

    This keeps all CLI commands loading the source tree associated with the
    current checkout instead of a stale global/site-packages install.
    """
    venv_python = determine_local_runtime_python()
    if venv_python is None:
        return

    argv = [str(venv_python), "-m", "repowise.cli.main", *sys.argv[1:]]
    os.execve(str(venv_python), argv, dict(os.environ))
