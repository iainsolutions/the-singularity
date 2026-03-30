"""
AppendToList Action Primitive

Appends an item to a list variable.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class AppendToList(ActionPrimitive):
    """
    Appends an item to a list variable in the action context.

    Parameters:
    - list_variable: Name of the list variable
    - item: Item to append (can be value or variable reference)
    - from_variable: Alternative parameter to specify item from variable
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.list_variable = config.get("list_variable") or config.get("list") or config.get("variable")
        self.item = config.get("item") or config.get("value")
        self.from_variable = config.get("from_variable")

    def execute(self, context: ActionContext) -> ActionResult:
        """Append item to the list"""
        if not self.list_variable:
            context.add_result("No list variable name specified")
            return ActionResult.FAILURE

        # Get the current list or initialize
        current_list = context.get_variable(self.list_variable, [])

        # Ensure it's a list
        if not isinstance(current_list, list):
            logger.warning(f"Variable '{self.list_variable}' is not a list, initializing as empty list")
            current_list = []

        # Determine the item to append
        if self.from_variable:
            item = context.get_variable(self.from_variable)
        elif isinstance(self.item, str) and context.has_variable(self.item):
            item = context.get_variable(self.item)
        else:
            item = self.item

        # Append the item
        current_list.append(item)
        context.set_variable(self.list_variable, current_list)

        logger.debug(f"Appended {item} to list '{self.list_variable}' (now has {len(current_list)} items)")
        context.add_result(f"Appended to {self.list_variable}")

        return ActionResult.SUCCESS
