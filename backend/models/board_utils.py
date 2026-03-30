"""
Utility functions for PlayerBoard operations to avoid repetitive code.
"""

from typing import TYPE_CHECKING

from models.card import Card, CardColor

if TYPE_CHECKING:
    from models.player import PlayerBoard


# Define the canonical list of colors once
BOARD_COLORS = ["blue", "red", "green", "yellow", "purple"]

# Create a mapping from CardColor enum to string values
COLOR_ENUM_TO_STRING = {
    CardColor.BLUE: "blue",
    CardColor.RED: "red",
    CardColor.GREEN: "green",
    CardColor.YELLOW: "yellow",
    CardColor.PURPLE: "purple",
}


class BoardColorIterator:
    """Helper class to iterate over board colors and their cards"""

    @staticmethod
    def get_all_colors() -> list[str]:
        """Get the list of all board colors"""
        return BOARD_COLORS.copy()

    @staticmethod
    def iterate_color_stacks(board: "PlayerBoard"):
        """
        Iterate over all color stacks on a board.
        Yields: (color_name, card_list)
        """
        for color in BOARD_COLORS:
            cards = getattr(board, f"{color}_cards", [])
            yield color, cards

    @staticmethod
    def iterate_non_empty_stacks(board: "PlayerBoard"):
        """
        Iterate over only non-empty color stacks on a board.
        Yields: (color_name, card_list)
        """
        for color, cards in BoardColorIterator.iterate_color_stacks(board):
            if cards:
                yield color, cards

    @staticmethod
    def get_board_colors_set(board: "PlayerBoard") -> set[str]:
        """
        Get a set of colors that have cards on the board.
        Returns: Set of color strings
        """
        board_colors = set()
        for color, _cards in BoardColorIterator.iterate_non_empty_stacks(board):
            board_colors.add(color)
        return board_colors

    @staticmethod
    def get_all_board_cards(board: "PlayerBoard") -> list[Card]:
        """
        Get all cards from all color stacks on the board.
        Returns: List of all cards on the board
        """
        all_cards = []
        for _color, cards in BoardColorIterator.iterate_color_stacks(board):
            all_cards.extend(cards)
        return all_cards

    @staticmethod
    def find_card_on_board(
        board: "PlayerBoard", card: Card
    ) -> tuple[str, int] | None:
        """
        Find a card on the board and return its color and position.
        Returns: (color_name, index) or None if not found
        """
        for color, cards in BoardColorIterator.iterate_color_stacks(board):
            try:
                index = cards.index(card)
                return (color, index)
            except ValueError:
                continue
        return None

    @staticmethod
    def remove_card_from_board(board: "PlayerBoard", card: Card) -> bool:
        """
        Remove a card from the board.
        Returns: True if card was found and removed, False otherwise
        """
        location = BoardColorIterator.find_card_on_board(board, card)
        if location:
            color, index = location
            cards = getattr(board, f"{color}_cards")
            cards.pop(index)
            return True
        return False

    @staticmethod
    def count_colors_with_cards(board: "PlayerBoard") -> int:
        """
        Count how many colors have at least one card.
        Returns: Number of colors with cards
        """
        count = 0
        for _color, _cards in BoardColorIterator.iterate_non_empty_stacks(board):
            count += 1
        return count

    @staticmethod
    def get_colors_not_on_board(board: "PlayerBoard") -> list[str]:
        """
        Get list of colors that don't have any cards on the board.
        Returns: List of color strings
        """
        board_colors = BoardColorIterator.get_board_colors_set(board)
        return [color for color in BOARD_COLORS if color not in board_colors]

    @staticmethod
    def get_color_stack_by_name(board: "PlayerBoard", color: str) -> list[Card]:
        """
        Get a specific color stack by name.
        Returns: List of cards in that color stack
        """
        if color not in BOARD_COLORS:
            return []
        return getattr(board, f"{color}_cards", [])
