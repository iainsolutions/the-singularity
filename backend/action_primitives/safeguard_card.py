"""
SafeguardCard Action Primitive

Safeguard achievements based on card conditions.
Part of the Unseen expansion mechanics.

This primitive finds cards matching specified conditions and safeguards
corresponding achievements (e.g., "Safeguard age achievements matching
colors on your board").
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class SafeguardCard(ActionPrimitive):
    """
    Safeguard achievements based on card conditions.

    Finds cards matching specified conditions and safeguards corresponding
    achievements. For example:
    - "Safeguard age achievements matching colors on your board"
    - "Safeguard achievements matching ages in your hand"

    Parameters:
    - card_source: Where to find cards ("hand", "board", "score_pile", "board_top")
    - condition: Optional filter condition (type: "color", "age", "has_symbol", etc.)
    - achievement_mapping: How cards map to achievements ("matching_age", "matching_color", "matching_value")
    - target_player: Which player's cards to check ("self", "opponent", "all")
    - store_result: Variable name to store safeguarded achievement IDs
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.cards_var = config.get("cards")  # Variable name containing cards
        self.card_source = config.get("card_source", "board")
        self.condition = config.get("condition")
        self.achievement_mapping = config.get("achievement_mapping", "matching_age")
        self.target_player = config.get("target_player", "self")
        self.store_result = config.get("store_result", "safeguarded_achievements")

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the safeguard card action"""
        logger.debug(
            f"SafeguardCard.execute: cards_var={self.cards_var}, source={self.card_source}, "
            f"mapping={self.achievement_mapping}, target={self.target_player}"
        )

        # Get target player
        if self.target_player == "opponent":
            target_player = context.target_player or context.get_opponent()
        else:
            target_player = context.player

        if not target_player:
            context.add_result("Error: No target player found")
            return ActionResult.FAILURE

        # Get cards from variable or source
        if self.cards_var:
            cards = context.get_variable(self.cards_var, [])
            if not isinstance(cards, list):
                cards = [cards] if cards else []
        else:
            cards = self._get_cards_from_source(context, target_player)

        if not cards:
            context.add_result(f"No cards found in {self.card_source}")
            return ActionResult.CONDITION_NOT_MET

        # Filter by condition if specified
        if self.condition:
            cards = self._filter_cards(cards, self.condition)

        if not cards:
            context.add_result(f"No cards match condition: {self.condition}")
            return ActionResult.CONDITION_NOT_MET

        # Map cards to achievement IDs
        achievement_ids = self._map_cards_to_achievements(cards)

        if not achievement_ids:
            context.add_result("No achievements to safeguard from cards")
            return ActionResult.CONDITION_NOT_MET

        # Safeguard each achievement
        safeguarded_count = 0
        for achievement_id in achievement_ids:
            success = self._safeguard_achievement(context, achievement_id)
            if success:
                safeguarded_count += 1

        # Store result
        context.set_variable(self.store_result, achievement_ids)

        # Log result
        activity_logger.info(
            f"{context.player.name} safeguarded {safeguarded_count} achievement(s) "
            f"based on {len(cards)} card(s)"
        )
        context.add_result(
            f"Safeguarded {safeguarded_count} achievement(s) from {len(cards)} card(s)"
        )

        logger.debug(f"SafeguardCard: Safeguarded {achievement_ids}")
        return ActionResult.SUCCESS

    def _get_cards_from_source(self, context: ActionContext, player):
        """Get cards from specified source"""
        cards = []

        if self.card_source == "hand":
            cards = player.hand.copy()

        elif self.card_source == "board":
            # All cards on board
            for color in ["red", "blue", "green", "yellow", "purple"]:
                stack = player.board.get_cards_by_color(color)
                cards.extend(stack)

        elif self.card_source == "board_top":
            # Only top cards
            cards = player.board.get_top_cards()

        elif self.card_source == "score_pile":
            cards = player.score_pile.copy()

        elif self.card_source == "safe":
            # Unseen expansion: cards in Safe
            if hasattr(player, "safe") and player.safe:
                cards = player.safe.cards.copy()

        return cards

    def _filter_cards(self, cards, condition):
        """Filter cards by condition"""
        if not condition:
            return cards

        condition_type = condition.get("type")
        condition_value = condition.get("value")

        filtered = []

        for card in cards:
            if condition_type == "color":
                if condition_value and card.color == condition_value:
                    filtered.append(card)
                elif not condition_value:
                    # No specific color, include all
                    filtered.append(card)

            elif condition_type == "age":
                if condition_value and card.age == condition_value:
                    filtered.append(card)
                elif not condition_value:
                    filtered.append(card)

            elif condition_type == "has_symbol":
                symbol = condition_value
                if symbol and hasattr(card, "symbols") and symbol in card.symbols:
                    filtered.append(card)

            elif condition_type == "min_age":
                if card.age >= condition_value:
                    filtered.append(card)

            elif condition_type == "max_age":
                if card.age <= condition_value:
                    filtered.append(card)

            else:
                # Unknown condition type, include card
                filtered.append(card)

        return filtered

    def _map_cards_to_achievements(self, cards):
        """Map cards to achievement IDs based on mapping type"""
        achievement_ids = set()  # Use set to avoid duplicates

        for card in cards:
            if self.achievement_mapping == "matching_age":
                # Safeguard age achievement matching card age
                if 1 <= card.age <= 11:
                    achievement_ids.add(f"age_{card.age}")

            elif self.achievement_mapping == "matching_color":
                # Safeguard special achievement matching card color
                # This is a creative interpretation - could map to color-based special achievements
                # For now, we'll use a generic mapping
                color_to_special = {
                    "red": "monument",
                    "blue": "empire",
                    "green": "world",
                    "yellow": "wonder",
                    "purple": "universe",
                }
                special = color_to_special.get(card.color)
                if special:
                    achievement_ids.add(f"special_{special}")

            elif self.achievement_mapping == "matching_value":
                # Safeguard score achievement matching card value
                # Assuming card has a score_value attribute
                if hasattr(card, "score_value") and card.score_value:
                    # Round to nearest standard score achievement (5, 10, 15, 20, etc.)
                    score_values = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
                    closest = min(score_values, key=lambda x: abs(x - card.score_value))
                    achievement_ids.add(f"score_{closest}")

        return list(achievement_ids)

    def _safeguard_achievement(
        self, context: ActionContext, achievement_id: str
    ) -> bool:
        """
        Safeguard a specific achievement for the current player.

        Args:
            context: Action context
            achievement_id: ID of achievement to safeguard

        Returns:
            True if safeguarded successfully
        """
        # Initialize active_safeguards if not present
        if not hasattr(context.game, "active_safeguards"):
            context.game.active_safeguards = {}

        # Get current safeguard owners for this achievement
        if achievement_id not in context.game.active_safeguards:
            context.game.active_safeguards[achievement_id] = set()

        # Add current player to safeguard owners
        context.game.active_safeguards[achievement_id].add(context.player.id)

        # Check if this creates a deadlock (multiple owners)
        owners = context.game.active_safeguards[achievement_id]
        is_deadlock = len(owners) > 1

        # Log safeguard activation
        logger.debug(
            f"Safeguarded {achievement_id} by {context.player.name} "
            f"(owners: {owners}, deadlock: {is_deadlock})"
        )

        return True

    def get_required_fields(self) -> list[str]:
        return ["achievement_mapping"]

    def get_optional_fields(self) -> list[str]:
        return ["card_source", "condition", "target_player", "store_result"]
