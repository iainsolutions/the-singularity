"""
Pydantic schemas for type-safe communication.
This package contains all data models for WebSocket messages and API contracts.
"""

from typing import Any

from pydantic import BaseModel

from models.card import Card
from models.game import ActionType


# Legacy schemas for API compatibility
class ActionRequest(BaseModel):
    player_id: str
    action_type: ActionType
    age: int | None = None
    card_name: str | None = None


class ActionResponse(BaseModel):
    success: bool
    action: str | None = None
    error: str | None = None
    error_code: str | None = None
    card_drawn: Card | None = None
    card_melded: Card | None = None
    card: Card | None = None
    effects: list[str] | None = None


class CreateGameRequest(BaseModel):
    created_by: str | None = None
    enabled_expansions: list[str] = []  # List of expansion names to enable


class CreateGameResponse(BaseModel):
    game_id: str
    player_id: str | None = None
    game_state: dict | None = None
    token: str | None = None


class JoinGameRequest(BaseModel):
    name: str | None = None


class JoinGameResponse(BaseModel):
    player_id: str
    game_state: dict  # Changed from Game to dict for JSON serialization
    token: str


class StartGameResponse(BaseModel):
    game_state: dict
    success: bool


class DogmaResponseRequest(BaseModel):
    player_id: str
    transaction_id: str | None = None  # Correlate with pending interaction
    card_id: str | None = None
    selected_cards: list[str] | None = None
    selected_achievement: str | None = (
        None  # For single achievement selection (AI format)
    )
    selected_achievements: list[
        str
    ] | None = None  # For multi-achievement selection (UI format)
    chosen_option: str | None = None  # For ChooseOption primitive responses
    selected_color: str | None = None  # For SelectColor primitive responses
    decline: bool | None = False


class ErrorResponse(BaseModel):
    error: str
    error_code: str
    detail: dict[str, Any] | None = None


from .interaction_data import *

# Import the new Pydantic models
from .websocket_messages import *
