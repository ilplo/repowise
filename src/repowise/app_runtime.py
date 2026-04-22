"""Central runtime paths for the repowise source-checkout application mode."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

APP_DIRNAME = ".repowise"
DB_FILENAME = "wiki.db"
GLOBAL_CONFIG_FILENAME = "config.yaml"
GLOBAL_ENV_FILENAME = ".env"
PROVIDER_CONFIG_FILENAME = "provider_config.json"
SERVER_STATE_FILENAME = "server.json"
SERVER_LOG_FILENAME = "server.log"


def find_app_root(start_dir: str | Path | None = None) -> Path:
    """Return the repowise checkout root.

    Resolution order:
    1. ``REPOWISE_APP_ROOT`` when set
    2. nearest ancestor containing both ``pyproject.toml`` and ``src/repowise``
       starting from *start_dir* (or this file's directory)
    """
    env_root = os.environ.get("REPOWISE_APP_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    candidate = Path(start_dir).expanduser().resolve() if start_dir else Path(__file__).resolve()
    search_roots = [candidate, *candidate.parents]
    for root in search_roots:
        if (root / "pyproject.toml").exists() and (root / "src" / "repowise").exists():
            return root

    raise RuntimeError("Could not locate the repowise application root.")


def get_app_data_dir(start_dir: str | Path | None = None) -> Path:
    return find_app_root(start_dir) / APP_DIRNAME


def ensure_app_data_dir(start_dir: str | Path | None = None) -> Path:
    path = get_app_data_dir(start_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_app_db_path(start_dir: str | Path | None = None) -> Path:
    return get_app_data_dir(start_dir) / DB_FILENAME


def get_global_config_path(start_dir: str | Path | None = None) -> Path:
    return get_app_data_dir(start_dir) / GLOBAL_CONFIG_FILENAME


def get_global_env_path(start_dir: str | Path | None = None) -> Path:
    return get_app_data_dir(start_dir) / GLOBAL_ENV_FILENAME


def get_provider_config_path(start_dir: str | Path | None = None) -> Path:
    return get_app_data_dir(start_dir) / PROVIDER_CONFIG_FILENAME


def _repo_key(repo_path: str | Path) -> str:
    resolved = Path(repo_path).expanduser().resolve()
    digest = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:12]
    slug = resolved.name or "repo"
    safe_slug = "".join(ch if ch.isalnum() or ch in "-._" else "-" for ch in slug).strip("-")
    return f"{safe_slug}-{digest}"


def get_repo_runtime_dir(repo_path: str | Path, start_dir: str | Path | None = None) -> Path:
    return get_app_data_dir(start_dir) / "repositories" / _repo_key(repo_path)


def ensure_repo_runtime_dir(repo_path: str | Path, start_dir: str | Path | None = None) -> Path:
    path = get_repo_runtime_dir(repo_path, start_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_repo_lancedb_dir(repo_path: str | Path, start_dir: str | Path | None = None) -> Path:
    return get_repo_runtime_dir(repo_path, start_dir) / "lancedb"


def get_repo_jobs_dir(repo_path: str | Path, start_dir: str | Path | None = None) -> Path:
    return get_repo_runtime_dir(repo_path, start_dir) / "jobs"


def get_server_state_path(start_dir: str | Path | None = None) -> Path:
    return get_app_data_dir(start_dir) / SERVER_STATE_FILENAME


def get_server_log_path(start_dir: str | Path | None = None) -> Path:
    return get_app_data_dir(start_dir) / SERVER_LOG_FILENAME
