"""
CheckHandNotEmpty Action Primitive

Checks if a player's hand is not empty.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class CheckHandNotEmpty(ActionPrimitive):
    """
    Checks if a player's hand is not empty.

    Parameters:
    - player: Player to check (default: current player)
    - store_result: Variable name to store the boolean result (default: "hand_not_empty")
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.player = config.get("player")
        self.store_result = config.get("store_result", "hand_not_empty")

    def execute(self, context: ActionContext) -> ActionResult:
        """Check if hand is not empty"""
        # Resolve player
        if self.player:
            if isinstance(self.player, str) and context.has_variable(self.player):
                player = context.get_variable(self.player)
            else:
                player = self.player
        else:
            player = context.current_player

        # Check hand
        has_cards = False
        if hasattr(player, "hand") and player.hand:
            has_cards = len(player.hand) > 0

        # Store result
        context.set_variable(self.store_result, has_cards)
        logger.debug(f"Hand not empty: {has_cards}")
        context.add_result(f"Hand not empty: {has_cards}")

        return ActionResult.SUCCESS
