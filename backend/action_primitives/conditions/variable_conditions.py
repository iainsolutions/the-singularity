"""Variable-based condition evaluators."""

import logging
from typing import Any

from .base import BaseConditionEvaluator

logger = logging.getLogger(__name__)


class VariableConditions(BaseConditionEvaluator):
    """Evaluates conditions related to context variables and comparisons."""

    @property
    def supported_conditions(self) -> set[str]:
        return {
            "variable_exists",
            "variable_not_empty",
            "variable_true",
            "variable_false",
            "variable_equals",
            "variable_gt",
            "variable_greater_than",
            "variable_lt",
            "variable_gte",
            "variable_lte",
            "count_greater_than",
            "count_less_than",
            "count_equals",
            "count_at_least",
            "last_evaluation_true",
            "compare",
        }

    def evaluate(self, condition: dict[str, Any], context) -> bool:
        """Evaluate variable-related conditions."""
        condition_type = condition.get("type")

        if condition_type == "variable_exists":
            # Check if a variable exists in context (not None)
            var_name = condition.get("variable")
            value = context.get_variable(var_name, None)
            return value is not None

        elif condition_type == "variable_not_empty":
            # Check if a variable exists and contains a non-empty collection
            # Used for checking if card selections have items
            var_name = condition.get("variable")
            value = context.get_variable(var_name, None)
            if value is None:
                return False
            if isinstance(value, (list, tuple, set)):
                return len(value) > 0
            # For non-collection types, treat as "exists and truthy"
            return bool(value)

        elif condition_type == "variable_true":
            # Check if a variable is true
            var_name = condition.get("variable")
            return bool(context.get_variable(var_name, False))

        elif condition_type == "variable_false":
            # Check if a variable is false
            var_name = condition.get("variable")
            return not bool(context.get_variable(var_name, False))

        elif condition_type == "variable_equals":
            # Check if a variable equals a specific value
            var_name = condition.get("variable")
            expected_value = condition.get("value")
            actual_value = context.get_variable(var_name, None)
            return actual_value == expected_value

        elif (
            condition_type == "variable_gt" or condition_type == "variable_greater_than"
        ):
            # Check if a variable is greater than another variable or value
            var_name = condition.get("variable")
            # Support both 'value' and 'compare_to' for backward compatibility
            compare_to = condition.get("compare_to")
            if compare_to is None:
                compare_to = condition.get("value", 0)
            actual_value = context.get_variable(var_name, 0)

            # Compare_to can be a variable name or a direct value
            if isinstance(compare_to, str):
                compare_value = context.get_variable(compare_to, 0)
            else:
                compare_value = compare_to

            return actual_value > compare_value

        elif condition_type == "variable_lt":
            # Check if a variable is less than another variable or value
            var_name = condition.get("variable")
            compare_to = condition.get("compare_to")
            actual_value = context.get_variable(var_name, 0)

            # Compare_to can be a variable name or a direct value
            if isinstance(compare_to, str):
                compare_value = context.get_variable(compare_to, 0)
            else:
                compare_value = compare_to

            return actual_value < compare_value

        elif condition_type == "variable_gte":
            # Check if a variable is greater than or equal to another variable or value
            var_name = condition.get("variable")
            # Support both 'value' and 'compare_to' for backward compatibility
            compare_to = condition.get("compare_to")
            threshold = condition.get("value")
            if threshold is not None:
                compare_to = threshold
            actual_value = context.get_variable(var_name, 0)

            # Compare_to can be a variable name or a direct value
            if isinstance(compare_to, str):
                compare_value = context.get_variable(compare_to, 0)
            else:
                compare_value = compare_to if compare_to is not None else 0

            return actual_value >= compare_value

        elif condition_type == "variable_lte":
            # Check if a variable is less than or equal to another variable or value
            var_name = condition.get("variable")
            compare_to = condition.get("compare_to")
            actual_value = context.get_variable(var_name, 0)

            # Compare_to can be a variable name or a direct value
            if isinstance(compare_to, str):
                compare_value = context.get_variable(compare_to, 0)
            else:
                compare_value = compare_to

            return actual_value <= compare_value

        elif condition_type == "count_greater_than":
            # Check if a variable value is greater than a threshold
            value_name = condition.get("value")
            threshold = condition.get("threshold", 0)
            actual_value = context.get_variable(value_name, 0)
            return actual_value > threshold

        elif condition_type == "count_less_than":
            # Check if a variable value is less than a threshold
            value_name = condition.get("value")
            threshold = condition.get("threshold", 0)
            actual_value = context.get_variable(value_name, 0)
            return actual_value < threshold

        elif condition_type == "count_equals":
            # Check if a variable value equals a threshold
            value_name = condition.get("value")
            threshold = condition.get("threshold", 0)
            actual_value = context.get_variable(value_name, 0)
            return actual_value == threshold

        elif condition_type == "count_at_least":
            # Check if a variable value is at least a threshold (>=)
            value_name = condition.get("value")
            threshold = condition.get("threshold", 0)
            actual_value = context.get_variable(value_name, 0)

            # DEBUG: Log variable lookup for City States debugging
            logger.debug(
                f"count_at_least: variable='{value_name}', threshold={threshold}, "
                f"actual_value={actual_value}, result={actual_value >= threshold}"
            )

            # Also log all available variables to debug context propagation
            if hasattr(context, "variables"):
                logger.debug(
                    f"Available variables in context: {list(context.variables.keys())}"
                )

            return actual_value >= threshold

        elif condition_type == "last_evaluation_true":
            # Check if last evaluation was true
            last_eval = context.get_variable("last_evaluation", False)
            return bool(last_eval)

        elif condition_type == "compare":
            # Generic comparison condition for any two values
            left = condition.get("left")
            operator = condition.get("operator", "==")
            right = condition.get("right")

            # Resolve left and right values (could be variables or literals)
            if isinstance(left, str):
                left_value = context.get_variable(left, left)
            else:
                left_value = left

            if isinstance(right, str):
                right_value = context.get_variable(right, right)
            else:
                right_value = right

            # Perform comparison with None safety
            try:
                if operator == "==":
                    return left_value == right_value
                elif operator == "!=":
                    return left_value != right_value
                elif operator == ">":
                    # None cannot be compared with > operator
                    if left_value is None or right_value is None:
                        return False
                    return left_value > right_value
                elif operator == ">=":
                    # None cannot be compared with >= operator
                    if left_value is None or right_value is None:
                        return False
                    return left_value >= right_value
                elif operator == "<":
                    # None cannot be compared with < operator
                    if left_value is None or right_value is None:
                        return False
                    return left_value < right_value
                elif operator == "<=":
                    # None cannot be compared with <= operator
                    if left_value is None or right_value is None:
                        return False
                    return left_value <= right_value
                else:
                    return False
            except (TypeError, ValueError):
                # Handle cases where values can't be compared
                return False

        return False
