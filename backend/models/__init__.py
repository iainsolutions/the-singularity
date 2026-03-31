"""Models package for The Singularity game."""

from .card import Card, CardColor, DogmaEffect, Symbol
from .game import ActionLogEntry, ActionType, Game, GamePhase, GameState
from .player import Player

# Rebuild models with forward references (Pydantic v2 requirement)
Player.model_rebuild()
Game.model_rebuild()

__all__ = [
    "Card",
    "CardColor",
    "DogmaEffect",
    "Symbol",
    "ActionLogEntry",
    "ActionType",
    "Game",
    "GamePhase",
    "GameState",
    "Player",
]
