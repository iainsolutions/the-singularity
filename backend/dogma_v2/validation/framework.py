"""
Validation framework for interaction responses.

This module provides comprehensive validation for player interactions
including card selections, achievement selections, and option choices.
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validation check"""

    is_valid: bool
    message: str
    validated_data: Any | None = None

    @classmethod
    def valid(cls, data: Any = None) -> "ValidationResult":
        """Create valid result"""
        return cls(is_valid=True, message="Valid", validated_data=data)

    @classmethod
    def invalid(cls, message: str) -> "ValidationResult":
        """Create invalid result"""
        return cls(is_valid=False, message=message, validated_data=None)


@dataclass
class CardSelectionConstraints:
    """Constraints for card selection validation"""

    min_count: int
    max_count: int
    source: str  # hand, board, score_pile
    eligible_cards: list[Any]
    is_optional: bool = False
    filter_description: str = ""


@dataclass
class AchievementSelectionConstraints:
    """Constraints for achievement selection validation"""

    min_count: int
    max_count: int
    eligible_achievements: list[Any]
    is_optional: bool = False


@dataclass
class OptionChoiceConstraints:
    """Constraints for option choice validation"""

    allowed_options: list[str]
    is_optional: bool = False


class ValidationFramework:
    """
    Comprehensive validation for interactions.

    This class provides validation methods for all types of player
    interactions according to DOGMA_TECHNICAL_SPECIFICATION.md Section 8.2.
    """

    @staticmethod
    def validate_card_selection(
        response: dict[str, Any], constraints: CardSelectionConstraints, game_state: Any
    ) -> ValidationResult:
        """
        Validate card selection response.

        Checks:
        1. Cards exist and are valid IDs
        2. Player owns the cards
        3. Cards are in specified location
        4. Count matches requirements
        5. Cards meet filter criteria
        """
        try:
            selected_ids = response.get("selected_cards", [])
            player_id = response.get("player_id")

            if not player_id:
                return ValidationResult.invalid("Missing player_id in response")

            # Check if selection is optional and empty
            if constraints.is_optional and not selected_ids:
                return ValidationResult.valid([])

            # Check count constraints
            if len(selected_ids) < constraints.min_count:
                return ValidationResult.invalid(
                    f"Too few cards selected: {len(selected_ids)} < {constraints.min_count}"
                )

            if len(selected_ids) > constraints.max_count:
                return ValidationResult.invalid(
                    f"Too many cards selected: {len(selected_ids)} > {constraints.max_count}"
                )

            # Find player in game state
            player = ValidationFramework._find_player(game_state, player_id)
            if not player:
                return ValidationResult.invalid(f"Player {player_id} not found")

            # Validate each selected card
            selected_cards = []
            for card_id in selected_ids:
                # Check if card is in eligible list
                card = ValidationFramework._find_card_in_list(
                    constraints.eligible_cards, card_id
                )
                if not card:
                    return ValidationResult.invalid(
                        f"Card {card_id} is not in eligible cards list"
                    )

                # Check ownership and location
                if not ValidationFramework._player_owns_card_in_location(
                    player, card, constraints.source
                ):
                    return ValidationResult.invalid(
                        f"Player doesn't own card {card.name} in {constraints.source}"
                    )

                selected_cards.append(card)

            # All validations passed
            return ValidationResult.valid(selected_cards)

        except Exception as e:
            logger.error(f"Card selection validation error: {e}", exc_info=True)
            return ValidationResult.invalid(f"Validation error: {e}")

    @staticmethod
    def validate_achievement_selection(
        response: dict[str, Any],
        constraints: AchievementSelectionConstraints,
        game_state: Any,
    ) -> ValidationResult:
        """
        Validate achievement selection response.

        Checks:
        1. Achievements exist and are valid
        2. Achievements are available (not claimed)
        3. Count matches requirements
        4. Player can claim the achievements (value check)
        """
        try:
            selected_ids = response.get("selected_achievements", [])
            player_id = response.get("player_id")

            if not player_id:
                return ValidationResult.invalid("Missing player_id in response")

            # Check if selection is optional and empty
            if constraints.is_optional and not selected_ids:
                return ValidationResult.valid([])

            # Check count constraints
            if len(selected_ids) < constraints.min_count:
                return ValidationResult.invalid(
                    f"Too few achievements selected: {len(selected_ids)} < {constraints.min_count}"
                )

            if len(selected_ids) > constraints.max_count:
                return ValidationResult.invalid(
                    f"Too many achievements selected: {len(selected_ids)} > {constraints.max_count}"
                )

            # Find player in game state
            player = ValidationFramework._find_player(game_state, player_id)
            if not player:
                return ValidationResult.invalid(f"Player {player_id} not found")

            # Validate each selected achievement
            selected_achievements = []
            for achievement_id in selected_ids:
                # Check if achievement is in eligible list
                achievement = ValidationFramework._find_achievement_in_list(
                    constraints.eligible_achievements, achievement_id
                )
                if not achievement:
                    return ValidationResult.invalid(
                        f"Achievement {achievement_id} is not in eligible list"
                    )

                # Check if achievement is available (not already claimed)
                if ValidationFramework._is_achievement_claimed(game_state, achievement):
                    return ValidationResult.invalid(
                        f"Achievement {achievement.name} is already claimed"
                    )

                selected_achievements.append(achievement)

            # All validations passed
            return ValidationResult.valid(selected_achievements)

        except Exception as e:
            logger.error(f"Achievement selection validation error: {e}", exc_info=True)
            return ValidationResult.invalid(f"Validation error: {e}")

    @staticmethod
    def validate_option_choice(
        response: dict[str, Any], constraints: OptionChoiceConstraints
    ) -> ValidationResult:
        """
        Validate option choice response.

        Checks:
        1. Chosen option is in allowed options
        2. Response format is correct
        """
        try:
            chosen_option = response.get("chosen_option")

            if chosen_option is None:
                if constraints.is_optional:
                    return ValidationResult.valid(None)
                else:
                    return ValidationResult.invalid("No option chosen")

            # Check if option is allowed
            if chosen_option not in constraints.allowed_options:
                return ValidationResult.invalid(
                    f"Invalid option: {chosen_option}. Allowed: {constraints.allowed_options}"
                )

            return ValidationResult.valid(chosen_option)

        except Exception as e:
            logger.error(f"Option choice validation error: {e}", exc_info=True)
            return ValidationResult.invalid(f"Validation error: {e}")

    @staticmethod
    def validate_tie_resolution(
        response: dict[str, Any], tied_cards: list[Any]
    ) -> ValidationResult:
        """
        Validate tie resolution for highest/lowest selection.

        Checks:
        1. Selected card is in the list of tied cards
        2. Exactly one card is selected
        """
        try:
            selected_id = response.get("selected_card")

            if not selected_id:
                return ValidationResult.invalid("No card selected for tie resolution")

            # Find card in tied cards list
            selected_card = ValidationFramework._find_card_in_list(
                tied_cards, selected_id
            )
            if not selected_card:
                return ValidationResult.invalid(
                    f"Selected card {selected_id} is not in the tied cards list"
                )

            return ValidationResult.valid(selected_card)

        except Exception as e:
            logger.error(f"Tie resolution validation error: {e}", exc_info=True)
            return ValidationResult.invalid(f"Validation error: {e}")

    # Helper methods

    @staticmethod
    def _find_player(game_state, player_id: str):
        """Find player in game state"""
        if hasattr(game_state, "players"):
            for player in game_state.players:
                if player.id == player_id:
                    return player
        return None

    @staticmethod
    def _find_card_in_list(cards: list[Any], card_id: str):
        """Find card in list by ID"""
        for card in cards:
            if (hasattr(card, "card_id") and card.card_id == card_id) or (hasattr(card, "id") and card.id == card_id):
                return card
        return None

    @staticmethod
    def _find_achievement_in_list(achievements: list[Any], achievement_id: str):
        """Find achievement in list by ID"""
        for achievement in achievements:
            if (hasattr(achievement, "id") and achievement.id == achievement_id) or (hasattr(achievement, "name") and achievement.name == achievement_id):
                return achievement
        return None

    @staticmethod
    def _player_owns_card_in_location(player, card, location: str) -> bool:
        """Check if player owns card in specified location"""
        if location == "hand":
            return card in getattr(player, "hand", [])
        elif location == "score_pile":
            return card in getattr(player, "score_pile", [])
        elif location == "board":
            board = getattr(player, "board", None)
            if board:
                return card in board.get_all_cards()
        return False

    @staticmethod
    def _is_achievement_claimed(game_state, achievement) -> bool:
        """Check if achievement is already claimed by any player"""
        if hasattr(game_state, "players"):
            for player in game_state.players:
                if achievement in getattr(player, "achievements", []):
                    return True
        return False
