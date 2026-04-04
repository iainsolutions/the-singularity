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

# Gemini model mappings for each difficulty level
# Models must exist in fetch_available_models() catalog to be selectable.
_GEMINI_DIFFICULTY_MODELS = {
    "novice": "gemini-2.5-flash-lite",
    "beginner": "gemini-2.5-flash-lite",
    "intermediate": "gemini-2.5-flash",
    "skilled": "gemini-2.5-flash",
    "advanced": "gemini-2.5-flash",
    "pro": "gemini-2.5-pro",
    "expert": "gemini-2.5-pro",
    "master": "gemini-2.5-pro",
}

_GEMINI_FALLBACK_MODEL = "gemini-2.5-flash"


class GeminiAIProvider(AIProvider):
    """AI provider that communicates with Google's Gemini models."""

    name = "gemini"

    _available_models: ClassVar[list[str] | None] = None
    _models_fetch_attempted: ClassVar[bool] = False
    _missing_usage_metadata_count: ClassVar[int] = 0  # Track API changes

    def __init__(self, *, api_key: str, config: dict | None = None) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")

        self._config = config or {}
        self._client = genai.Client(api_key=api_key)

    async def fetch_available_models(self) -> list[str]:
        """Fetch the list of models available to this API key.

        Why Hardcoded List:
        Unlike OpenAI and Anthropic, Google's Gemini API doesn't provide
        an endpoint to list base models. The API's models.list() endpoint
        only returns tuned/fine-tuned models, not the public base models.

        Maintenance:
        - List updated: 2025-01-14 (Gemini 2.5 series)
        - Override via: GEMINI_AVAILABLE_MODELS="model1,model2,..." env var
        - Check for new models: https://ai.google.dev/gemini-api/docs/models

        Returns:
            List of model identifiers (without 'models/' prefix)
        """
        if self.__class__._available_models is not None:
            return self.__class__._available_models

        if self.__class__._models_fetch_attempted:
            return []

        self.__class__._models_fetch_attempted = True

        # Check for environment variable override
        env_models = os.getenv("GEMINI_AVAILABLE_MODELS")
        if env_models:
            models = [m.strip() for m in env_models.split(",")]
            logger.info(f"Using GEMINI_AVAILABLE_MODELS override: {models}")
        else:
            # Gemini base models (not fetchable via API, hardcoded list)
            # Updated 2025-01-14: Gemini 2.5 series models
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
            logger.debug(f"No models fetched yet, using desired model: {desired_model}")
            return desired_model

        if desired_model in available_models:
            return desired_model

        # Try fallback
        if _GEMINI_FALLBACK_MODEL in available_models:
            logger.warning(
                f"Desired model '{desired_model}' not available for difficulty '{difficulty}', "
                f"using fallback: {_GEMINI_FALLBACK_MODEL}"
            )
            return _GEMINI_FALLBACK_MODEL

        # Return first available as last resort
        fallback = available_models[0]
        logger.warning(
            f"Neither desired model '{desired_model}' nor fallback '{_GEMINI_FALLBACK_MODEL}' "
            f"available for difficulty '{difficulty}', using first available: {fallback}"
        )
        return fallback

    @classmethod
    def get_difficulty_models(cls) -> dict[str, str]:
        """
        Get model mappings for each difficulty level.

        Public method to access difficulty-to-model mapping without
        exposing internal implementation details.
        """
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
        """
        Send message to Gemini.

        Args:
            prompt: User prompt text
            system_prompt: System context (string or list of cache blocks)
            model: Model identifier
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            prefill: Ignored (Gemini doesn't support prefilling)
            thinking_budget: Ignored (not applicable to Gemini)
            tools: Tool definitions (Gemini function calling support TBD)
            tool_choice: Tool choice configuration (ignored for now)

        Returns:
            AIProviderResponse with normalized fields

        Raises:
            ValueError: Invalid input parameters
            AIProviderRateLimitError: Rate limit exceeded
            AIProviderTimeoutError: Request timeout
            AIProviderConnectionError: Connection failed
            AIProviderError: Other provider errors
        """
        # Input validation
        if not prompt or not isinstance(prompt, str):
            raise ValueError("prompt must be a non-empty string")
        if not model or not isinstance(model, str):
            raise ValueError("model must be a non-empty string")
        # Validate model identifier format (prevent malformed model names)
        if "/" in model and not model.startswith("models/"):
            raise ValueError(
                f"Invalid model identifier '{model}'. "
                f"Models with '/' must start with 'models/' prefix."
            )
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        # Gemini supports temperature range: [0.0, 2.0]
        # https://ai.google.dev/gemini-api/docs/models/generative-models#model-parameters
        if not isinstance(temperature, (int, float)) or not (0.0 <= temperature <= 2.0):
            raise ValueError("temperature must be a number between 0.0 and 2.0")
        if system_prompt is not None and not isinstance(system_prompt, (str, list)):
            raise ValueError("system_prompt must be a string or list")

        try:
            # Normalize system prompt
            system_instruction = self._normalize_system_prompt(system_prompt)

            # Gemini API requires 'models/' prefix for all model identifiers
            api_model = model if model.startswith("models/") else f"models/{model}"

            # Build generation config
            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            # Add system instruction if provided
            if system_instruction:
                config.system_instruction = system_instruction

            # Call Gemini API (wrapped in thread to avoid blocking event loop)
            #
            # IMPORTANT: Async/Sync Mismatch and Performance Implications
            #
            # The google-genai SDK (v0.2.2) only provides synchronous client.
            # We use asyncio.to_thread() to run the blocking call in a thread pool,
            # preventing event loop blocking that would stall other coroutines.
            #
            # Performance characteristics:
            # - Thread pool overhead: ~1ms per call (negligible vs API latency)
            # - Preserves FastAPI concurrency for other requests/websockets
            # - No impact on response quality or token counting
            #
            # Alternative considered: google.generativeai.GenerativeModel.generate_content_async()
            # Not used because google-genai SDK doesn't expose async methods yet.
            #
            # Future: When google-genai adds native async support, replace with:
            #   response = await self._client.models.generate_content_async(...)
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=api_model,
                contents=prompt,
                config=config,
            )

            # Extract token counts
            usage = response.usage_metadata if hasattr(response, "usage_metadata") else None
            if usage:
                input_tokens = getattr(usage, "prompt_token_count", 0)
                output_tokens = getattr(usage, "candidates_token_count", 0)
                # Gemini has cached_token_count for caching support
                cached_tokens = getattr(usage, "cached_token_count", 0)
            else:
                # Fallback if usage metadata is unavailable
                # This could indicate API changes - log warning to catch early
                self.__class__._missing_usage_metadata_count += 1
                logger.warning(
                    f"Gemini response missing usage_metadata for model '{api_model}'. "
                    f"This may indicate an API change. Defaulting token counts to 0."
                )
                input_tokens = 0
                output_tokens = 0
                cached_tokens = 0

            # Extract response text
            text = response.text if hasattr(response, "text") else ""

        except errors.ClientError as exc:
            # Client-side errors (4xx): rate limits, invalid requests, auth failures
            if exc.code == 429:  # Rate limit exceeded
                raise AIProviderRateLimitError(str(exc)) from exc
            elif exc.code == 408:  # Request timeout
                raise AIProviderTimeoutError(str(exc)) from exc
            else:
                raise AIProviderError(str(exc)) from exc
        except errors.ServerError as exc:
            # Server-side errors (5xx): timeouts, service unavailable, internal errors
            if exc.code in (504, 408):  # Gateway timeout or request timeout
                raise AIProviderTimeoutError(str(exc)) from exc
            elif exc.code in (503, 502, 500):  # Service unavailable or server error
                raise AIProviderConnectionError(str(exc)) from exc
            else:
                raise AIProviderError(str(exc)) from exc
        except errors.APIError as exc:
            # Catch-all for other Gemini API errors
            logger.error(f"Gemini API error: {exc}")
            raise AIProviderError(str(exc)) from exc
        except Exception as exc:
            # Non-Gemini exceptions (e.g., network errors before API call)
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
        """Convert system prompt to provider-specific format."""
        if isinstance(system_prompt, str):
            return system_prompt

        # Extract text from cache blocks (list format from Anthropic)
        # Gemini doesn't use the same cache_control metadata structure
        parts = []
        for block in system_prompt:
            if isinstance(block, str):
                # Handle string items in list
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
            elif isinstance(block, dict):
                # Warn about dict blocks without 'text' field
                logger.warning(
                    f"System prompt block missing 'text' field: {block.get('type', 'unknown')}"
                )
        return "\n\n".join(parts)
