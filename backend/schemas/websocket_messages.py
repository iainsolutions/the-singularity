"""
WebSocket message models for type-safe communication.
CRITICAL: These models define the CONTRACT between frontend and backend.
Any changes must be reflected in TypeScript definitions.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MessageType(str, Enum):
    """All possible WebSocket message types"""

    GAME_STATE = "game_state"
    DOGMA_INTERACTION = "dogma_interaction"
    PLAYER_ACTION = "player_action"
    ERROR = "error"
    CONNECTION = "connection"


class InteractionType(str, Enum):
    """Types of player interactions"""

    SELECT_CARDS = "select_cards"
    CHOOSE_OPTION = "choose_option"
    SELECT_BOARD = "select_board"
    SELECT_PLAYER = "select_player"
    SELECT_ACHIEVEMENT = "select_achievement"
    SELECT_COLOR = "select_color"
    ORDER_CARDS = "order_cards"  # Cities: Search icon card ordering


class WebSocketMessage(BaseModel):
    """Base class for all WebSocket messages"""

    type: MessageType
    game_id: str = Field("", max_length=50)  # Allow empty string, will be set by caller
    player_id: str | None = Field(
        None, max_length=50
    )  # Optional, will be set by caller
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sequence_number: int | None = Field(None, ge=0)

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class DogmaInteractionRequest(WebSocketMessage):
    """Request for player interaction during dogma execution"""

    type: Literal[MessageType.DOGMA_INTERACTION]
    interaction_type: InteractionType
    data: dict[str, Any]  # Pydantic models converted to dict for JSON serialization
    timeout_seconds: int | None = Field(300, ge=30, le=600)
    can_cancel: bool = Field(True)
    execution_results: list[str] | None = Field(
        None
    )  # Recent execution context to show player what just happened


class InteractionResponse(BaseModel):
    """Response to an interaction request"""

    interaction_id: str = Field(..., min_length=1)
    selected_cards: list[str] | None = Field(None)
    selected_achievements: list[str] | None = Field(None)
    chosen_option: str | None = Field(None)
    selected_color: str | None = Field(None)
    ordered_card_ids: list[str] | None = Field(None)  # Cities: Card ordering response
    cancelled: bool = Field(False)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def validate_response_data(self) -> "InteractionResponse":
        """Ensure at least one response field is provided unless cancelled"""
        if not self.cancelled:
            # Check if at least one response field is provided
            if (
                not self.selected_cards
                and not self.selected_achievements
                and not self.chosen_option
                and not self.selected_color
            ):
                raise ValueError(
                    "Must provide either selected_cards, selected_achievements, chosen_option, or selected_color unless cancelled=True"
                )
        return self


class ErrorResponse(WebSocketMessage):
    """Error message with categorization and suggested actions"""

    type: Literal[MessageType.ERROR]
    error_code: str
    error_category: str  # field_name_mismatch, invalid_interaction, etc.
    message: str
    details: dict[str, Any] | None = None
    suggested_action: str | None = None
    retry_possible: bool = False


class GameStateUpdate(WebSocketMessage):
    """Game state update message"""

    type: Literal[MessageType.GAME_STATE]
    game_state: dict[str, Any]
    updated_fields: list[str] | None = None
