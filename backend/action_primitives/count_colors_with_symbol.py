"""
CountColorsWithSymbol Action Primitive

Counts board colors that have a specified symbol.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class CountColorsWithSymbol(ActionPrimitive):
    """
    Counts colors that have a specified symbol either from card list or board.

    Parameters:
    - symbol: Symbol to look for ("circuit", "data", "algorithm", "neural_net", "robot", "human_mind")
    - cards: Variable name containing cards to check (optional)
    - store_result: Variable name to store count
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.symbol = config.get("symbol", "")
        self.cards = config.get("cards")
        # Support both 'store_result' and 'store_as' parameter names
        self.store_result = config.get(
            "store_result", config.get("store_as", "color_count")
        )

    def execute(self, context: ActionContext) -> ActionResult:
        """Count colors with specified symbol"""
        if not self.symbol:
            context.add_result("No symbol specified")
            return ActionResult.FAILURE

        # If cards parameter is provided, count from card list
        if self.cards:
            cards = context.get_variable(self.cards, [])
            if not isinstance(cards, list):
                context.add_result(f"Variable {self.cards} is not a list")
                return ActionResult.FAILURE

            colors_with_symbol = set()
            for card in cards:
                if hasattr(card, "symbols") and hasattr(card, "color"):
                    # Check if card has the target symbol
                    for symbol in card.symbols:
                        symbol_str = ""
                        if hasattr(symbol, "value"):
                            symbol_str = symbol.value.lower()
                        elif hasattr(symbol, "name"):
                            symbol_str = symbol.name.lower()
                        else:
                            symbol_str = str(symbol).lower()

                        if symbol_str == self.symbol.lower():
                            # CardColor is str enum, can use directly
                            colors_with_symbol.add(str(card.color))
                            break

            count = len(colors_with_symbol)
            context.set_variable(self.store_result, count)
            context.add_result(
                f"Found {count} colors with {self.symbol} symbol in card list"
            )
            return ActionResult.SUCCESS

        # Otherwise count from player's board
        # Convert symbol name to Symbol enum if needed
        from models.card import Symbol

        symbol_map = {
            "circuit": Symbol.CIRCUIT,
            "data": Symbol.DATA,
            "algorithm": Symbol.ALGORITHM,
            "neural_net": Symbol.NEURAL_NET,
            "robot": Symbol.ROBOT,
            "human_mind": Symbol.HUMAN_MIND,
        }

        target_symbol = symbol_map.get(self.symbol.lower())
        if not target_symbol:
            context.add_result(f"Invalid symbol: {self.symbol}")
            return ActionResult.FAILURE

        count = 0
        board = context.player.board

        # Check each color stack for the symbol
        color_stacks = [
            ("blue", board.blue_cards),
            ("red", board.red_cards),
            ("green", board.green_cards),
            ("purple", board.purple_cards),
            ("yellow", board.yellow_cards),
        ]

        colors_with_symbol = []
        for color_name, cards in color_stacks:
            if cards:  # Stack has cards
                top_card = cards[-1]  # Top card of stack
                if target_symbol in top_card.symbols:
                    count += 1
                    colors_with_symbol.append(color_name)

        context.set_variable(self.store_result, count)

        if colors_with_symbol:
            context.add_result(
                f"Found {count} colors with {self.symbol} symbol: {', '.join(colors_with_symbol)}"
            )
        else:
            context.add_result(f"No colors have {self.symbol} symbol")

        logger.debug(f"Counted {count} colors with {self.symbol} symbol")
        return ActionResult.SUCCESS
