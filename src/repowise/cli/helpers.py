"""Shared CLI utilities — async bridge, path resolution, state, DB setup."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, TypeVar

import click
from rich.console import Console
from repowise.app_runtime import (
    ensure_app_data_dir,
    ensure_repo_runtime_dir,
    get_app_data_dir,
    get_global_config_path,
)
from repowise.core.persistence.database import create_engine, create_session_factory, get_session, init_db
from repowise.target_repo import (
    TargetRepoResolutionError,
    canonicalize_target_repo_path,
    resolve_target_repo_paths,
)

CONFIG_FILENAME = "config.yaml"

T = TypeVar("T")

console = Console()
err_console = Console(stderr=True)

STATE_FILENAME = "state.json"
REPOWISE_DIR = ".repowise"
SYNC_STATE_KEY = "_sync_state"


# ---------------------------------------------------------------------------
# Async bridge
# ---------------------------------------------------------------------------


def run_async(coro: Any) -> Any:
    """Run an async coroutine from synchronous Click code."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_repo_path(path: str | None, *, require_explicit: bool = False) -> Path:
    """Resolve the repository root path from a CLI argument.

    If *path* is ``None``, defaults to the current working directory unless
    ``require_explicit`` is true.
    """
    candidate = path
    if candidate is None:
        if require_explicit:
            raise click.UsageError("Missing target repository path.")
        candidate = str(Path.cwd())

    try:
        return resolve_target_repo_paths(candidate).repo_path
    except TargetRepoResolutionError as error:
        raise click.ClickException(str(error)) from error


def get_repowise_dir(repo_path: Path) -> Path:
    """Return the central runtime directory for a target repo."""
    return ensure_repo_runtime_dir(repo_path)


def ensure_repowise_dir(repo_path: Path) -> Path:
    """Create the central app/runtime directories needed for this repo."""
    try:
        resolve_target_repo_paths(repo_path)
    except TargetRepoResolutionError as error:
        raise click.ClickException(str(error)) from error
    ensure_app_data_dir()
    return ensure_repo_runtime_dir(repo_path)


def require_repowise_dir(repo_path: Path) -> Path:
    """Validate the target repo and return its central runtime directory."""
    return ensure_repowise_dir(repo_path)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


def get_db_url_for_repo(repo_path: Path) -> str:
    """Return a database URL for this repo.

    Prefers ``REPOWISE_DB_URL``, then the legacy ``REPOWISE_DATABASE_URL``.
    Otherwise defaults to the central repowise application DB.
    """
    from repowise.core.persistence.database import resolve_db_url

    return resolve_db_url(repo_path)


async def _ensure_db_async(repo_path: Path) -> tuple[Any, Any]:
    url = get_db_url_for_repo(repo_path)
    engine = create_engine(url)
    await init_db(engine)
    session_factory = create_session_factory(engine)
    return engine, session_factory


def ensure_db(repo_path: Path) -> tuple[Any, Any]:
    """Create the DB engine, initialise the schema, and return ``(engine, session_factory)``."""
    return run_async(_ensure_db_async(repo_path))


# ---------------------------------------------------------------------------
# Central config/state persistence
# ---------------------------------------------------------------------------


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-untyped]

        return yaml.safe_load(text) or {}
    except ImportError:
        result: dict[str, Any] = {}
        for line in text.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                result[k.strip()] = v.strip()
        return result


def _write_yaml_file(path: Path, data: dict[str, Any]) -> None:
    ensure_app_data_dir()
    try:
        import yaml  # type: ignore[import-untyped]

        path.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
    except ImportError:
        lines = [f"{key}: {value}" for key, value in data.items()]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_app_config() -> dict[str, Any]:
    """Load the global app config stored under the repowise checkout."""
    return _load_yaml_file(get_global_config_path())


def save_app_config(updates: dict[str, Any]) -> None:
    """Merge and persist global app config."""
    current = load_app_config()
    current.update(updates)
    _write_yaml_file(get_global_config_path(), current)


async def _get_or_create_repository_record(session: Any, repo_path: Path) -> Any:
    from repowise.core.persistence.crud import get_repository_by_path, upsert_repository

    repo = await get_repository_by_path(session, str(repo_path))
    if repo is None:
        repo = await upsert_repository(
            session,
            name=repo_path.name,
            local_path=str(repo_path),
        )
    return repo


async def _load_repo_settings_async(repo_path: Path) -> dict[str, Any]:
    engine = create_engine(get_db_url_for_repo(repo_path))
    await init_db(engine)
    sf = create_session_factory(engine)
    try:
        async with get_session(sf) as session:
            from repowise.core.persistence.crud import get_repository_by_path

            repo = await get_repository_by_path(session, str(canonicalize_target_repo_path(repo_path)))
            if repo is not None and repo.settings_json:
                return json.loads(repo.settings_json)
    finally:
        await engine.dispose()
    return {}


