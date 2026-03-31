"""Board-related utility functions.

This module provides common utilities for working with player boards,
including validation, color handling, and board state queries.
"""

import logging

from models.card import Card

logger = logging.getLogger(__name__)


def validate_player_has_board(player) -> bool:
    """Validate that a player has a board attribute.

    Args:
        player: Player object to check.

    Returns:
        True if player has a valid board, False otherwise.
    """
    return hasattr(player, "board") and player.board is not None


def get_board_colors(board) -> set[str]:
    """Get all colors present on a board.

    Args:
        board: PlayerBoard instance.

    Returns:
        Set of color strings that have cards on the board.
    """
    colors = set()
    for color in ["red", "blue", "green", "purple", "yellow"]:
        stack = getattr(board, f"{color}_cards", [])
        if stack:
            colors.add(color)
    return colors


def can_splay_color(board, color: str, direction: str) -> bool:
    """Check if a color stack can be splayed in a given direction.
    
    Args:
        board: PlayerBoard instance.
        color: Color to check (red, blue, green, yellow, purple).
        direction: Splay direction (left, right, up).
    
    Returns:
        True if the color stack is eligible to be splayed in that direction.
        Eligible means: has 2+ cards AND not already splayed in that direction.
    """
    # Check if stack has at least 2 cards
    stack = board.get_cards_by_color(color)
    if len(stack) < 2:
        return False
    
    # Check if already splayed in this direction
    current_splay = board.splay_directions.get(color)
    if current_splay == direction:
        return False
    
    return True


def get_splayable_colors(board, direction: str) -> set[str]:
    """Get all colors that can be splayed in a given direction.
    
    Args:
        board: PlayerBoard instance.
        direction: Splay direction (left, right, up).
    
    Returns:
        Set of color strings that are eligible for splaying.
    """
    colors = set()
    for color in ["red", "blue", "green", "purple", "yellow"]:
        if can_splay_color(board, color, direction):
            colors.add(color)
    return colors


def get_non_empty_color_stacks(board) -> dict[str, list[Card]]:
    """Get all non-empty color stacks from a board.

    Args:
        board: PlayerBoard instance.

    Returns:
        Dictionary mapping color names to their card stacks (non-empty only).
    """
    stacks = {}
    for color in ["red", "blue", "green", "purple", "yellow"]:
        stack = getattr(board, f"{color}_cards", [])
        if stack:
            stacks[color] = stack
    return stacks


def get_color_stack(board, color: str) -> list[Card]:
    """Get cards from a specific color stack.

    Args:
        board: PlayerBoard instance.
        color: Color name as string.

    Returns:
        List of cards in the color stack, empty list if no cards.
    """
    return getattr(board, f"{color}_cards", [])


def get_top_card_from_color(board, color: str) -> Card | None:
    """Get the top card from a specific color stack.

    Args:
        board: PlayerBoard instance.
        color: Color name as string.

    Returns:
        Top card from the stack, or None if stack is empty.
    """
    stack = get_color_stack(board, color)
    return stack[-1] if stack else None


def get_splay_direction(board, color: str) -> str | None:
    """Get the splay direction for a color stack.

    Args:
        board: PlayerBoard instance.
        color: Color name as string.

    Returns:
        Splay direction string ('left', 'right', 'up') or None if not splayed.
    """
    return getattr(board, f"{color}_splay", None)


def is_color_splayed(board, color: str, direction: str | None = None) -> bool:
    """Check if a color is splayed in a specific direction.

    Args:
        board: PlayerBoard instance.
        color: Color name as string.
        direction: Optional specific direction to check. If None, checks if splayed at all.

    Returns:
        True if color is splayed (in specified direction if given).
    """
    splay_dir = get_splay_direction(board, color)
    if direction is None:
        return splay_dir is not None
    return splay_dir == direction


def count_cards_on_board(board) -> int:
    """Count total number of cards on a board.

    Args:
        board: PlayerBoard instance.

    Returns:
        Total number of cards across all color stacks.
    """
    total = 0
    for color in ["red", "blue", "green", "purple", "yellow"]:
        stack = get_color_stack(board, color)
        total += len(stack)
    return total


def get_all_board_cards(board) -> list[Card]:
    """Get all cards from all color stacks on a board.

    Args:
        board: PlayerBoard instance.

    Returns:
        List of all cards on the board.
    """
    all_cards = []
    for color in ["red", "blue", "green", "purple", "yellow"]:
        stack = get_color_stack(board, color)
        all_cards.extend(stack)
    return all_cards


