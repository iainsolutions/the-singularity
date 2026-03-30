"""Logical operator condition evaluators."""

import logging
from typing import Any

from .base import BaseConditionEvaluator

logger = logging.getLogger(__name__)


class LogicalConditions(BaseConditionEvaluator):
    """Evaluates logical operator conditions (and, or, not)."""

    @property
    def supported_conditions(self) -> set[str]:
        return {"and", "or", "not"}

    def evaluate(self, condition: dict[str, Any], context) -> bool:
        """Evaluate logical conditions."""
        condition_type = condition.get("type")

        if condition_type == "and":
            # Evaluate all conditions in the list - all must be true
            conditions = condition.get("conditions", [])
            for cond in conditions:
                # Import here to avoid circular dependency
                from . import evaluate_condition

                if not evaluate_condition(cond, context):
                    return False
            return True

        elif condition_type == "or":
            # Evaluate all conditions in the list - at least one must be true
            conditions = condition.get("conditions", [])
            for cond in conditions:
                # Import here to avoid circular dependency
                from . import evaluate_condition

                if evaluate_condition(cond, context):
                    return True
            return False

        elif condition_type == "not":
            # Negate a condition
            inner_condition = condition.get("condition")
            if inner_condition:
                # Import here to avoid circular dependency
                from . import evaluate_condition

                return not evaluate_condition(inner_condition, context)
            return False

        return False
