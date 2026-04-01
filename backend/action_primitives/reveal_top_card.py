"""
RevealTopCard Action Primitive

Reveals (peeks at) the top card of a deck without drawing it.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class RevealTopCard(ActionPrimitive):
    """
    Reveals the top card of an age deck without drawing it.

    Parameters:
    - age: Age of deck to reveal from (can be a number or variable name)
    - store_result: Variable name to store revealed card info (default: "revealed_card")
    - store_color: Variable name to store the card's color (default: "revealed_color")
    - store_name: Variable name to store the card's name (default: "revealed_name")
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.age = config.get("age")
        self.store_result = config.get("store_result", "revealed_card")
        self.store_color = config.get("store_color", "revealed_color")
        self.store_name = config.get("store_name", "revealed_name")

    def execute(self, context: ActionContext) -> ActionResult:
        """Reveal the top card of the specified age deck"""
        logger.debug(f"RevealTopCard.execute: age={self.age}")

        # Check for required parameters
        if self.age is None:
            context.add_result("Missing required parameter: age")
            return ActionResult.FAILURE

        # Resolve age value
        if isinstance(self.age, str) and context.has_variable(self.age):
            age = context.get_variable(self.age)
        else:
            age = self.age

        # Convert to int
        try:
            age = int(age)
        except (ValueError, TypeError):
            context.add_result(f"Invalid era value: {age}")
            return ActionResult.FAILURE

        # Get the game state
        game_state = context.game_state
        if not game_state:
            context.add_result("No game state available")
            return ActionResult.FAILURE

        # Get the deck for this age
        deck_key = f"age_{age}"
        if deck_key not in game_state.decks:
            context.add_result(f"No supply found for era {age}")
            return ActionResult.FAILURE

        deck = game_state.decks[deck_key]

        # Check if deck is empty
        if not deck or len(deck) == 0:
            logger.debug(f"RevealTopCard: Deck {age} is empty")
            context.add_result(f"Deck {age} is empty")
            # Store None to indicate no card
            context.set_variable(self.store_result, None)
            context.set_variable(self.store_color, None)
            context.set_variable(self.store_name, None)
            return ActionResult.SUCCESS

        # Peek at the top card (last in the list)
        top_card = deck[-1]

        # Store card information
        context.set_variable(self.store_result, top_card)
        context.set_variable(self.store_color, top_card.color)
        context.set_variable(self.store_name, top_card.name)

        logger.info(
            f"🔍 {context.player.name} revealed {top_card.name} (age {age}, {top_card.color})"
        )

        return ActionResult.SUCCESS
