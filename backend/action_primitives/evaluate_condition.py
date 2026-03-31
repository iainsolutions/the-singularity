"""
EvaluateCondition Action Primitive

Evaluates conditional logic for branching execution.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class EvaluateCondition(ActionPrimitive):
    """
    Evaluates conditional logic and stores the result.

    Parameters:
    - condition: The condition to evaluate (can be string or structured)
    - store_result: Variable name to store the boolean result
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.condition = config.get("condition")
        self.store_result = config.get("store_result", "condition_result")

    def execute(self, context: ActionContext) -> ActionResult:
        """Evaluate condition and store result"""
        if not self.condition:
            context.add_result("No condition specified")
            return ActionResult.FAILURE

        # Evaluate condition
        condition_met = self._evaluate_condition(context, self.condition)
        logger.debug(f"Condition '{self.condition}' evaluated to {condition_met}")

        # Store the result in the configured variable
        context.set_variable(self.store_result, condition_met)

        # ALWAYS store in "last_evaluation" for ConditionalAction to use
        context.set_variable("last_evaluation", condition_met)

        context.add_result(
            f"Condition evaluated to {condition_met}, stored in '{self.store_result}' and 'last_evaluation'"
        )

        return ActionResult.SUCCESS

    def _evaluate_condition(self, context: ActionContext, condition) -> bool:
        """Evaluate a condition (string or structured)"""
        try:
            # Handle structured conditions
            if isinstance(condition, dict):
                return self._evaluate_structured_condition(context, condition)

            # Handle string conditions
            # Handle comparison operators
            if ">=" in condition:
                left, right = condition.split(">=", 1)
                return self._get_value(context, left.strip()) >= self._get_value(
                    context, right.strip()
                )
            elif "<=" in condition:
                left, right = condition.split("<=", 1)
                return self._get_value(context, left.strip()) <= self._get_value(
                    context, right.strip()
                )
            elif ">" in condition:
                left, right = condition.split(">", 1)
                return self._get_value(context, left.strip()) > self._get_value(
                    context, right.strip()
                )
            elif "<" in condition:
                left, right = condition.split("<", 1)
                return self._get_value(context, left.strip()) < self._get_value(
                    context, right.strip()
                )
            elif "==" in condition:
                left, right = condition.split("==", 1)
                return self._get_value(context, left.strip()) == self._get_value(
                    context, right.strip()
                )
            elif "!=" in condition:
                left, right = condition.split("!=", 1)
                return self._get_value(context, left.strip()) != self._get_value(
                    context, right.strip()
                )
            elif "has_symbol" in condition:
                # Format: "player has_symbol castle >= 3"
                return self._evaluate_symbol_condition(context, condition)
            else:
                # Try to evaluate as a boolean expression
                value = self._get_value(context, condition)
                return bool(value)
        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{condition}': {e}")
            return False

    def _evaluate_structured_condition(
        self, context: ActionContext, condition: dict
    ) -> bool:
        """Evaluate a structured condition using centralized evaluator"""
        from .conditions import evaluate_condition

        # Use the centralized condition evaluation system
        return evaluate_condition(condition, context)

    def _evaluate_symbol_condition(
        self, context: ActionContext, condition: str
    ) -> bool:
        """Evaluate symbol-based conditions"""
        parts = condition.split()
        if len(parts) < 3:
            return False

        # Parse the condition
        symbol_name = parts[2]
        operator = ">=" if len(parts) <= 3 else parts[3]
        threshold = 1 if len(parts) <= 4 else int(parts[4])

        from models.card import Symbol

        symbol_map = {
            "circuit": Symbol.CIRCUIT,
            "data": Symbol.DATA,
            "algorithm": Symbol.ALGORITHM,
            "neural_net": Symbol.NEURAL_NET,
            "robot": Symbol.ROBOT,
            "human_mind": Symbol.HUMAN_MIND,
        }

        if symbol_name not in symbol_map:
            logger.warning(f"Invalid symbol in condition: {symbol_name}")
            return False

        count = context.player.count_symbol(symbol_map[symbol_name])

        if operator == ">=":
            return count >= threshold
        elif operator == "<=":
            return count <= threshold
        elif operator == "==":
            return count == threshold
        elif operator == "!=":
            return count != threshold
        elif operator == ">":
            return count > threshold
        elif operator == "<":
            return count < threshold
        else:
            logger.warning(f"Invalid operator in symbol condition: {operator}")
            return False

    def _get_value(self, context: ActionContext, expression):
        """Get the value of an expression"""
        # Handle non-string expressions (already resolved values)
        if not isinstance(expression, str):
            return expression

        expression = expression.strip()

        # Check for variable reference
        if context.has_variable(expression):
            return context.get_variable(expression)

        # Boolean literals
        if expression.lower() == "true":
            return True
        elif expression.lower() == "false":
            return False

        # Numeric literal
        try:
            if "." in expression:
                return float(expression)
            else:
                return int(expression)
        except ValueError:
            pass

        # String literal
        if (expression.startswith('"') and expression.endswith('"')) or (
            expression.startswith("'") and expression.endswith("'")
        ):
            return expression[1:-1]

        # Special values
        if expression == "hand_size":
            return len(getattr(context.player, "hand", []))
        elif expression == "score_pile_size":
            return len(getattr(context.player, "score_pile", []))
        elif expression == "board_colors":
            # Count colors on board
            count = 0
            if hasattr(context.player, "board"):
                for color in ["red", "blue", "green", "purple", "yellow"]:
                    stack = getattr(context.player.board, f"{color}_cards", [])
                    if stack:
                        count += 1
            return count
        elif expression.endswith("_count"):
            # Variable count
            var_name = expression[:-6]  # Remove "_count" suffix
            items = context.get_variable(var_name, [])
            return len(items) if isinstance(items, list) else 0

        # Default to 0 for invalid expressions
        logger.debug(f"Invalid expression '{expression}', defaulting to 0")
        return 0
