"""Factory helpers for creating AI providers."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from logging_config import get_logger
from services.ai_providers.anthropic_provider import AnthropicAIProvider
from services.ai_providers.base import AIProvider
from services.ai_providers.gemini_provider import GeminiAIProvider
from services.ai_providers.openai_provider import OpenAIProvider

logger = get_logger(__name__)


_PROVIDER_REGISTRY: dict[str, type[AIProvider]] = {
    AnthropicAIProvider.name: AnthropicAIProvider,
    GeminiAIProvider.name: GeminiAIProvider,
    OpenAIProvider.name: OpenAIProvider,
}


def register_provider(name: str, provider_cls: type[AIProvider]) -> None:
    """Register an AI provider implementation at runtime."""

    normalized = name.lower()
    _PROVIDER_REGISTRY[normalized] = provider_cls


def _validate_ollama_url(url: str) -> str:
    """
    Validate Ollama URL for security (SSRF protection).

    Args:
        url: The Ollama base URL to validate

    Returns:
        The validated URL

    Raises:
        ValueError: If URL is invalid or potentially unsafe
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValueError(f"Invalid URL format: {url}") from e

    # Only allow http/https protocols
    if parsed.scheme not in ["http", "https"]:
        raise ValueError(
            f"Invalid URL scheme '{parsed.scheme}' for Ollama. "
            f"Only http/https allowed. URL: {url}"
        )

    # Validate hostname exists
    if not parsed.hostname:
        raise ValueError(f"URL missing hostname: {url}")

    # Warn on non-localhost in production (SSRF protection)
    is_localhost = parsed.hostname in ["localhost", "127.0.0.1", "::1"]
    is_production = os.getenv("INNOVATION_ENV") == "production"

    if not is_localhost and is_production:
        raise ValueError(
            f"Non-localhost Ollama URL in production: {parsed.hostname}. "
            f"Use private network/VPC with firewall rules. "
            f"See docs/OLLAMA_SETUP.md (Production Deployment section) for security setup."
        )

    if not is_localhost:
        logger.warning(
            f"Ollama URL points to non-localhost: {parsed.hostname}. "
            f"Ensure network is trusted and access is restricted. "
            f"Ollama has NO authentication."
        )

    return url


def create_ai_provider(
    *, api_key: str, config: dict | None = None, provider_name: str | None = None
) -> AIProvider:
    """Create an AI provider instance based on configuration."""

    name = (
        provider_name
        or (config or {}).get("provider")
        or os.getenv("AI_PROVIDER", "anthropic")
    ).lower()

    # Handle Ollama as OpenAI-compatible provider with custom config
    if name == "ollama":
        config = config or {}
        # Add Ollama-specific configuration
        config["is_ollama"] = True  # Explicit flag instead of URL heuristic

        # Validate base_url for security (SSRF protection)
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        config["base_url"] = _validate_ollama_url(base_url)

        config["timeout"] = float(os.getenv("OLLAMA_TIMEOUT", "120.0"))  # Ollama can be slower on CPU
        # Use OpenAI provider with custom base_url
        name = "openai"

    provider_cls = _PROVIDER_REGISTRY.get(name)
    if provider_cls is None:
        available = ", ".join(sorted(_PROVIDER_REGISTRY)) or "<none>"
        raise ValueError(
            f"Unknown AI provider '{name}'. Available providers: {available}"
        )

    return provider_cls(api_key=api_key, config=config)
