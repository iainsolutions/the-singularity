"""OpenAI implementation of the AI provider abstraction."""

from __future__ import annotations

from typing import ClassVar

import openai

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


# OpenAI model mappings for each difficulty level
# Models must pass fetch_available_models() gpt-* filter to be selectable.
_OPENAI_DIFFICULTY_MODELS = {
    "novice": "gpt-4o-mini",
    "beginner": "gpt-4o-mini",
    "intermediate": "gpt-4o",
    "skilled": "gpt-4o",
    "advanced": "gpt-4o",
    "pro": "gpt-4o",
    "expert": "gpt-4o",
    "master": "gpt-4o",
}

_OPENAI_FALLBACK_MODEL = "gpt-4o-mini"

# Ollama model mappings (when using Ollama as OpenAI-compatible backend)
# Optimized for game AI - balancing speed, quality, and hardware requirements
# Models must be pulled first: ollama pull <model>
_OLLAMA_DIFFICULTY_MODELS = {
    "novice": "phi3.5:3.8b",           # Fast, simple decisions (~2-4GB VRAM)
    "beginner": "gemma2:2b",           # Quick responses (~2GB VRAM)
    "intermediate": "llama3.1:8b",     # Good reasoning (~5GB VRAM)
    "skilled": "qwen2.5:7b",           # Strong instruction following (~5GB VRAM)
    "advanced": "mistral-small:22b",   # Advanced planning (~14GB VRAM)
    "pro": "phi4-reasoning:14b",       # Complex reasoning (~9GB VRAM)
    "expert": "deepseek-r1:14b",       # Strategic depth (~9GB VRAM)
    "master": "llama3.1:70b",          # Maximum capability (~40GB VRAM, multi-GPU)
}

_OLLAMA_FALLBACK_MODEL = "llama3.1:8b"


