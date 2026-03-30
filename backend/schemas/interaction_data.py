"""
Data models for player interactions.
CRITICAL: The field 'eligible_cards' is CANONICAL.
NEVER use 'cards' for selection - this has caused multiple bugs.
"""
from enum import Enum
from typing import Any, Literal, Union

from pydantic import BaseModel, Field, model_validator, validator


class CardReference(BaseModel):
    """Reference to a card in the game"""

    card_id: str = Field(..., description="Unique card identifier")
    name: str = Field(..., description="Card name")
    age: int = Field(..., ge=1, le=10, description="Card age")
    color: str = Field(..., description="Card color")
    location: str = Field(
        ..., description="Card location (hand, board, score_pile, etc.)"
    )


class CardSource(str, Enum):
    """Where cards can be selected from"""

    HAND = "hand"
    BOARD = "board"
    SCORE_PILE = "score_pile"
    ALL_CARDS = "all"


class InteractionData(BaseModel):
    """Base class for interaction data"""

    message: str = Field(..., min_length=1, max_length=200)
    source_player: str = Field(..., description="Player who triggered interaction")


class CardSelectionData(InteractionData):
    """
    Data for card selection interactions.

    Phase 1A: Now uses eligible_card_ids (just IDs) instead of full card objects.
    The frontend uses these IDs for O(1) lookups against player's actual cards.
    Combined with clickable_locations and clickable_player_ids for complete UI hints.
    """

    type: Literal["select_cards"]
    eligible_card_ids: list[str] = Field(
        ...,
        description="Card IDs eligible for selection (Phase 1A: O(1) frontend lookup)",
    )
    min_count: int = Field(1, ge=0, le=10, description="Minimum cards to select")
    max_count: int = Field(1, ge=1, le=10, description="Maximum cards to select")
    source: CardSource = Field(CardSource.HAND, description="Source of cards")
    is_optional: bool = Field(False, description="Whether selection is optional")

    @validator("max_count")
    def validate_counts(cls, v, values):
        """Ensure max_count >= min_count"""
        min_count = values.get("min_count", 0)
        if v < min_count:
            raise ValueError(f"max_count ({v}) must be >= min_count ({min_count})")
        return v

    @model_validator(mode="after")
    def validate_card_selection_constraints(self):
        """Validate CardSelectionData constraints after all fields are set"""
        # Note: Duplicate card IDs are ALLOWED in Innovation - players can have multiple copies
        # of the same card (e.g., multiple Pottery cards from different draws)
        # The original validation was too strict and prevented valid game states

        # Check if empty is allowed - only fail if empty AND min_count > 0
        if len(self.eligible_card_ids) == 0 and self.min_count > 0:
            raise ValueError(
                f"eligible_card_ids cannot be empty when min_count={self.min_count} (must be 0 to allow empty)"
            )

        return self


class CardOrderingData(InteractionData):
    """
    Data for card ordering interactions (Cities expansion: Search icon).

    Player must arrange cards in a specific order (e.g., returning non-matching
    cards to bottom of deck in any order they choose).
    """

    type: Literal["order_cards"]
    cards_to_order: list[dict[str, Any]] = Field(
        ...,
        description="Cards that need to be ordered (each with card_id, name, age, color)",
        min_items=1
    )
    instruction: str = Field(
        ...,
        description="Specific instruction (e.g., 'Order cards to return to deck bottom')"
    )

    @model_validator(mode="after")
    def validate_cards_to_order(self):
        """Ensure all cards have required fields"""
        for i, card in enumerate(self.cards_to_order):
            if not isinstance(card, dict):
                raise ValueError(f"Card {i} must be a dict")
            required_fields = ["card_id", "name", "age", "color"]
            for field in required_fields:
                if field not in card:
                    raise ValueError(f"Card {i} missing required field: {field}")
        return self


class OptionSelectionData(InteractionData):
    """Data for option selection interactions

    Supports two formats for options:
    1. Simple strings: ["Option A", "Option B"]  (backward compatible)
    2. Structured objects: [{"label": "Option A", "value": "a"}, ...]  (preferred for semantic values)
    """

    type: Literal["choose_option"]
    options: list[str | dict[str, Any]] = Field(..., min_items=1, max_items=11)
    allow_cancel: bool = Field(True)
    default_option: str | None = Field(None)

    @validator("options")
    def validate_options(cls, v):
        """Ensure structured options have required fields"""
        for i, option in enumerate(v):
            if isinstance(option, dict):
                if "label" not in option:
                    raise ValueError(f"Option {i}: dict options must have 'label' field")
                if "value" not in option:
                    raise ValueError(f"Option {i}: dict options must have 'value' field")
        return v

    @validator("default_option")
    def validate_default_option(cls, v, values):
        """Ensure default_option is in options if provided"""
        if v is not None:
            options = values.get("options", [])
            # Extract string values for comparison
            option_values = []
            for opt in options:
                if isinstance(opt, dict):
                    option_values.append(opt.get("label", ""))
                else:
                    option_values.append(opt)

            if v not in option_values:
                raise ValueError(f"default_option '{v}' must be in options list")
        return v


