"""Shared model configuration utilities for AI providers."""

from __future__ import annotations

import os
from collections.abc import Iterable

# Three difficulty tiers, each backed by a genuinely different model.
# Override via environment variables for alternative providers (Gemini, Ollama, etc.).
# Pinned model versions. Update these when new models are released.
_DIFFICULTY_MODEL_DEFAULTS: list[tuple[str, str, str]] = [
    ("easy", "AI_EASY_MODEL", "claude-haiku-3-5-20241022"),
    ("medium", "AI_MEDIUM_MODEL", "claude-sonnet-4-5-20250929"),
    ("hard", "AI_HARD_MODEL", "claude-opus-4-20250514"),
]

_FALLBACK_MODEL = "claude-haiku-3-5-20241022"


def get_supported_difficulties() -> list[str]:
    """Return the canonical list of supported difficulty levels."""

    return [difficulty for difficulty, _env, _default in _DIFFICULTY_MODEL_DEFAULTS]


def _resolve_model_overrides() -> dict[str, str]:
    """Resolve environment overrides for each difficulty into a model map."""

    model_map: dict[str, str] = {}
    for difficulty, env_key, default in _DIFFICULTY_MODEL_DEFAULTS:
        model_map[difficulty] = os.getenv(env_key, default)
    return model_map


def get_difficulty_model_map() -> dict[str, str]:
    """Return the difficulty-to-model mapping, applying environment overrides."""

    return _resolve_model_overrides()


def get_default_model_for_difficulty(difficulty: str) -> str:
    """Return the configured model for the provided difficulty level."""

    return get_difficulty_model_map().get(difficulty, _FALLBACK_MODEL)


def get_fallback_model() -> str:
    """Return the default fallback model when a preferred option is unavailable."""

    return _FALLBACK_MODEL


def get_first_available_model(
    candidates: Iterable[str], available: Iterable[str]
) -> str | None:
    """Return the first candidate model present in the available model list."""

    available_set = set(available)
    for candidate in candidates:
        if candidate in available_set:
            return candidate
    return None
