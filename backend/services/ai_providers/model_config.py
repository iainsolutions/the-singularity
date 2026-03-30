"""Shared model configuration utilities for AI providers."""

from __future__ import annotations

import os
from collections.abc import Iterable

# Difficulty levels and their corresponding environment variable overrides.
# Phase 2 Optimization: Upgraded Intermediate (Haiku → Sonnet 3.7) and Skilled (Sonnet 3.7 → Sonnet 4)
#
# Defaults are Claude models. For Gemini, override with environment variables:
# - Novice/Beginner: gemini-2.5-flash-lite
# - Intermediate/Skilled: gemini-2.5-flash
# - Advanced/Pro: gemini-2.5-flash or gemini-2.5-pro
# - Expert/Master: gemini-2.5-pro
# Pinned model versions. Update these when new models are released.
_DIFFICULTY_MODEL_DEFAULTS: list[tuple[str, str, str]] = [
    ("novice", "AI_NOVICE_MODEL", "claude-sonnet-4-5-20250929"),
    ("beginner", "AI_BEGINNER_MODEL", "claude-sonnet-4-5-20250929"),
    ("intermediate", "AI_INTERMEDIATE_MODEL", "claude-sonnet-4-5-20250929"),
    ("skilled", "AI_SKILLED_MODEL", "claude-sonnet-4-5-20250929"),
    ("advanced", "AI_ADVANCED_MODEL", "claude-sonnet-4-5-20250929"),
    ("pro", "AI_PRO_MODEL", "claude-sonnet-4-5-20250929"),
    ("expert", "AI_EXPERT_MODEL", "claude-opus-4-20250514"),
    ("master", "AI_MASTER_MODEL", "claude-opus-4-20250514"),
]

_FALLBACK_MODEL = "claude-sonnet-4-5-20250929"


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