async def _merge_repo_settings_async(repo_path: Path, updates: dict[str, Any]) -> dict[str, Any]:
    engine = create_engine(get_db_url_for_repo(repo_path))
    await init_db(engine)
    sf = create_session_factory(engine)
    try:
        async with get_session(sf) as session:
            repo = await _get_or_create_repository_record(session, repo_path)
            current = json.loads(repo.settings_json or "{}")
            current.update(updates)
            repo.settings_json = json.dumps(current)
            return current
    finally:
        await engine.dispose()


async def _load_repo_state_async(repo_path: Path) -> dict[str, Any]:
    settings = await _load_repo_settings_async(repo_path)
    state = settings.get(SYNC_STATE_KEY)
    if isinstance(state, dict):
        return state
    return {}


async def _save_repo_state_async(repo_path: Path, state: dict[str, Any]) -> dict[str, Any]:
    return await _merge_repo_settings_async(repo_path, {SYNC_STATE_KEY: state})


def load_state(repo_path: Path) -> dict[str, Any]:
    """Load repo sync state from the central database."""
    return run_async(_load_repo_state_async(repo_path))


def save_state(repo_path: Path, state: dict[str, Any]) -> None:
    """Persist repo sync state in the central database."""
    ensure_repowise_dir(repo_path)
    run_async(_save_repo_state_async(repo_path, state))


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def get_head_commit(repo_path: Path) -> str | None:
    """Return the HEAD commit SHA or ``None`` if not a git repo."""
    try:
        import git as gitpython

        repo = gitpython.Repo(repo_path, search_parent_directories=True)
        sha = repo.head.commit.hexsha
        repo.close()
        return sha
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Config (provider / model / embedder persisted after init)
# ---------------------------------------------------------------------------


def load_config(repo_path: Path) -> dict[str, Any]:
    """Load repo settings from the central database."""
    return run_async(_load_repo_settings_async(repo_path))


def save_config(
    repo_path: Path,
    provider: str,
    model: str,
    embedder: str,
    *,
    exclude_patterns: list[str] | None = None,
    commit_limit: int | None = None,
) -> None:
    """Persist repo settings in the central database."""
    ensure_repowise_dir(repo_path)
    existing = load_config(repo_path)
    existing["provider"] = provider
    existing["model"] = model
    existing["embedder"] = embedder
    if exclude_patterns is not None:
        existing["exclude_patterns"] = exclude_patterns
    if commit_limit is not None:
        existing["commit_limit"] = commit_limit
    run_async(_merge_repo_settings_async(repo_path, existing))


# ---------------------------------------------------------------------------
# Provider resolution
# ---------------------------------------------------------------------------


def resolve_provider(
    provider_name: str | None,
    model: str | None,
    repo_path: Path | None = None,
) -> Any:
    """Resolve a provider instance from CLI flags or environment variables.

    Resolution order:
      1. Explicit ``--provider`` flag
      2. ``REPOWISE_PROVIDER`` env var
      3. Central repository settings persisted by ``repowise init``
      4. Auto-detect from API key env vars
    """
    from repowise.core.providers import get_provider

    if provider_name is None:
        provider_name = os.environ.get("REPOWISE_PROVIDER")

    if provider_name is None and repo_path is not None:
        cfg = load_config(repo_path)
        if cfg.get("provider"):
            provider_name = cfg["provider"]
            if model is None and cfg.get("model"):
                model = cfg["model"]

    if provider_name is not None:
        # Validate configuration before attempting to create provider
        warnings = validate_provider_config(provider_name)
        if warnings:
            for warning in warnings:
                err_console.print(f"[yellow]Warning:[/yellow] {warning}")
            # For explicit provider requests, we still try to create it
            # The provider constructor will fail if the API key is actually required

        kwargs: dict[str, Any] = {}
        if model:
            kwargs["model"] = model

        # Pass API key from environment if available
        if provider_name == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
            kwargs["api_key"] = os.environ["ANTHROPIC_API_KEY"]
        elif provider_name == "xai" and os.environ.get("XAI_API_KEY"):
            kwargs["api_key"] = os.environ["XAI_API_KEY"]
            if os.environ.get("XAI_BASE_URL"):
                kwargs["base_url"] = os.environ["XAI_BASE_URL"]
        elif provider_name == "openai" and os.environ.get("OPENAI_API_KEY"):
            kwargs["api_key"] = os.environ["OPENAI_API_KEY"]
        elif provider_name == "gemini" and (
            os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        ):
            kwargs["api_key"] = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        elif provider_name == "ollama" and os.environ.get("OLLAMA_BASE_URL"):
            kwargs["base_url"] = os.environ["OLLAMA_BASE_URL"]

        return get_provider(provider_name, **kwargs)

    # Auto-detect from env vars
    if os.environ.get("ANTHROPIC_API_KEY") and os.environ["ANTHROPIC_API_KEY"].strip():
        anthropic_kwargs: dict[str, Any] = (
            {"model": model, "api_key": os.environ["ANTHROPIC_API_KEY"]}
            if model
            else {"api_key": os.environ["ANTHROPIC_API_KEY"]}
        )
        return get_provider("anthropic", **anthropic_kwargs)
    if os.environ.get("XAI_API_KEY") and os.environ["XAI_API_KEY"].strip():
        xai_kwargs: dict[str, Any] = (
            {"model": model, "api_key": os.environ["XAI_API_KEY"]}
            if model
            else {"api_key": os.environ["XAI_API_KEY"]}
        )
        if os.environ.get("XAI_BASE_URL"):
            xai_kwargs["base_url"] = os.environ["XAI_BASE_URL"]
        return get_provider("xai", **xai_kwargs)
    if os.environ.get("OPENAI_API_KEY") and os.environ["OPENAI_API_KEY"].strip():
        openai_kwargs: dict[str, Any] = (
            {"model": model, "api_key": os.environ["OPENAI_API_KEY"]}
            if model
            else {"api_key": os.environ["OPENAI_API_KEY"]}
        )
        return get_provider("openai", **openai_kwargs)
    if os.environ.get("OLLAMA_BASE_URL") and os.environ["OLLAMA_BASE_URL"].strip():
        ollama_kwargs: dict[str, Any] = (
            {"model": model, "base_url": os.environ["OLLAMA_BASE_URL"]}
            if model
            else {"base_url": os.environ["OLLAMA_BASE_URL"]}
        )
        return get_provider("ollama", **ollama_kwargs)
    if (os.environ.get("GEMINI_API_KEY") and os.environ["GEMINI_API_KEY"].strip()) or (
        os.environ.get("GOOGLE_API_KEY") and os.environ["GOOGLE_API_KEY"].strip()
    ):
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        gemini_kwargs: dict[str, Any] = (
            {"model": model, "api_key": api_key} if model else {"api_key": api_key}
        )
        return get_provider("gemini", **gemini_kwargs)

    raise click.ClickException(
        "No provider configured. Use --provider, set REPOWISE_PROVIDER, "
        "or set ANTHROPIC_API_KEY / XAI_API_KEY / OPENAI_API_KEY / "
        "OLLAMA_BASE_URL / GEMINI_API_KEY / GOOGLE_API_KEY."
    )


