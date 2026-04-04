"""Google Gemini implementation of the AI provider abstraction."""

from __future__ import annotations

import asyncio
import os
from typing import ClassVar

from google import genai
from google.genai import errors, types

from logging_config import get_logger
from services.ai_providers.base import (
    AIProvider,
    AIProviderConnectionError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderResponse,
    AIProviderTimeoutError,
)

# Module-level logger for better performance
logger = get_logger(__name__)

# Gemini model mappings for each difficulty tier
_GEMINI_DIFFICULTY_MODELS = {
    "easy": "gemini-2.5-flash-lite",
    "medium": "gemini-2.5-flash",
    "hard": "gemini-2.5-pro",
}

_GEMINI_FALLBACK_MODEL = "gemini-2.5-flash"


class GeminiAIProvider(AIProvider):
    """AI provider that communicates with Google's Gemini models."""

    name = "gemini"

    _available_models: ClassVar[list[str] | None] = None
    _models_fetch_attempted: ClassVar[bool] = False
    _missing_usage_metadata_count: ClassVar[int] = 0

    def __init__(self, *, api_key: str, config: dict | None = None) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")

        self._config = config or {}
        self._client = genai.Client(api_key=api_key)

    async def fetch_available_models(self) -> list[str]:
        """Fetch the list of models available to this API key.

        Google's Gemini API doesn't provide an endpoint to list base models.
        Uses a hardcoded list, overridable via GEMINI_AVAILABLE_MODELS env var.
        """
        if self.__class__._available_models is not None:
            return self.__class__._available_models

        if self.__class__._models_fetch_attempted:
            return []

        self.__class__._models_fetch_attempted = True

        env_models = os.getenv("GEMINI_AVAILABLE_MODELS")
        if env_models:
            models = [m.strip() for m in env_models.split(",")]
            logger.info(f"Using GEMINI_AVAILABLE_MODELS override: {models}")
        else:
            models = [
                "gemini-2.5-pro",
                "gemini-2.5-flash",
                "gemini-2.5-flash-lite",
                "gemini-2.0-flash",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
            ]
            logger.debug(f"Using default Gemini models: {models}")

        self.__class__._available_models = models
        return models

    def get_model_for_difficulty(self, difficulty: str) -> str:
        """Return the Gemini model configured for the given difficulty."""
        desired_model = _GEMINI_DIFFICULTY_MODELS.get(difficulty, _GEMINI_FALLBACK_MODEL)

        available_models = self.__class__._available_models
        if not available_models:
            return desired_model

        if desired_model in available_models:
            return desired_model

        if _GEMINI_FALLBACK_MODEL in available_models:
            logger.warning(
                f"Desired model '{desired_model}' not available for '{difficulty}', "
                f"using fallback: {_GEMINI_FALLBACK_MODEL}"
            )
            return _GEMINI_FALLBACK_MODEL

        fallback = available_models[0]
        logger.warning(f"Using first available model: {fallback}")
        return fallback

    @classmethod
    def get_difficulty_models(cls) -> dict[str, str]:
        """Get model mappings for each difficulty tier."""
        return _GEMINI_DIFFICULTY_MODELS.copy()

    def supports_prefill(self) -> bool:
        """Gemini does not support response prefilling."""
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
        """Send message to Gemini API."""
        if not prompt or not isinstance(prompt, str):
            raise ValueError("prompt must be a non-empty string")
        if not model or not isinstance(model, str):
            raise ValueError("model must be a non-empty string")
        if "/" in model and not model.startswith("models/"):
            raise ValueError(f"Invalid model identifier '{model}'.")
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        if not isinstance(temperature, (int, float)) or not (0.0 <= temperature <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")

        try:
            system_instruction = self._normalize_system_prompt(system_prompt)

            # Gemini API requires 'models/' prefix
            api_model = model if model.startswith("models/") else f"models/{model}"

            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            if system_instruction:
                config.system_instruction = system_instruction

            # Call Gemini API (wrapped in thread to avoid blocking event loop)
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=api_model,
                contents=prompt,
                config=config,
            )

            usage = response.usage_metadata if hasattr(response, "usage_metadata") else None
            if usage:
                input_tokens = getattr(usage, "prompt_token_count", 0)
                output_tokens = getattr(usage, "candidates_token_count", 0)
                cached_tokens = getattr(usage, "cached_token_count", 0)
            else:
                self.__class__._missing_usage_metadata_count += 1
                logger.warning(
                    f"Gemini response missing usage_metadata for model '{api_model}'."
                )
                input_tokens = 0
                output_tokens = 0
                cached_tokens = 0

            text = response.text if hasattr(response, "text") else ""

        except errors.ClientError as exc:
            if exc.code == 429:
                raise AIProviderRateLimitError(str(exc)) from exc
            elif exc.code == 408:
                raise AIProviderTimeoutError(str(exc)) from exc
            else:
                raise AIProviderError(str(exc)) from exc
        except errors.ServerError as exc:
            if exc.code in (504, 408):
                raise AIProviderTimeoutError(str(exc)) from exc
            elif exc.code in (503, 502, 500):
                raise AIProviderConnectionError(str(exc)) from exc
            else:
                raise AIProviderError(str(exc)) from exc
        except errors.APIError as exc:
            logger.error(f"Gemini API error: {exc}")
            raise AIProviderError(str(exc)) from exc
        except Exception as exc:
            logger.error(f"Gemini connection error: {exc}")
            raise AIProviderConnectionError(f"Connection failed: {exc}") from exc

        return AIProviderResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            raw_response=response,
        )

    def _normalize_system_prompt(self, system_prompt: str | list) -> str:
        """Convert system prompt to plain string from Anthropic-style cache blocks."""
        if isinstance(system_prompt, str):
            return system_prompt

        parts = []
        for block in system_prompt:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        return "\n\n".join(parts)
