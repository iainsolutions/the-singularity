"""
CheckIsMyTurn Action Primitive

Checks if the current player is the active turn player.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class CheckIsMyTurn(ActionPrimitive):
    """
    Checks if the current player is the active turn player.

    Parameters:
    - store_result: Variable name to store the boolean result (default: "is_my_turn")
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.store_result = config.get("store_result", "is_my_turn")

    def execute(self, context: ActionContext) -> ActionResult:
        """Check if it's the current player's turn"""
        is_my_turn = False

        # Check if game state has current_turn_player
        if hasattr(context.game_state, "current_turn_player"):
            current_turn_player = context.game_state.current_turn_player
            is_my_turn = current_turn_player == context.current_player.id

        # Also check activating_player (for dogma execution context)
        elif hasattr(context, "activating_player"):
            is_my_turn = context.activating_player == context.current_player

        # Store result
        context.set_variable(self.store_result, is_my_turn)
        logger.debug(f"Is my turn: {is_my_turn}")
        context.add_result(f"Is my turn: {is_my_turn}")

        return ActionResult.SUCCESS
