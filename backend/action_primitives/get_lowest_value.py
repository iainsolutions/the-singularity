"""
GetLowestValue Action Primitive

Finds the lowest value from a list of numbers or cards.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class GetLowestValue(ActionPrimitive):
    """
    Finds the lowest value from a list.

    Parameters:
    - source: Variable containing list of values or cards
    - attribute: If source contains cards, which attribute to compare (default: "age")
    - store_result: Variable name to store the lowest value (default: "lowest_value")
    - store_item: Variable name to store the item with lowest value (optional)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.source = config.get("source") or config.get("list")
        self.attribute = config.get("attribute", "age")
        self.store_result = config.get("store_result", "lowest_value")
        self.store_item = config.get("store_item")

    def execute(self, context: ActionContext) -> ActionResult:
        """Find the lowest value"""
        if not self.source:
            context.add_result("No source specified for GetLowestValue")
            return ActionResult.FAILURE

        # Get the list from context
        items = context.get_variable(self.source)

        if not items:
            context.set_variable(self.store_result, None)
            if self.store_item:
                context.set_variable(self.store_item, None)
            context.add_result("No items found")
            return ActionResult.SUCCESS

        # Ensure it's a list
        if not isinstance(items, list):
            items = [items]

        if not items:
            context.set_variable(self.store_result, None)
            if self.store_item:
                context.set_variable(self.store_item, None)
            return ActionResult.SUCCESS

        # Find lowest value
        lowest_value = None
        lowest_item = None

        for item in items:
            # Get value from item
            if hasattr(item, self.attribute):
                value = getattr(item, self.attribute)
            elif isinstance(item, dict) and self.attribute in item:
                value = item[self.attribute]
            else:
                # Assume item is the value itself
                value = item

            # Convert to numeric
            try:
                value = int(value) if not isinstance(value, (int, float)) else value
            except (ValueError, TypeError):
                continue

            # Track lowest
            if lowest_value is None or value < lowest_value:
                lowest_value = value
                lowest_item = item

        # Store results
        context.set_variable(self.store_result, lowest_value)
        if self.store_item and lowest_item is not None:
            context.set_variable(self.store_item, lowest_item)

        logger.debug(f"Lowest value from {len(items)} items: {lowest_value}")
        context.add_result(f"Found lowest value: {lowest_value}")

        return ActionResult.SUCCESS
