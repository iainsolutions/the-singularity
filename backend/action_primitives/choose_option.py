"""
ChooseOption Action Primitive

Presents multiple choice options to the player.
"""

import logging
from typing import Any

from interaction.builder import StandardInteractionBuilder

from .base import ActionContext, ActionPrimitive, ActionResult
from .utils import attach_player_to_interaction

logger = logging.getLogger(__name__)


class ChooseOption(ActionPrimitive):
    """
    Primitive for presenting multiple choice options to the player.

    Parameters:
    - options: List of option configurations with descriptions and actions
    - auto_select_single: Auto-select if only one option (default: True)

    The chosen option value is always stored in the "chosen_option" context variable.
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.options = config.get("options", [])
        self.auto_select_single = config.get("auto_select_single", True)
        self.filter_splayable = config.get("filter_splayable")  # Optional: splay direction to filter by

    def execute(self, context: ActionContext) -> ActionResult:
        """Present options to the player or auto-select if appropriate"""
        if not self.options:
            context.add_result("No options provided")
            return ActionResult.FAILURE

        # Filter options based on splay eligibility if configured
        filtered_options = self.options
        logger.info(f"ChooseOption: filter_splayable={self.filter_splayable}, options={[o.get('value') for o in self.options]}")
        if self.filter_splayable:
            filtered_options = self._filter_splayable_options(context, self.filter_splayable)
            logger.info(f"ChooseOption: After filtering, options={[o.get('value') for o in filtered_options]}")
            if not filtered_options:
                if self.config.get("is_optional", False):
                    context.add_result("No eligible colors to splay")
                    return ActionResult.SUCCESS
                else:
                    context.add_result("No eligible colors to splay")
                    return ActionResult.FAILURE

        # Use filtered options for the rest of execution
        options_to_use = filtered_options

        # Check if we're resuming with a choice already made
        from .selection_utils import handle_selection_resume

        def value_extractor(option, index):
            """Extract value and description from option object."""
            value = option.get("value", f"option_{index}")
            desc = option.get("description", f"Option {index + 1}")
            return (value, desc)

        def on_success(chosen_option, choice_value, choice_desc):
            """Handle successful option selection."""
            # Debug logging for Canal Building
            logger.debug(
                f"ChooseOption: chose value={choice_value}, desc={choice_desc}"
            )
            logger.debug(
                f"ChooseOption: stored chosen_option={context.get_variable('chosen_option')}"
            )

            # Enhanced activity logging for all choice selections
            try:
                from logging_config import EventType, activity_logger

                if activity_logger:
                    choice_index = self.options.index(chosen_option)
                    activity_logger.log_game_event(
                        event_type=EventType.DOGMA_EFFECT_EXECUTED,
                        game_id=getattr(context.game, "game_id", ""),
                        player_id=getattr(context.player, "id", ""),
                        data={
                            "card_name": getattr(context.card, "name", "Unknown"),
                            "choice_phase": "option_selected",
                            "selected_option": {
                                "index": choice_index,
                                "description": choice_desc,
                                "value": choice_value,
                            },
                            "total_options": len(self.options),
                            "has_actions": "actions" in chosen_option,
                        },
                        message=f"Selected option: {choice_desc}",
                    )
            except Exception:
                pass

            # Execute the chosen option's actions
            if "actions" in chosen_option:
                result = self._execute_option_actions(context, chosen_option["actions"])
                if result != ActionResult.SUCCESS:
                    return result

            return ActionResult.SUCCESS

        result = handle_selection_resume(
            context,
            resume_var_name="chosen_option_choice",
            result_var_name="chosen_option",
            available_options=options_to_use,
            primitive_name="ChooseOption",
            value_extractor=value_extractor,
            on_success=on_success,
            result_message_prefix="Player chose",
        )
        if result is not None:
            return result
        # Need to create a pending action for player choice - use StandardInteractionBuilder

        # If only one option and auto-select is enabled (and not optional), select it
        # For optional choices, always ask even if only 1 option (player can decline)
        is_optional = self.config.get("is_optional", False)
        if len(options_to_use) == 1 and self.auto_select_single and not is_optional:
            # Store the resolved value for condition evaluation
            choice_value = options_to_use[0].get("value", "option_0")
            context.set_variable("chosen_option", choice_value)

            context.add_result(
                f"Auto-selected single option: {options_to_use[0].get('description', 'Option 1')}"
            )

            # Execute the option's actions if present
            if "actions" in options_to_use[0]:
                result = self._execute_option_actions(
                    context, options_to_use[0]["actions"]
                )
                if result != ActionResult.SUCCESS:
                    return result

            return ActionResult.SUCCESS

        # Create final WebSocket message directly
        # Use the new method that preserves option values
        interaction_request = (
            StandardInteractionBuilder.create_choice_selection_request_with_options(
                options=options_to_use,
                message=self.config.get("prompt", "Choose an option"),
                is_optional=self.config.get("is_optional", False),
                source_player="current_player",
                execution_results=list(context.results) if context.results else None,
            )
        )

        # Use the player from context - phase layer has already set the correct player
        target_player_id = getattr(context.player, "id", None)
        logger.debug(f"ChooseOption: Targeting player {context.player.name}")

        interaction_request = attach_player_to_interaction(
            interaction_request,
            target_player_id,
            getattr(context.game, "game_id", None),
        )

        # Store the original option configurations for execution after choice is made
        context.set_variable("pending_option_configs", options_to_use)

        # Store for direct WebSocket transmission
        context.set_variable("final_interaction_request", interaction_request)
        context.add_result(f"Awaiting player choice from {len(options_to_use)} options")

        logger.info(f"Created pending choice with {len(options_to_use)} options")

        # Return REQUIRES_INTERACTION to signal that user input is needed
        return ActionResult.REQUIRES_INTERACTION

    def _execute_option_actions(
        self, context: ActionContext, actions: list[dict]
    ) -> ActionResult:
        """Execute the actions for a chosen option"""
        if not actions:
            return ActionResult.SUCCESS

        # Import here to avoid circular dependency
        from action_primitives import create_action_primitive

        for action_config in actions:
            action = create_action_primitive(action_config)
            if action:
                result = action.execute(context)
                if result not in [ActionResult.SUCCESS, ActionResult.SKIPPED]:
                    logger.warning(f"Option action failed: {action_config.get('type')}")
                    return result
            else:
                logger.error(f"Could not create action: {action_config.get('type')}")
                return ActionResult.FAILURE

        return ActionResult.SUCCESS

    def _filter_splayable_options(
        self, context: ActionContext, splay_direction: str
    ) -> list[dict]:
        """Filter options to only include colors that can be splayed in the given direction.
        
        Args:
            context: Action execution context
            splay_direction: Direction to splay (left, right, up)
            
        Returns:
            List of options where the color is eligible for splaying
        """
        from utils.board_utils import can_splay_color, validate_player_has_board
        
        if not validate_player_has_board(context.player):
            return []
        
        filtered = []
        for option in self.options:
            color = option.get("value")
            if not color:
                continue
            
            # Check if this color can be splayed
            if can_splay_color(context.player.board, color, splay_direction):
                filtered.append(option)
            else:
                logger.debug(
                    f"ChooseOption: Filtering out {color} - not eligible for {splay_direction} splay"
                )
        
        return filtered
