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


# OpenAI model mappings for each difficulty tier
_OPENAI_DIFFICULTY_MODELS = {
    "easy": "gpt-4o-mini",
    "medium": "gpt-4o",
    "hard": "gpt-4o",
}

_OPENAI_FALLBACK_MODEL = "gpt-4o-mini"

# Ollama model mappings (when using Ollama as OpenAI-compatible backend)
# Models must be pulled first: ollama pull <model>
_OLLAMA_DIFFICULTY_MODELS = {
    "easy": "gemma2:2b",              # Fast, simple decisions (~2GB VRAM)
    "medium": "llama3.1:8b",          # Good reasoning (~5GB VRAM)
    "hard": "deepseek-r1:14b",        # Strategic depth (~9GB VRAM)
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
        timeout = self._config.get("timeout", 60.0)
        if not isinstance(timeout, (int, float)) or timeout < 1 or timeout > 600:
            raise ValueError(
                f"Invalid timeout: {timeout}. Must be between 1 and 600 seconds"
            )

        # Support custom base_url for Ollama or other OpenAI-compatible backends
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

        # Test Ollama connectivity on initialization
        if self._is_ollama and base_url:
            self._check_ollama_health(base_url)

    def _check_ollama_health(self, base_url: str) -> None:
        """Best-effort Ollama health check. Failures logged as warnings."""
        try:
            import httpx

            ollama_base = base_url.rstrip("/v1").rstrip("/")
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{ollama_base}/api/tags")
                if response.status_code == 200:
                    models_data = response.json()
                    model_count = len(models_data.get("models", []))
                    logger.info(
                        f"Ollama server healthy at {ollama_base} "
                        f"({model_count} models available)"
                    )
                else:
                    logger.info(
                        f"Ollama server returned status {response.status_code} at {ollama_base}."
                    )
        except ImportError:
            logger.debug("httpx not available for Ollama health check")
        except Exception as e:
            logger.info(
                f"Could not verify Ollama at {base_url}: {e}. "
                f"Provider will work when Ollama becomes available."
            )

    async def fetch_available_models(self) -> list[str]:
        """Fetch the list of models available to this API key."""
        if self._is_ollama:
            logger.debug("Skipping model fetch for Ollama (using local model list)")
            return []

        if self.__class__._available_models is not None:
            return self.__class__._available_models

        if self.__class__._models_fetch_attempted:
            return []

        self.__class__._models_fetch_attempted = True

        try:
            models = await self._client.models.list()
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
        if self._is_ollama:
            return _OLLAMA_DIFFICULTY_MODELS.get(difficulty, _OLLAMA_FALLBACK_MODEL)

        desired_model = _OPENAI_DIFFICULTY_MODELS.get(difficulty, _OPENAI_FALLBACK_MODEL)

        available_models = self.__class__._available_models
        if not available_models:
            return desired_model

        if desired_model in available_models:
            return desired_model

        logger.warning(
            f"OpenAI model '{desired_model}' not available for difficulty '{difficulty}', "
            f"trying fallback"
        )

        if _OPENAI_FALLBACK_MODEL in available_models:
            return _OPENAI_FALLBACK_MODEL

        for model in available_models:
            if model.startswith("gpt-4"):
                return model

        fallback = available_models[0] if available_models else desired_model
        logger.warning(f"No GPT-4 models available, using: {fallback}")
        return fallback

    def supports_prefill(self) -> bool:
        """OpenAI does not support response prefilling."""
        return False

    @classmethod
    def get_difficulty_models(cls) -> dict[str, str]:
        """Get model mappings for each difficulty tier."""
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
        """Send message to OpenAI Chat Completions API."""
        try:
            messages = []

            # Handle system prompt (string or list of cache blocks)
            if isinstance(system_prompt, list):
                system_text_parts = []
                for block in system_prompt:
                    if isinstance(block, dict) and "text" in block:
                        system_text_parts.append(block["text"])
                system_text = "\n\n".join(system_text_parts)
                if system_text:
                    messages.append({"role": "system", "content": system_text})
            elif system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

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

                if tool_choice and tool_choice.get("type") == "tool":
                    api_params["tool_choice"] = {
                        "type": "function",
                        "function": {"name": tool_choice["name"]}
                    }

            response = await self._client.chat.completions.create(**api_params)

            if not response.choices:
                raise AIProviderError("OpenAI returned empty response (no choices)")

            choice = response.choices[0]
            content = choice.message.content or ""
            tool_name = None
            tool_input = None

            if choice.message.tool_calls:
                import json
                tool_call = choice.message.tool_calls[0]
                tool_name = tool_call.function.name
                try:
                    tool_input = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse tool arguments: {tool_call.function.arguments}")
                    tool_input = {}

            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
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
            if self._is_ollama:
                raise AIProviderError(
                    f"Ollama model '{model}' not found. "
                    f"Pull the model first: ollama pull {model}"
                ) from exc
            raise AIProviderError(str(exc)) from exc
        except openai.APIError as exc:
            raise AIProviderError(str(exc)) from exc
