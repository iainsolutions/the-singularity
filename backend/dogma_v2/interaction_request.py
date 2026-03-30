"""
InteractionRequest - Request model for player interactions during dogma execution
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class InteractionType(Enum):
    """Types of player interactions"""

    SELECT_CARDS = "select_cards"
    SELECT_ACHIEVEMENT = "select_achievement"
    CHOOSE_OPTION = "choose_option"
    RETURN_CARDS = "return_cards"
    SELECT_COLOR = "select_color"
    SELECT_SYMBOL = "select_symbol"
    CHOOSE_HIGHEST_TIE = "choose_highest_tie"


@dataclass(frozen=True)
class InteractionRequest:
    """Request for player interaction during dogma execution"""

    id: str  # Unique interaction ID
    player_id: str  # Player who must respond
    type: InteractionType  # Type of interaction
    data: dict[str, Any]  # Type-specific interaction data
    message: str  # Human-readable message for UI
    timeout: int | None = None  # Seconds before auto-resolve

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "id": self.id,
            "player_id": self.player_id,
            "type": self.type.value,
            "data": self.data,
            "message": self.message,
            "timeout": self.timeout,
        }
