"""
Declarative Effect Selection System

This module handles selection of which dogma effect to execute for multi-effect cards.
Instead of hardcoding card-specific logic in the execution pipeline, cards specify
selection conditions declaratively in their card data.

Example card data with selection conditions:

{
  "name": "Tools",
  "dogma_effects": [
    {
      "effect_index": 0,
      "selection_condition": {
        "type": "default",
        "description": "Use if no age 3+ cards in hand"
      },
      "actions": [...]
    },
    {
      "effect_index": 1,
      "selection_condition": {
        "type": "CardCondition",
        "field": "age",
        "operator": ">=",
        "value": 3,
        "location": "hand",
        "match_count": "any"
      },
      "actions": [...]
    }
  ]
}
"""

import logging

logger = logging.getLogger(__name__)


class EffectSelector:
    """Handles selection of which dogma effect to use for multi-effect cards."""

    @staticmethod
    def select_effect_index(
        card,
        effects: list,
        context,
    ) -> int:
        """Select which effect to execute based on declarative conditions.

        Args:
            card: The card being executed
            effects: List of dogma effect configurations (can be DogmaEffect objects or dicts)
            context: Current dogma context (DogmaContext)

        Returns:
            Index of the effect to use (0-based)

        Logic:
            1. If only one effect, return 0
            2. Iterate through effects in order
            3. For each effect, check if selection_condition is met
            4. Return index of first effect whose condition is met
            5. If no conditions met, return effect marked as "default"
            6. If no default, return 0
        """
        if len(effects) <= 1:
            return 0

        logger.info(
            f"EFFECT SELECTION: Card {card.name} has {len(effects)} effects, "
            f"evaluating selection conditions"
        )

        # Evaluate each effect's selection condition
        for i, effect in enumerate(effects):
            # Handle both DogmaEffect objects and dict representations
            if hasattr(effect, "selection_condition"):
                selection_condition = effect.selection_condition
            elif isinstance(effect, dict):
                selection_condition = effect.get("selection_condition")
            else:
                logger.warning(
                    f"EFFECT SELECTION: Effect {i} has unexpected type {type(effect)}"
                )
                selection_condition = None

            if not selection_condition:
                # No condition means "always use if reached"
                logger.info(f"EFFECT SELECTION: Effect {i} has no condition, using it")
                return i

            # Handle both dict and object selection conditions
            if isinstance(selection_condition, dict):
                condition_type = selection_condition.get("type", "default")
            else:
                condition_type = getattr(selection_condition, "type", "default")

            if condition_type == "default":
                # Default effect - used if no others match
                continue

            # Evaluate condition
            if EffectSelector._evaluate_condition(selection_condition, context, card):
                logger.info(
                    f"EFFECT SELECTION: Effect {i} condition met: "
                    f"{EffectSelector._get_condition_description(selection_condition)}"
                )
                return i

        # No conditions met - use first effect marked as "default"
        for i, effect in enumerate(effects):
            if hasattr(effect, "selection_condition"):
                selection_condition = effect.selection_condition
            elif isinstance(effect, dict):
                selection_condition = effect.get("selection_condition")
            else:
                continue

            if selection_condition:
                if isinstance(selection_condition, dict):
                    condition_type = selection_condition.get("type")
                else:
                    condition_type = getattr(selection_condition, "type", None)

                if condition_type == "default":
                    logger.info(f"EFFECT SELECTION: Using default effect {i}")
                    return i

        # Fallback to first effect
        logger.info("EFFECT SELECTION: No conditions met, using effect 0 as fallback")
        return 0

    @staticmethod
    def _get_condition_description(condition) -> str:
        """Get human-readable description of a condition."""
        if isinstance(condition, dict):
            return condition.get("description", str(condition))
        return getattr(condition, "description", str(condition))

    @staticmethod
    def _evaluate_condition(condition, context, card) -> bool:
        """Evaluate a selection condition.

        Supported condition types:
        - CardCondition: Check for cards matching criteria in a location
        - VariableCondition: Check context variable value
        - PlayerStateCondition: Check player board/hand/score state
        """
        # Handle both dict and object conditions
        if isinstance(condition, dict):
            condition_type = condition.get("type")
        else:
            condition_type = getattr(condition, "type", None)

        if condition_type == "CardCondition":
            return EffectSelector._evaluate_card_condition(condition, context)

        elif condition_type == "VariableCondition":
            return EffectSelector._evaluate_variable_condition(condition, context)

        elif condition_type == "PlayerStateCondition":
            return EffectSelector._evaluate_player_state_condition(condition, context)

        else:
            logger.warning(
                f"Unknown condition type: {condition_type}, treating as false"
            )
            return False

    @staticmethod
    def _evaluate_card_condition(condition, context) -> bool:
        """Evaluate CardCondition - check for cards matching criteria.

        Example condition (dict format):
        {
            "type": "CardCondition",
            "field": "age",
            "operator": ">=",
            "value": 3,
            "location": "hand",
            "match_count": "any"  # "any", "all", or specific number
        }
        """
        # Extract condition parameters (support both dict and object)
        if isinstance(condition, dict):
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value")
            location = condition.get("location", "hand")
            match_count = condition.get("match_count", "any")
        else:
            field = getattr(condition, "field", None)
            operator = getattr(condition, "operator", None)
            value = getattr(condition, "value", None)
            location = getattr(condition, "location", "hand")
            match_count = getattr(condition, "match_count", "any")

        player = context.activating_player

        logger.info(
            f"CardCondition: Evaluating for player={player.name if hasattr(player, 'name') else 'NO_NAME'}, location={location}"
        )

        # Get cards from location
        if location == "hand":
            cards = player.hand if hasattr(player, "hand") else []
            logger.info(
                f"CardCondition: hand has {len(cards)} cards: {[c.name if hasattr(c, 'name') else str(c) for c in cards]}"
            )
        elif location == "board":
            cards = (
                player.board.get_all_cards()
                if hasattr(player, "board") and hasattr(player.board, "get_all_cards")
                else []
            )
        elif location == "score_pile":
            cards = player.score_pile if hasattr(player, "score_pile") else []
        else:
            logger.warning(f"Unknown location for CardCondition: {location}")
            return False

        # Filter cards based on condition
        filtered_cards = []
        for card in cards:
            card_value = getattr(card, field, None)
            if card_value is None:
                continue

            # Apply operator
            matches = False
            if operator == "==":
                matches = card_value == value
            elif operator == "!=":
                matches = card_value != value
            elif operator == ">":
                matches = card_value > value
            elif operator == ">=":
                matches = card_value >= value
            elif operator == "<":
                matches = card_value < value
            elif operator == "<=":
                matches = card_value <= value
            else:
                logger.warning(f"Unknown operator for CardCondition: {operator}")

            if matches:
                filtered_cards.append(card)

        # Check match count
        if match_count == "any":
            result = len(filtered_cards) > 0
        elif match_count == "all":
            result = len(filtered_cards) == len(cards) and len(cards) > 0
        elif isinstance(match_count, int):
            result = len(filtered_cards) >= match_count
        else:
            logger.warning(f"Invalid match_count: {match_count}")
            result = False

        logger.info(
            f"CardCondition evaluated: {len(filtered_cards)} cards matched "
            f"(field={field} {operator} {value} in {location}), "
            f"required {match_count}, result={result}"
        )
        return result

    @staticmethod
    def _evaluate_variable_condition(condition, context) -> bool:
        """Evaluate VariableCondition - check context variable value.

        Example condition:
        {
            "type": "VariableCondition",
            "variable": "has_achieved_age_3",
            "operator": "==",
            "value": true
        }
        """
        # Extract parameters
        if isinstance(condition, dict):
            variable_name = condition.get("variable")
            operator = condition.get("operator", "==")
            expected_value = condition.get("value")
        else:
            variable_name = getattr(condition, "variable", None)
            operator = getattr(condition, "operator", "==")
            expected_value = getattr(condition, "value", None)

        actual_value = context.get_variable(variable_name)

        if operator == "==":
            return actual_value == expected_value
        elif operator == "!=":
            return actual_value != expected_value
        elif operator == ">":
            return actual_value > expected_value
        elif operator == ">=":
            return actual_value >= expected_value
        elif operator == "<":
            return actual_value < expected_value
        elif operator == "<=":
            return actual_value <= expected_value
        elif operator == "exists":
            return actual_value is not None
        else:
            logger.warning(f"Unknown operator for VariableCondition: {operator}")
            return False

    @staticmethod
    def _evaluate_player_state_condition(condition, context) -> bool:
        """Evaluate PlayerStateCondition - check player board state.

        Example condition:
        {
            "type": "PlayerStateCondition",
            "check": "has_splayed_stack",
            "color": "blue"  # optional
        }

        Supported checks:
        - has_splayed_stack: Player has any splayed stack
        - has_color_splayed: Player has specific color splayed
        - achievement_count_gte: Player has N+ achievements
        """
        if isinstance(condition, dict):
            check = condition.get("check")
            color = condition.get("color")
            threshold = condition.get("threshold")
        else:
            check = getattr(condition, "check", None)
            color = getattr(condition, "color", None)
            threshold = getattr(condition, "threshold", None)

        player = context.activating_player

        if check == "has_splayed_stack":
            # Check if player has any splayed stacks
            if hasattr(player, "board") and hasattr(player.board, "splay_directions"):
                return len(player.board.splay_directions) > 0
            return False

        elif check == "has_color_splayed":
            # Check if specific color is splayed
            if hasattr(player, "board") and hasattr(player.board, "splay_directions"):
                return color in player.board.splay_directions
            return False

        elif check == "achievement_count_gte":
            # Check if player has N+ achievements
            if hasattr(player, "achievements"):
                return len(player.achievements) >= (threshold or 0)
            return False

        else:
            logger.warning(f"Unknown check for PlayerStateCondition: {check}")
            return False
