"""repowise LLM provider sub-package.

All LLM providers implement BaseProvider. Use get_provider() from the registry
to instantiate a provider by name — this is the preferred entry point.

    from repowise.core.providers.llm import get_provider

    provider = get_provider("xai")
    response = await provider.generate(system_prompt="...", user_prompt="...")

Built-in providers:
    xai        — Grok hosted models
    mock       — deterministic test provider
"""

from repowise.core.providers.llm.base import (
    BaseProvider,
    ChatProvider,
    ChatStreamEvent,
    ChatToolCall,
    GeneratedResponse,
    ProviderError,
    RateLimitError,
)
from repowise.core.providers.llm.registry import get_provider, list_providers, register_provider

__all__ = [
    "BaseProvider",
    "ChatProvider",
    "ChatStreamEvent",
    "ChatToolCall",
    "GeneratedResponse",
    "ProviderError",
    "RateLimitError",
    "get_provider",
    "list_providers",
    "register_provider",
]
