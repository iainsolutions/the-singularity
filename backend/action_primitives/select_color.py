"""
SelectColor Action Primitive

Allows player to select a color from available options.
"""

import logging
from typing import Any

from utils.board_utils import get_board_colors, get_splayable_colors, validate_player_has_board
from utils.card_utils import normalize_card_color

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class SelectColor(ActionPrimitive):
    """
    Allows player to select a color from available options.

    Parameters:
    - source: Where to get color options ("board_colors", "hand_colors", "all_colors")
    - is_optional: Whether selection can be declined (default: False)
    - store_result: Variable name to store selected color
    - filter_splayable_direction: Filter to only colors that can be splayed in direction ("left", "right", "up")
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.source = config.get("source", "board_colors")
        self.is_optional = config.get("is_optional", False)
        # Support both 'store_result' and 'store_as' parameters
        self.store_result = config.get("store_result") or config.get("store_as", "selected_color")
        self.available_colors = config.get("available_colors", [])
        self.filter_splayable_direction = config.get("filter_splayable_direction")

    def execute(self, context: ActionContext) -> ActionResult:
        """Select a color from available options"""
        available_colors = self._get_available_colors(context)
        logger.debug(
            f"SelectColor: Available colors detected: {list(available_colors)}"
        )

        if not available_colors:
            if self.is_optional:
                context.add_result("No colors available for selection")
                return ActionResult.SUCCESS
            else:
                context.add_result("No colors available for selection")
                return ActionResult.FAILURE

        # Check if we're resuming with a choice already made
        from .selection_utils import handle_selection_resume

        def on_success(_chosen_color, value, _desc):
            # CRITICAL: Also ensure "selected_color" is always set regardless of store_result config
            if self.store_result != "selected_color":
                context.set_variable("selected_color", value)
                logger.debug(
                    f"SelectColor: Set both {self.store_result} and selected_color to {value}"
                )
            return ActionResult.SUCCESS

        result = handle_selection_resume(
            context,
            resume_var_name="selected_color_choice",
            result_var_name=self.store_result,
            available_options=list(available_colors),
            primitive_name="SelectColor",
            on_success=on_success,
        )
        if result is not None:
            return result
        # Fall through to normal interaction request below

        # If only one color available, auto-select it
        if len(available_colors) == 1:
            selected_color = next(iter(available_colors))
            context.set_variable(self.store_result, selected_color)
            # CRITICAL: Also ensure "selected_color" is always set for color_selected condition
            if self.store_result != "selected_color":
                context.set_variable("selected_color", selected_color)
            context.add_result(f"Auto-selected only available color: {selected_color}")
            logger.info(f"SelectColor: Auto-selected {selected_color}")
            return ActionResult.SUCCESS

        # Need player interaction - use StandardInteractionBuilder for type safety
        from interaction.builder import StandardInteractionBuilder

        options_list = list(available_colors)
        context.set_variable("pending_color_options", options_list)

        # Use StandardInteractionBuilder to create proper color selection interaction
        interaction_request = StandardInteractionBuilder.create_color_selection_request(
            available_colors=options_list,
            message="Select a color for the effect",
            is_optional=bool(self.is_optional),
            execution_results=list(context.results) if context.results else None,
            context=context,
        )

        # Set game_id and player_id as required by the WebSocket system
        interaction_request.game_id = getattr(context.game, "game_id", "")
        interaction_request.player_id = getattr(context.player, "id", "")
        # Expose to the higher-level adapter which will carry it through
        context.set_variable("final_interaction_request", interaction_request)

        context.add_result(f"Awaiting color selection from: {', '.join(options_list)}")

        logger.info(f"Created pending color selection with {len(options_list)} options")
        return ActionResult.REQUIRES_INTERACTION

    def _get_available_colors(self, context: ActionContext) -> set[str]:
        """Get available colors based on source"""
        # Check if available_colors was provided directly in config
        if self.available_colors:
            # Normalize to lowercase for case-insensitive comparison
            colors = {
                c.lower() if isinstance(c, str) else c for c in self.available_colors
            }
        elif self.source == "board_colors":
            colors = self._get_board_colors(context.player)
        elif self.source == "hand_colors":
            colors = self._get_hand_colors(context.player)
        elif self.source == "all_colors":
            colors = {"red", "blue", "green", "purple", "yellow"}
        else:
            # Try to interpret source as a variable containing colors
            if context.has_variable(self.source):
                color_data = context.get_variable(self.source)
                if isinstance(color_data, list | set):
                    # Normalize to lowercase
                    colors = {c.lower() if isinstance(c, str) else c for c in color_data}
                elif isinstance(color_data, str):
                    colors = {color_data.lower()}
                else:
                    colors = set()
            else:
                colors = set()

        # Apply splayable filtering if requested
        if self.filter_splayable_direction:
            if not hasattr(context.player, "board"):
                return set()
            splayable_colors = get_splayable_colors(context.player.board, self.filter_splayable_direction)
            colors = colors & splayable_colors
            logger.debug(
                f"SelectColor: Filtered to splayable colors for direction '{self.filter_splayable_direction}': {colors}"
            )

        return colors

    def _get_board_colors(self, player) -> set[str]:
        """Get all colors present on a player's board"""
        if not validate_player_has_board(player):
            return set()

        return get_board_colors(player.board)

    def _get_hand_colors(self, player) -> set[str]:
        """Get all colors present in a player's hand"""
        if not hasattr(player, "hand"):
            return set()

        colors = set()
        for card in player.hand:
            color = normalize_card_color(card)
            if color:
                colors.add(color)

        return colors
