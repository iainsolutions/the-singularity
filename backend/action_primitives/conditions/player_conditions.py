"""Player state and multi-player condition evaluators."""

import logging
from typing import Any

from utils.board_utils import validate_player_has_board
from utils.player_utils import get_player_symbol_count

from .base import BaseConditionEvaluator

logger = logging.getLogger(__name__)


class PlayerConditions(BaseConditionEvaluator):
    """Evaluates conditions related to player state and multi-player comparisons."""

    @property
    def supported_conditions(self) -> set[str]:
        return {
            "has_cards",
            "hand_not_empty",
            "hand_count_at_least",
            "has_achievement",
            "has_twice_achievements_of_opponents",
            "not_highest_score",
            "single_player_with_most_symbol",
            "any_player_has_fewer_than_symbol",
            "no_player_has_more_symbol_than",
            "only_player_with_condition",
            "symbol_count",
            "symbol_count_at_least",
            "all_non_color_top_cards_min_age",
            "all_top_cards_have_symbol",
            "color_on_board",
            "color_splayed",
            "color_splayed_aslant",
            "color_not_splayed_aslant",
            "color_selected",
            "color_count_at_least",
        }

    def evaluate(self, condition: dict[str, Any], context) -> bool:
        """Evaluate player-related conditions."""
        condition_type = condition.get("type")

        if condition_type == "hand_not_empty":
            # Check if player has at least one card in hand
            return len(getattr(context.player, "hand", [])) > 0

        elif condition_type == "has_cards":
            # Check if cards exist in a location or context variable
            source = condition.get("source")
            location = condition.get("location", "hand")
            min_count = condition.get("min_count", 1)

            # If source is a context variable name, check that variable
            if source and source not in ("hand", "score_pile", "board"):
                cards = context.get_variable(source, [])
                if isinstance(cards, list):
                    return len(cards) >= min_count
                return bool(cards)

            # Fall back to checking player locations
            loc = source or location
            if loc == "hand":
                return len(getattr(context.player, "hand", [])) >= min_count
            elif loc == "score_pile":
                return len(getattr(context.player, "score_pile", [])) >= min_count
            elif loc == "board":
                board = getattr(context.player, "board", None)
                if board:
                    return len(board.get_all_cards()) >= min_count
            return False

        elif condition_type == "hand_count_at_least":
            # Check if hand has at least N cards
            min_count = condition.get("count", 1)
            hand_count = len(getattr(context.player, "hand", []))
            return hand_count >= min_count

        elif condition_type == "has_achievement":
            # Check if player has a specific achievement
            achievement_name = condition.get("name")
            if hasattr(context.player, "achievements"):
                for achievement in context.player.achievements:
                    if (
                        hasattr(achievement, "name")
                        and achievement.name == achievement_name
                    ):
                        return True
            return False

        elif condition_type == "has_twice_achievements_of_opponents":
            # Check if player has at least twice the achievements of each opponent
            my_achievements = len(getattr(context.player, "achievements", []))

            if hasattr(context.game, "players"):
                for other_player in context.game.players:
                    if other_player.id != context.player.id:
                        other_achievements = len(
                            getattr(other_player, "achievements", [])
                        )
                        if my_achievements < 2 * other_achievements:
                            return False
            return True

        elif condition_type == "not_highest_score":
            # Check if player doesn't have highest score
            my_score = len(getattr(context.player, "score_pile", []))

            if hasattr(context.game, "players"):
                for other_player in context.game.players:
                    if other_player.id != context.player.id:
                        other_score = len(getattr(other_player, "score_pile", []))
                        if other_score > my_score:
                            return True
            return False

        elif condition_type == "single_player_with_most_symbol":
            # Check if there's a single player with most of a symbol (no ties)
            symbol = condition.get("symbol")

            if hasattr(context.game, "players"):
                symbol_counts = {}
                for player in context.game.players:
                    if validate_player_has_board(player):
                        count = get_player_symbol_count(player, symbol)
                        symbol_counts[player.id] = count

                if symbol_counts:
                    max_count = max(symbol_counts.values())
                    players_with_max = [
                        pid
                        for pid, count in symbol_counts.items()
                        if count == max_count
                    ]
                    return len(players_with_max) == 1
            return False

        elif condition_type == "any_player_has_fewer_than_symbol":
            # Check if any player has fewer than N of a symbol
            symbol = condition.get("symbol")
            count = condition.get("count", 1)

            if hasattr(context.game, "players"):
                for player in context.game.players:
                    if validate_player_has_board(player):
                        symbol_count = get_player_symbol_count(player, symbol)
                        if symbol_count < count:
                            return True
            return False

        elif condition_type == "no_player_has_more_symbol_than":
            # Check if no player has more of symbol1 than symbol2
            symbol1 = condition.get("symbol1")
            symbol2 = condition.get("symbol2")

            if hasattr(context.game, "players"):
                for player in context.game.players:
                    if validate_player_has_board(player):
                        symbol1_count = get_player_symbol_count(player, symbol1)
                        symbol2_count = get_player_symbol_count(player, symbol2)
                        if symbol1_count > symbol2_count:
                            return False
            return True

        elif condition_type == "only_player_with_condition":
            # Check if this player is the only one meeting a condition
            condition_name = condition.get("condition")

            if condition_name == "five_top_cards":
                my_top_cards = (
                    len(context.player.board.get_top_cards())
                    if hasattr(context.player.board, "get_top_cards")
                    else 0
                )
                if my_top_cards != 5:
                    return False

                if hasattr(context.game, "players"):
                    for other_player in context.game.players:
                        if other_player.id != context.player.id:
                            other_top_cards = (
                                len(other_player.board.get_top_cards())
                                if hasattr(other_player.board, "get_top_cards")
                                else 0
                            )
                            if other_top_cards == 5:
                                return False
                return True
            return False

        elif condition_type == "symbol_count":
            # Check symbol count on board or other location
            source = condition.get("source")
            symbol = condition.get("symbol")
            operator = condition.get("operator", ">=")
            value = condition.get("value", 0)

            symbol_count = 0
            if source == "opponent_board":
                for opponent in context.game.players:
                    if opponent.id != context.player.id:
                        if validate_player_has_board(opponent):
                            symbol_count += get_player_symbol_count(opponent, symbol)
            elif source == "player_board":
                if validate_player_has_board(context.player):
                    symbol_count += get_player_symbol_count(context.player, symbol)

            # Compare based on operator
            if operator == ">=":
                return symbol_count >= value
            elif operator == "<=":
                return symbol_count <= value
            elif operator == "==":
                return symbol_count == value
            elif operator == ">":
                return symbol_count > value
            elif operator == "<":
                return symbol_count < value
            else:
                return False

        elif condition_type == "symbol_count_at_least":
            # Check if symbol count is at least N
            symbol = condition.get("symbol")
            min_count = condition.get("count", 1)

            if validate_player_has_board(context.player):
                count = get_player_symbol_count(context.player, symbol)
                return count >= min_count
            return False

        elif condition_type == "all_non_color_top_cards_min_age":
            # Check if all non-specified color top cards meet min age
            color = condition.get("color")
            min_age = condition.get("min_age", 0)

            if hasattr(context.player, "board"):
                for stack_color in ["red", "blue", "green", "purple", "yellow"]:
                    if stack_color != color:
                        stack = getattr(
                            context.player.board, f"{stack_color}_cards", []
                        )
                        if stack:
                            top_card = stack[-1]
                            if getattr(top_card, "age", 0) < min_age:
                                return False
            return True

        elif condition_type == "all_top_cards_have_symbol":
            # Check if all top cards on board have a specific symbol
            symbol = condition.get("symbol")

            if hasattr(context.player, "board"):
                for color in ["red", "blue", "green", "purple", "yellow"]:
                    stack = getattr(context.player.board, f"{color}_cards", [])
                    if stack:
                        top_card = stack[-1]
                        if (
                            hasattr(top_card, "symbols")
                            and symbol not in top_card.symbols
                        ):
                            return False
            return True

        elif condition_type == "color_on_board":
            # Check if a specific color is present on the player's board
            color_variable = condition.get("color")
            drawn_color = context.get_variable(color_variable)
            if drawn_color and hasattr(context.player, "board"):
                board_colors = self._get_board_colors(context.player.board)
                return drawn_color in board_colors
            return False

        elif condition_type == "color_splayed":
            # Check if a color is splayed in a specific direction
            color = condition.get("color")
            direction = condition.get("direction")

            if hasattr(context.player, "board"):
                splay_dir = getattr(context.player.board, f"{color}_splay", None)
                return splay_dir == direction
            return False

        elif condition_type == "color_splayed_aslant":
            # Check if a color is splayed aslant (up)
            color_var = condition.get("color", "revealed_card_color")
            color = (
                context.get_variable(color_var)
                if isinstance(color_var, str)
                else color_var
            )

            if color and hasattr(context.player, "board"):
                splay_dir = getattr(context.player.board, f"{color}_splay", None)
                return splay_dir == "up"
            return False

        elif condition_type == "color_not_splayed_aslant":
            # Check if a color is not splayed aslant (up)
            color = condition.get("color")

            if hasattr(context.player, "board"):
                splay_dir = getattr(context.player.board, f"{color}_splay", None)
                return splay_dir != "up"
            return True

        elif condition_type == "color_selected":
            # Check if a color was selected
            selected_color = context.get_variable("selected_color")
            logger.debug(
                f"color_selected condition: selected_color={selected_color}, bool={bool(selected_color)}"
            )
            return bool(selected_color)

        elif condition_type == "color_count_at_least":
            # Check if a color appears at least N times
            color_var = condition.get("color", "melded_card_color")
            count = condition.get("count", 1)
            color = context.get_variable(color_var)

            if color and hasattr(context.player, "board"):
                stack = getattr(context.player.board, f"{color}_cards", [])
                return len(stack) >= count
            return False

        return False
