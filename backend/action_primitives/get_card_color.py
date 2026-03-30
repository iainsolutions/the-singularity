"""
GetCardColor primitive - Gets the color of a specified card.
"""

from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult


class GetCardColor(ActionPrimitive):
    """
    Gets the color of a specified card and stores it in a variable.

    Config:
        - card: Variable containing the card or card name
        - source: Where to find the card ('variable', 'top_card', 'last_drawn')
        - color: If source is 'top_card', which color stack (optional)
        - store_result: Variable name to store the color
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.card_source = config.get("card")
        self.source = config.get("source", "variable")
        self.color = config.get("color")
        # Support both 'store_result' and 'store_as' parameters
        self.store_result = config.get("store_result") or config.get(
            "store_as", "card_color"
        )

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the get card color action"""
        try:
            card = None

            if self.source == "variable":
                # Get card from variable
                card = context.get_variable(self.card_source)
                if isinstance(card, list) and card:
                    card = card[0]

            elif self.source == "last_drawn":
                # Get last drawn card
                last_drawn = context.get_variable("last_drawn", [])
                if last_drawn:
                    card = last_drawn[0] if isinstance(last_drawn, list) else last_drawn

            elif self.source == "top_card":
                # Get top card from board
                if self.color:
                    # Specific color stack
                    color_cards = getattr(
                        context.player.board, f"{self.color}_cards", []
                    )
                    if color_cards:
                        card = color_cards[-1]
                else:
                    # Any top card
                    top_cards = context.player.board.get_top_cards()
                    if top_cards:
                        card = top_cards[0]

            if not card:
                context.add_result("No card found to get color from")
                # Set a default value
                context.set_variable(self.store_result, None)
                return ActionResult.SUCCESS

            # Get the color
            if hasattr(card, "color"):
                # Card object with color attribute - store the actual CardColor enum
                color = card.color
            else:
                # Dictionary or other structure
                color = card.get("color") if isinstance(card, dict) else None

            if not color:
                context.add_result("Card has no color attribute")
                context.set_variable(self.store_result, None)
                return ActionResult.SUCCESS

            # Store the color
            context.set_variable(self.store_result, color)

            # Log the action
            card_name = card.name if hasattr(card, "name") else str(card)
            context.add_result(f"Got color '{color}' from {card_name}")

            return ActionResult.SUCCESS

        except Exception as e:
            context.add_result(f"Error getting card color: {e!s}")
            return ActionResult.FAILURE
