"""
CountUniqueColors Action Primitive

Counts unique colors on a player's board.
"""

import logging
from typing import Any

from utils.board_utils import get_board_colors, validate_player_has_board
from utils.card_utils import normalize_card_color

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class CountUniqueColors(ActionPrimitive):
    """
    Counts unique colors either from a card list or player's board.

    Parameters:
    - cards: Variable name containing cards to count colors from (optional)
    - source: Source to count from ("board" is default)
    - compare_to: What to compare against ("opponents_boards" for unique colors)
    - scope: What to count ("unique_to_player", "total_colors", "from_cards")
    - store_result/store_as: Variable name to store the count
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.cards = config.get("cards")
        self.source = config.get("source", "board")  # Support 'source' parameter
        self.compare_to = config.get("compare_to")  # Support 'compare_to' parameter
        # Map compare_to to scope for backward compatibility
        if self.compare_to == "opponents_boards":
            self.scope = "unique_to_player"
        else:
            self.scope = config.get(
                "scope", "from_cards" if self.cards else "unique_to_player"
            )
        # Support both 'store_as' and 'store_result' for consistency
        self.store_result = config.get(
            "store_as", config.get("store_result", "unique_color_count")
        )

    def execute(self, context: ActionContext) -> ActionResult:
        """Count unique colors"""
        if self.scope == "from_cards" or self.cards:
            # Count unique colors from a card list
            cards = context.get_variable(self.cards, [])
            if not isinstance(cards, list):
                context.add_result(f"Variable {self.cards} is not a list")
                return ActionResult.FAILURE

            unique_colors = set()
            for card in cards:
                color = normalize_card_color(card)
                if color:
                    unique_colors.add(color)

            count = len(unique_colors)
            context.set_variable(self.store_result, count)
            context.add_result(f"Found {count} unique colors in card list")

        elif self.scope == "unique_to_player":
            # Count colors on player's board that no opponent has
            player_colors = self._get_board_colors(context.player)
            opponent_colors = set()

            # Collect all colors from all opponents
            if hasattr(context.game, "players"):
                for other_player in context.game.players:
                    if other_player.id != context.player.id:
                        opponent_colors.update(self._get_board_colors(other_player))

            # Count colors unique to this player
            unique_colors = player_colors - opponent_colors
            count = len(unique_colors)

            context.set_variable(self.store_result, count)
            context.add_result(f"Player has {count} unique color(s)")

        elif self.scope == "total_colors":
            # Count total number of colors on player's board
            player_colors = self._get_board_colors(context.player)
            count = len(player_colors)

            context.set_variable(self.store_result, count)
            context.add_result(f"Player has {count} color(s) on board")

        else:
            context.set_variable(self.store_result, 0)
            context.add_result(f"Invalid scope: {self.scope}")
            return ActionResult.FAILURE

        logger.debug(f"Counted {count} colors with scope {self.scope}")
        return ActionResult.SUCCESS

    def _get_board_colors(self, player) -> set[str]:
        """Get all colors present on a player's board"""
        if not validate_player_has_board(player):
            return set()

        return get_board_colors(player.board)