class OpenAIProvider(AIProvider):
    """AI provider that communicates with OpenAI's GPT models."""

    name = "openai"

    _available_models: ClassVar[list[str] | None] = None
    _models_fetch_attempted: ClassVar[bool] = False

    def __init__(self, *, api_key: str, config: dict | None = None) -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required")

        self._config = config or {}

        # Configure timeout (default 60s, configurable via config)
        # Validate timeout is reasonable (between 1s and 600s)
        timeout = self._config.get("timeout", 60.0)
        if not isinstance(timeout, (int, float)) or timeout < 1 or timeout > 600:
            raise ValueError(
                f"Invalid timeout: {timeout}. Must be between 1 and 600 seconds"
            )

        # Support custom base_url for Ollama or other OpenAI-compatible backends
        # Ollama: http://localhost:11434/v1
        base_url = self._config.get("base_url")

        # Explicit flag from factory instead of URL heuristic
        self._is_ollama = self._config.get("is_ollama", False)

        if base_url:
            logger.info(f"Using custom OpenAI-compatible endpoint: {base_url}")
            if self._is_ollama:
                logger.info("Using Ollama backend - free local LLM models")

        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            timeout=timeout,
            base_url=base_url
        )

        # Test Ollama connectivity on initialization (optional health check)
        if self._is_ollama and base_url:
            self._check_ollama_health(base_url)

    def _check_ollama_health(self, base_url: str) -> None:
        """
        Check if Ollama server is reachable (synchronous health check).

        This is a best-effort check during initialization. Failures are logged
        as warnings but don't prevent provider creation (graceful degradation).

        Uses short timeout (2s) to avoid blocking provider initialization.
        """
        try:
            import httpx  # Already in requirements.txt (also used by openai package)

            # Strip /v1 suffix to get base Ollama URL
            ollama_base = base_url.rstrip("/v1").rstrip("/")

            # Quick health check with short timeout (2s max)
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{ollama_base}/api/tags")

                if response.status_code == 200:
                    models_data = response.json()
                    model_count = len(models_data.get("models", []))
                    logger.info(
                        f"✅ Ollama server healthy at {ollama_base} "
                        f"({model_count} models available)"
                    )
                else:
                    # INFO level: non-200 status is unusual but provider works without health check
                    logger.info(
                        f"Ollama server returned status {response.status_code} at {ollama_base}. "
                        f"Server may not be fully operational. Provider will work if Ollama becomes available."
                    )

        except ImportError:
            logger.debug("httpx not available for Ollama health check (optional)")
        except Exception as e:
            # INFO level: graceful degradation, not a critical error
            logger.info(
                f"Could not verify Ollama availability at {base_url}: {e}. "
                f"This is normal if Ollama isn't running yet. "
                f"Provider will work when Ollama becomes available."
            )

    async def fetch_available_models(self) -> list[str]:
        """Fetch the list of models available to this API key."""
        # Ollama: Skip model fetch (local models, no API list endpoint)
        if self._is_ollama:
            logger.debug("Skipping model fetch for Ollama (using local model list)")
            # Return empty list - model validation handled by get_model_for_difficulty
            return []

        if self.__class__._available_models is not None:
            return self.__class__._available_models

        if self.__class__._models_fetch_attempted:
            return []

        self.__class__._models_fetch_attempted = True

        try:
            models = await self._client.models.list()
            # Filter to GPT models only (OpenAI)
            model_ids = [
                model.id
                for model in models.data
                if model.id.startswith("gpt-")
            ]
            self.__class__._available_models = model_ids
            return model_ids

        except openai.APIConnectionError as exc:
            raise AIProviderConnectionError(str(exc)) from exc
        except openai.APIError as exc:
            raise AIProviderError(f"Failed to fetch models: {exc}") from exc

    def get_model_for_difficulty(self, difficulty: str) -> str:
        """Return the GPT/Ollama model configured for the given difficulty."""
        # Use Ollama models if detected
        if self._is_ollama:
            return _OLLAMA_DIFFICULTY_MODELS.get(difficulty, _OLLAMA_FALLBACK_MODEL)

        # Otherwise use OpenAI models
        desired_model = _OPENAI_DIFFICULTY_MODELS.get(difficulty, _OPENAI_FALLBACK_MODEL)

        available_models = self.__class__._available_models
        if not available_models:
            return desired_model

        if desired_model in available_models:
            return desired_model

        # Model not available - try fallback
        logger.warning(
            f"OpenAI model '{desired_model}' not available for difficulty '{difficulty}', "
            f"trying fallback"
        )

        # Try fallback model
        if _OPENAI_FALLBACK_MODEL in available_models:
            logger.info(f"Using fallback model: {_OPENAI_FALLBACK_MODEL}")
            return _OPENAI_FALLBACK_MODEL

        # Try any available GPT-4 model
        for model in available_models:
            if model.startswith("gpt-4"):
                logger.info(f"Using GPT-4 fallback: {model}")
                return model

        # Last resort: return first available model
        fallback = available_models[0] if available_models else desired_model
        logger.warning(f"No GPT-4 models available, using: {fallback}")
        return fallback

    def supports_prefill(self) -> bool:
        """OpenAI does not support response prefilling."""
        return False

    @classmethod
    def get_difficulty_models(cls) -> dict[str, str]:
        """
        Get model mappings for each difficulty level.

        Public method to access difficulty-to-model mapping without
        exposing internal implementation details.

        Note: Returns OpenAI models by default. Instance method should be used
        for Ollama-specific mappings (requires self._is_ollama check).
        """
        return _OPENAI_DIFFICULTY_MODELS.copy()


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
        Send message to OpenAI Chat Completions API.

        Note: OpenAI does not support prefill or thinking_budget parameters.
        These are gracefully ignored (provider-agnostic design).

        Args:
            prompt: User prompt text
            system_prompt: System context (string or list of cache blocks from Anthropic format)
            model: OpenAI model identifier (e.g., "gpt-4-turbo")
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 2.0)
            prefill: Ignored for OpenAI (Anthropic-specific feature)
            thinking_budget: Ignored for OpenAI (use o1 models for extended reasoning)
            tools: Optional list of Anthropic-format tools (converted to OpenAI functions)
            tool_choice: Optional tool choice configuration
        """
        try:
            # Convert system prompt to OpenAI format
            messages = []

            # Handle system prompt (string or list of cache blocks)
            if isinstance(system_prompt, list):
                # Extract text from Anthropic-style cache blocks
                system_text_parts = []
                skipped_blocks = 0

                for block in system_prompt:
                    if isinstance(block, dict):
                        if "text" in block:
                            system_text_parts.append(block["text"])
                        else:
                            # Log non-text blocks for debugging
                            block_type = block.get("type", "unknown")
                            logger.debug(
                                f"Skipping non-text cache block: type={block_type}"
                            )
                            skipped_blocks += 1
                    else:
                        logger.warning(
                            f"Invalid cache block format (not a dict): {type(block)}"
                        )

                if skipped_blocks > 0:
                    logger.debug(f"Skipped {skipped_blocks} non-text cache blocks")

                system_text = "\n\n".join(system_text_parts)
                if system_text:
                    messages.append({"role": "system", "content": system_text})
                elif system_prompt:
                    # If all blocks were non-text, log error
                    logger.error(
                        "All cache blocks were non-text - no system prompt added"
                    )
            elif system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # Add user prompt
            messages.append({"role": "user", "content": prompt})

            # Note: prefill and thinking_budget are ignored
            # OpenAI doesn't support prefilling (Anthropic-specific)
            # For extended reasoning, use o1-preview or o1-mini models instead

            # Build API params
            api_params = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            # Convert Anthropic-format tools to OpenAI function format
            if tools:
                openai_tools = []
                for tool in tools:
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool.get("description", ""),
                            "parameters": tool.get("input_schema", {}),
                        }
                    })
                api_params["tools"] = openai_tools

                # Convert tool_choice format
                if tool_choice and tool_choice.get("type") == "tool":
                    api_params["tool_choice"] = {
                        "type": "function",
                        "function": {"name": tool_choice["name"]}
                    }

            response = await self._client.chat.completions.create(**api_params)

            # Validate response has choices
            if not response.choices:
                raise AIProviderError("OpenAI returned empty response (no choices)")

            choice = response.choices[0]
            content = choice.message.content or ""
            tool_name = None
            tool_input = None

            # Check for tool calls
            if choice.message.tool_calls:
                import json
                tool_call = choice.message.tool_calls[0]
                tool_name = tool_call.function.name
                try:
                    tool_input = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse tool arguments: {tool_call.function.arguments}")
                    tool_input = {}

            # Get token usage
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0

            # OpenAI Prompt Caching Limitations:
            # - Caching is automatic for prompts >1024 tokens
            # - 50% discount on cached tokens (vs Anthropic's 90%)
            # - Cache stats not exposed in API response
            # - Cannot track cache hits like Anthropic
            # Reference: https://platform.openai.com/docs/guides/prompt-caching
            cached_tokens = 0  # Not available from OpenAI API

            return AIProviderResponse(
                text=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                raw_response=response,
                tool_name=tool_name,
                tool_input=tool_input,
            )

        except openai.RateLimitError as exc:
            raise AIProviderRateLimitError(str(exc)) from exc
        except openai.APITimeoutError as exc:
            raise AIProviderTimeoutError(str(exc)) from exc
        except openai.APIConnectionError as exc:
            raise AIProviderConnectionError(str(exc)) from exc
        except openai.NotFoundError as exc:
            # Ollama: Model not found (likely not pulled)
            if self._is_ollama:
                raise AIProviderError(
                    f"Ollama model '{model}' not found. "
                    f"Pull the model first: ollama pull {model}"
                ) from exc
            raise AIProviderError(str(exc)) from exc
        except openai.APIError as exc:
            raise AIProviderError(str(exc)) from exc
