"""
RevealCard Action Primitive

Reveals a specific card to players.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class RevealCard(ActionPrimitive):
    """
    Reveals a specific card.

    Parameters:
    - card: Card to reveal (variable reference or card object)
    - to_player: Player who can see the card (default: all players - public reveal)
    - store_color: Variable name to store the card's color (optional)
    - store_age: Variable name to store the card's age (optional)
    - store_name: Variable name to store the card's name (optional)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.card = config.get("card") or config.get("card_variable")
        self.to_player = config.get("to_player")
        self.store_color = config.get("store_color")
        self.store_age = config.get("store_age")
        self.store_name = config.get("store_name")

    def execute(self, context: ActionContext) -> ActionResult:
        """Reveal the card"""
        if not self.card:
            context.add_result("No card specified to reveal")
            return ActionResult.FAILURE

        # Resolve card
        if isinstance(self.card, str) and context.has_variable(self.card):
            card = context.get_variable(self.card)
        else:
            card = self.card

        if not card:
            context.add_result("Card not found")
            return ActionResult.SUCCESS

        # Handle list of cards (reveal first)
        if isinstance(card, list):
            if not card:
                context.add_result("No cards to reveal")
                return ActionResult.SUCCESS
            card = card[0]

        # Store card information if requested
        if self.store_color:
            color = card.color if hasattr(card, "color") else card.get("color")
            context.set_variable(self.store_color, str(color))

        if self.store_age:
            age = card.age if hasattr(card, "age") else card.get("age")
            context.set_variable(self.store_age, age)

        if self.store_name:
            name = card.name if hasattr(card, "name") else card.get("name")
            context.set_variable(self.store_name, name)

        # Log the reveal
        card_name = card.name if hasattr(card, "name") else card.get("name", "Unknown")
        player_name = context.player.name if hasattr(context.player, "name") else "Player"

        if self.to_player:
            to_player_name = self.to_player if isinstance(self.to_player, str) else getattr(self.to_player, "name", "unknown")
            activity_logger.info(f"👁️ {player_name} reveals {card_name} to {to_player_name}")
        else:
            activity_logger.info(f"👁️ {player_name} reveals {card_name}")

        context.add_result(f"Revealed {card_name}")

        return ActionResult.SUCCESS
