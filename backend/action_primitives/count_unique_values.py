"""
CountUniqueValues Action Primitive

Counts unique ages/values in a card list.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class CountUniqueValues(ActionPrimitive):
    """
    Counts unique ages/values in a card list.

    Parameters:
    - cards: Variable name containing cards to count
    - criteria: What values to count ("age", "color", "symbol_count")
    - store_result: Variable name to store count
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        # Accept "selection", "source", or "cards" for field name consistency
        self.cards_var = config.get("selection") or config.get("source") or config.get("cards", "")
        self.criteria = config.get("criteria", "age")
        self.store_result = config.get("store_result", "unique_count")

    def execute(self, context: ActionContext) -> ActionResult:
        """Count unique values in a set of cards"""
        if not self.cards_var:
            context.add_result("No cards variable specified")
            return ActionResult.FAILURE

        cards = context.get_variable(self.cards_var, [])

        # Handle single card
        if not isinstance(cards, list):
            cards = [cards] if cards else []

        if not cards:
            context.set_variable(self.store_result, 0)
            context.add_result("No cards to count")
            return ActionResult.SUCCESS

        # Count unique values based on criteria
        unique_values = set()

        for card in cards:
            value = self._get_card_value(card)
            if value is not None:
                unique_values.add(value)

        count = len(unique_values)
        context.set_variable(self.store_result, count)

        context.add_result(f"Found {count} unique {self.criteria} value(s)")
        logger.debug(f"Counted {count} unique values from {len(cards)} cards")

        return ActionResult.SUCCESS

    def _get_card_value(self, card):
        """Get the value to count based on criteria"""
        if not card:
            return None

        if self.criteria == "age":
            return getattr(card, "age", None)
        elif self.criteria == "color":
            # CardColor is str enum, can use directly
            if hasattr(card, "color"):
                return card.color.value.lower()
            return None
        elif self.criteria == "symbol_count":
            # Count total symbols on the card
            count = 0
            for attr in ["top_left", "top_center", "top_right", "bottom"]:
                if hasattr(card, attr) and getattr(card, attr):
                    count += 1
            return count
        elif self.criteria == "name":
            return getattr(card, "name", None)
        else:
            # Default to age
            return getattr(card, "age", None)
