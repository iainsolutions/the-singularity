"""Models package for Innovation game."""

from .card import Card, CardColor, DogmaEffect, Symbol
from .expansion import Expansion, ExpansionConfig
from .forecast_zone import ForecastZone
from .game import ActionLogEntry, ActionType, Game, GamePhase, GameState
from .player import Player
from .safe import Safe

# Rebuild models with forward references (Pydantic v2 requirement)
# This resolves the Safe and ForecastZone forward references in Player model
Player.model_rebuild()
Game.model_rebuild()

__all__ = [
    "Card",
    "CardColor",
    "DogmaEffect",
    "Symbol",
    "Expansion",
    "ExpansionConfig",
    "ForecastZone",
    "ActionLogEntry",
    "ActionType",
    "Game",
    "GamePhase",
    "GameState",
    "Player",
    "Safe",
]
