"""
WinGame and LoseGame Action Primitives

Immediately ends the game with a winner or loser.
"""

import logging
from typing import Any

from logging_config import activity_logger
from models.game import GamePhase

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class WinGame(ActionPrimitive):
    """
    Immediately ends the game with the current player (or target player) as the winner.

    Parameters:
    - target_player: Optional player to win ("self", "opponent", "demanding")
                     If not specified, defaults to context.player
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.target_player = config.get("target_player", "self")

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the win game action"""
        logger.debug(f"WinGame.execute: target_player={self.target_player}")

        # Determine which player wins
        if self.target_player == "opponent":
            winner = context.target_player or context.player
        elif self.target_player == "demanding" and context.demanding_player:
            winner = context.demanding_player
        else:
            winner = context.player

        # End the game
        context.game.winner = winner
        context.game.phase = GamePhase.FINISHED

        # Log the victory
        logger.info(f"🏆 {winner.name} wins the game!")
        context.add_result(f"{winner.name} wins the game!")

        logger.info(f"Game ended - Winner: {winner.name}")
        return ActionResult.SUCCESS

    def get_required_fields(self) -> list[str]:
        return []

    def get_optional_fields(self) -> list[str]:
        return ["target_player"]


class LoseGame(ActionPrimitive):
    """
    Immediately ends the game with the current player (or target player) as the loser.

    Parameters:
    - target_player: Optional player to lose ("self", "opponent", "demanding")
                     If not specified, defaults to context.player
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.target_player = config.get("target_player", "self")

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the lose game action"""
        logger.debug(f"LoseGame.execute: target_player={self.target_player}")

        # Determine which player loses
        if self.target_player == "opponent":
            loser = context.target_player or context.player
        elif self.target_player == "demanding" and context.demanding_player:
            loser = context.demanding_player
        else:
            loser = context.player

        # Find another player to be the winner (game must have a winner)
        # In 2-player game, the other player wins
        # In multiplayer, we could implement different logic, but for now use first non-loser
        winner = None
        for player in context.game.players:
            if player.id != loser.id:
                winner = player
                break

        if winner is None:
            # Edge case: only one player in game
            logger.warning("LoseGame: Cannot determine winner (only one player?)")
            context.add_result("Cannot determine winner")
            return ActionResult.FAILURE

        # End the game
        context.game.winner = winner
        context.game.phase = GamePhase.FINISHED

        # Log the loss
        logger.info(f"💀 {loser.name} loses the game! {winner.name} wins!")
        context.add_result(f"{loser.name} loses the game! {winner.name} wins!")

        logger.info(f"Game ended - Loser: {loser.name}, Winner: {winner.name}")
        return ActionResult.SUCCESS

    def get_required_fields(self) -> list[str]:
        return []

    def get_optional_fields(self) -> list[str]:
        return ["target_player"]
