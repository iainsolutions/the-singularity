"""
GetSplayDirection Action Primitive

Gets the current splay direction of a color on the board.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class GetSplayDirection(ActionPrimitive):
    """
    Gets the current splay direction for a color stack.

    Parameters:
    - color: Color to check (can be literal or variable reference)
    - player: Player to check (default: current player)
    - store_result: Variable name to store the direction (default: "splay_direction")
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.color = config.get("color")
        self.player = config.get("player")
        self.store_result = config.get("store_result", "splay_direction")

    def execute(self, context: ActionContext) -> ActionResult:
        """Get the splay direction"""
        if not self.color:
            context.add_result("No color specified for GetSplayDirection")
            return ActionResult.FAILURE

        # Resolve color
        if isinstance(self.color, str) and context.has_variable(self.color):
            color = context.get_variable(self.color)
        else:
            color = self.color

        # Resolve player
        if self.player:
            if isinstance(self.player, str) and context.has_variable(self.player):
                player = context.get_variable(self.player)
            else:
                player = self.player
        else:
            player = context.current_player

        # Get the splay direction
        if not hasattr(player, "board"):
            context.add_result(f"Player has no board")
            context.set_variable(self.store_result, "none")
            return ActionResult.SUCCESS

        # Get splay state from board
        splay_attr = f"{color}_splay"
        splay_direction = getattr(player.board, splay_attr, "none")

        # Store the result
        context.set_variable(self.store_result, splay_direction)
        logger.debug(f"Splay direction for {color}: {splay_direction}")
        context.add_result(f"{color} splay direction: {splay_direction}")

        return ActionResult.SUCCESS
