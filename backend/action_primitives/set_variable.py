"""
SetVariable Action Primitive

Sets a variable in the action context to a specified value.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class SetVariable(ActionPrimitive):
    """
    Sets a variable in the action context.

    Parameters:
    - variable: Name of the variable to set
    - value: Value to set (can be literal or reference to another variable)
    - from_variable: Alternative parameter to read from another variable
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.variable = config.get("variable") or config.get("name")
        self.value = config.get("value")
        self.from_variable = config.get("from_variable")

    def execute(self, context: ActionContext) -> ActionResult:
        """Set the variable in context"""
        if not self.variable:
            context.add_result("No variable name specified")
            return ActionResult.FAILURE

        # Determine the value to set
        if self.from_variable:
            # Copy from another variable
            value = context.get_variable(self.from_variable)
        elif isinstance(self.value, str) and context.has_variable(self.value):
            # Value is a variable reference
            value = context.get_variable(self.value)
        else:
            # Use the literal value
            value = self.value

        # Set the variable
        context.set_variable(self.variable, value)

        logger.debug(f"Set variable '{self.variable}' to {value}")
        context.add_result(f"Set {self.variable} = {value}")

        return ActionResult.SUCCESS
