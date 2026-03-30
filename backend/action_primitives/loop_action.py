"""
LoopAction Action Primitive

Repeats actions until a condition is met.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult


def safe_get(obj, attr, default=None):
    """Safely get attribute from Pydantic object or dictionary."""
    if hasattr(obj, attr):  # Pydantic object
        return getattr(obj, attr, default)
    elif isinstance(obj, dict):  # Dictionary
        return obj.get(attr, default)
    else:
        return default


logger = logging.getLogger(__name__)


class LoopAction(ActionPrimitive):
    """
    Repeats actions until a condition is met.

    Parameters:
    - action: Action configuration to repeat
    - continue_condition: Condition to check for continuation
    - max_iterations: Safety limit (default: 10)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        # Support both 'action' (single) and 'actions' (list)
        if "actions" in config:
            self.actions_config = config["actions"]
        elif "action" in config:
            self.actions_config = [config["action"]]
        else:
            self.actions_config = []
        # Support both 'condition' and 'continue_condition'
        self.continue_condition = config.get("continue_condition") or config.get(
            "condition"
        )
        # Support "times" parameter for fixed iteration count
        self.times_variable = config.get("times")
        self.max_iterations = config.get("max_iterations", 10)

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute loop until condition is met or max iterations reached"""
        # Import here to avoid circular dependency
        from . import create_action_primitive
        from .evaluate_condition import EvaluateCondition

        # CRITICAL FIX: Check if this is a break directive (not a loop to execute)
        # When used from ConditionalAction's if_false: [{"type": "LoopAction", "action": "break"}]
        # This creates a LoopAction with actions_config = ["break"]
        # It should just set the flag for the PARENT loop without consuming it
        if len(self.actions_config) == 1 and self.actions_config[0] == "break":
            logger.info("🔴 LoopAction: Setting break directive for parent loop")
            context.set_variable("_loop_break", True)
            return ActionResult.SUCCESS

        if not self.actions_config:
            context.add_result("No actions specified for loop")
            return ActionResult.FAILURE

        # Get target iteration count if using "times" parameter
        target_iterations = None
        if self.times_variable:
            target_iterations = context.get_variable(self.times_variable)
            if target_iterations is not None:
                logger.debug(f"Loop will run {target_iterations} times (from variable '{self.times_variable}')")
                # Cap at max_iterations for safety
                if target_iterations > self.max_iterations:
                    logger.warning(f"Target iterations {target_iterations} exceeds max {self.max_iterations}, capping")
                    target_iterations = self.max_iterations
            else:
                logger.warning(f"Variable '{self.times_variable}' not found, defaulting to 1 iteration")
                target_iterations = 1

        iterations = 0
        loop_continued = False  # Track if we're continuing the loop

        max_loop = target_iterations if target_iterations is not None else self.max_iterations
        while iterations < max_loop:
            iterations += 1
            logger.debug(f"Loop iteration {iterations}/{self.max_iterations}")

            # CRITICAL: Clear draw-related variables at the start of each iteration (after iteration 1)
            # to prevent stale data from previous iteration affecting current iteration
            if iterations > 1:
                logger.debug("LoopAction: Clearing draw variables for fresh iteration")
                variables_to_clear = [
                    "last_drawn",
                    "first_drawn",
                    "second_drawn",
                    "third_drawn",
                ]

                # Track which variables existed before clearing (for assertion)
                vars_before = {
                    var: context.has_variable(var) for var in variables_to_clear
                }

                for var_name in variables_to_clear:
                    if context.has_variable(var_name):
                        context.remove_variable(var_name)

                # RUNTIME ASSERTION: Validate all variables were actually cleared
                for var_name in variables_to_clear:
                    if context.has_variable(var_name):
                        error_msg = f"VARIABLE LIFECYCLE ERROR: {var_name} still exists after clearing in loop iteration {iterations}"
                        logger.error(error_msg)
                        logger.error(f"Variables before clear: {vars_before}")
                        context.add_result(error_msg)
                        return ActionResult.FAILURE

            # Execute all actions in the list
            # Initialize result to SUCCESS in case we break early (e.g., break directive)
            result = ActionResult.SUCCESS

            for action_config in self.actions_config:
                # Support special break directive in multiple formats:
                # 1. Dict format: {"type": "LoopAction", "action": "break"}
                # 2. String format: "break" (when wrapped by __init__)
                if (
                    isinstance(action_config, dict)
                    and action_config.get("type") == "LoopAction"
                    and action_config.get("action") == "break"
                ) or (isinstance(action_config, str) and action_config == "break"):
                    logger.debug("LoopAction: received break directive; exiting loop")
                    context.set_variable("_loop_break", True)
                    break

                # CRITICAL FIX: Check if action_config is a dict before calling .get()
                # If it's not a dict and not "break", it's an error
                if not isinstance(action_config, dict):
                    logger.error(f"LoopAction: Invalid action_config type: {type(action_config)}, value: {action_config}")
                    context.add_result(f"Invalid loop action configuration: expected dict, got {type(action_config).__name__}")
                    return ActionResult.FAILURE

                logger.debug(f"Executing loop action: {action_config.get('type')}")
                action = create_action_primitive(action_config)
                result = action.execute(context)
                logger.debug(
                    f"Action result: {result}, context has {len(context.results)} results"
                )

                if result == ActionResult.REQUIRES_INTERACTION:
                    # Can't continue loop if waiting for interaction
                    logger.info(
                        f"Loop paused for interaction at iteration {iterations}"
                    )
                    # Propagate the interaction request from the nested action
                    if context.has_variable("final_interaction_request"):
                        interaction_request = context.get_variable(
                            "final_interaction_request"
                        )
                        logger.info(
                            f"Loop propagating interaction request: {safe_get(interaction_request, 'type', 'unknown')}"
                        )
                        # Keep the interaction request in context for caller to handle
                    return result
                elif result == ActionResult.FAILURE:
                    logger.warning(f"Loop action failed at iteration {iterations}")
                    # Surface a helpful error for adapters
                    if not context.has_variable("error"):
                        context.set_variable(
                            "error", f"LoopAction failed at iteration {iterations}"
                        )
                    break

            # Check if we broke out of the actions loop due to failure
            if result == ActionResult.FAILURE:
                break

            # Check for explicit break directive
            if context.get_variable("_loop_break", False):
                # Reset the directive and exit the loop
                context.set_variable("_loop_break", False)
                logger.debug("LoopAction: breaking outer loop due to directive")
                break

            # Check continue condition - AFTER executing actions
            if self.continue_condition:
                condition_evaluator = EvaluateCondition(
                    {"condition": self.continue_condition}
                )
                should_continue = condition_evaluator._evaluate_condition(
                    context, self.continue_condition
                )
                logger.debug(f"Loop condition evaluated to: {should_continue}")
                if not should_continue:
                    logger.debug(
                        f"Loop condition not met, exiting at iteration {iterations}"
                    )
                    break
                else:
                    loop_continued = True
                    logger.debug("Loop continuing to next iteration")
            elif target_iterations is not None:
                # Using "times" parameter - continue until we reach target
                if iterations < target_iterations:
                    loop_continued = True
                    logger.debug(f"Loop continuing: {iterations}/{target_iterations}")
                else:
                    logger.debug(f"Loop completed: {iterations}/{target_iterations}")
                    break
            else:
                # Without condition or times, only run once
                break

        # Only add summary if we actually looped multiple times
        if iterations > 1 or loop_continued:
            context.add_result(f"Repeated {iterations} times")

        logger.info(
            f"Loop completed after {iterations} iterations, total results: {len(context.results)}"
        )
        logger.debug(f"Loop results: {context.results}")
        return ActionResult.SUCCESS
