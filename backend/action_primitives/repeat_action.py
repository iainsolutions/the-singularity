"""
RepeatAction Action Primitive

Repeats an action a specified number of times.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class RepeatAction(ActionPrimitive):
    """
    Repeats an action a specified number of times.

    Parameters:
    - count: Number of times to repeat (integer or variable name)
    - action: Action configuration to repeat
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.count_config = config.get("count", 1)
        # Support both 'action' (single) and 'actions' (list)
        if "actions" in config:
            self.actions_config = config["actions"]
        elif "action" in config:
            self.actions_config = [config["action"]]
        else:
            self.actions_config = []

    @staticmethod
    def _find_inner_selection_vars(actions_config: list) -> set[str]:
        """Find store_result variables of any nested SelectCards primitives.

        Only these variables should be cleared between iterations, since they
        would be written by inner SelectCards and contaminate subsequent iterations.
        Variables merely READ by other actions (e.g., ScoreCards reading selected_cards)
        should NOT be cleared.
        """
        vars_found = set()
        for action in actions_config:
            if not isinstance(action, dict):
                continue
            if action.get("type") == "SelectCards":
                vars_found.add(action.get("store_result", "selected_cards"))
            # Recurse into ConditionalAction branches
            for key in ("if_true", "if_false", "actions"):
                nested = action.get(key, [])
                if isinstance(nested, list):
                    vars_found.update(RepeatAction._find_inner_selection_vars(nested))
        return vars_found

    def execute(self, context: ActionContext) -> ActionResult:
        """Repeat an action a specified number of times with incremental UI updates"""
        # Import here to avoid circular dependency
        from . import create_action_primitive

        # CRITICAL FIX: Check if this is a break directive (not a loop to execute)
        # When used from ConditionalAction's if_false: [{"type": "LoopAction", "action": "break"}]
        # This creates a RepeatAction with actions_config = ["break"]
        if len(self.actions_config) == 1 and self.actions_config[0] == "break":
            logger.info("🔴 RepeatAction: Setting break directive for parent loop")
            context.set_variable("_loop_break", True)
            return ActionResult.SUCCESS

        # Get count value
        if isinstance(self.count_config, str):
            count = context.get_variable(self.count_config, 0)
        else:
            count = int(self.count_config)

        if count <= 0:
            context.add_result("Repeat count is 0 or negative, skipping")
            return ActionResult.SUCCESS

        # Find variables that nested SelectCards would write to.
        # We must clear these between iterations to prevent stale selections
        # from outer scope or previous iterations contaminating the next iteration.
        # Only clear variables that inner SelectCards would SET, not variables
        # that other actions merely READ (e.g., ScoreCards reading selected_cards).
        inner_selection_vars = self._find_inner_selection_vars(self.actions_config)

        # Resume tracking: skip already-completed iterations on re-execution
        completed = context.get_variable("_repeat_completed", 0)
        resuming = context.get_variable("_repeat_resuming", False)

        context.add_result(f"Repeating action {count} times")
        logger.debug(f"Starting repeat loop for {count} iterations (completed={completed}, resuming={resuming})")

        # Track accumulated results for DrawCards actions
        accumulated_drawn = []

        # Execute the actions multiple times
        for i in range(count):
            # Skip already-completed iterations (fast-forward on resume)
            if i < completed:
                continue

            # Clear stale selection variables for fresh iterations.
            # EXCEPT when this is the resumed iteration where the response
            # handler has already set the correct selection variable.
            if inner_selection_vars:
                if i == completed and resuming:
                    # Resuming this iteration - preserve selection from response handler
                    context.remove_variable("_repeat_resuming")
                    logger.debug(f"RepeatAction: Resuming iteration {i}, preserving selection variables")
                else:
                    # Fresh iteration - clear to prevent contamination
                    for var_name in inner_selection_vars:
                        context.remove_variable(var_name)
                    context.remove_variable("final_interaction_request")
                    context.remove_variable("pending_store_result")
                    logger.debug(f"RepeatAction: Cleared selection vars {inner_selection_vars} for fresh iteration {i}")

            try:
                # Execute each action in the list
                for action_config in self.actions_config:
                    action_primitive = create_action_primitive(action_config)
                    result = action_primitive.execute(context)

                    # If this is a DrawCards action, accumulate the drawn cards
                    if action_config.get("type") == "DrawCards":
                        last_drawn = context.get_variable("last_drawn")
                        if last_drawn:
                            if isinstance(last_drawn, list):
                                accumulated_drawn.extend(last_drawn)
                            else:
                                accumulated_drawn.append(last_drawn)

                            # If this was a revealed draw, broadcast state for UI refresh
                            location = action_config.get("location", "hand")
                            if location in ["reveal", "revealed"]:
                                # Broadcast current state so UI shows the drawn card
                                logger.info(f"🔄 RepeatAction broadcasting state after revealed draw {i + 1}/{count}")

                                # Broadcast current game state via WebSocket (async, non-blocking)
                                try:
                                    import asyncio
                                    from services.broadcast_service import get_broadcast_service

                                    service = get_broadcast_service()

                                    # Format game state for broadcast
                                    game_state = context.game.to_dict()

                                    # Fire async broadcast without blocking (schedule on event loop)
                                    loop = asyncio.get_running_loop()
                                    loop.create_task(
                                        service.broadcast_game_update(
                                            game_id=context.game.game_id,
                                            message_type="game_state_updated",
                                            data={"game_state": game_state}
                                        )
                                    )
                                    logger.debug(f"Scheduled broadcast for game {context.game.game_id}")
                                except Exception as e:
                                    logger.warning(f"Failed to schedule broadcast during RepeatAction: {e}")

                    if result == ActionResult.REQUIRES_INTERACTION:
                        # Save iteration state for resume
                        if inner_selection_vars:
                            context.set_variable("_repeat_completed", i)
                            context.set_variable("_repeat_resuming", True)
                        logger.info(
                            f"RepeatAction paused for interaction at iteration {i + 1}/{count}"
                        )
                        return ActionResult.REQUIRES_INTERACTION

                    if result == ActionResult.FAILURE:
                        context.add_result(
                            f"Repeated action failed on iteration {i + 1}"
                        )
                        logger.warning(f"Repeat action failed at iteration {i + 1}")
                        return ActionResult.FAILURE

                    # Check for break directive from nested action
                    if context.get_variable("_loop_break", False):
                        logger.debug("RepeatAction: breaking inner loop due to _loop_break directive")
                        break  # Don't clear flag here - outer loop needs to see it

            except Exception as e:
                context.add_result(f"Error on iteration {i + 1}: {e!s}")
                logger.error(f"Exception in repeat action iteration {i + 1}: {e}")
                return ActionResult.FAILURE

            # Mark iteration as completed (for resume tracking)
            if inner_selection_vars:
                context.set_variable("_repeat_completed", i + 1)

            # Check for break directive after each iteration
            if context.get_variable("_loop_break", False):
                logger.debug("RepeatAction: breaking outer loop due to _loop_break directive")
                context.set_variable("_loop_break", False)
                break

        # Clean up tracking variables
        if inner_selection_vars:
            context.remove_variable("_repeat_completed")
            context.remove_variable("_repeat_resuming")

        # Store accumulated drawn cards for conditional checks
        if accumulated_drawn:
            context.set_variable("last_drawn_all", accumulated_drawn)
            logger.debug(
                f"Stored {len(accumulated_drawn)} accumulated drawn cards in last_drawn_all"
            )

        logger.info(f"Successfully completed {count} iterations")
        return ActionResult.SUCCESS
