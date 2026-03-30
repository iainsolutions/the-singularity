"""
ConvertToInt Action Primitive

Converts a value to an integer and stores it.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class ConvertToInt(ActionPrimitive):
    """
    Converts a value to an integer.

    Parameters:
    - value: Value to convert (can be literal or variable reference)
    - from_variable: Alternative parameter to specify source variable
    - store_result: Variable name to store the result (default: "int_value")
    - default: Default value if conversion fails (default: 0)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.value = config.get("value")
        self.from_variable = config.get("from_variable")
        self.store_result = config.get("store_result", "int_value")
        self.default = config.get("default", 0)

    def execute(self, context: ActionContext) -> ActionResult:
        """Convert value to integer"""
        # Determine the source value
        if self.from_variable:
            source_value = context.get_variable(self.from_variable)
        elif isinstance(self.value, str) and context.has_variable(self.value):
            source_value = context.get_variable(self.value)
        else:
            source_value = self.value

        # Convert to int
        try:
            int_value = int(source_value)
            context.set_variable(self.store_result, int_value)
            logger.debug(f"Converted '{source_value}' to int: {int_value}")
            context.add_result(f"Converted to int: {int_value}")
            return ActionResult.SUCCESS
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to convert '{source_value}' to int: {e}, using default {self.default}")
            context.set_variable(self.store_result, self.default)
            context.add_result(f"Conversion failed, using default: {self.default}")
            return ActionResult.SUCCESS
