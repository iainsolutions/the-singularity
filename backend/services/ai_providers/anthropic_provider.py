"""Anthropic implementation of the AI provider abstraction."""

from __future__ import annotations

from typing import ClassVar

import httpx
from anthropic import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncAnthropic,
    RateLimitError,
)
from services.ai_providers.base import (
    AIProvider,
    AIProviderConnectionError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderResponse,
    AIProviderTimeoutError,
)
from services.ai_providers.model_config import (
    get_default_model_for_difficulty,
    get_difficulty_model_map,
    get_fallback_model,
    get_first_available_model,
)


class AnthropicAIProvider(AIProvider):
    """AI provider that communicates with Anthropic's Claude models."""

    name = "anthropic"

    _available_models: ClassVar[list[str] | None] = None
    _models_fetch_attempted: ClassVar[bool] = False

    def __init__(self, *, api_key: str, config: dict | None = None) -> None:
        if not api_key:
            raise ValueError("Anthropic API key is required")

        self._config = config or {}
        # Set reasonable timeout: 120s default, prevents hanging on slow/stuck API calls
        timeout = self._config.get("timeout", 120.0)
        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout)

    async def fetch_available_models(self) -> list[str]:
        """Fetch the list of models available to this API key."""
        if self.__class__._available_models is not None:
            return self.__class__._available_models

        if self.__class__._models_fetch_attempted:
            return []

        self.__class__._models_fetch_attempted = True

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": self._client.api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
        except httpx.HTTPError as exc:  # pragma: no cover - network errors are rare
            raise AIProviderConnectionError(str(exc)) from exc

        if response.status_code == 200:
            data = response.json()
            models = [
                model.get("id", "") for model in data.get("data", []) if model.get("id")
            ]
            self.__class__._available_models = models
            return models

        raise AIProviderError(
            f"Failed to fetch models: HTTP {response.status_code} {response.text}"
        )

    def get_model_for_difficulty(self, difficulty: str) -> str:
        """Return the Claude model configured for the given difficulty."""
        desired_model = get_default_model_for_difficulty(difficulty)

        available_models = self.__class__._available_models
        if not available_models:
            return desired_model

        if desired_model in available_models:
            return desired_model

        fallback_model = get_fallback_model()
        if fallback_model in available_models:
            return fallback_model

        candidate_models = get_difficulty_model_map().values()
        matched_model = get_first_available_model(candidate_models, available_models)
        if matched_model is not None:
            return matched_model

        return available_models[0]

    def supports_prefill(self) -> bool:
        """Anthropic supports response prefilling."""
        return True

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
        Send message to Anthropic with optional response prefilling and extended thinking.

        Args:
            prefill: If provided, Claude will start its response with this text.
                    Useful for forcing structured reasoning (e.g., "<thinking>")
            thinking_budget: Number of tokens for extended thinking (Sonnet 4.5+ only).
                           Enables deeper reasoning before responding.
            json_schema: JSON schema to enforce structured output format
            tools: List of tool definitions for structured output
            tool_choice: Tool choice configuration (e.g., {"type": "tool", "name": "..."})
        """
        try:
            # Build messages list
            messages = [{"role": "user", "content": prompt}]

            # Add prefill as assistant message if provided
            if prefill:
                messages.append({"role": "assistant", "content": prefill})

            # Build API parameters
            api_params = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_prompt,
                "messages": messages,
            }

            # Add JSON schema to system prompt for structured output
            # (Claude API doesn't support response_format yet, so we use prompt engineering)
            if json_schema:
                import json

                schema_str = json.dumps(json_schema, indent=2)
                if isinstance(system_prompt, list):
                    system_prompt.append(
                        {
                            "type": "text",
                            "text": f"\nYou must output JSON that matches this schema:\n{schema_str}",
                        }
                    )
                else:
                    system_prompt = f"{system_prompt}\nYou must output JSON that matches this schema:\n{schema_str}"

            # Extended thinking for capable models (Sonnet 4+, Opus 4+)
            # API constraints: temperature must be 1, max_tokens must exceed budget
            if thinking_budget:
                api_params["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": thinking_budget,
                }
                api_params["temperature"] = 1
                # max_tokens must be > thinking budget (budget + room for response)
                if max_tokens <= thinking_budget:
                    api_params["max_tokens"] = thinking_budget + 2000

            # Add tools for structured output
            if tools:
                api_params["tools"] = tools
                # Force specific tool — but not when thinking is enabled
                # (API rejects tool_choice + thinking combination)
                if tool_choice and "thinking" not in api_params:
                    api_params["tool_choice"] = tool_choice

            message = await self._client.messages.create(**api_params)
        except RateLimitError as exc:
            raise AIProviderRateLimitError(str(exc)) from exc
        except APITimeoutError as exc:
            raise AIProviderTimeoutError(str(exc)) from exc
        except APIConnectionError as exc:
            raise AIProviderConnectionError(str(exc)) from exc
        except APIError as exc:
            raise AIProviderError(str(exc)) from exc

        usage = message.usage
        cached_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0

        # Handle multiple content blocks (e.g., thinking + text, or tool_use)
        content_parts = []
        tool_name = None
        tool_input = None

        for block in message.content:
            block_type = getattr(block, "type", None)
            if block_type == "text" and hasattr(block, "text"):
                content_parts.append(block.text)
            elif block_type == "tool_use":
                # Extract structured tool output
                tool_name = getattr(block, "name", None)
                tool_input = getattr(block, "input", None)

        content = "".join(content_parts) if content_parts else ""

        # If no text blocks found but we have other blocks, try fallback
        if not content and message.content and not tool_name:
            for block in message.content:
                if hasattr(block, "text"):
                    content_parts.append(block.text)
            content = "".join(content_parts)

        # If prefill was used, prepend it to the response for consistency
        if prefill:
            content = prefill + content

        return AIProviderResponse(
            text=content,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=cached_tokens,
            raw_response=message,
            tool_name=tool_name,
            tool_input=tool_input,
        )
