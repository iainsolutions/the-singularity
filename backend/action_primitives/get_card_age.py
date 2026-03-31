"""
GetCardAge Action Primitive

Retrieves the age value of a card and stores it in a variable.
"""

from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult


class GetCardAge(ActionPrimitive):
    """
    Retrieves the age of a card from a variable.

    Parameters:
    - source: Variable name containing the card(s)
    - store_result: Variable name to store the age value
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        # Support both 'source' and 'card' parameters
        self.source = config.get("source") or config.get("card", "")
        # Support both 'store_result' and 'store_as' parameters
        self.store_result = config.get("store_result") or config.get("store_as", "card_age")

    def execute(self, context: ActionContext) -> ActionResult:
        """Get the age of the card(s) in the source variable"""
        # Get the card(s) from the source variable
        card_data = context.get_variable(self.source, None)

        # Handle empty source
        if not card_data:
            context.set_variable(self.store_result, 0)
            return ActionResult.SUCCESS

        age = 0

        # If it's a single Card object, get its age
        if hasattr(card_data, "age"):
            age = card_data.age
            context.set_variable(self.store_result, age)
            context.add_result(f"Retrieved era {age} from card")
            return ActionResult.SUCCESS

        # If it's a single card (dict), get its age
        if isinstance(card_data, dict):
            age = card_data.get("age", 0)
            context.set_variable(self.store_result, age)
            context.add_result(f"Retrieved era {age} from card dict")
            return ActionResult.SUCCESS

        # If it's a list of cards, get the first card's age
        if isinstance(card_data, list) and card_data:
            first_card = card_data[0]
            if hasattr(first_card, "age"):
                age = first_card.age
            elif isinstance(first_card, dict):
                age = first_card.get("age", 0)
            else:
                age = getattr(first_card, "age", 0)
            context.set_variable(self.store_result, age)
            context.add_result(f"Retrieved era {age} from first card in list")
            return ActionResult.SUCCESS

        # Default case
        context.set_variable(self.store_result, 0)
        return ActionResult.SUCCESS