# ---------------------------------------------------------------------------
# Provider validation
# ---------------------------------------------------------------------------


def validate_provider_config(provider_name: str | None = None) -> list[str]:
    """Validate that required API keys/environment variables are set for the provider.

    Args:
        provider_name: The provider name to validate. If None, checks all possible providers.

    Returns:
        List of warning messages for missing or invalid configuration.
        Empty list means all required config is present.
    """
    warnings = []

    def _is_env_var_set(var_name: str) -> bool:
        """Check if environment variable is set and non-empty."""
        value = os.environ.get(var_name)
        return value is not None and value.strip() != ""

    def _is_env_var_exists(var_name: str) -> bool:
        """Check if environment variable exists (even if empty)."""
        return var_name in os.environ

    # Define required environment variables for each provider
    provider_env_vars = {
        "anthropic": ["ANTHROPIC_API_KEY"],
        "xai": ["XAI_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
        "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],  # Either one
        "ollama": ["OLLAMA_BASE_URL"],
        "litellm": ["LITELLM_API_KEY"],  # May need others depending on backend
    }

    if provider_name:
        # Validate specific provider
        if provider_name not in provider_env_vars:
            warnings.append(f"Unknown provider '{provider_name}' - cannot validate configuration")
            return warnings

        env_vars = provider_env_vars[provider_name]
        missing_vars = []

        if provider_name == "gemini":
            # Special case: either GEMINI_API_KEY or GOOGLE_API_KEY
            if not (_is_env_var_set("GEMINI_API_KEY") or _is_env_var_set("GOOGLE_API_KEY")):
                missing_vars = env_vars
        else:
            for var in env_vars:
                if not _is_env_var_set(var):
                    missing_vars.append(var)

        if missing_vars:
            warnings.append(
                f"Provider '{provider_name}' requires environment variables: {', '.join(missing_vars)}"
            )
    else:
        # Check all providers - warn about any that could be configured but are missing keys
        for name, env_vars in provider_env_vars.items():
            if name == "gemini":
                if os.environ.get("REPOWISE_PROVIDER") == "gemini" and not (
                    _is_env_var_set("GEMINI_API_KEY") or _is_env_var_set("GOOGLE_API_KEY")
                ):
                    # Only warn if it looks like they might be trying to use gemini
                    warnings.append(
                        "Provider 'gemini' requires GEMINI_API_KEY or GOOGLE_API_KEY environment variable"
                    )
                continue

            missing = [var for var in env_vars if not _is_env_var_set(var)]
            if missing:
                # Only warn if this provider is explicitly requested OR
                # if the env var exists but is invalid (empty)
                env_var_exists = any(_is_env_var_exists(var) for var in env_vars)
                explicitly_requested = os.environ.get("REPOWISE_PROVIDER") == name

                if explicitly_requested or env_var_exists:
                    warnings.append(
                        f"Provider '{name}' requires environment variables: {', '.join(missing)}"
                    )

    return warnings