def get_top_cards_from_board(board) -> list[Card]:
    """Get the top card from each non-empty color stack.

    Args:
        board: PlayerBoard instance.

    Returns:
        List of top cards from each color that has cards.
    """
    top_cards = []
    for color in ["red", "blue", "green", "purple", "yellow"]:
        top_card = get_top_card_from_color(board, color)
        if top_card:
            top_cards.append(top_card)
    return top_cards


class BoardColorIterator:
    """Utility class for iterating over board color stacks."""

    @staticmethod
    def iterate_all_stacks(board):
        """Iterate over all color stacks (including empty ones).

        Args:
            board: PlayerBoard instance.

        Yields:
            Tuples of (color_name, card_list) for each color.
        """
        for color in ["red", "blue", "green", "purple", "yellow"]:
            stack = get_color_stack(board, color)
            yield color, stack

    @staticmethod
    def iterate_non_empty_stacks(board):
        """Iterate over non-empty color stacks only.

        Args:
            board: PlayerBoard instance.

        Yields:
            Tuples of (color_name, card_list) for colors with cards.
        """
        for color, stack in BoardColorIterator.iterate_all_stacks(board):
            if stack:
                yield color, stack

    @staticmethod
    def iterate_top_cards(board):
        """Iterate over top cards from each color.

        Args:
            board: PlayerBoard instance.

        Yields:
            Tuples of (color_name, top_card) for colors with cards.
        """
        for color, stack in BoardColorIterator.iterate_non_empty_stacks(board):
            if stack:
                yield color, stack[-1]


def board_has_color(board, target_color: str) -> bool:
    """Check if a board has cards of a specific color.

    Args:
        board: PlayerBoard instance.
        target_color: Color to check for.

    Returns:
        True if the board has cards of the specified color.
    """
    return target_color in get_board_colors(board)


def board_missing_color(board, target_color: str) -> bool:
    """Check if a board is missing cards of a specific color.

    Args:
        board: PlayerBoard instance.
        target_color: Color to check for.

    Returns:
        True if the board has no cards of the specified color.
    """
    return not board_has_color(board, target_color)


def get_colors_with_min_cards(board, min_count: int = 1) -> set[str]:
    """Get colors that have at least the specified number of cards.

    Args:
        board: PlayerBoard instance.
        min_count: Minimum number of cards required.

    Returns:
        Set of color names that meet the minimum card count.
    """
    colors = set()
    for color in ["red", "blue", "green", "purple", "yellow"]:
        stack = get_color_stack(board, color)
        if len(stack) >= min_count:
            colors.add(color)
    return colors


def get_highest_age_on_board(board) -> int | None:
    """Get the highest age of any card on the board.

    Args:
        board: PlayerBoard instance.

    Returns:
        Highest age found, or None if no cards on board.
    """
    top_cards = get_top_cards_from_board(board)
    if not top_cards:
        return None
    return max(getattr(card, "age", 0) for card in top_cards)


def get_lowest_age_on_board(board) -> int | None:
    """Get the lowest age of any card on the board.

    Args:
        board: PlayerBoard instance.

    Returns:
        Lowest age found, or None if no cards on board.
    """
    top_cards = get_top_cards_from_board(board)
    if not top_cards:
        return None
    return min(getattr(card, "age", 0) for card in top_cards)


def _matches_card_identifier(card, identifier: str) -> bool:
    """Helper function to check if card matches identifier (card_id or name).

    Args:
        card: Card instance
        identifier: Card identifier (card_id or name)

    Returns:
        True if card matches identifier
    """
    # Check card_id first (preferred stable identifier)
    if hasattr(card, 'card_id') and card.card_id and card.card_id == identifier:
        return True
    # Fall back to name for backwards compatibility
    return hasattr(card, "name") and card.name == identifier


def find_cards_by_name_on_board(board, card_identifier: str) -> list[Card]:
    """Find all cards with a specific identifier (card_id or name) on the board.

    Args:
        board: PlayerBoard instance.
        card_identifier: Card identifier (card_id or name for backwards compatibility).

    Returns:
        List of cards with matching identifier.
    """
    matching_cards = []
    all_cards = get_all_board_cards(board)
    for card in all_cards:
        if _matches_card_identifier(card, card_identifier):
            matching_cards.append(card)
    return matching_cards


def is_card_on_top_of_board(board, card_identifier: str) -> bool:
    """Check if a card is on top of any color stack.

    Args:
        board: PlayerBoard instance.
        card_identifier: Card identifier (card_id or name for backwards compatibility).

    Returns:
        True if the card is on top of any stack.
    """
    for _color, top_card in BoardColorIterator.iterate_top_cards(board):
        if _matches_card_identifier(top_card, card_identifier):
            return True
    return False
