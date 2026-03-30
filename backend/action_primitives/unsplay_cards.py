"""
UnsplayCards Action Primitive

Remove splay from one or more color stacks.
Part of the Unseen expansion mechanics.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class UnsplayCards(ActionPrimitive):
    """
    Remove splay from color stacks (set splay direction to None).

    When splay is removed:
    - Only the top card of the stack remains visible
    - Icons from lower cards are no longer visible
    - Safe limit may decrease (for Unseen expansion)
    - Safeguards may be deactivated (for Unseen expansion)

    Parameters:
    - color: Color to unsplay ("red", "blue", "green", "yellow", "purple", "all", or variable name)
    - target_player: Which player's board to unsplay ("self", "opponent", "all")
    - update_safeguards: Whether to rebuild Safeguards after unsplaying (default: True)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.color = config.get("color")
        self.target_player = config.get("target_player", "self")
        self.update_safeguards = config.get("update_safeguards", True)

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the unsplay action"""
        logger.debug(
            f"UnsplayCards.execute: color={self.color}, target={self.target_player}"
        )

        # Validate color
        if not self.color:
            context.add_result("Error: color required for unsplay")
            return ActionResult.FAILURE

        # Resolve color (may be a variable reference)
        colors = self._resolve_colors(context)

        if not colors:
            context.add_result(f"Error: Invalid color {self.color}")
            return ActionResult.FAILURE

        # Get target player(s)
        if self.target_player == "all":
            # Unsplay for all players
            unsplay_count = 0
            for player in context.game.players:
                unsplay_count += self._unsplay_player(context, player, colors)

            activity_logger.info(
                f"Unsplayed {unsplay_count} stack(s) for all players"
            )
            context.add_result(f"Unsplayed {unsplay_count} stack(s) for all players")

        else:
            # Get specific player
            if self.target_player == "opponent":
                target_player = context.target_player or context.get_opponent()
            else:
                target_player = context.player

            if not target_player:
                context.add_result("Error: No target player found")
                return ActionResult.FAILURE

            # Unsplay for target player
            unsplay_count = self._unsplay_player(context, target_player, colors)

            activity_logger.info(
                f"{target_player.name} unsplayed {unsplay_count} color(s): {', '.join(colors)}"
            )
            context.add_result(
                f"Unsplayed {unsplay_count} color(s): {', '.join(colors)}"
            )

        # Update Safeguards if needed (Unseen expansion)
        if self.update_safeguards and context.game.expansion_config.is_enabled("unseen"):
            try:
                from game_logic.unseen.safeguard_tracker import SafeguardTracker
                tracker = SafeguardTracker(context.game)
                tracker.rebuild_all_safeguards()
                logger.debug("Safeguards rebuilt after unsplay")
            except ImportError:
                logger.warning("Could not import SafeguardTracker for unsplay")

        logger.debug("UnsplayCards: Complete")
        return ActionResult.SUCCESS

    def _resolve_colors(self, context: ActionContext) -> list[str]:
        """
        Resolve color parameter to list of color strings.

        Returns:
            List of color strings (e.g., ["red"], ["red", "blue"], or all five colors)
        """
        colors = []

        if self.color == "all":
            # All colors
            colors = ["red", "blue", "green", "yellow", "purple"]

        elif self.color in ["red", "blue", "green", "yellow", "purple"]:
            # Single specific color
            colors = [self.color]

        elif context.has_variable(self.color):
            # Variable reference (e.g., "selected_color")
            color_value = context.get_variable(self.color)
            if color_value in ["red", "blue", "green", "yellow", "purple"]:
                colors = [color_value]
            elif color_value == "all":
                colors = ["red", "blue", "green", "yellow", "purple"]

        return colors

    def _unsplay_player(self, context: ActionContext, player, colors: list[str]) -> int:
        """
        Unsplay color stacks for a specific player.

        Args:
            context: Action context
            player: Player to unsplay
            colors: List of colors to unsplay

        Returns:
            Number of stacks that were unsplayed (had splay removed)
        """
        unsplay_count = 0

        for color in colors:
            # Check if this color is currently splayed
            current_splay = player.board.splay_directions.get(color)

            if current_splay and current_splay != "none":
                # Remove splay
                player.board.splay_directions[color] = None
                unsplay_count += 1

                logger.debug(
                    f"Unsplayed {color} for {player.name} (was {current_splay})"
                )

                # Emit splay changed event
                try:
                    from logging_config import EventType
                    activity_logger.log_game_event(
                        event_type=EventType.SPLAY_CHANGED,
                        game_id=context.game.game_id,
                        player_id=player.id,
                        data={
                            "color": color,
                            "old_direction": current_splay,
                            "new_direction": None,
                            "action": "unsplay"
                        },
                        message=f"{player.name} unsplayed {color}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to log splay event: {e}")

                # Update Safe limit if Unseen expansion enabled
                if hasattr(player, "safe") and player.safe:
                    old_limit = player.get_safe_limit()
                    # Safe limit may have decreased
                    new_limit = player.get_safe_limit()

                    if new_limit != old_limit:
                        logger.debug(
                            f"Safe limit changed for {player.name}: {old_limit} -> {new_limit}"
                        )

                        try:
                            from logging_config import EventType
                            activity_logger.log_game_event(
                                event_type=EventType.SAFE_LIMIT_CHANGED,
                                game_id=context.game.game_id,
                                player_id=player.id,
                                data={
                                    "old_limit": old_limit,
                                    "new_limit": new_limit,
                                    "splay_color": color,
                                    "splay_direction": None,
                                    "safe_count": player.safe.get_card_count()
                                },
                                message=f"{player.name}'s Safe limit: {old_limit} -> {new_limit}"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to log Safe limit event: {e}")

        return unsplay_count

    def get_required_fields(self) -> list[str]:
        return ["color"]

    def get_optional_fields(self) -> list[str]:
        return ["target_player", "update_safeguards"]
