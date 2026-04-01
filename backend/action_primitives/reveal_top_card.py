"""
RevealTopCard Action Primitive

Reveals (peeks at) the top card of a deck without drawing it.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class RevealTopCard(ActionPrimitive):
    """
    Reveals the top card of an age deck without drawing it.

    Parameters:
    - age: Era of supply to reveal from (number or variable name)
    - store_result: Variable name to store revealed card (default: "revealed_card")
    - store_color: Variable name to store card color (default: "revealed_color")
    - store_name: Variable name to store card name (default: "revealed_name")
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.age = config.get("age")
        self.store_result = config.get("store_result", "revealed_card")
        self.store_color = config.get("store_color", "revealed_color")
        self.store_name = config.get("store_name", "revealed_name")

    def execute(self, context: ActionContext) -> ActionResult:
        # Resolve age
        if self.age is None:
            context.add_result("Missing required parameter: age")
            return ActionResult.FAILURE

        if isinstance(self.age, str) and context.has_variable(self.age):
            age = context.get_variable(self.age)
        else:
            age = self.age

        try:
            age = int(age)
        except (ValueError, TypeError):
            context.add_result(f"Invalid era value: {age}")
            return ActionResult.FAILURE

        # Get deck from game's deck_manager
        game = context.game
        if not game or not hasattr(game, "deck_manager"):
            context.add_result("No game available")
            return ActionResult.FAILURE

        deck = game.deck_manager.age_decks.get(age, [])

        if not deck:
            context.add_result(f"Era {age} supply is empty")
            context.set_variable(self.store_result, None)
            context.set_variable(self.store_color, None)
            context.set_variable(self.store_name, None)
            return ActionResult.SUCCESS

        # Peek at top card (last in list)
        top_card = deck[-1]

        context.set_variable(self.store_result, top_card)
        color_value = top_card.color.value if hasattr(top_card.color, "value") else str(top_card.color)
        context.set_variable(self.store_color, color_value)
        context.set_variable(self.store_name, top_card.name)

        logger.info(
            f"{context.player.name} revealed {top_card.name} (era {age}, {color_value})"
        )

        return ActionResult.SUCCESS
