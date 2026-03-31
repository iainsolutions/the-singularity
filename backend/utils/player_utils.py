"""Player-related utility functions.

This module provides common utilities for working with players,
including validation, card access, and multi-player operations.
"""

import logging

from models.card import Card

logger = logging.getLogger(__name__)


def validate_player(player) -> bool:
    """Validate that a player object has required attributes.

    Args:
        player: Player object to validate.

    Returns:
        True if player has basic required attributes.
    """
    return (
        hasattr(player, "id")
        and hasattr(player, "name")
        and hasattr(player, "hand")
        and hasattr(player, "board")
        and hasattr(player, "score_pile")
    )


def get_player_hand(player) -> list[Card]:
    """Get player's hand with safe access.

    Args:
        player: Player object.

    Returns:
        List of cards in hand, empty if no hand attribute.
    """
    return getattr(player, "hand", [])


def get_player_score_pile(player) -> list[Card]:
    """Get player's score pile with safe access.

    Args:
        player: Player object.

    Returns:
        List of cards in score pile, empty if no score_pile attribute.
    """
    return getattr(player, "score_pile", [])


def get_player_achievements(player) -> list[Card]:
    """Get player's achievements with safe access.

    Args:
        player: Player object.

    Returns:
        List of achievement cards, empty if no achievements attribute.
    """
    return getattr(player, "achievements", [])


def get_player_board(player):
    """Get player's board with safe access.

    Args:
        player: Player object.

    Returns:
        Player's board object, or None if no board attribute.
    """
    return getattr(player, "board", None)


def count_player_cards(player, location: str) -> int:
    """Count cards in a specific player location.

    Args:
        player: Player object.
        location: Location to count ('hand', 'score_pile', 'achievements', 'board').

    Returns:
        Number of cards in the specified location.
    """
    if location == "hand":
        return len(get_player_hand(player))
    elif location == "score_pile":
        return len(get_player_score_pile(player))
    elif location == "achievements":
        return len(get_player_achievements(player))
    elif location == "board":
        board = get_player_board(player)
        if board and hasattr(board, "get_all_cards"):
            return len(board.get_all_cards())
        elif board:
            from utils.board_utils import count_cards_on_board

            return count_cards_on_board(board)
    return 0


def get_player_cards_from_location(player, location: str) -> list[Card]:
    """Get cards from a specific player location.

    Args:
        player: Player object.
        location: Location to get cards from.

    Returns:
        List of cards from the specified location.
    """
    if location == "hand":
        return get_player_hand(player)
    elif location == "score_pile":
        return get_player_score_pile(player)
    elif location == "achievements":
        return get_player_achievements(player)
    elif location == "board":
        board = get_player_board(player)
        if board and hasattr(board, "get_all_cards"):
            return board.get_all_cards()
        elif board:
            from utils.board_utils import get_all_board_cards

            return get_all_board_cards(board)
    return []


def get_player_top_cards(player) -> list[Card]:
    """Get top cards from player's board.

    Args:
        player: Player object.

    Returns:
        List of top cards from board, empty if no board.
    """
    board = get_player_board(player)
    if board and hasattr(board, "get_top_cards"):
        return board.get_top_cards()
    elif board:
        from utils.board_utils import get_top_cards_from_board

        return get_top_cards_from_board(board)
    return []


def calculate_player_score(player) -> int:
    """Calculate player's total score from score pile.

    Args:
        player: Player object.

    Returns:
        Sum of ages of cards in score pile.
    """
    score_pile = get_player_score_pile(player)
    return sum(getattr(card, "age", 0) for card in score_pile)


def count_player_achievements_by_age(player, age: int) -> int:
    """Count achievements of a specific age for a player.

    Args:
        player: Player object.
        age: Age of achievements to count.

    Returns:
        Number of achievements of the specified age.
    """
    achievements = get_player_achievements(player)
    return sum(
        1 for achievement in achievements if getattr(achievement, "age", 0) == age
    )


def player_has_achievement(player, achievement_name: str) -> bool:
    """Check if player has a specific achievement by name.

    Args:
        player: Player object.
        achievement_name: Name of achievement to check for.

    Returns:
        True if player has the achievement.
    """
    achievements = get_player_achievements(player)
    for achievement in achievements:
        if hasattr(achievement, "name") and achievement.name == achievement_name:
            return True
    return False


def get_player_symbol_count(player, symbol) -> int:
    """Count symbols on player's board.

    Args:
        player: Player object.
        symbol: Symbol to count (Symbol enum or string).

    Returns:
        Total count of the symbol on player's board.
    """
    board = get_player_board(player)
    if not board:
        return 0

    # Convert string to Symbol enum if needed
    if isinstance(symbol, str):
        from utils.symbol_mapping import string_to_symbol

        try:
            symbol = string_to_symbol(symbol)
        except ValueError:
            return 0

    # Use board's count_symbol method if available
    if hasattr(board, "count_symbol"):
        return board.count_symbol(symbol)

    # Fallback: count manually on top cards
    top_cards = get_player_top_cards(player)
    total = 0
    for card in top_cards:
        if hasattr(card, "symbols"):
            total += card.symbols.count(symbol)
    return total


def find_players_by_condition(players: list, condition_func) -> list:
    """Find players that match a condition.

    Args:
        players: List of player objects.
        condition_func: Function that takes a player and returns bool.

    Returns:
        List of players matching the condition.
    """
    return [player for player in players if condition_func(player)]


