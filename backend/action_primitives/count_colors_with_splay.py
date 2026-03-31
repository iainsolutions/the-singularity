"""
CountColorsWithSplay primitive - Counts colors that have a specific splay direction.
"""

from typing import Any

from models.board_utils import BoardColorIterator

from .base import ActionContext, ActionPrimitive, ActionResult


class CountColorsWithSplay(ActionPrimitive):
    """
    Counts the number of colors on a player's board that have a specific splay direction.

    Config:
        - direction: The splay direction to check for ('left', 'right', 'up', 'aslant', or 'any')
        - player: Which player to check ('active', 'opponent', or player_id)
        - store_result: Variable name to store the count
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.direction = config.get("direction", "any")
        self.player = config.get("player", "active")
        self.store_result = config.get("store_result", "splay_count")

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the count colors with splay action"""
        try:
            # Get the target player
            if self.player == "active":
                target_player = context.player
            elif self.player == "opponent":
                # Get first opponent
                opponents = [
                    p for p in context.game.players if p.id != context.player.id
                ]
                if not opponents:
                    context.add_result("No opponents to check splays")
                    return ActionResult.SUCCESS
                target_player = opponents[0]
            else:
                target_player = context.game.get_player_by_id(self.player)
                if not target_player:
                    context.add_result(f"Player {self.player} not found")
                    return ActionResult.FAILURE

            # Count colors with the specified splay
            count = 0

            for color, color_cards in BoardColorIterator.iterate_color_stacks(
                target_player.board
            ):
                if not color_cards:
                    continue

                # Check splay direction
                splay_dir = target_player.board.splay_directions.get(color)

                if self.direction == "any":
                    # Count any splayed color
                    if splay_dir and splay_dir in ["left", "right", "up", "aslant"]:
                        count += 1
                elif self.direction == splay_dir:
                    # Count only colors with specific splay
                    count += 1

            # Store the result
            context.set_variable(self.store_result, count)

            # Log the action
            if self.direction == "any":
                context.add_result(f"Counted {count} proliferated colors")
            else:
                context.add_result(f"Counted {count} colors proliferated {self.direction}")

            return ActionResult.SUCCESS

        except Exception as e:
            context.add_result(f"Error counting proliferated colors: {e!s}")
            return ActionResult.FAILURE
