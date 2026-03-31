"""Validation utility functions.

This module provides common validation patterns used throughout
the action primitives and game logic for consistent error handling
and validation.
"""

import logging
from typing import Any, Union

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation failures."""

    pass


def validate_not_none(value, name: str):
    """Validate that a value is not None.

    Args:
        value: Value to check.
        name: Name of the value for error messages.

    Raises:
        ValidationError: If value is None.
    """
    if value is None:
        raise ValidationError(f"{name} cannot be None")


def validate_positive_integer(value: Union[int, str], name: str) -> int:
    """Validate and convert to positive integer.

    Args:
        value: Value to validate and convert.
        name: Name of the value for error messages.

    Returns:
        Validated positive integer.

    Raises:
        ValidationError: If value is not a positive integer.
    """
    try:
        int_value = int(value) if isinstance(value, str) else int(value)

        if int_value < 0:
            raise ValidationError(f"{name} must be non-negative, got {int_value}")

        return int_value
    except (ValueError, TypeError) as e:
        raise ValidationError(f"{name} must be a valid integer, got {value}") from e


def validate_non_negative_integer(value: Union[int, str], name: str) -> int:
    """Validate and convert to non-negative integer.

    Args:
        value: Value to validate and convert.
        name: Name of the value for error messages.

    Returns:
        Validated non-negative integer.

    Raises:
        ValidationError: If value is not a non-negative integer.
    """
    return validate_positive_integer(value, name)  # Same validation


def validate_integer_range(
    value: Union[int, str],
    name: str,
    min_val: int | None = None,
    max_val: int | None = None,
) -> int:
    """Validate integer is within a range.

    Args:
        value: Value to validate.
        name: Name of the value for error messages.
        min_val: Minimum allowed value (inclusive).
        max_val: Maximum allowed value (inclusive).

    Returns:
        Validated integer.

    Raises:
        ValidationError: If value is not within the specified range.
    """
    try:
        int_value = int(value) if isinstance(value, str) else int(value)

        if min_val is not None and int_value < min_val:
            raise ValidationError(f"{name} must be at least {min_val}, got {int_value}")

        if max_val is not None and int_value > max_val:
            raise ValidationError(f"{name} must be at most {max_val}, got {int_value}")

        return int_value
    except (ValueError, TypeError) as e:
        raise ValidationError(f"{name} must be a valid integer, got {value}") from e


def validate_string_not_empty(value: str, name: str) -> str:
    """Validate that a string is not empty.

    Args:
        value: String value to validate.
        name: Name of the value for error messages.

    Returns:
        Validated string.

    Raises:
        ValidationError: If string is None or empty.
    """
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string, got {type(value)}")

    if not value or not value.strip():
        raise ValidationError(f"{name} cannot be empty")

    return value.strip()


def validate_list_not_empty(value: list, name: str) -> list:
    """Validate that a list is not empty.

    Args:
        value: List to validate.
        name: Name of the value for error messages.

    Returns:
        Validated list.

    Raises:
        ValidationError: If list is None or empty.
    """
    if not isinstance(value, list):
        raise ValidationError(f"{name} must be a list, got {type(value)}")

    if not value:
        raise ValidationError(f"{name} cannot be empty")

    return value


def validate_list_max_length(value: list, name: str, max_length: int) -> list:
    """Validate that a list doesn't exceed maximum length.

    Args:
        value: List to validate.
        name: Name of the value for error messages.
        max_length: Maximum allowed length.

    Returns:
        Validated list.

    Raises:
        ValidationError: If list is too long.
    """
    if not isinstance(value, list):
        raise ValidationError(f"{name} must be a list, got {type(value)}")

    if len(value) > max_length:
        raise ValidationError(
            f"{name} cannot have more than {max_length} items, got {len(value)}"
        )

    return value


def validate_choice(value: str, name: str, valid_choices: list[str]) -> str:
    """Validate that a value is one of the allowed choices.

    Args:
        value: Value to validate.
        name: Name of the value for error messages.
        valid_choices: List of valid choices.

    Returns:
        Validated choice.

    Raises:
        ValidationError: If value is not in valid choices.
    """
    if value not in valid_choices:
        raise ValidationError(f"{name} must be one of {valid_choices}, got '{value}'")

    return value


def validate_color(color: str) -> str:
    """Validate that a color is valid.

    Args:
        color: Color string to validate.

    Returns:
        Validated color string.

    Raises:
        ValidationError: If color is not valid.
    """
    valid_colors = ["red", "blue", "green", "purple", "yellow"]
    return validate_choice(color, "color", valid_colors)


def validate_symbol(symbol: str) -> str:
    """Validate that a symbol name is valid.

    Args:
        symbol: Symbol name to validate.

    Returns:
        Validated symbol name.

    Raises:
        ValidationError: If symbol is not valid.
    """
    valid_symbols = ["circuit", "data", "algorithm", "neural_net", "robot", "human_mind"]
    return validate_choice(symbol.lower(), "symbol", valid_symbols)


def validate_age(age: Union[int, str]) -> int:
    """Validate that an age is valid for The Singularity.

    Args:
        age: Age value to validate.

    Returns:
        Validated age integer.

    Raises:
        ValidationError: If age is not valid.
    """
    return validate_integer_range(age, "age", min_val=1, max_val=10)


def validate_player_has_attributes(
    player, required_attrs: list[str], player_name: str = "player"
):
    """Validate that a player has required attributes.

    Args:
        player: Player object to validate.
        required_attrs: List of attribute names to check.
        player_name: Name for error messages.

    Raises:
        ValidationError: If player is missing required attributes.
    """
    if player is None:
        raise ValidationError(f"{player_name} cannot be None")

    for attr in required_attrs:
        if not hasattr(player, attr):
            raise ValidationError(f"{player_name} must have '{attr}' attribute")


def validate_card_has_attributes(
    card, required_attrs: list[str], card_name: str = "card"
):
    """Validate that a card has required attributes.

    Args:
        card: Card object to validate.
        required_attrs: List of attribute names to check.
        card_name: Name for error messages.

    Raises:
        ValidationError: If card is missing required attributes.
    """
    if card is None:
        raise ValidationError(f"{card_name} cannot be None")

    for attr in required_attrs:
        if not hasattr(card, attr):
            raise ValidationError(f"{card_name} must have '{attr}' attribute")


def validate_game_has_attributes(game, required_attrs: list[str]):
    """Validate that a game has required attributes.

    Args:
        game: Game object to validate.
        required_attrs: List of attribute names to check.

    Raises:
        ValidationError: If game is missing required attributes.
    """
    if game is None:
        raise ValidationError("game cannot be None")

    for attr in required_attrs:
        if not hasattr(game, attr):
            raise ValidationError(f"game must have '{attr}' attribute")


def validate_context_has_attributes(context, required_attrs: list[str]):
    """Validate that a context has required attributes.

    Args:
        context: Context object to validate.
        required_attrs: List of attribute names to check.

    Raises:
        ValidationError: If context is missing required attributes.
    """
    if context is None:
        raise ValidationError("context cannot be None")

    for attr in required_attrs:
        if not hasattr(context, attr):
            raise ValidationError(f"context must have '{attr}' attribute")


def safe_get_attribute(obj, attr_name: str, default=None, obj_name: str = "object"):
    """Safely get an attribute with validation and default.

    Args:
        obj: Object to get attribute from.
        attr_name: Name of attribute to get.
        default: Default value if attribute doesn't exist.
        obj_name: Name of object for error messages.

    Returns:
        Attribute value or default.

    Raises:
        ValidationError: If object is None and no default provided.
    """
    if obj is None:
        if default is not None:
            return default
        raise ValidationError(f"{obj_name} cannot be None")

    return getattr(obj, attr_name, default)


def validate_selection_constraints(
    selected_count: int, min_count: int, max_count: int, is_optional: bool = False
) -> bool:
    """Validate that a selection meets count constraints.

    Args:
        selected_count: Number of items selected.
        min_count: Minimum required selections.
        max_count: Maximum allowed selections.
        is_optional: Whether selection is optional.

    Returns:
        True if selection is valid.

    Raises:
        ValidationError: If selection doesn't meet constraints.
    """
    if not is_optional and selected_count < min_count:
        raise ValidationError(
            f"Must select at least {min_count} items, got {selected_count}"
        )

    if selected_count > max_count:
        raise ValidationError(
            f"Cannot select more than {max_count} items, got {selected_count}"
        )

    if is_optional and selected_count == 0:
        return True  # Optional selection with no items is valid

    return True


class ConfigValidator:
    """Utility class for validating action primitive configurations."""

    @staticmethod
    def validate_required_keys(
        config: dict[str, Any], required_keys: list[str], action_name: str = "action"
    ):
        """Validate that config has all required keys.

        Args:
            config: Configuration dictionary to validate.
            required_keys: List of required key names.
            action_name: Name of action for error messages.

        Raises:
            ValidationError: If required keys are missing.
        """
        if not isinstance(config, dict):
            raise ValidationError(f"{action_name} config must be a dictionary")

        missing_keys = []
        for key in required_keys:
            if key not in config:
                missing_keys.append(key)

        if missing_keys:
            raise ValidationError(
                f"{action_name} config missing required keys: {missing_keys}"
            )

    @staticmethod
    def validate_optional_keys(
        config: dict[str, Any], valid_keys: list[str], action_name: str = "action"
    ):
        """Validate that config only contains valid keys.

        Args:
            config: Configuration dictionary to validate.
            valid_keys: List of valid key names.
            action_name: Name of action for error messages.

        Raises:
            ValidationError: If invalid keys are present.
        """
        if not isinstance(config, dict):
            raise ValidationError(f"{action_name} config must be a dictionary")

        invalid_keys = []
        for key in config:
            if key not in valid_keys:
                invalid_keys.append(key)

        if invalid_keys:
            logger.warning(f"{action_name} config has unknown keys: {invalid_keys}")

    @staticmethod
    def validate_source_location(source: str) -> str:
        """Validate that a source location is valid.

        Args:
            source: Source location string.

        Returns:
            Validated source location.

        Raises:
            ValidationError: If source is not valid.
        """
        valid_sources = [
            "hand",
            "board",
            "score_pile",
            "achievements",
            "board_top",
            "age_deck",
            "revealed_cards",
            "selected_cards",
            "last_drawn",
        ]
        return validate_choice(source, "source", valid_sources)


def validate_and_convert_config(
    config: dict[str, Any], conversions: dict[str, Any]
) -> dict[str, Any]:
    """Validate and convert config values using provided conversion functions.

    Args:
        config: Configuration dictionary to validate.
        conversions: Dictionary mapping config keys to conversion functions.

    Returns:
        Dictionary with converted values.

    Raises:
        ValidationError: If conversion fails.
    """
    converted = config.copy()

    for key, converter in conversions.items():
        if key in converted:
            try:
                converted[key] = converter(converted[key])
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Failed to convert {key}: {e}") from e

    return converted