class BoardSelectionData(InteractionData):
    """Data for board selection interactions (like Compass)"""

    type: Literal["select_board"]
    eligible_boards: list[str] = Field(
        ..., description="Player IDs whose boards can be selected"
    )
    allow_own_board: bool = Field(False)


class PlayerSelectionData(InteractionData):
    """Data for player selection interactions"""

    type: Literal["select_player"]
    eligible_players: list[str] = Field(
        ..., description="Player IDs eligible for selection"
    )
    exclude_self: bool = Field(True)


class AchievementSelectionData(InteractionData):
    """Data for achievement selection interactions"""

    type: Literal["select_achievement"]
    eligible_achievements: list[dict[str, Any]] = Field(
        ..., description="Achievements eligible for selection"
    )
    is_optional: bool = Field(False, description="Whether selection is optional")
    store_result: str = Field(
        "selected_achievements", description="Variable name to store selection result"
    )

    @model_validator(mode="after")
    def validate_achievement_selection_constraints(self):
        """Validate AchievementSelectionData constraints after all fields are set"""
        if len(self.eligible_achievements) == 0 and not self.is_optional:
            raise ValueError(
                "eligible_achievements cannot be empty when selection is not optional"
            )

        # Validate each achievement has required fields
        for i, achievement in enumerate(self.eligible_achievements):
            if not isinstance(achievement, dict):
                raise ValueError(f"Achievement {i} must be a dictionary")
            if "name" not in achievement and "description" not in achievement:
                raise ValueError(
                    f"Achievement {i} must have either 'name' or 'description' field"
                )

        return self


class SymbolSelectionData(InteractionData):
    """Data for symbol selection interactions"""

    type: Literal["select_symbol"]
    available_symbols: list[str] = Field(
        ..., min_items=1, description="Symbols available for selection"
    )
    is_optional: bool = Field(False, description="Whether selection is optional")

    @validator("available_symbols")
    def validate_symbols(cls, v):
        """Ensure all symbols are valid"""
        valid_symbols = {"castle", "leaf", "lightbulb", "crown", "factory", "clock"}
        for symbol in v:
            if symbol not in valid_symbols:
                raise ValueError(
                    f"Invalid symbol: {symbol}. Must be one of {valid_symbols}"
                )
        return v


class ColorSelectionData(InteractionData):
    """Data for color selection interactions"""

    type: Literal["select_color"]
    available_colors: list[str] = Field(
        ..., min_items=1, description="Colors available for selection"
    )
    is_optional: bool = Field(False, description="Whether selection is optional")

    @validator("available_colors")
    def validate_colors(cls, v):
        """Ensure all colors are valid"""
        valid_colors = {"red", "blue", "green", "yellow", "purple"}
        for color in v:
            if color not in valid_colors:
                raise ValueError(
                    f"Invalid color: {color}. Must be one of {valid_colors}"
                )
        return v


class ReturnCardsData(InteractionData):
    """Data for return cards interactions"""

    type: Literal["return_cards"]
    eligible_cards: list[CardReference] = Field(
        ..., description="Cards eligible to be returned"
    )
    min_count: int = Field(1, ge=0, le=10, description="Minimum cards to return")
    max_count: int = Field(1, ge=1, le=10, description="Maximum cards to return")
    is_optional: bool = Field(False, description="Whether selection is optional")

    @validator("max_count")
    def validate_counts(cls, v, values):
        """Ensure max_count >= min_count"""
        min_count = values.get("min_count", 0)
        if v < min_count:
            raise ValueError(f"max_count ({v}) must be >= min_count ({min_count})")
        return v


class TiebreakerSelectionData(InteractionData):
    """Data for tiebreaker selection interactions (choose_highest_tie)"""

    type: Literal["choose_highest_tie"]
    tied_cards: list[CardReference] = Field(
        ..., min_items=2, description="Cards tied for highest"
    )


# Union type for all interaction data
InteractionData = Union[
    CardSelectionData,
    CardOrderingData,
    OptionSelectionData,
    BoardSelectionData,
    PlayerSelectionData,
    AchievementSelectionData,
    SymbolSelectionData,
    ColorSelectionData,
    ReturnCardsData,
    TiebreakerSelectionData,
]


# Validation function to check field compliance
def validate_no_cards_field(data: dict) -> bool:
    """
    Validate that the data doesn't contain the problematic 'cards' field.
    This function helps prevent the recurring field name bug.

    Args:
        data: Dictionary representation of interaction data

    Returns:
        True if valid (no 'cards' field), raises ValueError if invalid

    Raises:
        ValueError: If 'cards' field is found
    """
    import json

    json_str = json.dumps(data)
    if '"cards"' in json_str and '"eligible_cards"' not in json_str:
        raise ValueError(
            "CRITICAL: Found 'cards' field without 'eligible_cards'. "
            "Use 'eligible_cards' instead to fix the recurring field name bug!"
        )
    return True


def validate_model_no_cards_field(model: BaseModel) -> bool:
    """
    Validate that a Pydantic model doesn't contain the problematic 'cards' field.

    Args:
        model: Pydantic model instance

    Returns:
        True if valid, raises ValueError if invalid
    """
    data = model.model_dump()
    return validate_no_cards_field(data)
