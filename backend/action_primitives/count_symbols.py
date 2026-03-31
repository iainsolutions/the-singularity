"""
CountSymbols Action Primitive

Counts symbols on a player's board.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class CountSymbols(ActionPrimitive):
    """
    Primitive for counting symbols on a player's board.

    Parameters:
    - symbol: Symbol to count ("data", "circuit", "neural_net", "algorithm", "robot", "human_mind")
    - scope: How to count - "total_symbols" or "colors_with_symbol" (unique colors)
    - store_result: Variable name to store the count (default: "symbol_count")
    - player: Which player to count for ("self", "target", "all_opponents")
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.symbol = config.get("symbol", "data")
        self.scope = config.get("scope", "total_symbols")
        # Support both 'store_result' and 'store_as' parameter names for backward compatibility
        self.store_result = config.get(
            "store_result", config.get("store_as", "symbol_count")
        )
        self.player = config.get("player", "self")

    def execute(self, context: ActionContext) -> ActionResult:
        """Count symbols on the board"""
        # Normalize symbol name to lowercase for consistent comparison
        symbol_lower = self.symbol.lower()

        # Validate symbol name against known symbols
        valid_symbols = ["circuit", "data", "algorithm", "neural_net", "robot", "human_mind"]
        if symbol_lower not in valid_symbols:
            context.add_result(f"Invalid symbol: {self.symbol}")
            return ActionResult.FAILURE

        # Determine target player based on configuration
        if self.player == "self":
            target_player = context.player
        elif self.player == "target" and context.target_player is not None:
            target_player = context.target_player
        else:
            target_player = context.player

        # Handle edge case where player has no board
        if not hasattr(target_player, "board"):
            context.set_variable(self.store_result, 0)
            context.add_result(f"Player has no board, {symbol_lower} count: 0")
            return ActionResult.SUCCESS

        board = target_player.board

        if self.scope == "colors_with_symbol":
            # Count unique colors that have at least one of the symbol
            # This is complex because we need to isolate each color stack to count accurately

            # Import symbol mapping utilities for consistent conversion
            from models.card import Symbol

            symbol_map = {
                "circuit": Symbol.CIRCUIT,
                "data": Symbol.DATA,
                "algorithm": Symbol.ALGORITHM,
                "neural_net": Symbol.NEURAL_NET,
                "robot": Symbol.ROBOT,
                "human_mind": Symbol.HUMAN_MIND,
            }
            symbol_enum = symbol_map.get(symbol_lower, symbol_lower)

            colors_with_symbol = set()

            # Check each color independently to avoid splay interference
            for color in ["red", "blue", "green", "purple", "yellow"]:
                stack = board.get_cards_by_color(color)
                if stack:
                    # CRITICAL: Temporarily isolate this color stack
                    # The board.count_symbol() method considers splay effects across ALL colors,
                    # but we only want symbols from THIS specific color. To do this safely,
                    # we temporarily empty other color stacks, count symbols, then restore.

                    # Step 1: Store original state of other color stacks
                    original_stacks = {}
                    for c in ["red", "blue", "green", "purple", "yellow"]:
                        if c != color:
                            # Save the original stack
                            original_stacks[c] = getattr(board, f"{c}_cards")
                            # Temporarily empty this stack
                            setattr(board, f"{c}_cards", [])

                    # Step 2: Count symbols with only this color present
                    # Now board.count_symbol() will only see symbols from our target color
                    count_for_color = board.count_symbol(symbol_enum)

                    # Step 3: Restore all other color stacks to original state
                    for c, stack_val in original_stacks.items():
                        setattr(board, f"{c}_cards", stack_val)

                    # Step 4: Record if this color has any of the target symbol
                    if count_for_color > 0:
                        colors_with_symbol.add(color)

            # Final result: number of unique colors with the symbol
            count = len(colors_with_symbol)
            context.set_variable(self.store_result, count)
            context.add_result(f"Colors with {symbol_lower}: {count}")

        else:
            # Count total symbols across entire board - simpler case
            # Use board's count_symbol method which handles splay effects automatically

            from models.card import Symbol

            symbol_map = {
                "circuit": Symbol.CIRCUIT,
                "data": Symbol.DATA,
                "algorithm": Symbol.ALGORITHM,
                "neural_net": Symbol.NEURAL_NET,
                "robot": Symbol.ROBOT,
                "human_mind": Symbol.HUMAN_MIND,
            }
            symbol_enum = symbol_map.get(symbol_lower, symbol_lower)

            try:
                # Board's count_symbol method automatically handles:
                # - Splay direction visibility rules
                # - Multiple instances of same symbol on a card
                # - All color stacks simultaneously
                count = board.count_symbol(symbol_enum)
            except Exception as e:
                logger.error(f"Failed to count symbols: {e}")
                count = 0

            context.set_variable(self.store_result, count)
            context.add_result(f"Total {symbol_lower} symbols: {count}")

        logger.debug(f"Counted {count} {symbol_lower} symbols (scope: {self.scope})")
        return ActionResult.SUCCESS
