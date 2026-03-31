"""Base classes for condition evaluation system."""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseConditionEvaluator(ABC):
    """Base class for all condition evaluators.

    Each evaluator is responsible for a specific category of conditions
    and provides a consistent interface for evaluation.
    """

    @property
    @abstractmethod
    def supported_conditions(self) -> set[str]:
        """Return set of condition types this evaluator supports."""
        pass

    def can_evaluate(self, condition_type: str) -> bool:
        """Check if this evaluator can handle the given condition type.

        Args:
            condition_type: The type of condition to evaluate.

        Returns:
            True if this evaluator supports the condition type.
        """
        return condition_type in self.supported_conditions

    @abstractmethod
    def evaluate(self, condition: dict[str, Any], context) -> bool:
        """Evaluate a condition.

        Args:
            condition: Condition configuration with type and parameters.
            context: ActionContext for game state access.

        Returns:
            Boolean result of condition evaluation.
        """
        pass

    def _get_board_colors(self, board) -> set:
        """Get all colors present on a board."""
        colors = set()
        for color in ["red", "blue", "green", "purple", "yellow"]:
            stack = getattr(board, f"{color}_cards", [])
            if stack:
                colors.add(color)
        return colors

    def _count_board_symbol(self, board, symbol_name: str) -> int:
        """Count occurrences of a symbol on a board."""
        from models.card import Symbol

        symbol_map = {
            "circuit": Symbol.CIRCUIT,
            "data": Symbol.DATA,
            "algorithm": Symbol.ALGORITHM,
            "neural_net": Symbol.NEURAL_NET,
            "robot": Symbol.ROBOT,
            "human_mind": Symbol.HUMAN_MIND,
        }

        target_symbol = symbol_map.get(symbol_name.lower())
        if not target_symbol:
            return 0

        # Count symbol on all visible cards
        count = 0
        for color in ["red", "blue", "green", "purple", "yellow"]:
            stack = getattr(board, f"{color}_cards", [])
            if stack:
                # For now, just count on top card (can be expanded for splaying)
                top_card = stack[-1]
                if hasattr(top_card, "symbols"):
                    count += top_card.symbols.count(target_symbol)

        return count
