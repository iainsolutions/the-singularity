"""Additional condition evaluators for Unseen expansion cards."""

import logging
from typing import Any

from .base import BaseConditionEvaluator

logger = logging.getLogger(__name__)


class UnseenConditions(BaseConditionEvaluator):
    """Evaluates conditions specific to Unseen expansion and frequently-used missing types."""

    @property
    def supported_conditions(self) -> set[str]:
        return {
            # TOP PRIORITY - Most frequently used
            "choice_equals",  # 51 usages
            "card_selected",  # 38 usages
            "standard",  # 16 usages
            "value_not_in_board_or_score",  # 10 usages
            "color_is_splayed",  # 10 usages
            # HIGH PRIORITY - Frequently used
            "card_has_symbol",  # 6 usages
            "value_equals",  # 5 usages
            "color_splayed_direction",  # 5 usages
            "color_not_on_board",  # 5 usages
            "color_has_symbol",  # 5 usages
            "color_equals",  # 5 usages
            "achievement_selected",  # 5 usages
            "value_at_least",  # 4 usages
            # MEDIUM PRIORITY
            "symbols_count_threshold",  # 3 usages
            "list_contains",  # 3 usages
            "has_exact_symbol_count",  # 3 usages
            "cards_selected_count",  # 3 usages
            "is_splayed",  # 2 usages
            "has_card_with_age",  # 2 usages
            "has_card_in_score",  # 2 usages
            "greater_than_or_equal",  # 2 usages
            "greater_than",  # 2 usages
            "color_in_list",  # 2 usages
            "coin_flip_result",  # 2 usages
            "cards_count_at_least",  # 2 usages
            "card_is_bottom",  # 2 usages
            # LOW PRIORITY (1 usage each but needed)
            "tucked_yellow_or_expansion",
            "set_equals",
            "returned_card_age",
            "points_scored_less_than",
            "player_has_no_symbol",
            "player_has_no_color_in_hand",
            "player_chooses_continue",
            "not_null",
            "no_player_has_top_card_color",
            "no_cards_returned",
            "no_card_transferred_from_demand",
            "no_card_scored_and_hand_not_empty",
            "list_not_contains",
            "less_than",
            "is_current_turn",
            "has_top_card_name",
            "cards_returned_count",
            "card_is_top_on_board",
            "card_has_no_symbol",
            "card_exists",
            "board_empty",
            "all_cards_selected",
        }

    def evaluate(self, condition: dict[str, Any], context) -> bool:
        """Evaluate Unseen-specific conditions."""
        condition_type = condition.get("type")

        # ===== TOP PRIORITY CONDITIONS =====

        if condition_type == "choice_equals":
            # Check if chosen option equals a value (51 usages)
            expected = condition.get("choice") or condition.get("value")
            chosen = context.get_variable("chosen_option")
            return chosen == expected

        elif condition_type == "card_selected":
            # Check if a card was selected (38 usages)
            card_var = condition.get("variable", "selected_cards")
            cards = context.get_variable(card_var, [])
            return bool(cards) and len(cards) > 0

        elif condition_type == "standard":
            # Check if achievement is standard (16 usages)
            achievement_var = condition.get("achievement", "selected_achievement")
            achievement = context.get_variable(achievement_var)
            if achievement:
                # Standard achievements are ages 1-9
                if hasattr(achievement, "age"):
                    return 1 <= achievement.age <= 9
                elif isinstance(achievement, dict) and "age" in achievement:
                    return 1 <= achievement["age"] <= 9
            return False

        elif condition_type == "value_not_in_board_or_score":
            # Check if a value is not present in board or score (10 usages)
            value = condition.get("value")
            player = context.current_player

            # Check board
            if hasattr(player, "board"):
                for color in ["red", "blue", "green", "yellow", "purple"]:
                    cards = getattr(player.board, f"{color}_cards", [])
                    for card in cards:
                        if hasattr(card, "age") and card.age == value:
                            return False

            # Check score pile
            if hasattr(player, "score_pile"):
                for card in player.score_pile:
                    if hasattr(card, "age") and card.age == value:
                        return False

            return True

        elif condition_type == "color_is_splayed":
            # Check if a color is splayed (10 usages)
            color = condition.get("color")
            if isinstance(color, str) and context.has_variable(color):
                color = context.get_variable(color)

            player = context.current_player
            if hasattr(player, "board"):
                splay_attr = f"{color}_splay"
                splay = getattr(player.board, splay_attr, "none")
                return splay != "none"
            return False

        # ===== HIGH PRIORITY CONDITIONS =====

        elif condition_type == "card_has_symbol":
            # Check if card has a specific symbol (6 usages)
            card_var = condition.get("card", "selected_cards")
            symbol = condition.get("symbol")

            card = context.get_variable(card_var)
            if isinstance(card, list) and card:
                card = card[0]

            if card and hasattr(card, "symbols"):
                from models.card import Symbol
                symbol_map = {
                    "castle": Symbol.CASTLE,
                    "leaf": Symbol.LEAF,
                    "lightbulb": Symbol.LIGHTBULB,
                    "crown": Symbol.CROWN,
                    "factory": Symbol.FACTORY,
                    "clock": Symbol.CLOCK,
                }
                target_symbol = symbol_map.get(str(symbol).lower()) if isinstance(symbol, str) else symbol
                return target_symbol in card.symbols
            return False

        elif condition_type == "value_equals":
            # Check if a value equals another (5 usages)
            left = condition.get("left") or condition.get("variable")
            right = condition.get("right") or condition.get("value")

            # Resolve variables
            if isinstance(left, str) and context.has_variable(left):
                left = context.get_variable(left)
            if isinstance(right, str) and context.has_variable(right):
                right = context.get_variable(right)

            return left == right

        elif condition_type == "color_splayed_direction":
            # Check if color is splayed in a specific direction (5 usages)
            color = condition.get("color")
            direction = condition.get("direction")

            if isinstance(color, str) and context.has_variable(color):
                color = context.get_variable(color)

            player = context.current_player
            if hasattr(player, "board"):
                splay_attr = f"{color}_splay"
                splay = getattr(player.board, splay_attr, "none")
                return splay == direction
            return False

        elif condition_type == "color_not_on_board":
            # Check if color is not on board (5 usages)
            color = condition.get("color")
            if isinstance(color, str) and context.has_variable(color):
                color = context.get_variable(color)

            player = context.current_player
            if hasattr(player, "board"):
                cards = getattr(player.board, f"{color}_cards", [])
                return len(cards) == 0
            return True

        elif condition_type == "color_has_symbol":
            # Check if a color stack has a symbol (5 usages)
            color = condition.get("color")
            symbol = condition.get("symbol")

            if isinstance(color, str) and context.has_variable(color):
                color = context.get_variable(color)

            player = context.current_player
            if hasattr(player, "board"):
                cards = getattr(player.board, f"{color}_cards", [])
                if cards:
                    from models.card import Symbol
                    symbol_map = {
                        "castle": Symbol.CASTLE,
                        "leaf": Symbol.LEAF,
                        "lightbulb": Symbol.LIGHTBULB,
                        "crown": Symbol.CROWN,
                        "factory": Symbol.FACTORY,
                        "clock": Symbol.CLOCK,
                    }
                    target_symbol = symbol_map.get(str(symbol).lower())
                    for card in cards:
                        if hasattr(card, "symbols") and target_symbol in card.symbols:
                            return True
            return False

        elif condition_type == "color_equals":
            # Check if a color equals another (5 usages)
            left = condition.get("left") or condition.get("color")
            right = condition.get("right") or condition.get("value")

            if isinstance(left, str) and context.has_variable(left):
                left = context.get_variable(left)
            if isinstance(right, str) and context.has_variable(right):
                right = context.get_variable(right)

            return str(left) == str(right)

        elif condition_type == "achievement_selected":
            # Check if an achievement was selected (5 usages)
            achievement_var = condition.get("variable", "selected_achievement")
            achievement = context.get_variable(achievement_var)
            return achievement is not None

        elif condition_type == "value_at_least":
            # Check if a value is at least a threshold (4 usages)
            value = condition.get("value") or condition.get("variable")
            threshold = condition.get("threshold") or condition.get("min")

            if isinstance(value, str) and context.has_variable(value):
                value = context.get_variable(value)

            try:
                return int(value) >= int(threshold)
            except (ValueError, TypeError):
                return False

        # ===== MEDIUM & LOW PRIORITY CONDITIONS =====

        elif condition_type == "cards_selected_count":
            # Count of selected cards equals threshold
            card_var = condition.get("variable", "selected_cards")
            expected_count = condition.get("count", 1)
            cards = context.get_variable(card_var, [])
            actual_count = len(cards) if isinstance(cards, list) else (1 if cards else 0)
            return actual_count == expected_count

        elif condition_type == "greater_than":
            left = condition.get("left") or condition.get("variable")
            right = condition.get("right") or condition.get("value")
            if isinstance(left, str) and context.has_variable(left):
                left = context.get_variable(left)
            if isinstance(right, str) and context.has_variable(right):
                right = context.get_variable(right)
            try:
                return float(left) > float(right)
            except (ValueError, TypeError):
                return False

        elif condition_type == "greater_than_or_equal":
            left = condition.get("left") or condition.get("variable")
            right = condition.get("right") or condition.get("value")
            if isinstance(left, str) and context.has_variable(left):
                left = context.get_variable(left)
            if isinstance(right, str) and context.has_variable(right):
                right = context.get_variable(right)
            try:
                return float(left) >= float(right)
            except (ValueError, TypeError):
                return False

        elif condition_type == "less_than":
            left = condition.get("left") or condition.get("variable")
            right = condition.get("right") or condition.get("value")
            if isinstance(left, str) and context.has_variable(left):
                left = context.get_variable(left)
            if isinstance(right, str) and context.has_variable(right):
                right = context.get_variable(right)
            try:
                return float(left) < float(right)
            except (ValueError, TypeError):
                return False

        elif condition_type == "not_null":
            variable = condition.get("variable") or condition.get("value")
            if isinstance(variable, str):
                value = context.get_variable(variable, None)
                return value is not None
            return variable is not None

        elif condition_type == "list_contains":
            list_var = condition.get("list")
            item = condition.get("item") or condition.get("value")
            items = context.get_variable(list_var, [])
            if isinstance(items, list):
                return item in items
            return False

        elif condition_type == "list_not_contains":
            list_var = condition.get("list")
            item = condition.get("item") or condition.get("value")
            items = context.get_variable(list_var, [])
            if isinstance(items, list):
                return item not in items
            return True

        elif condition_type == "coin_flip_result":
            result = context.get_variable("coin_flip_result", "")
            expected = condition.get("result", "heads")
            return result == expected

        elif condition_type == "is_current_turn":
            if hasattr(context.game_state, "current_turn_player"):
                return context.game_state.current_turn_player == context.current_player.id
            return False

        # Return False for unhandled conditions
        logger.debug(f"UnseenConditions: Unhandled condition type '{condition_type}'")
        return False
