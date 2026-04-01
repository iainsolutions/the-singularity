"""
GetCardColors Action Primitive

Gets the color(s) from one or more cards and stores them.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class GetCardColors(ActionPrimitive):
    """
    Gets the color(s) from card(s) and stores them.

    Parameters:
    - source: Variable name containing the card(s)
    - store_result: Variable name to store the color(s) (default: "card_colors")
    - unique: Whether to return only unique colors (default: False)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.source = config.get("source") or config.get("cards")
        self.store_result = config.get("store_result", "card_colors")
        self.unique = config.get("unique", False)

    def execute(self, context: ActionContext) -> ActionResult:
        """Get colors from cards"""
        if not self.source:
            context.add_result("No source specified for GetCardColors")
            return ActionResult.FAILURE

        # Get the card(s) from context
        cards_data = context.get_variable(self.source)

        if not cards_data:
            context.set_variable(self.store_result, [])
            context.add_result("No cards found, returning empty list")
            return ActionResult.SUCCESS

        colors = []

        # Handle single card
        if not isinstance(cards_data, list):
            cards_data = [cards_data]

        # Extract colors from each card
        for card in cards_data:
            if hasattr(card, "color"):
                # Card object
                colors.append(card.color.value)
            elif isinstance(card, dict) and "color" in card:
                # Card dictionary
                colors.append(card["color"])

        # Remove duplicates if requested
        if self.unique:
            colors = list(dict.fromkeys(colors))  # Preserve order

        context.set_variable(self.store_result, colors)
        logger.debug(f"Extracted {len(colors)} color(s) from {len(cards_data)} card(s): {colors}")
        context.add_result(f"Extracted colors: {colors}")

        return ActionResult.SUCCESS
