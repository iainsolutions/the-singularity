"""
FlipCoin Action Primitive

Simulates a coin flip for game mechanics.
"""

import logging
import random
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class FlipCoin(ActionPrimitive):
    """
    Flips a coin (random 50/50 outcome).

    Parameters:
    - store_result: Variable name to store the flip result (default: "flip_result")
    - win_value: Value to store for winning flip (default: "win")
    - lose_value: Value to store for losing flip (default: "lose")
    - target_player: Optional player to flip for (defaults to context.player)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.store_result = config.get("store_result", "flip_result")
        self.win_value = config.get("win_value", "win")
        self.lose_value = config.get("lose_value", "lose")
        self.target_player = config.get("target_player")

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the coin flip"""
        logger.debug(f"FlipCoin.execute: store_result={self.store_result}")

        # Determine which player is flipping
        if self.target_player == "opponent":
            player = context.target_player or context.player
            player_name = player.name
        else:
            player = context.player
            player_name = player.name

        # Perform the coin flip (True = win, False = lose)
        flip_result = random.choice([True, False])

        # Store the result
        result_value = self.win_value if flip_result else self.lose_value
        context.set_variable(self.store_result, result_value)

        # Log the result
        outcome_text = "wins" if flip_result else "loses"
        activity_logger.info(f"{player_name} flips a coin and {outcome_text} the flip")
        context.add_result(f"{player_name} {outcome_text} the coin flip")

        logger.debug(f"FlipCoin: Result = {result_value} (stored in {self.store_result})")
        return ActionResult.SUCCESS

    def get_required_fields(self) -> list[str]:
        return []

    def get_optional_fields(self) -> list[str]:
        return ["store_result", "win_value", "lose_value", "target_player"]
