"""
CountUniqueSymbols Action Primitive

Counts the number of unique symbol types in a card or collection of cards.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class CountUniqueSymbols(ActionPrimitive):
    """
    Counts unique symbol types from card(s).

    Parameters:
    - source: Variable name containing the card(s) or player reference
    - scope: Where to count from ('card', 'cards', 'board', 'hand', 'all') (default: 'cards')
    - store_result: Variable name to store the count (default: "unique_symbol_count")
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.source = config.get("source") or config.get("cards")
        self.scope = config.get("scope", "cards")
        self.store_result = config.get("store_result", "unique_symbol_count")

    def execute(self, context: ActionContext) -> ActionResult:
        """Count unique symbols"""
        unique_symbols = set()

        if self.scope == "board":
            # Count unique symbols on player's board
            player = context.player
            if hasattr(player, "board"):
                for color in ["red", "blue", "green", "yellow", "purple"]:
                    cards = getattr(player.board, f"{color}_cards", [])
                    for card in cards:
                        if hasattr(card, "symbols"):
                            for symbol in card.symbols:
                                unique_symbols.add(str(symbol))

        elif self.scope == "hand":
            # Count unique symbols in player's hand
            player = context.player
            if hasattr(player, "hand"):
                for card in player.hand:
                    if hasattr(card, "symbols"):
                        for symbol in card.symbols:
                            unique_symbols.add(str(symbol))

        elif self.scope == "all":
            # Count unique symbols across all player's cards
            player = context.player
            # Board
            if hasattr(player, "board"):
                for color in ["red", "blue", "green", "yellow", "purple"]:
                    cards = getattr(player.board, f"{color}_cards", [])
                    for card in cards:
                        if hasattr(card, "symbols"):
                            for symbol in card.symbols:
                                unique_symbols.add(str(symbol))
            # Hand
            if hasattr(player, "hand"):
                for card in player.hand:
                    if hasattr(card, "symbols"):
                        for symbol in card.symbols:
                            unique_symbols.add(str(symbol))
            # Score pile
            if hasattr(player, "score_pile"):
                for card in player.score_pile:
                    if hasattr(card, "symbols"):
                        for symbol in card.symbols:
                            unique_symbols.add(str(symbol))

        else:  # cards or card
            # Count unique symbols from specified cards
            if self.source:
                cards_data = context.get_variable(self.source)

                if cards_data:
                    # Handle single card
                    if not isinstance(cards_data, list):
                        cards_data = [cards_data]

                    # Extract symbols
                    for card in cards_data:
                        if hasattr(card, "symbols"):
                            for symbol in card.symbols:
                                unique_symbols.add(str(symbol))
                        elif isinstance(card, dict) and "symbols" in card:
                            for symbol in card["symbols"]:
                                unique_symbols.add(str(symbol))

        # Store the count
        count = len(unique_symbols)
        context.set_variable(self.store_result, count)
        logger.debug(f"Counted {count} unique symbols: {unique_symbols}")
        context.add_result(f"Unique symbols: {count}")

        return ActionResult.SUCCESS
