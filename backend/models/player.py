import logging
import uuid
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from .board_utils import BoardColorIterator
from .card import Card, Symbol


if TYPE_CHECKING:
    pass


class PlayerBoard(BaseModel):
    """Represents a player's tableau of cards"""

    blue_cards: list[Card] = Field(default_factory=list)
    red_cards: list[Card] = Field(default_factory=list)
    green_cards: list[Card] = Field(default_factory=list)
    yellow_cards: list[Card] = Field(default_factory=list)
    purple_cards: list[Card] = Field(default_factory=list)
    splay_directions: dict[str, str] = Field(default_factory=dict)

    def get_cards_by_color(self, color: str) -> list[Card]:
        color_map = {
            "blue": self.blue_cards,
            "red": self.red_cards,
            "green": self.green_cards,
            "yellow": self.yellow_cards,
            "purple": self.purple_cards,
        }
        return color_map.get(color, [])

    def get_splay(self, color: str) -> str | None:
        """Get the splay direction for a color, or None if not splayed"""
        return self.splay_directions.get(color)

    def get_top_card(self, color: str) -> Card | None:
        """Get the top card for a specific color, or None if no cards"""
        color_stack = self.get_cards_by_color(color)
        return color_stack[-1] if color_stack else None

    def add_card(self, card: Card):
        """Add a card to the appropriate color stack"""
        if card is None:
            # Defensive check: don't add None cards
            import logging

            logging.warning("Attempted to add None card to player board")
            return

        color_map = {
            "blue": self.blue_cards,
            "red": self.red_cards,
            "green": self.green_cards,
            "yellow": self.yellow_cards,
            "purple": self.purple_cards,
        }
        if card.color.value in color_map:
            color_map[card.color.value].append(card)

    def tuck_card(self, card: Card):
        """Tuck a card under its color stack."""
        if card is None:
            # Defensive check: don't tuck None cards
            import logging

            logging.warning("Attempted to tuck None card to player board")
            return

        color = card.color.value
        if color == "blue":
            self.blue_cards.insert(0, card)
        elif color == "red":
            self.red_cards.insert(0, card)
        elif color == "green":
            self.green_cards.insert(0, card)
        elif color == "yellow":
            self.yellow_cards.insert(0, card)
        elif color == "purple":
            self.purple_cards.insert(0, card)

    def splay(self, color: str, direction: str):
        """Set the splay direction for a color."""
        self.splay_directions[color] = direction

    def get_top_cards(self) -> list[Card]:
        """Get the top card from each color stack"""
        top_cards = []
        for cards in [
            self.blue_cards,
            self.red_cards,
            self.green_cards,
            self.yellow_cards,
            self.purple_cards,
        ]:
            if cards:
                top_cards.append(cards[-1])
        return top_cards

    def count_symbol(self, symbol: Symbol) -> int:
        """Count total symbols of a type on the board (including splayed cards)"""
        count = 0

        # Count symbols from all visible cards (top cards + splayed cards)
        for color, color_stack in BoardColorIterator.iterate_color_stacks(self):
            splay_direction = self.splay_directions.get(color, None)

            if not color_stack:
                continue

            # Top card is always fully visible
            count += color_stack[-1].get_symbol_count(symbol)

            # Add symbols from splayed cards based on splay direction and position
            if len(color_stack) > 1 and splay_direction:
                # Card symbol positions are indexed as:
                # Position 0: top-left
                # Position 1: bottom-left
                # Position 2: bottom-middle
                # Position 3: bottom-right
                #
                # When you splay LEFT, top card slides LEFT, revealing RIGHT edge (position 3) of cards below
                # When you splay RIGHT, top card slides RIGHT, revealing LEFT edge (positions 0, 1) of cards below
                # When you splay UP, top card slides UP, revealing BOTTOM row (positions 1, 2, 3) of cards below
                # When you splay ASLANT, all positions are visible on cards below
                visible_positions = {
                    "left": [3],  # Left splay: reveals rightmost icon (position 3) only
                    "right": [
                        0,
                        1,
                    ],  # Right splay: reveals leftmost icons (top-left and bottom-left)
                    "up": [
                        1,
                        2,
                        3,
                    ],  # Up splay: reveals bottom row (all 3 bottom positions)
                    "aslant": [
                        0,
                        1,
                        2,
                        3,
                    ],  # Aslant splay: reveals all 4 positions on each card below
                }.get(splay_direction, [])

                for card in color_stack[:-1]:  # All cards except the top card
                    # Count symbols from visible positions only
                    for pos in visible_positions:
                        if (
                            pos < len(card.symbol_positions)
                            and card.symbol_positions[pos] == symbol
                        ):
                            count += 1

        return count

    def count_symbol_by_color(self, symbol: Symbol, color: str) -> int:
        """Count symbols of a type in a specific color stack (including splayed cards)"""
        count = 0

        # Get the specific color stack
        color_stack = self.get_cards_by_color(color)
        splay_direction = self.splay_directions.get(color, None)

        if not color_stack:
            return 0

        # Top card is always fully visible
        count += color_stack[-1].get_symbol_count(symbol)

        # Add symbols from splayed cards based on splay direction and position
        if len(color_stack) > 1 and splay_direction:
            visible_positions = {
                "left": [3],  # Left splay: reveals rightmost icon (position 3) only
                "right": [
                    0,
                    1,
                ],  # Right splay: reveals leftmost icons (top-left and bottom-left)
                "up": [
                    1,
                    2,
                    3,
                ],  # Up splay: reveals bottom row (all 3 bottom positions)
                "aslant": [
                    0,
                    1,
                    2,
                    3,
                ],  # Aslant splay: reveals all 4 positions on each card below
            }.get(splay_direction, [])

            for card in color_stack[:-1]:  # All cards except the top card
                # Count symbols from visible positions only
                for pos in visible_positions:
                    if (
                        pos < len(card.symbol_positions)
                        and card.symbol_positions[pos] == symbol
                    ):
                        count += 1

        return count

    def get_highest_age(self) -> int:
        """Get the highest age card on the board.

        Returns the highest era number among top cards on the board.
        """
        top_cards = self.get_top_cards()
        if not top_cards:
            return 0
        return max(card.age for card in top_cards)

    def get_total_cards(self) -> int:
        """Get the total number of cards on the board"""
        return (
            len(self.blue_cards)
            + len(self.red_cards)
            + len(self.green_cards)
            + len(self.yellow_cards)
            + len(self.purple_cards)
        )

    def get_all_cards(self) -> list["Card"]:
        """Get all cards on the board (not just top cards)"""
        all_cards = []
        all_cards.extend(self.blue_cards)
        all_cards.extend(self.red_cards)
        all_cards.extend(self.green_cards)
        all_cards.extend(self.yellow_cards)
        all_cards.extend(self.purple_cards)
        return all_cards


