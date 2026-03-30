"""Condition evaluation system for ConditionalAction primitive.

This package provides a structured approach to evaluating complex game state
conditions. Conditions are organized by category for maintainability and
extensibility.

Available condition evaluators:
- CardConditions: Card-based and card analysis conditions
- PlayerConditions: Player state and multi-player conditions
- GameStateConditions: Game state and action result conditions
- VariableConditions: Variable-based comparisons and logic
- LogicalConditions: Logical operators (and, or, not)
"""

from .base import BaseConditionEvaluator
from .card_conditions import CardConditions
from .game_state_conditions import GameStateConditions
from .logical_conditions import LogicalConditions
from .player_conditions import PlayerConditions
from .variable_conditions import VariableConditions
from .unseen_conditions import UnseenConditions

# Registry of all condition evaluators
CONDITION_EVALUATORS = [
    UnseenConditions(),  # Check Unseen conditions first (most specific)
    CardConditions(),
    PlayerConditions(),
    GameStateConditions(),
    VariableConditions(),
    LogicalConditions(),
]


def evaluate_condition(condition: dict, context) -> bool:
    """Evaluate a condition using the appropriate evaluator.

    Args:
        condition: Condition configuration with type and parameters.
        context: ActionContext for game state access.

    Returns:
        Boolean result of condition evaluation.
    """
    condition_type = condition.get("type")

    # Infer type from {"variable": ..., "operator": ..., "value": ...} shorthand
    if condition_type is None and "variable" in condition and "operator" in condition:
        operator = condition["operator"]
        condition_type = f"variable_{operator}"
        condition = {**condition, "type": condition_type}

    # Compatibility: support simple comparison condition shapes like
    # {"type": "equals", "left": {"type": "variable", "name": "x"}, "right": 0}
    # and lt/lte/gt/gte variants used in some tests.
    def _resolve_operand(operand):
        if isinstance(operand, dict) and operand.get("type") == "variable":
            return context.get_variable(operand.get("name"))
        return operand

    if condition_type in {"equals", "eq", "lt", "lte", "gt", "gte"}:
        left = _resolve_operand(condition.get("left"))
        right = _resolve_operand(condition.get("right"))
        try:
            if condition_type in {"equals", "eq"}:
                return left == right
            if condition_type == "lt":
                return left < right
            if condition_type == "lte":
                return left <= right
            if condition_type == "gt":
                return left > right
            if condition_type == "gte":
                return left >= right
        except Exception:
            return False

    # Try each evaluator until one handles the condition
    for evaluator in CONDITION_EVALUATORS:
        if evaluator.can_evaluate(condition_type):
            return evaluator.evaluate(condition, context)

    # Unknown condition type
    import logging

    logger = logging.getLogger(__name__)
    logger.warning(f"Unknown condition type: {condition_type}")
    return False
