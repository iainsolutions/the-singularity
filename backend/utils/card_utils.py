"""Card-related utility functions.

This module provides common utilities for working with cards,
including color handling, filtering, and card property access.
"""

import logging
from typing import Any

from models.card import Card, Symbol

logger = logging.getLogger(__name__)


def normalize_card_color(card) -> str | None:
    """Normalize card color to string format.

    Args:
        card: Card object with color attribute.

    Returns:
        Color as string, or None if card has no color.
    """
    if not hasattr(card, "color"):
        return None

    color = card.color
    # Handle both enum values and string values
    if hasattr(color, "value"):
        return color.value
    return str(color)


def get_card_age(card) -> int:
    """Get card age with safe default.

    Args:
        card: Card object.

    Returns:
        Card age, or 0 if no age attribute.
    """
    return getattr(card, "age", 0)


def get_card_name(card) -> str:
    """Get card name with safe default.

    Args:
        card: Card object.

    Returns:
        Card name, or empty string if no name attribute.
    """
    return getattr(card, "name", "")


def has_card_symbol(card, symbol) -> bool:
    """Check if a card has a specific symbol.

    Args:
        card: Card object.
        symbol: Symbol to check for (Symbol enum or string).

    Returns:
        True if card has the symbol.
    """
    if not hasattr(card, "symbols"):
        return False

    # Convert string to Symbol enum if needed
    if isinstance(symbol, str):
        from utils.symbol_mapping import string_to_symbol

        try:
            symbol = string_to_symbol(symbol)
        except ValueError:
            return False

    return symbol in card.symbols


def count_card_symbols(card, symbol) -> int:
    """Count occurrences of a specific symbol on a card.

    Args:
        card: Card object.
        symbol: Symbol to count (Symbol enum or string).

    Returns:
        Number of times the symbol appears on the card.
    """
    if not hasattr(card, "symbols"):
        return 0

    # Convert string to Symbol enum if needed
    if isinstance(symbol, str):
        from utils.symbol_mapping import string_to_symbol

        try:
            symbol = string_to_symbol(symbol)
        except ValueError:
            return 0

    return card.symbols.count(symbol)


def get_card_symbols(card) -> list[Symbol]:
    """Get all symbols from a card.

    Args:
        card: Card object.

    Returns:
        List of Symbol enums, empty if no symbols.
    """
    return getattr(card, "symbols", [])


def card_matches_color(card, color: str) -> bool:
    """Check if a card matches a specific color.

    Args:
        card: Card object.
        color: Color string to match against.

    Returns:
        True if card color matches.
    """
    card_color = normalize_card_color(card)
    return card_color == color


def card_has_any_symbol(card, symbols: list) -> bool:
    """Check if a card has any of the specified symbols.

    Args:
        card: Card object.
        symbols: List of symbols to check for (Symbol enums or strings).

    Returns:
        True if card has at least one of the symbols.
    """
    return any(has_card_symbol(card, symbol) for symbol in symbols)


def card_has_all_symbols(card, symbols: list) -> bool:
    """Check if a card has all of the specified symbols.

    Args:
        card: Card object.
        symbols: List of symbols to check for (Symbol enums or strings).

    Returns:
        True if card has all the symbols.
    """
    return all(has_card_symbol(card, symbol) for symbol in symbols)


def filter_cards_by_color(cards: list[Card], colors: list[str]) -> list[Card]:
    """Filter cards by color.

    Args:
        cards: List of cards to filter.
        colors: List of color strings to match.

    Returns:
        List of cards that match any of the specified colors.
    """
    return [card for card in cards if normalize_card_color(card) in colors]


def filter_cards_by_age_range(
    cards: list[Card], min_age: int | None = None, max_age: int | None = None
) -> list[Card]:
    """Filter cards by age range.

    Args:
        cards: List of cards to filter.
        min_age: Minimum age (inclusive), or None for no minimum.
        max_age: Maximum age (inclusive), or None for no maximum.

    Returns:
        List of cards within the age range.
    """
    filtered = cards

    if min_age is not None:
        filtered = [card for card in filtered if get_card_age(card) >= min_age]

    if max_age is not None:
        filtered = [card for card in filtered if get_card_age(card) <= max_age]

    return filtered


def filter_cards_by_symbol(
    cards: list[Card], symbol, has_symbol: bool = True
) -> list[Card]:
    """Filter cards by symbol presence.

    Args:
        cards: List of cards to filter.
        symbol: Symbol to check for (Symbol enum or string).
        has_symbol: True to include cards with symbol, False to exclude them.

    Returns:
        List of cards matching the symbol criteria.
    """
    if has_symbol:
        return [card for card in cards if has_card_symbol(card, symbol)]
    else:
        return [card for card in cards if not has_card_symbol(card, symbol)]


def filter_cards_by_name_pattern(
    cards: list[Card], pattern: str, case_sensitive: bool = False
) -> list[Card]:
    """Filter cards by name pattern.

    Args:
        cards: List of cards to filter.
        pattern: String pattern to match in card names.
        case_sensitive: Whether matching should be case sensitive.

    Returns:
        List of cards whose names contain the pattern.
    """
    if not case_sensitive:
        pattern = pattern.lower()

    filtered = []
    for card in cards:
        card_name = get_card_name(card)
        if not case_sensitive:
            card_name = card_name.lower()

        if pattern in card_name:
            filtered.append(card)

    return filtered


