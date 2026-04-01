"""
RevealHand Action Primitive

Reveals a player's hand to another player or publicly.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class RevealHand(ActionPrimitive):
    """
    Reveals a player's hand.

    Parameters:
    - player: Player whose hand to reveal (default: current player)
    - to_player: Player who can see the hand (default: all players - public reveal)
    - store_cards: Variable name to store the revealed cards (optional)
    - store_colors: Variable name to store the card colors (optional)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.player = config.get("player")
        self.to_player = config.get("to_player")
        self.store_cards = config.get("store_cards")
        self.store_colors = config.get("store_colors")

    def execute(self, context: ActionContext) -> ActionResult:
        """Reveal the player's hand"""
        # Resolve player whose hand to reveal
        if self.player:
            if isinstance(self.player, str) and context.has_variable(self.player):
                player = context.get_variable(self.player)
            else:
                player = self.player
        else:
            player = context.player

        # Get the hand
        if not hasattr(player, "hand"):
            context.add_result(f"Player has no hand")
            return ActionResult.SUCCESS

        hand_cards = list(player.hand)

        # Store cards if requested
        if self.store_cards:
            context.set_variable(self.store_cards, hand_cards)

        # Store colors if requested
        if self.store_colors:
            colors = [str(card.color) if hasattr(card, "color") else card.get("color")
                     for card in hand_cards]
            context.set_variable(self.store_colors, colors)

        # Log the reveal
        player_name = player.name if hasattr(player, "name") else str(player.id)
        card_names = [card.name if hasattr(card, "name") else str(card) for card in hand_cards]

        if self.to_player:
            to_player_name = self.to_player if isinstance(self.to_player, str) else getattr(self.to_player, "name", "unknown")
            logger.info(f"👁️ {player_name} reveals hand to {to_player_name}: {', '.join(card_names)}")
        else:
            logger.info(f"👁️ {player_name} reveals hand: {', '.join(card_names)}")

        context.add_result(f"Revealed {len(hand_cards)} cards from hand")

        return ActionResult.SUCCESS
