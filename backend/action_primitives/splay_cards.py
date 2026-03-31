"""
SplayCards Action Primitive

Changes the splay direction of a color stack on the player's board.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class SplayCards(ActionPrimitive):
    """
    Primitive for splaying cards in a specific direction.

    Parameters:
    - color: Color to splay ("red", "blue", etc.) or variable name
    - direction: Splay direction ("left", "right", "up")
    - is_optional: Whether splaying can be declined (default: True)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.color = config.get("color")
        self.direction = config.get("direction", "left")
        self.is_optional = config.get("is_optional", True)

    def execute(self, context: ActionContext) -> ActionResult:
        """Splay cards in the specified direction"""
        logger.info(
            f"🎴 SplayCards execute: color config={self.color}, direction={self.direction}, is_optional={self.is_optional}"
        )

        # Resolve color if it's a variable
        if isinstance(self.color, str) and context.has_variable(self.color):
            color = context.get_variable(self.color)
            logger.info(
                f"🎴 SplayCards: Resolved color variable '{self.color}' to '{color}'"
            )
        else:
            color = self.color
            logger.info(f"🎴 SplayCards: Using literal color '{color}'")

        if not color:
            logger.info(f"🎴 SplayCards: No color specified, is_optional={self.is_optional}")
            context.add_result("No color specified for splaying")
            if self.is_optional:
                return ActionResult.SUCCESS
            return ActionResult.FAILURE

        # Normalize color to lowercase string
        if hasattr(color, "value"):
            # It's an enum
            color_str = color.value.lower()
        else:
            color_str = str(color).lower()

        logger.info(f"🎴 SplayCards: Normalized color_str = '{color_str}'")

        # Validate color
        valid_colors = ["red", "blue", "green", "purple", "yellow"]
        if color_str not in valid_colors:
            logger.error(f"🎴 SplayCards: Invalid color '{color_str}', is_optional={self.is_optional}")
            context.add_result(f"Invalid color for splaying: {color}")
            if self.is_optional:
                return ActionResult.SUCCESS
            return ActionResult.FAILURE

        # Check if player has cards in that color
        if not hasattr(context.player, "board"):
            logger.error(f"🎴 SplayCards: Player has no board, is_optional={self.is_optional}")
            context.add_result("Player has no board")
            if self.is_optional:
                return ActionResult.SUCCESS
            return ActionResult.FAILURE

        # Get the stack for this color
        stack_attr = f"{color_str}_cards"
        if not hasattr(context.player.board, stack_attr):
            # Create empty stack if it doesn't exist
            setattr(context.player.board, stack_attr, [])

        stack = getattr(context.player.board, stack_attr)

        logger.info(f"🎴 SplayCards: Stack '{stack_attr}' has {len(stack)} cards")

        # Check if we have enough cards for splaying
        if len(stack) < 2:
            # Silently skip - nothing to splay
            logger.info(f"🎴 SplayCards: Not enough cards to splay ({len(stack)} < 2), returning SUCCESS")
            context.add_result(f"No cards to splay in {color_str}")
            return ActionResult.SUCCESS

        # Check if already splayed in this direction
        old_direction = None
        if hasattr(context.player.board, "splay_directions"):
            old_direction = context.player.board.splay_directions.get(color_str)
            if old_direction == self.direction:
                # Already splayed correctly - silently skip
                logger.info(f"🎴 SplayCards: Already splayed {self.direction}, returning SUCCESS")
                context.add_result(
                    f"{color_str.capitalize()} already splayed {self.direction}"
                )
                return ActionResult.SUCCESS

        # Use board's splay method if available, otherwise set splay_directions directly
        if hasattr(context.player.board, "splay") and callable(
            context.player.board.splay
        ):
            try:
                context.player.board.splay(color_str, self.direction)
                context.add_result(f"{color_str.capitalize()} stack splayed {self.direction}")
                logger.info(
                    f"✅ Splayed {color_str} cards {self.direction} for player {getattr(context.player, 'name', 'Player')}"
                )
                # Record state change BEFORE returning
                context.state_tracker.record_splay(
                    player_name=context.player.name,
                    color=color_str,
                    direction=self.direction,
                    context=context.get_variable("current_effect_context", "splay"),
                )

                return ActionResult.SUCCESS
            except Exception as e:
                logger.error(f"🎴 SplayCards: Exception in board.splay: {e}, is_optional={self.is_optional}")
                if self.is_optional:
                    return ActionResult.SUCCESS
                return ActionResult.FAILURE

        # Fallback: Set the splay direction in the splay_directions dictionary
        if not hasattr(context.player.board, "splay_directions"):
            context.player.board.splay_directions = {}

        # Handle mappingproxy (immutable dict proxy from Pydantic)
        splay_dirs = context.player.board.splay_directions
        if type(splay_dirs).__name__ == "mappingproxy":
            # Convert to mutable dict
            splay_dirs = dict(splay_dirs)
            context.player.board.splay_directions = splay_dirs

        context.player.board.splay_directions[color_str] = self.direction

        # Record state change
        context.state_tracker.record_splay(
            player_name=context.player.name,
            color=color_str,
            direction=self.direction,
            context=context.get_variable("current_effect_context", "splay"),
        )

        context.add_result(f"{color_str.capitalize()} stack splayed {self.direction}")
        logger.info(
            f"✅ Splayed {color_str} cards {self.direction} for player {getattr(context.player, 'name', 'Player')}"
        )

        # Activity: record splay action
        try:
            from logging_config import activity_logger

            activity_logger.log_game_event(
                event_type=None,
                game_id=getattr(context.game, "game_id", ""),
                player_id=getattr(context.player, "id", ""),
                data={
                    "action": "splay",
                    "card_name": getattr(context.card, "name", "Effect"),
                    "color": color_str,
                    "direction": self.direction,
                },
                message=f"Splayed {color_str} {self.direction}",
            )
        except Exception:
            pass

        return ActionResult.SUCCESS
