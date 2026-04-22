"""Provider configuration management — API keys, active provider, model selection.

Stores configuration in a server-side JSON file. Environment variables take
precedence over stored keys for each provider.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from repowise.app_runtime import ensure_app_data_dir, get_provider_config_path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider catalog (hardcoded — add new providers here)
# ---------------------------------------------------------------------------

PROVIDER_CATALOG: list[dict[str, Any]] = [
    {
        "id": "xai",
        "name": "xAI / Grok",
        "default_model": "grok-4-1-fast-reasoning",
        "models": [
            "grok-4-1-fast-reasoning",
            "grok-4-fast-reasoning",
            "grok-3-mini-fast",
        ],
        "env_keys": ["XAI_API_KEY"],
        "requires_key": True,
    },
]

_CATALOG_BY_ID = {p["id"]: p for p in PROVIDER_CATALOG}


# ---------------------------------------------------------------------------
# Config file I/O
# ---------------------------------------------------------------------------


def _config_path() -> Path:
    ensure_app_data_dir()
    config_dir = os.environ.get("REPOWISE_CONFIG_DIR", "")
    if config_dir:
        return Path(config_dir) / "provider_config.json"
    return get_provider_config_path()


def _load_config() -> dict[str, Any]:
    path = _config_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to read provider config, using defaults")
    return {}


def _save_config(config: dict[str, Any]) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _get_key_for_provider(provider_id: str) -> str | None:
    """Get API key: env var takes precedence, then stored config."""
    catalog = _CATALOG_BY_ID.get(provider_id)
    if not catalog:
        return None

    # Check env vars first
    for env_key in catalog.get("env_keys", []):
        val = os.environ.get(env_key)
        if val:
            return val

    # Check stored config
    config = _load_config()
    keys = config.get("keys", {})
    return keys.get(provider_id)


def list_provider_status() -> dict[str, Any]:
    """Return the full provider status including active selection."""
    config = _load_config()
    active_id = config.get("active_provider")
    active_model = config.get("active_model")

    # Auto-detect active if not set
    if not active_id:
        for p in PROVIDER_CATALOG:
            if _get_key_for_provider(p["id"]) or not p["requires_key"]:
                active_id = p["id"]
                active_model = p["default_model"]
                break

    providers = []
    for p in PROVIDER_CATALOG:
        has_key = bool(_get_key_for_provider(p["id"]))
        configured = has_key or not p["requires_key"]
        providers.append(
            {
                "id": p["id"],
                "name": p["name"],
                "models": p["models"],
                "default_model": p["default_model"],
                "configured": configured,
            }
        )

    return {
        "active": {
            "provider": active_id,
            "model": active_model
            or (_CATALOG_BY_ID.get(active_id, {}).get("default_model") if active_id else None),
        },
        "providers": providers,
    }


def get_active_provider() -> tuple[str | None, str | None]:
    """Return (provider_id, model) for the currently active provider."""
    status = list_provider_status()
    active = status["active"]
    return active["provider"], active["model"]


def set_active_provider(provider_id: str, model: str | None = None) -> None:
    """Set the active provider and model. Persists to config file."""
    if provider_id not in _CATALOG_BY_ID:
        raise ValueError(f"Unknown provider: {provider_id}")
    config = _load_config()
    config["active_provider"] = provider_id
    config["active_model"] = model or _CATALOG_BY_ID[provider_id]["default_model"]
    _save_config(config)


def set_api_key(provider_id: str, key: str | None) -> None:
    """Store or remove an API key for a provider."""
    if provider_id not in _CATALOG_BY_ID:
        raise ValueError(f"Unknown provider: {provider_id}")
    config = _load_config()
    keys = config.setdefault("keys", {})
    if key:
        keys[provider_id] = key
    else:
        keys.pop(provider_id, None)
    _save_config(config)


def get_chat_provider_instance():
    """Create a provider instance for chat using the active config.

    Returns a provider that implements both BaseProvider and ChatProvider.
    """
    from repowise.core.providers.llm.registry import get_provider

    provider_id, model = get_active_provider()
    if not provider_id:
        raise ValueError("No active provider configured. Set an API key first.")

    api_key = _get_key_for_provider(provider_id)
    catalog = _CATALOG_BY_ID[provider_id]

    kwargs: dict[str, Any] = {"model": model or catalog["default_model"]}
    if api_key:
        kwargs["api_key"] = api_key

    return get_provider(provider_id, with_rate_limiter=False, **kwargs)
