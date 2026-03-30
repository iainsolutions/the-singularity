"""
State management for Dogma v2 system.

This module provides enhanced state capture, comparison,
and transaction management capabilities.
"""

from .capture import GameStateSnapshot, PlayerStateSnapshot, StateCapture

__all__ = [
    "GameStateSnapshot",
    "PlayerStateSnapshot",
    "StateCapture",
]
