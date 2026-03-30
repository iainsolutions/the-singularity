"""
ConditionalAction Action Primitive

Executes actions conditionally based on game state.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class ConditionalAction(ActionPrimitive):
    """
    Executes actions conditionally based on game state.

    Parameters:
    - condition: Condition to evaluate (dict with type and parameters)
    - true_action: Action to execute if condition is true
    - false_action: Optional action to execute if condition is false
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.condition = config.get("condition", {})
        self.execute_as = config.get(
            "execute_as"
        )  # Support execute_as at ConditionalAction level
        # Support multiple naming variants:
        # if_true/if_false, then_actions/else_actions, true_action/false_action
        self.true_actions = (
            config.get("if_true")
            or config.get("then_actions")
            or config.get("true_action")
        )
        self.false_actions = (
            config.get("if_false")
            or config.get("else_actions")
            or config.get("false_action")
        )

        # Ensure actions are lists
        if self.true_actions and not isinstance(self.true_actions, list):
            self.true_actions = [self.true_actions]
        if self.false_actions and not isinstance(self.false_actions, list):
            self.false_actions = [self.false_actions]

    def execute(self, context: ActionContext) -> ActionResult:
        """Evaluate condition and execute appropriate action(s)"""
        # Import here to avoid circular dependency
        from . import create_action_primitive

        # Resume tracking: if a sub-action previously suspended for interaction,
        # skip directly to that sub-action instead of re-executing completed ones.
        # Uses a stack to handle nested ConditionalActions correctly.
        resume_stack = context.get_variable("_conditional_resume_stack", [])
        if resume_stack:
            branch, start_idx = resume_stack.pop()
            context.set_variable("_conditional_resume_stack", resume_stack)
            actions_to_execute = self.true_actions if branch == "true" else self.false_actions
            logger.debug(
                f"ConditionalAction: Resuming {branch} branch at sub-action {start_idx}"
            )
        else:
            # Fresh execution - evaluate condition
            condition_met = self._evaluate_condition(context)

            # Debug logging for Canal Building
            if self.condition.get("type") == "option_chosen":
                option_value = self.condition.get("option")
                chosen_option = context.get_variable("chosen_option")
                logger.debug(
                    f"ConditionalAction option_chosen: expected={option_value}, actual={chosen_option}, match={condition_met}"
                )

            logger.info(
                f"=== ConditionalAction: Condition type '{self.condition.get('type')}' evaluated to {condition_met}"
            )

            actions_to_execute = self.true_actions if condition_met else self.false_actions
            start_idx = 0

        if actions_to_execute:
            if start_idx == 0:
                context.add_result(
                    f"Condition evaluated, executing {len(actions_to_execute)} actions"
                )
            logger.info(
                f"=== ConditionalAction: Executing {len(actions_to_execute)} actions (start_idx={start_idx})"
            )
            # Execute actions in sequence, skipping completed ones on resume
            for i, action_config in enumerate(actions_to_execute):
                if i < start_idx:
                    logger.debug(f"ConditionalAction: Skipping completed sub-action {i}")
                    continue

                logger.info(f"=== ConditionalAction: Executing sub-action {i}: {action_config.get('type', 'unknown')}")

                # CRITICAL FIX: Check execute_as parameter to determine which player executes
                # This is needed for nested actions inside demands (e.g., Oars DrawCards)
                # Check execute_as on the action config first, then fall back to ConditionalAction's execute_as
                exec_as = ""
                if isinstance(action_config, dict):
                    exec_as = (
                        action_config.get("execute_as") or self.execute_as or ""
                    ).lower()
                elif self.execute_as:
                    exec_as = self.execute_as.lower()

                if exec_as in (
                    "activating",
                    "demanding",
                    "active",
                    "activating_player",
                ):
                    # Execute as activating player (the one who played the dogma card)
                    activating_player = context.get_variable(
                        "activating_player"
                    ) or getattr(context, "activating_player", None)
                    if activating_player:
                        # Create a new context with the activating player
                        from .base import ActionContext

                        exec_context = ActionContext(
                            game=context.game,
                            player=activating_player,
                            card=context.card,
                            variables=context.variables,
                            results=context.results,
                            state_tracker=context.state_tracker,
                        )
                        logger.debug(
                            f"ConditionalAction: Executing nested action as activating player {activating_player.name}"
                        )
                    else:
                        exec_context = context
                else:
                    # Execute as current context player (default)
                    exec_context = context

                action = create_action_primitive(action_config)
                result = action.execute(exec_context)
                logger.debug(f"Sub-action {i} result: {result}")
                if result == ActionResult.REQUIRES_INTERACTION:
                    # Save resume state: which branch and which sub-action to resume at
                    branch = "true" if actions_to_execute is self.true_actions else "false"
                    resume_stack = context.get_variable("_conditional_resume_stack", [])
                    resume_stack.append((branch, i))
                    context.set_variable("_conditional_resume_stack", resume_stack)
                    logger.info(
                        f"ConditionalAction: Sub-action {i} requires interaction, saving resume state"
                    )
                    return ActionResult.REQUIRES_INTERACTION
                if result == ActionResult.FAILURE:
                    logger.error(
                        f"ConditionalAction sub-action {i} failed: {action_config['type']} returned {result}"
                    )
                    return result  # Stop on first failure
            return ActionResult.SUCCESS
        else:
            context.add_result(
                f"Condition evaluated, no action to execute"
            )
            return ActionResult.SUCCESS

    def _evaluate_condition(self, context: ActionContext) -> bool:
        """Evaluate the condition using the structured condition evaluation system."""
        from .conditions import evaluate_condition

        return evaluate_condition(self.condition, context)

    def _get_board_colors(self, board) -> set:
        """Get all colors present on a board"""
        colors = set()
        for color in ["red", "blue", "green", "purple", "yellow"]:
            stack = getattr(board, f"{color}_cards", [])
            if stack:
                colors.add(color)
        return colors

    def _count_board_symbol(self, board, symbol_name: str) -> int:
        """Count occurrences of a symbol on a board"""
        from models.card import Symbol

        symbol_map = {
            "castle": Symbol.CASTLE,
            "leaf": Symbol.LEAF,
            "lightbulb": Symbol.LIGHTBULB,
            "crown": Symbol.CROWN,
            "factory": Symbol.FACTORY,
            "clock": Symbol.CLOCK,
        }

        target_symbol = symbol_map.get(symbol_name.lower())
        if not target_symbol:
            return 0

        # Count symbol on all visible cards
        count = 0
        for color in ["red", "blue", "green", "purple", "yellow"]:
            stack = getattr(board, f"{color}_cards", [])
            if stack:
                # For now, just count on top card (can be expanded for splaying)
                top_card = stack[-1]
                if hasattr(top_card, "symbols"):
                    count += top_card.symbols.count(target_symbol)

        return count