logger = logging.getLogger(__name__)


class Player(BaseModel):
    id: str
    name: str
    hand: list[Card] = Field(default_factory=list)
    board: PlayerBoard = Field(default_factory=PlayerBoard)
    score_pile: list[Card] = Field(default_factory=list)
    achievements: list[Card] = Field(
        default_factory=list
    )  # Achievement cards (Card objects, not strings)
    achievement_sources: list[tuple[int, str]] = Field(
        default_factory=list
    )  # Track achievement sources: [(age, "standard"|"flag_blue"|"fountain"), ...]
    setup_selection_made: bool = False
    is_ai: bool = False  # Flag for AI players
    ai_difficulty: str | None = None  # Track AI difficulty level
    ai_memory: dict = Field(
        default_factory=dict
    )  # AI strategic memory (goals, plans, observations)


    def __init__(self, **data):
        if "id" not in data or data["id"] is None:
            data["id"] = str(uuid.uuid4())
        super().__init__(**data)

    @property
    def score(self) -> int:
        """Calculate player's current score"""
        return sum(card.age for card in self.score_pile)

    # Special achievement names that should not be counted for score threshold calculations
    SPECIAL_ACHIEVEMENT_NAMES: frozenset[str] = frozenset([
        "Monument", "Empire", "World", "Wonder", "Universe", "Wealth", "Destiny", "Supremacy", "Mastery"
    ])

    def required_score_for_achievement(self, age: int) -> int:
        """Compute the score needed to claim an achievement of a given age.

        Note: This method is only used for age-based achievements (1-10).
        Special achievements (Empire, Monument, World) don't use this calculation
        and should not be counted when determining score thresholds.
        """
        # Count how many regular (non-special) achievements of this age the player already has
        same_age_count = len([
            ach for ach in self.achievements
            if ach.age == age and ach.name not in self.SPECIAL_ACHIEVEMENT_NAMES
        ])
        return 5 * age * (same_age_count + 1)

    def can_achieve(self, achievement_card: Card) -> bool:
        """Check if player meets achievement requirements"""
        if not achievement_card:
            return False

        age = achievement_card.age
        # Must have a top card of at least the achievement's age
        if self.board.get_highest_age() < age:
            return False

        return self.score >= self.required_score_for_achievement(age)

    def add_to_hand(self, card: Card):
        """Add a card to the player's hand"""
        self.hand.append(card)

    def add_to_score_pile(self, card: Card):
        """Add a card to the score pile"""
        self.score_pile.append(card)

    def remove_from_hand(self, card: Card) -> bool:
        """Remove a card from hand, return True if successful

        CRITICAL FIX: Enhanced card removal with comprehensive matching and logging
        to fix Tools card bug where cards remained in hand after "removal"
        """
        # Log attempt for debugging Tools card issue
        logger.debug(
            "Attempting to remove card from %s's hand: %s (id: %s)",
            self.name,
            card.name,
            getattr(card, "card_id", "none"),
        )
        logger.debug(
            "Current hand: %s",
            [
                f'{hand_card.name}(id:{getattr(hand_card, "card_id", "none")})'
                for hand_card in self.hand
            ],
        )

        # Strategy 1: Try exact object reference match first (fastest and most reliable)
        try:
            hand_index = self.hand.index(card)
            removed_card = self.hand.pop(hand_index)
            logger.info(
                "SUCCESS: Removed %s from %s's hand by object reference",
                removed_card.name,
                self.name,
            )
            return True
        except ValueError:
            # Object not found by reference, fall back to identifier matching
            logger.debug("Card not found by object reference, trying ID/name matching")
            pass

        # Strategy 2: Match by card_id (preferred stable identifier)
        if hasattr(card, "card_id") and card.card_id:
            for i, hand_card in enumerate(self.hand):
                if hasattr(hand_card, "card_id") and hand_card.card_id == card.card_id:
                    removed_card = self.hand.pop(i)
                    logger.info(
                        "SUCCESS: Removed %s from %s's hand by card_id %s",
                        removed_card.name,
                        self.name,
                        card.card_id,
                    )
                    return True

        # Strategy 3: Match by name (fallback for backwards compatibility)
        for i, hand_card in enumerate(self.hand):
            if hand_card.name == card.name:
                removed_card = self.hand.pop(i)
                logger.info(
                    "SUCCESS: Removed %s from %s's hand by name",
                    removed_card.name,
                    self.name,
                )
                return True

        # All strategies failed
        logger.error(
            "FAILED: Could not remove %s from %s's hand - not found by any method",
            card.name,
            self.name,
        )
        logger.error(
            "Hand after failed removal: %s",
            [
                f'{hand_card.name}(id:{getattr(hand_card, "card_id", "none")})'
                for hand_card in self.hand
            ],
        )
        return False

    def remove_from_hand_by_name(self, card_name: str) -> Card | None:
        """Remove a card from hand by name, return the card if found"""
        for i, hand_card in enumerate(self.hand):
            if hand_card.name == card_name:
                return self.hand.pop(i)
        return None

    def remove_from_hand_by_id(self, card_id: str) -> Card | None:
        """Remove a card from hand by ID, return the card if found"""
        for i, hand_card in enumerate(self.hand):
            if hand_card.card_id == card_id:
                return self.hand.pop(i)
        return None

    def find_card_by_id(self, card_id: str, location: str = "all") -> Card | None:
        """Find a card by ID in specified location(s)

        Args:
            card_id: The unique card ID to search for
            location: Where to search - "hand", "board", "score_pile", or "all"
                     Note: achievements are not searched by this method

        Returns:
            The card if found, None otherwise
        """
        if location in ["hand", "all"]:
            for card in self.hand:
                if card.card_id == card_id:
                    return card

        if location in ["board", "all"]:
            for card in self.board.get_all_cards():
                if card.card_id == card_id:
                    return card

        if location in ["score_pile", "all"]:
            for card in self.score_pile:
                if card.card_id == card_id:
                    return card

        # Achievements are now strings, not Cards, so we skip them

        return None

    def meld_card(self, card: Card):
        """Meld a card to the board"""
        self.board.add_card(card)

    def count_symbol(self, symbol) -> int:
        """Count total symbols of a type on the player's board."""
        from models.card import Symbol

        # Handle both string and Symbol enum
        if isinstance(symbol, str):
            symbol_map = {
                "circuit": Symbol.CIRCUIT,
                "data": Symbol.DATA,
                "algorithm": Symbol.ALGORITHM,
                "neural_net": Symbol.NEURAL_NET,
                "robot": Symbol.ROBOT,
                "human_mind": Symbol.HUMAN_MIND,
            }
            symbol_enum = symbol_map.get(symbol.lower())
            if not symbol_enum:
                return 0
        else:
            symbol_enum = symbol

        return self.board.count_symbol(symbol_enum)

    def count_symbol_by_color(self, symbol, color: str) -> int:
        """Count symbols of a type in a specific color stack (including splayed cards)"""
        from models.card import Symbol

        # Handle both string and Symbol enum
        if isinstance(symbol, str):
            symbol_map = {
                "circuit": Symbol.CIRCUIT,
                "data": Symbol.DATA,
                "algorithm": Symbol.ALGORITHM,
                "neural_net": Symbol.NEURAL_NET,
                "robot": Symbol.ROBOT,
                "human_mind": Symbol.HUMAN_MIND,
            }
            symbol_enum = symbol_map.get(symbol.lower())
            if not symbol_enum:
                return 0
        else:
            symbol_enum = symbol

        # Count from board for specific color
        count = self.board.count_symbol_by_color(symbol_enum, color)

        return count

    def to_dict(
        self,
        include_computed: bool = True,
        achievement_cards: dict | None = None,
    ) -> dict:
        """
        Convert player to dictionary.

        Args:
            include_computed: Include computed_state fields (default True for Phase 2)
            achievement_cards: Achievement cards dict for achievement calculations (least privilege)
        """
        base_dict = {
            "id": self.id,
            "name": self.name,
            "hand": [card.to_dict() for card in self.hand],
            "board": {
                "blue_cards": [card.to_dict() for card in self.board.blue_cards],
                "red_cards": [card.to_dict() for card in self.board.red_cards],
                "green_cards": [card.to_dict() for card in self.board.green_cards],
                "yellow_cards": [card.to_dict() for card in self.board.yellow_cards],
                "purple_cards": [card.to_dict() for card in self.board.purple_cards],
                "splay_directions": self.board.splay_directions,
            },
            "score_pile": [card.to_dict() for card in self.score_pile],
            "achievements": [
                card.to_dict() if hasattr(card, "to_dict") else card
                for card in self.achievements
            ],
            "score": self.score,
            "is_ai": self.is_ai,
            "ai_difficulty": self.ai_difficulty,
        }

        # Phase 2: Add computed state if requested
        if include_computed:
            base_dict["computed_state"] = self._compute_state(achievement_cards)

        return base_dict

    def _compute_state(self, achievement_cards: dict | None = None) -> dict:
        """
        Compute all derived player state (Phase 2).

        This method calculates all the information that the frontend previously
        computed itself. By moving this to the backend, we get:
        - Single source of truth for calculations
        - Consistent logic between validation and display
        - Opportunity for caching and optimization
        - Simpler frontend code

        Args:
            achievement_cards: Achievement cards dict for achievement calculations (least privilege)

        Returns:
            Dictionary with computed state fields
        """
        # Calculate draw age (highest age on board)
        # Clamp at calculation time for consistency (minimum 1, maximum 11)
        base_draw_age = max(1, self.board.get_highest_age())

        # Future: Check for draw age modifiers (Calendar, etc.)
        draw_age_modifiers: list[str] = []

        # Apply all limits here (including future modifiers)
        final_draw_age = max(1, min(11, base_draw_age))

        # Count all visible symbols on board
        visible_symbols = {
            "circuit": self.count_symbol("circuit"),
            "neural_net": self.count_symbol("neural_net"),
            "data": self.count_symbol("data"),
            "algorithm": self.count_symbol("algorithm"),
            "robot": self.count_symbol("robot"),
            "human_mind": self.count_symbol("human_mind"),
        }

        # Calculate total score
        total_score = self.score

        # Determine available actions (requires achievement_cards context)
        can_activate_dogma = []
        can_achieve = []
        achievement_requirements = {}

        # Get list of cards that can activate dogma (top cards with dogma effects)
        # This doesn't require any external context
        can_activate_dogma = self._get_activatable_dogma_cards()

        # Calculate achievement requirements for all ages
        # This doesn't require any external context
        achievement_requirements = self._calculate_achievement_requirements()

        # Get list of achievable ages (requires achievement_cards)
        if achievement_cards is not None:
            can_achieve = self._get_achievable_ages(achievement_cards)

        return {
            "draw_age": final_draw_age,
            "base_draw_age": base_draw_age,
            "draw_age_modifiers": draw_age_modifiers,
            "visible_symbols": visible_symbols,
            "total_score": total_score,
            "can_draw": True,  # Always can draw if have actions
            "can_meld": len(self.hand) > 0,  # Can meld if have cards in hand
            "can_activate_dogma": can_activate_dogma,
            "can_achieve": can_achieve,
            "achievement_requirements": achievement_requirements,
        }

    def _get_activatable_dogma_cards(self) -> list[str]:
        """
        Get list of card names that can activate dogma.

        A card can activate dogma if:
        1. It's a top card on its color stack
        2. It has dogma effects

        Returns:
            List of card names (strings)
        """
        activatable = []
        top_cards = self.board.get_top_cards()

        for card in top_cards:
            # Check if card has dogma effects
            if hasattr(card, "dogma_effects") and card.dogma_effects:
                activatable.append(card.name)

        return activatable

    def _get_achievable_ages(self, achievement_cards: dict) -> list[int]:
        """
        Get list of ages player can claim.

        Requirements:
        1. Achievement must be available (not claimed by anyone)
        2. Player must have top card >= achievement age
        3. Player must have required score

        Args:
            achievement_cards: Dictionary mapping age -> list of achievement cards

        Returns:
            List of achievable age numbers
        """
        achievable = []

        # Get highest age on board
        highest_board_age = self.board.get_highest_age()
        total_score = self.score

        # Check each age
        for age in range(1, 11):
            # Check if achievement available
            if age not in achievement_cards or not achievement_cards[age]:
                continue

            # Check if already claimed by this player
            achievement = achievement_cards[age][0]
            if achievement in self.achievements:
                continue

            # Check board requirement (must have top card >= age)
            if highest_board_age < age:
                continue

            # Check score requirement
            required = self.required_score_for_achievement(age)
            if total_score >= required:
                achievable.append(age)

        return achievable

    def _calculate_achievement_requirements(self) -> dict[int, int]:
        """
        Calculate score requirements for all ages.

        Returns:
            Dictionary mapping age -> required score
        """
        requirements = {}

        for age in range(1, 11):
            requirements[age] = self.required_score_for_achievement(age)

        return requirements
