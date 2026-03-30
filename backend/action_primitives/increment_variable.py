"""
IncrementVariable Action Primitive

Increments a numeric variable by a specified amount.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class IncrementVariable(ActionPrimitive):
    """
    Increments a numeric variable in the action context.

    Parameters:
    - variable: Name of the variable to increment
    - amount: Amount to increment by (default: 1)
    - initialize: Value to initialize if variable doesn't exist (default: 0)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.variable = config.get("variable") or config.get("name")
        self.amount = config.get("amount", 1)
        self.initialize = config.get("initialize", 0)

    def execute(self, context: ActionContext) -> ActionResult:
        """Increment the variable"""
        if not self.variable:
            context.add_result("No variable name specified")
            return ActionResult.FAILURE

        # Resolve the increment amount
        if isinstance(self.amount, str) and context.has_variable(self.amount):
            amount = context.get_variable(self.amount)
        else:
            amount = self.amount

        # Convert amount to int
        try:
            amount = int(amount)
        except (ValueError, TypeError):
            logger.warning(f"Invalid increment amount: {amount}, using 1")
            amount = 1

        # Get current value or initialize
        current_value = context.get_variable(self.variable, self.initialize)

        # Convert to int
        try:
            current_value = int(current_value)
        except (ValueError, TypeError):
            logger.warning(f"Variable '{self.variable}' is not numeric, initializing to {self.initialize}")
            current_value = self.initialize

        # Increment
        new_value = current_value + amount
        context.set_variable(self.variable, new_value)

        logger.debug(f"Incremented '{self.variable}' from {current_value} to {new_value}")
        context.add_result(f"Incremented {self.variable}: {current_value} → {new_value}")

        return ActionResult.SUCCESS
