from typing import Any

from pydantic import BaseModel

from models.card import Card
from models.game import ActionType, Game
from models.player import Player


class CreateGameResponse(BaseModel):
    game_id: str
    player_id: str | None = None
    game_state: dict | None = None
    token: str | None = None


class CreateGameRequest(BaseModel):
    created_by: str | None = None
    enabled_expansions: list[str] = []  # List of expansion names to enable


class JoinGameRequest(BaseModel):
    name: str | None = None


class JoinGameResponse(BaseModel):
    player_id: str
    game_state: Game
    token: str  # JWT token for WebSocket authentication


class StartGameResponse(BaseModel):
    game_state: Game
    success: bool


class ActionRequest(BaseModel):
    player_id: str
    action_type: ActionType
    age: int | None = None
    card_name: str | None = None
    # UNSEEN EXPANSION: Achieve/meld from Safe
    source: str | None = None  # "hand", "board", "safe"
    safe_index: int | None = None  # Index in Safe (for source="safe")


class DogmaResponseRequest(BaseModel):
    player_id: str
    transaction_id: str | None = None  # Correlate with pending interaction
    card_id: str | None = None  # For single card selection
    selected_cards: list[str] | None = None  # For multi-card selection (card IDs)
    selected_achievement: str | None = (
        None  # For single achievement selection (AI format)
    )
    selected_achievements: list[
        str
    ] | None = None  # For multi-achievement selection (UI format)
    chosen_option: str | None = None  # For ChooseOption primitive responses
    decline: bool | None = False
    cancelled: bool | None = None  # AI uses "cancelled", map to decline

    def model_post_init(self, __context):
        """Map cancelled to decline for AI compatibility"""
        if self.cancelled and not self.decline:
            self.decline = True


class ErrorResponse(BaseModel):
    """Standardized error response"""

    error: str
    error_code: str
    detail: dict[str, Any] | None = None


class ActionResponse(BaseModel):
    success: bool
    action: str | None = None
    error: str | None = None
    error_code: str | None = None
    card_drawn: Card | None = None
    card_melded: Card | None = None
    card: Card | None = None
    effects: list[str] | None = None
    achievement: Card | None = None
    game_state: Game
    winner: Player | None = None
    pending_interaction: dict | None = None
