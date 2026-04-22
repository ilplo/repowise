"""xAI provider for repowise.

Uses xAI's OpenAI-compatible API surface with the repo's provider abstraction.
Default model is Grok 4.1 Fast Reasoning.
"""

from __future__ import annotations

import os

from repowise.core.providers.llm.base import ProviderError
from repowise.core.providers.llm.openai import OpenAIProvider
from repowise.core.rate_limiter import RateLimiter

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repowise.core.generation.cost_tracker import CostTracker

_DEFAULT_BASE_URL = "https://api.x.ai/v1"


class XAIProvider(OpenAIProvider):
    """xAI chat-completions provider via the OpenAI-compatible endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "grok-4-1-fast-reasoning",
        base_url: str | None = None,
        rate_limiter: RateLimiter | None = None,
        cost_tracker: "CostTracker | None" = None,
    ) -> None:
        resolved_key = api_key or os.environ.get("XAI_API_KEY")
        if not resolved_key:
            raise ProviderError(
                "xai",
                "No API key provided. Pass api_key= or set XAI_API_KEY.",
            )
        resolved_base_url = base_url or os.environ.get("XAI_BASE_URL") or _DEFAULT_BASE_URL
        super().__init__(
            api_key=resolved_key,
            model=model,
            base_url=resolved_base_url,
            rate_limiter=rate_limiter,
            cost_tracker=cost_tracker,
        )

    @property
    def provider_name(self) -> str:
        return "xai"
