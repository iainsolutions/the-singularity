"""
GetCardSymbols Action Primitive

Gets the symbols from one or more cards and stores them.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class GetCardSymbols(ActionPrimitive):
    """
    Gets the symbols from card(s) and stores them.

    Parameters:
    - source: Variable name containing the card(s)
    - store_result: Variable name to store the symbols (default: "card_symbols")
    - flatten: Whether to flatten symbols from multiple cards into one list (default: False)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.source = config.get("source") or config.get("cards")
        self.store_result = config.get("store_result", "card_symbols")
        self.flatten = config.get("flatten", False)

    def execute(self, context: ActionContext) -> ActionResult:
        """Get symbols from cards"""
        if not self.source:
            context.add_result("No source specified for GetCardSymbols")
            return ActionResult.FAILURE

        # Get the card(s) from context
        cards_data = context.get_variable(self.source)

        if not cards_data:
            context.set_variable(self.store_result, [])
            context.add_result("No cards found, returning empty list")
            return ActionResult.SUCCESS

        all_symbols = []

        # Handle single card
        if not isinstance(cards_data, list):
            cards_data = [cards_data]

        # Extract symbols from each card
        for card in cards_data:
            card_symbols = []

            if hasattr(card, "symbols"):
                # Card object with symbols list
                card_symbols = [str(s) for s in card.symbols]
            elif isinstance(card, dict) and "symbols" in card:
                # Card dictionary
                symbols_data = card["symbols"]
                if isinstance(symbols_data, list):
                    card_symbols = [str(s) for s in symbols_data]

            if self.flatten:
                all_symbols.extend(card_symbols)
            else:
                all_symbols.append(card_symbols)

        # Store the result
        context.set_variable(self.store_result, all_symbols)
        logger.debug(f"Extracted symbols from {len(cards_data)} card(s): {all_symbols}")
        context.add_result(f"Extracted symbols from {len(cards_data)} card(s)")

        return ActionResult.SUCCESS
