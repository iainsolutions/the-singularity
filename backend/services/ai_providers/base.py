"""Common abstractions for AI provider integrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class AIProviderError(Exception):
    """Base exception for AI provider errors."""


class AIProviderRateLimitError(AIProviderError):
    """Raised when a provider reports a rate limit error."""


class AIProviderTimeoutError(AIProviderError):
    """Raised when the provider request times out."""


class AIProviderConnectionError(AIProviderError):
    """Raised when the provider cannot be reached."""


@dataclass(slots=True)
class AIProviderResponse:
    """Standard response payload returned from AI providers."""

    text: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    raw_response: Any | None = None
    # Tool use fields - when tools are used, these contain structured output
    tool_name: str | None = None
    tool_input: dict | None = None


class AIProvider(Protocol):
    """Protocol that all AI providers must implement."""

    name: str

    def get_model_for_difficulty(self, difficulty: str) -> str:
        """Return the model identifier to use for the given difficulty."""

    def supports_prefill(self) -> bool:
        """
        Check if provider supports response prefilling.

        Response prefilling allows forcing the model to start its response
        with specific text (e.g., "<thinking>" to ensure reasoning).

        Returns:
            True if prefill is supported, False otherwise
        """
        return False

    async def send_message(
        self,
        *,
        prompt: str,
        system_prompt: str | list,
        model: str,
        max_tokens: int,
        temperature: float,
        prefill: str | None = None,
        thinking_budget: int | None = None,
        json_schema: dict | None = None,
        tools: list[dict] | None = None,
        tool_choice: dict | None = None,
    ) -> AIProviderResponse:
        """
        Send a prompt to the provider and return a normalized response.

        Args:
            prompt: User prompt text
            system_prompt: System context (string or list of cache blocks)
            model: Model identifier
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            prefill: Optional response prefilling (provider-specific, may be ignored)
            thinking_budget: Optional extended thinking token budget (provider-specific, may be ignored)
            json_schema: Optional JSON schema to enforce structured output (provider-specific, may be ignored)
            tools: Optional list of tool definitions for structured output
            tool_choice: Optional tool choice configuration (e.g., {"type": "tool", "name": "..."})

        Returns:
            AIProviderResponse with normalized fields
        """

    async def fetch_available_models(self) -> list[str]:
        """Fetch available models for the provider if supported."""
        ...
