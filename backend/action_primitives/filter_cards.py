"""
FilterCards Action Primitive

Filters cards based on various criteria.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult
from .utils import CardFilterUtils, CardSourceResolver

logger = logging.getLogger(__name__)


class FilterCards(ActionPrimitive):
    """
    Primitive for filtering cards based on various criteria.

    Parameters:
    - source: Cards to filter (variable name or source location like "hand")
    - criteria: Filtering criteria dict
    - store_result: Variable name to store filtered cards (default: "filtered_cards")
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.source = config.get("source", "hand")
        self.criteria = config.get("criteria", {})
        # Support both "store_result" and "store_as" parameter names
        self.store_result = (
            config.get("store_result")
            if config.get("store_result") is not None
            else config.get("store_as", "filtered")
        )
        self.target_player = config.get("target_player")

        # Support nested filter parameter from cards
        if "filter" in config:
            nested_filter = config["filter"]
            if isinstance(nested_filter, dict):
                # Handle "all": true filter - return all cards (no actual filtering)
                if nested_filter.get("all") is True:
                    # Criteria stays empty - will return all cards
                    pass
                # Handle nested filter format from card definitions
                elif nested_filter.get("type") == "has_symbol":
                    self.criteria["has_symbol"] = nested_filter.get("symbol")
                elif nested_filter.get("type") == "age_equals":
                    age_value = nested_filter.get("age")
                    if isinstance(age_value, str):
                        # Variable reference like "selected_age"
                        self.criteria["variable_age"] = age_value
                    else:
                        self.criteria["age"] = age_value
                elif nested_filter.get("type") == "not_name_equals":
                    # Filter out cards with specific name
                    self.criteria["exclude_name"] = nested_filter.get("name")
                # Add other filter types as needed

    def execute(self, context: ActionContext) -> ActionResult:
        """Filter cards based on criteria"""
        # Use criteria dict directly
        criteria = self.criteria.copy()

        # Get source cards - handle target_player for multi-player sources
        if self.target_player:
            source_cards = self._get_cards_from_target_player(context)
        else:
            # Debug log to understand what's happening
            logger.info(f"FilterCards: getting cards from source '{self.source}'")
            source_cards = CardSourceResolver.get_cards(context, self.source)
            # Debug logging for deck sources
            if self.source.startswith("deck_"):
                logger.info(
                    f"FilterCards: source={self.source}, found {len(source_cards)} cards"
                )
                if source_cards:
                    card_names = [getattr(c, "name", str(c)) for c in source_cards[:5]]
                    logger.info(
                        f"FilterCards: first cards from {self.source}: {card_names}"
                    )
            # Check if we're getting wrong cards
            if self.source == "deck_2" and source_cards:
                # Check if these are the drawn cards
                last_drawn = context.get_variable("last_drawn_all", [])
                if last_drawn and source_cards[:2] == last_drawn[:2]:
                    logger.warning(
                        "FilterCards: deck_2 is returning drawn cards instead of deck cards!"
                    )

        # Apply filtering
        filtered_cards = self._apply_filters(context, source_cards, criteria)

        # Store result
        logger.info(f"FilterCards: About to store {len(filtered_cards)} cards in variable '{self.store_result}'")
        if filtered_cards:
            logger.info(f"FilterCards: First 3 card IDs being stored: {[(getattr(c, 'card_id', None), getattr(c, 'name', None)) for c in filtered_cards[:3]]}")
        context.set_variable(self.store_result, filtered_cards)
        context.add_result(f"Filtered to {len(filtered_cards)} cards")

        logger.debug(
            f"Filtered {len(source_cards)} cards to {len(filtered_cards)} using criteria: {criteria}"
        )

        return ActionResult.SUCCESS

    def _apply_filters(
        self, context: ActionContext, cards: list, criteria: dict[str, Any]
    ) -> list:
        """Apply filtering criteria to cards"""
        if not cards:
            return []

        filtered = cards.copy()

        # Filter by symbol
        if "has_symbol" in criteria:
            symbol = criteria["has_symbol"]
            # Resolve variable reference if needed
            if isinstance(symbol, str) and context.has_variable(symbol):
                symbol = context.get_variable(symbol)
            filtered = CardFilterUtils.filter_by_symbol(filtered, symbol)

        # Filter by color
        if "color" in criteria:
            color = criteria["color"]
            # Resolve variable reference if needed
            if isinstance(color, str) and context.has_variable(color):
                color = context.get_variable(color)
            filtered = CardFilterUtils.filter_by_color(filtered, color)

        # Filter by age
        if "age" in criteria:
            age = criteria["age"]
            # Resolve variable reference if needed
            if isinstance(age, str) and context.has_variable(age):
                age = context.get_variable(age)
            filtered = CardFilterUtils.filter_by_age(filtered, exact_age=age)
        elif "min_age" in criteria or "max_age" in criteria:
            min_age = criteria.get("min_age", 1)
            max_age = criteria.get("max_age", 10)
            filtered = CardFilterUtils.filter_by_age(
                filtered, min_age=min_age, max_age=max_age
            )

        # Filter by highest/lowest age
        if "highest" in criteria:
            filtered = CardFilterUtils.filter_highest(filtered)
        elif "lowest" in criteria:
            filtered = CardFilterUtils.filter_lowest(filtered)

        # Filter by color difference from board
        if "different_color_from_board" in criteria:
            filtered = CardFilterUtils.filter_by_board_colors(
                filtered, context, different_from_board=True
            )

        # Filter by color same as board
        if "same_color_as_board" in criteria:
            filtered = CardFilterUtils.filter_by_board_colors(
                filtered, context, same_as_board=True
            )

        # Filter by value (for cards with numeric values)
        if "value" in criteria:
            value = criteria["value"]
            filtered = [c for c in filtered if getattr(c, "value", None) == value]

        # Filter by name
        if "name" in criteria:
            name = criteria["name"]
            filtered = [
                c for c in filtered if getattr(c, "name", "").lower() == name.lower()
            ]

        # Filter out cards by name (exclude)
        if "exclude_name" in criteria:
            exclude_name = criteria["exclude_name"]
            filtered = [
                c for c in filtered if getattr(c, "name", "").lower() != exclude_name.lower()
            ]

        # Filter by having dogma effects
        if "has_dogma" in criteria:
            filtered = [c for c in filtered if getattr(c, "dogma_actions", [])]

        # Custom filter function
        if "filter_func" in criteria:
            filter_func = criteria["filter_func"]
            filtered = [c for c in filtered if filter_func(c)]

        return filtered

    def _get_cards_from_target_player(self, context: ActionContext) -> list:
        """Get cards from target player(s) based on target_player specification"""
        all_cards = []

        if self.target_player == "any_opponent" or self.target_player == "opponent":
            # Get cards from all opponents
            if hasattr(context.game, "players"):
                for player in context.game.players:
                    if player.id != context.player.id:
                        if self.source == "board_top" or self.source == "board":
                            all_cards.extend(player.board.get_top_cards())
                        elif self.source == "hand":
                            all_cards.extend(player.hand)
                        elif self.source == "score" or self.source == "score_pile":
                            all_cards.extend(player.score_pile)
                        elif self.source == "achievements":
                            all_cards.extend(player.achievements)
                        elif self.source == "junk" or self.source == "junk_pile":
                            # Junk is game-level, not player-level, so only add once
                            if hasattr(context.game, "junk_pile") and not all_cards:
                                all_cards.extend(context.game.junk_pile)
        elif self.target_player == "all":
            # Get cards from all players including current player
            if hasattr(context.game, "players"):
                for player in context.game.players:
                    if self.source == "board_top" or self.source == "board":
                        all_cards.extend(player.board.get_top_cards())
                    elif self.source == "hand":
                        all_cards.extend(player.hand)
                    elif self.source == "score" or self.source == "score_pile":
                        all_cards.extend(player.score_pile)
                    elif self.source == "achievements":
                        all_cards.extend(player.achievements)
                    elif self.source == "junk" or self.source == "junk_pile":
                        # Junk is game-level, so only add once (not per player)
                        if hasattr(context.game, "junk_pile") and not all_cards:
                            all_cards.extend(context.game.junk_pile)
        else:
            # Specific player target
            # For now, fall back to CardSourceResolver
            all_cards = CardSourceResolver.get_cards(context, self.source)

        return all_cards

    @staticmethod
    def evaluate_filter(card, filter_config: dict, context) -> bool:
        """
        Evaluate a single filter against a card.

        This static method can be used by other primitives that need to apply
        filter logic without creating a FilterCards instance.

        Supported filter types:
        - color_equals: Match cards of a specific color
        - age_equals: Match cards of a specific age
        - age_in_range: Match cards within an age range
        - has_symbol: Match cards containing a specific symbol

        Args:
            card: The card to check (must have attributes like color, age, symbols)
            filter_config: Filter configuration dict with 'type' key and filter-specific params
            context: Action context for resolving variable references

        Returns:
            bool: True if card matches the filter, False otherwise.
                  Returns True for unknown filter types (permissive default).

        Examples:
            >>> FilterCards.evaluate_filter(card, {"type": "color_equals", "color": "blue"}, context)
            >>> FilterCards.evaluate_filter(card, {"type": "age_in_range", "min_age": 1, "max_age": 3}, context)
        """
        try:
            filter_type = filter_config.get("type")

            if filter_type == "color_equals":
                # Check if card color matches the specified color (can be a variable name)
                target_color = filter_config.get("color")

                # Resolve variable reference if needed
                if isinstance(target_color, str) and context.has_variable(target_color):
                    target_color = context.get_variable(target_color)

                # Validate card has color attribute
                if not hasattr(card, "color"):
                    return False

                # Normalize color for comparison (handle CardColor enum)
                card_color = card.color
                if card_color:
                    # Handle CardColor enum for card
                    if hasattr(card_color, "value"):
                        card_color = card_color.value
                    # Handle CardColor enum for target
                    if hasattr(target_color, "value"):
                        target_color = target_color.value
                    # Convert to lowercase for comparison
                    card_color_str = str(card_color).lower()
                    target_color_str = str(target_color).lower()
                    return card_color_str == target_color_str
                return False

            elif filter_type == "age_equals":
                target_age = filter_config.get("age")
                if isinstance(target_age, str) and context.has_variable(target_age):
                    target_age = context.get_variable(target_age)
                card_age = getattr(card, "age", None)
                return card_age == target_age

            elif filter_type == "age_in_range":
                min_age = filter_config.get("min_age", 1)
                max_age = filter_config.get("max_age", 10)
                card_age = getattr(card, "age", None)
                if card_age is None:
                    return False
                return min_age <= card_age <= max_age

            elif filter_type == "has_symbol":
                symbol = filter_config.get("symbol")
                if isinstance(symbol, str) and context.has_variable(symbol):
                    symbol = context.get_variable(symbol)
                card_symbols = getattr(card, "symbols", [])
                return symbol in card_symbols

            # Default: unknown filter type means accept all (permissive)
            return True

        except (AttributeError, TypeError) as e:
            logger.error(f"Error evaluating filter {filter_config.get('type', 'unknown')}: {e}")
            return False
