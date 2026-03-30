"""
CalculateValue Action Primitive

Performs arithmetic calculations on values and stores the result.
"""

from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult


class CalculateValue(ActionPrimitive):
    """
    Performs arithmetic operations on values.

    Parameters:
    - operation: The operation to perform ('add', 'subtract', 'multiply', 'divide')
    - left: Left operand (can be a number or variable name)
    - right: Right operand (can be a number or variable name)
    - store_result: Variable name to store the result
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.operation = config.get("operation", "add")
        # Support both parameter name styles
        self.left = config.get("left") or config.get("operand1") or config.get("value1")
        self.right = config.get("right") or config.get("operand2") or config.get("value2")
        # Support both store_result and store_as parameter names (Printing Press uses store_as)
        self.store_result = config.get("store_result") or config.get("store_as", "calculated_value")

    def _resolve_operand(self, operand, context: ActionContext):
        """Resolve an operand to its value.

        Handles:
        - Dict with {"type": "variable", "name": "var_name"} - resolve from context
        - String - resolve from context if variable exists, else use as literal
        - Number - use directly
        """
        if isinstance(operand, dict) and operand.get("type") == "variable":
            # Dict reference like {"type": "variable", "name": "temp_count_1"}
            var_name = operand.get("name")
            return context.get_variable(var_name, 0)
        elif isinstance(operand, str) and context.has_variable(operand):
            # String variable name
            return context.get_variable(operand)
        else:
            # Direct value (number)
            return operand

    def execute(self, context: ActionContext) -> ActionResult:
        """Perform the calculation"""
        # Resolve left operand
        left_value = self._resolve_operand(self.left, context)

        # Resolve right operand
        right_value = self._resolve_operand(self.right, context)

        # Convert to numbers
        try:
            left_value = int(left_value) if left_value is not None else 0
            right_value = int(right_value) if right_value is not None else 0
        except (ValueError, TypeError):
            context.add_result(
                f"Invalid operands for calculation: {left_value}, {right_value}"
            )
            return ActionResult.FAILURE

        # Perform operation
        if self.operation == "add":
            calculated = left_value + right_value
        elif self.operation == "subtract":
            calculated = left_value - right_value
        elif self.operation == "multiply":
            calculated = left_value * right_value
        elif self.operation == "divide":
            calculated = 0 if right_value == 0 else left_value // right_value  # Integer division, avoid division by zero
        else:
            context.add_result(f"Invalid operation: {self.operation}")
            return ActionResult.FAILURE

        # Store result
        context.set_variable(self.store_result, calculated)
        context.add_result(
            f"Calculated {left_value} {self.operation} {right_value} = {calculated}"
        )

        return ActionResult.SUCCESS
