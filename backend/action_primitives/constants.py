"""
Constants for action primitives.
Centralizes all magic strings and values used throughout the system.
"""

from enum import Enum
from typing import Final


class CardSource(str, Enum):
    """Standard card source locations."""

    HAND = "hand"
    BOARD = "board"
    BOARD_BOTTOM = "board_bottom"  # Bottom cards from each color stack
    SCORE_PILE = "score_pile"
    ACHIEVEMENTS = "achievements"
    BOARD_ALL = "board_all"  # All cards on board, not just top

    # Special sources
    LAST_DRAWN = "last_drawn"
    DRAWN_CARD = "drawn_card"
    LOWEST_CARD = "lowest_card"
    HIGHEST_CARD = "highest_card"
    SELECTED_CARDS = "selected_cards"
    FILTERED_CARDS = "filtered_cards"

    # Opponent sources
    OPPONENT_HAND = "opponent_hand"
    OPPONENT_BOARD = "opponent_board"
    OPPONENT_SCORE_PILE = "opponent_score_pile"

    # Age deck sources (age_1 through age_10)
    @classmethod
    def age_deck(cls, age: int) -> str:
        """Get age deck source string."""
        return f"age_{age}"


class CardTarget(str, Enum):
    """Standard card target locations."""

    HAND = "hand"
    BOARD = "board"
    SCORE_PILE = "score_pile"
    AGE_DECK = "age_deck"
    BOTTOM_OF_DECK = "bottom_of_deck"
    UNDERNEATH = "underneath"  # Tuck under a stack


class FilterCriteria(str, Enum):
    """Standard filtering criteria."""

    AGE = "age"
    MIN_AGE = "min_age"
    MAX_AGE = "max_age"
    COLOR = "color"
    HAS_SYMBOL = "has_symbol"
    DIFFERENT_COLOR_FROM_BOARD = "different_color_from_board"
    SAME_COLOR_AS_BOARD = "same_color_as_board"
    VALUE = "value"
    MIN_VALUE = "min_value"
    MAX_VALUE = "max_value"


class SortCriteria(str, Enum):
    """Criteria for sorting cards."""

    AGE = "age"
    SCORE_VALUE = "score_value"
    SYMBOL_COUNT = "symbol_count"


class SplayDirection(str, Enum):
    """Card splay directions."""

    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    ASLANT = "aslant"  # Diagonal splay (Unseen expansion)
    NONE = "none"  # Not splayed


class ActionType(str, Enum):
    """Types of action primitives."""

    DRAW_CARDS = "DrawCards"
    TRANSFER_CARDS = "TransferCards"
    SELECT_CARDS = "SelectCards"
    FILTER_CARDS = "FilterCards"
    MELD_CARD = "MeldCard"
    TUCK_CARD = "TuckCard"
    SCORE_CARDS = "ScoreCards"
    RETURN_CARDS = "ReturnCards"
    SPLAY_CARDS = "SplayCards"
    EXCHANGE_CARDS = "ExchangeCards"
    CHOOSE_OPTION = "ChooseOption"
    DEMAND_EFFECT = "DemandEffect"
    CONDITIONAL_ACTION = "ConditionalAction"
    LOOP_ACTION = "LoopAction"
    REPEAT_ACTION = "RepeatAction"
    COUNT_SYMBOLS = "CountSymbols"
    COUNT_UNIQUE_COLORS = "CountUniqueColors"
    COUNT_UNIQUE_VALUES = "CountUniqueValues"
    SELECT_HIGHEST = "SelectHighest"
    SELECT_LOWEST = "SelectLowest"
    SELECT_COLOR = "SelectColor"
    EVALUATE_CONDITION = "EvaluateCondition"
    REVEAL_AND_PROCESS = "RevealAndProcess"
    CLAIM_ACHIEVEMENT = "ClaimAchievement"


class InteractionType(str, Enum):
    """Types of player interactions required."""

    SELECT_CARDS = "select_cards"
    CHOOSE_OPTION = "choose_option"
    DEMAND_RESPONSE = "demand_response"
    RETURN_CARDS = "return_cards"


# Numeric constants
DEFAULT_DRAW_COUNT: Final[int] = 1
DEFAULT_SELECT_COUNT: Final[int] = 1
MAX_HAND_SIZE: Final[int] = 99  # Effectively unlimited in Innovation
MIN_AGE: Final[int] = 1
ACTIONS_PER_TURN: Final[int] = 2


# Symbol names (for consistency)
class SymbolName(str, Enum):
    """Symbol names as strings."""

    CASTLE = "castle"
    LEAF = "leaf"
    LIGHTBULB = "lightbulb"
    CROWN = "crown"
    FACTORY = "factory"
    CLOCK = "clock"


# Color names (for consistency)
class ColorName(str, Enum):
    """Color names as strings."""

    RED = "red"
    BLUE = "blue"
    GREEN = "green"
    YELLOW = "yellow"
    PURPLE = "purple"


# Common variable names used in action contexts
class ContextVariable(str, Enum):
    """Standard variable names in ActionContext."""

    LAST_DRAWN = "last_drawn"
    DRAWN_CARD = "drawn_card"
    SELECTED_CARDS = "selected_cards"
    FILTERED_CARDS = "filtered_cards"
    TRANSFER_COUNT = "transfer_count"
    SYMBOL_COUNT = "symbol_count"
    COLOR_COUNT = "color_count"
    UNIQUE_VALUES = "unique_values"
    CHOSEN_OPTION = "chosen_option"
    CHOSEN_COLOR = "chosen_color"
    CONDITION_MET = "condition_met"
    LOOP_COUNT = "loop_count"
    CASTLE_CARDS = "castle_cards"  # Used by Masonry
    ELIGIBLE_CARDS = "eligible_cards"
