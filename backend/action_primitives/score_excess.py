"""
ScoreExcess Action Primitive

Scores all but the top N cards of a specified color.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class ScoreExcess(ActionPrimitive):
    """
    Scores all but the top N cards of a color.

    Parameters:
    - color: Color of cards to score (or variable name)
    - keep_top: Number of cards to keep on top (default: 5)
    - store_result: Variable name to store count of scored cards
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.color = config.get("color")
        self.keep_top = config.get("keep_top", 5)
        self.store_result = config.get("store_result", "scored_count")

    def execute(self, context: ActionContext) -> ActionResult:
        """Score all but top N cards of the specified color"""
        logger.debug(f"ScoreExcess.execute: color={self.color}, keep_top={self.keep_top}")

        # Check for required parameters
        if self.color is None:
            context.add_result("Missing required parameter: color")
            return ActionResult.FAILURE

        # Resolve color value
        if isinstance(self.color, str) and context.has_variable(self.color):
            color = context.get_variable(self.color)
        else:
            color = self.color

        # Resolve keep_top value
        if isinstance(self.keep_top, str) and context.has_variable(self.keep_top):
            keep_top = context.get_variable(self.keep_top)
        else:
            keep_top = self.keep_top

        try:
            keep_top = int(keep_top)
        except (ValueError, TypeError):
            context.add_result(f"Invalid keep_top value: {keep_top}")
            return ActionResult.FAILURE

        # Get the player's board
        player = context.player
        board = player.board

        # Get the color stack
        if color not in board:
            context.add_result(f"No {color} cards on board")
            context.set_variable(self.store_result, 0)
            return ActionResult.SUCCESS

        color_stack = board[color]

        # Check if there are cards to score
        if len(color_stack) <= keep_top:
            logger.debug(f"ScoreExcess: Only {len(color_stack)} cards in {color}, keeping all")
            context.set_variable(self.store_result, 0)
            return ActionResult.SUCCESS

        # Calculate how many cards to score
        num_to_score = len(color_stack) - keep_top

        # Score the bottom cards (first N cards in the list)
        cards_to_score = color_stack[:num_to_score]

        # Move cards to score pile
        for card in cards_to_score:
            player.score_pile.append(card)

        # Remove scored cards from the board
        board[color] = color_stack[num_to_score:]

        # Store the count
        context.set_variable(self.store_result, num_to_score)

        activity_logger.info(
            f"📊 {player.name} scored {num_to_score} excess {color} cards (keeping top {keep_top})"
        )

        return ActionResult.SUCCESS
