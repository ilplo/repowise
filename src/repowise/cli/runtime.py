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


def _find_repowise_checkout(start_dir: Path) -> Path | None:
    for root in _iter_search_roots(start_dir):
        if _is_repowise_checkout(root):
            return root
    return None


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


def _project_venv_dir(root: Path) -> Path | None:
    venv_dir = root / ".venv"
    return venv_dir.resolve() if venv_dir.exists() else None


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

    root = _find_repowise_checkout(search_start)
    if root is None:
        return None

    venv_python = _project_venv_python(root)
    if venv_python is None:
        return None

    if current_executable == venv_python:
        return None

    return venv_python


def _prepend_pythonpath(env: dict[str, str], source_path: Path) -> dict[str, str]:
    next_env = dict(env)
    source = str(source_path.resolve())
    existing = next_env.get("PYTHONPATH")
    if existing:
        paths = existing.split(os.pathsep)
        next_env["PYTHONPATH"] = existing if paths[0] == source else os.pathsep.join([source, existing])
    else:
        next_env["PYTHONPATH"] = source
    return next_env


def _prepend_path(env: dict[str, str], path: Path) -> dict[str, str]:
    next_env = dict(env)
    entry = str(path.resolve())
    existing = next_env.get("PATH")
    if existing:
        paths = existing.split(os.pathsep)
        next_env["PATH"] = existing if paths[0] == entry else os.pathsep.join([entry, existing])
    else:
        next_env["PATH"] = entry
    return next_env


def _with_project_venv_env(env: dict[str, str], *, checkout: Path, venv_dir: Path) -> dict[str, str]:
    next_env = _prepend_pythonpath(env, checkout / "src")
    next_env = _prepend_path(next_env, venv_dir / ("Scripts" if os.name == "nt" else "bin"))
    next_env["VIRTUAL_ENV"] = str(venv_dir.resolve())
    next_env.pop("PYTHONHOME", None)
    return next_env


def ensure_local_cli_runtime() -> None:
    """Re-exec the CLI through the checkout `.venv` when needed.

    This keeps all CLI commands loading the source tree associated with the
    current checkout instead of a stale global/site-packages install.
    """
    checkout = _find_repowise_checkout(Path.cwd())
    if checkout is None:
        return

    venv_dir = _project_venv_dir(checkout)
    venv_python = _project_venv_python(checkout)
    if venv_dir is None or venv_python is None:
        return

    env = _with_project_venv_env(dict(os.environ), checkout=checkout, venv_dir=venv_dir)
    if Path(sys.executable).resolve() == venv_python:
        os.environ.clear()
        os.environ.update(env)
        return

    argv = [str(venv_python), "-m", "repowise", *sys.argv[1:]]
    os.execve(str(venv_python), argv, env)