def get_highest_age_cards(cards: list[Card]) -> list[Card]:
    """Get all cards with the highest age.

    Args:
        cards: List of cards to evaluate.

    Returns:
        List of cards with the maximum age value.
    """
    if not cards:
        return []

    max_age = max(get_card_age(card) for card in cards)
    return [card for card in cards if get_card_age(card) == max_age]


def get_lowest_age_cards(cards: list[Card]) -> list[Card]:
    """Get all cards with the lowest age.

    Args:
        cards: List of cards to evaluate.

    Returns:
        List of cards with the minimum age value.
    """
    if not cards:
        return []

    min_age = min(get_card_age(card) for card in cards)
    return [card for card in cards if get_card_age(card) == min_age]


def group_cards_by_color(cards: list[Card]) -> dict[str, list[Card]]:
    """Group cards by their color.

    Args:
        cards: List of cards to group.

    Returns:
        Dictionary mapping color strings to lists of cards.
    """
    groups = {}
    for card in cards:
        color = normalize_card_color(card)
        if color:
            if color not in groups:
                groups[color] = []
            groups[color].append(card)
    return groups


def group_cards_by_age(cards: list[Card]) -> dict[int, list[Card]]:
    """Group cards by their age.

    Args:
        cards: List of cards to group.

    Returns:
        Dictionary mapping age values to lists of cards.
    """
    groups = {}
    for card in cards:
        age = get_card_age(card)
        if age not in groups:
            groups[age] = []
        groups[age].append(card)
    return groups


def get_unique_colors_in_cards(cards: list[Card]) -> set[str]:
    """Get set of unique colors represented in a list of cards.

    Args:
        cards: List of cards to analyze.

    Returns:
        Set of color strings found in the cards.
    """
    colors = set()
    for card in cards:
        color = normalize_card_color(card)
        if color:
            colors.add(color)
    return colors


def get_unique_ages_in_cards(cards: list[Card]) -> set[int]:
    """Get set of unique ages represented in a list of cards.

    Args:
        cards: List of cards to analyze.

    Returns:
        Set of age values found in the cards.
    """
    return {get_card_age(card) for card in cards}


def find_cards_by_name(cards: list[Card], name: str) -> list[Card]:
    """Find all cards with a specific name.

    Args:
        cards: List of cards to search.
        name: Exact name to match.

    Returns:
        List of cards with matching names.
    """
    return [card for card in cards if get_card_name(card) == name]


def remove_none_cards(cards: list[Card | None]) -> list[Card]:
    """Remove None values from a list of cards.

    Args:
        cards: List that may contain None values.

    Returns:
        List with None values filtered out.
    """
    return [card for card in cards if card is not None]


def validate_card_list(cards: list) -> list[Card]:
    """Validate and clean a list of cards.

    Args:
        cards: List that may contain None values or invalid cards.

    Returns:
        List of valid Card objects only.
    """
    valid_cards = []
    for card in cards:
        if card is not None and hasattr(card, "name"):
            valid_cards.append(card)
        else:
            logger.warning(f"Invalid card in list: {card}")
    return valid_cards


class CardSelector:
    """Utility class for advanced card selection operations."""

    @staticmethod
    def select_by_criteria(cards: list[Card], criteria: dict[str, Any]) -> list[Card]:
        """Select cards based on multiple criteria.

        Args:
            cards: List of cards to filter.
            criteria: Dictionary of filter criteria.

        Returns:
            List of cards matching all criteria.
        """
        filtered = remove_none_cards(cards)

        # Color filters
        if "color" in criteria:
            filtered = filter_cards_by_color(filtered, [criteria["color"]])
        elif "colors" in criteria:
            filtered = filter_cards_by_color(filtered, criteria["colors"])

        if "not_color" in criteria:
            filtered = [
                c for c in filtered if normalize_card_color(c) != criteria["not_color"]
            ]

        # Age filters
        if "min_age" in criteria or "max_age" in criteria:
            filtered = filter_cards_by_age_range(
                filtered, criteria.get("min_age"), criteria.get("max_age")
            )

        # Symbol filters
        if "symbol" in criteria or "has_symbol" in criteria:
            symbol = criteria.get("symbol") or criteria.get("has_symbol")
            filtered = filter_cards_by_symbol(filtered, symbol, True)

        if "not_has_symbol" in criteria:
            filtered = filter_cards_by_symbol(
                filtered, criteria["not_has_symbol"], False
            )

        # Name filters
        if "name_contains" in criteria:
            filtered = filter_cards_by_name_pattern(filtered, criteria["name_contains"])

        return filtered

    @staticmethod
    def auto_select(
        cards: list[Card], selection_type: str, count: int = 1
    ) -> list[Card]:
        """Automatically select cards based on selection type.

        Args:
            cards: List of cards to select from.
            selection_type: Type of selection ('highest_age', 'lowest_age', 'random').
            count: Number of cards to select.

        Returns:
            List of selected cards.
        """
        if not cards:
            return []

        if selection_type == "highest_age":
            candidates = get_highest_age_cards(cards)
        elif selection_type == "lowest_age":
            candidates = get_lowest_age_cards(cards)
        elif selection_type == "random":
            candidates = cards
        else:
            candidates = cards

        return candidates[:count]