def get_opponents(players: list, current_player) -> list:
    """Get all opponents of the current player.

    Args:
        players: List of all players.
        current_player: Current player object.

    Returns:
        List of opponent players.
    """
    if not hasattr(current_player, "id"):
        return []

    return [
        player
        for player in players
        if hasattr(player, "id") and player.id != current_player.id
    ]


def get_player_by_id(players: list, player_id: str):
    """Find a player by ID.

    Args:
        players: List of player objects.
        player_id: ID to search for.

    Returns:
        Player object with matching ID, or None if not found.
    """
    for player in players:
        if hasattr(player, "id") and player.id == player_id:
            return player
    return None


def get_players_with_most_symbol(players: list, symbol) -> list:
    """Get players with the highest count of a specific symbol.

    Args:
        players: List of player objects.
        symbol: Symbol to check (Symbol enum or string).

    Returns:
        List of players tied for most of the symbol.
    """
    if not players:
        return []

    # Calculate symbol count for each player
    symbol_counts = {}
    for player in players:
        if validate_player(player):
            symbol_counts[player.id] = get_player_symbol_count(player, symbol)

    if not symbol_counts:
        return []

    # Find maximum count
    max_count = max(symbol_counts.values())

    # Return players with maximum count
    return [
        player
        for player in players
        if hasattr(player, "id") and symbol_counts.get(player.id, 0) == max_count
    ]


def get_players_with_least_symbol(players: list, symbol) -> list:
    """Get players with the lowest count of a specific symbol.

    Args:
        players: List of player objects.
        symbol: Symbol to check (Symbol enum or string).

    Returns:
        List of players tied for least of the symbol.
    """
    if not players:
        return []

    # Calculate symbol count for each player
    symbol_counts = {}
    for player in players:
        if validate_player(player):
            symbol_counts[player.id] = get_player_symbol_count(player, symbol)

    if not symbol_counts:
        return []

    # Find minimum count
    min_count = min(symbol_counts.values())

    # Return players with minimum count
    return [
        player
        for player in players
        if hasattr(player, "id")
        and symbol_counts.get(player.id, float("inf")) == min_count
    ]


def get_player_with_most_achievements(players: list):
    """Get player with the most achievements.

    Args:
        players: List of player objects.

    Returns:
        Player with most achievements, or None if no valid players.
    """
    if not players:
        return None

    max_achievements = 0
    winning_player = None

    for player in players:
        if validate_player(player):
            achievement_count = len(get_player_achievements(player))
            if achievement_count > max_achievements:
                max_achievements = achievement_count
                winning_player = player

    return winning_player


def get_player_with_highest_score(players: list):
    """Get player with the highest score.

    Args:
        players: List of player objects.

    Returns:
        Player with highest score, or None if no valid players.
    """
    if not players:
        return None

    max_score = 0
    winning_player = None

    for player in players:
        if validate_player(player):
            score = calculate_player_score(player)
            if score > max_score:
                max_score = score
                winning_player = player

    return winning_player


def players_meeting_condition(players: list, condition: str, **kwargs) -> list:
    """Get players meeting a specific condition.

    Args:
        players: List of player objects.
        condition: Condition type string.
        **kwargs: Additional parameters for the condition.

    Returns:
        List of players meeting the condition.
    """
    meeting_condition = []

    for player in players:
        if not validate_player(player):
            continue

        if condition == "has_achievement":
            achievement_name = kwargs.get("achievement_name")
            if player_has_achievement(player, achievement_name):
                meeting_condition.append(player)

        elif condition == "min_score":
            min_score = kwargs.get("min_score", 0)
            if calculate_player_score(player) >= min_score:
                meeting_condition.append(player)

        elif condition == "min_achievements":
            min_count = kwargs.get("min_count", 1)
            if len(get_player_achievements(player)) >= min_count:
                meeting_condition.append(player)

        elif condition == "has_board_color":
            color = kwargs.get("color")
            board = get_player_board(player)
            if board:
                from utils.board_utils import board_has_color

                if board_has_color(board, color):
                    meeting_condition.append(player)

        elif condition == "symbol_count_at_least":
            symbol = kwargs.get("symbol")
            min_count = kwargs.get("min_count", 1)
            if get_player_symbol_count(player, symbol) >= min_count:
                meeting_condition.append(player)

    return meeting_condition


class PlayerComparator:
    """Utility class for comparing players."""

    @staticmethod
    def compare_by_score(player1, player2) -> int:
        """Compare players by score.

        Args:
            player1: First player.
            player2: Second player.

        Returns:
            -1 if player1 < player2, 0 if equal, 1 if player1 > player2.
        """
        score1 = calculate_player_score(player1)
        score2 = calculate_player_score(player2)

        if score1 < score2:
            return -1
        elif score1 > score2:
            return 1
        return 0

    @staticmethod
    def compare_by_achievements(player1, player2) -> int:
        """Compare players by achievement count.

        Args:
            player1: First player.
            player2: Second player.

        Returns:
            -1 if player1 < player2, 0 if equal, 1 if player1 > player2.
        """
        count1 = len(get_player_achievements(player1))
        count2 = len(get_player_achievements(player2))

        if count1 < count2:
            return -1
        elif count1 > count2:
            return 1
        return 0

    @staticmethod
    def compare_by_symbol_count(player1, player2, symbol) -> int:
        """Compare players by symbol count.

        Args:
            player1: First player.
            player2: Second player.
            symbol: Symbol to compare counts of.

        Returns:
            -1 if player1 < player2, 0 if equal, 1 if player1 > player2.
        """
        count1 = get_player_symbol_count(player1, symbol)
        count2 = get_player_symbol_count(player2, symbol)

        if count1 < count2:
            return -1
        elif count1 > count2:
            return 1
        return 0
