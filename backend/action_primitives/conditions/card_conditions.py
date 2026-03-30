"""Card-related condition evaluators."""

import logging
from typing import Any

from utils.board_utils import (
    get_board_colors,
    is_card_on_top_of_board,
    validate_player_has_board,
)
from utils.card_utils import normalize_card_color

from .base import BaseConditionEvaluator

logger = logging.getLogger(__name__)


class CardConditions(BaseConditionEvaluator):
    """Evaluates conditions related to cards and card properties."""

    @property
    def supported_conditions(self) -> set[str]:
        return {
            "cards_tucked",
            "no_transfer",
            "cards_transferred",
            "no_cards_transferred",
            "cards_selected",
            "cards_scored",
            "has_symbol",
            "card_color",
            "card_name",
            "is_top_card",
            "card_is_top_on_any_board",
            "any_card_color",
            "at_least_n_same_color",
            "card_color_in_selected",
            "cards_count_equals",
            "cards_are_top_on_any_board",
            "card_color_on_board",
            "last_drawn_color_equals",
            "last_melded_has_symbol",
            "last_returned_age_equals",
            "returned_count_equals",
            "returned_most_cards_this_action",
        }

    def evaluate(self, condition: dict[str, Any], context) -> bool:
        """Evaluate card-related conditions."""
        condition_type = condition.get("type")

        if condition_type == "cards_tucked":
            # Check if cards were tucked in previous actions
            tucked_count = context.get_variable("tucked_count", 0)
            expected_count = condition.get("count", 1)
            return tucked_count >= expected_count

        elif condition_type == "no_transfer":
            # Check if no cards were transferred
            transferred_count = context.get_variable("transferred_count", 0)
            return transferred_count == 0

        elif condition_type == "cards_transferred":
            # Check if cards were transferred in previous actions
            transferred_count = context.get_variable("transferred_count", 0)
            demand_transferred_count = context.get_variable(
                "demand_transferred_count", 0
            )
            expected = condition.get("count", 1)
            return (transferred_count >= expected) or (
                demand_transferred_count >= expected
            )

        elif condition_type == "no_cards_transferred":
            # Check that no cards were transferred
            transferred_count = context.get_variable("transferred_count", 0)
            demand_transferred_count = context.get_variable(
                "demand_transferred_count", 0
            )
            return transferred_count == 0 and demand_transferred_count == 0

        elif condition_type == "cards_selected":
            # Check if cards were selected in a previous action
            # If a specific variable is specified, check only that variable
            check_variable = condition.get("variable")
            if check_variable:
                selected_cards = context.get_variable(check_variable, [])
                logger.info(
                    f"DEBUG cards_selected condition: checking specific variable '{check_variable}' = {selected_cards}, result = {bool(selected_cards)}"
                )
                return bool(selected_cards)
            else:
                # Default behavior: check common variable names
                selected_cards = context.get_variable("selected_cards", []) or []
                cards_to_return = context.get_variable("cards_to_return", []) or []

                # CRITICAL FIX: Also check the stored interaction_response for recent card selections
                # This handles the case where context variables were lost during suspension/resume
                interaction_response = context.get_variable("interaction_response", {})
                response_cards = (
                    interaction_response.get("selected_cards", [])
                    if interaction_response
                    else []
                )

                # WORKAROUND: For now, if we're in a resumed transaction and see an interaction response
                # with selected cards, treat that as cards being selected even if context vars are empty
                if response_cards and not (selected_cards or cards_to_return):
                    logger.info(
                        f"DEBUG cards_selected WORKAROUND: Found response_cards={len(response_cards)} in interaction_response, treating as selected"
                    )
                    return True

                has_cards = bool(selected_cards or cards_to_return or response_cards)
                logger.info(
                    f"DEBUG cards_selected condition: selected_cards={len(selected_cards)}, cards_to_return={len(cards_to_return)}, response_cards={len(response_cards)}, result={has_cards}"
                )

                return has_cards

        elif condition_type == "cards_scored":
            # Check if cards were scored in this action
            scored_count = context.get_variable("scored_count", 0)
            min_count = condition.get("count", 1)
            return scored_count >= min_count

        elif condition_type == "has_symbol":
            # Check if a card has a specific symbol
            source = condition.get("source")
            symbol = condition.get("symbol")
            card_or_cards = context.get_variable(source)

            logger.info(f"🔍 has_symbol check: source='{source}', symbol='{symbol}'")
            logger.info(f"🔍 has_symbol: card_or_cards={card_or_cards}")
            logger.info(f"🔍 has_symbol: card_or_cards type={type(card_or_cards)}")

            if card_or_cards:
                cards = (
                    card_or_cards
                    if isinstance(card_or_cards, list)
                    else [card_or_cards]
                )
                logger.info(f"🔍 has_symbol: checking {len(cards)} card(s)")
                for i, card in enumerate(cards):
                    card_name = getattr(card, "name", "UNKNOWN")
                    card_symbols = getattr(card, "symbols", [])
                    has_attr = hasattr(card, "symbols")
                    symbol_in = symbol in card_symbols if has_attr else False

                    logger.info(f"🔍 has_symbol: card[{i}]='{card_name}'")
                    logger.info(f"🔍 has_symbol: card.hasattr('symbols')={has_attr}")
                    logger.info(f"🔍 has_symbol: card.symbols={card_symbols}")
                    logger.info(f"🔍 has_symbol: '{symbol}' in symbols? {symbol_in}")

                    if hasattr(card, "symbols") and symbol in card.symbols:
                        logger.info(f"✅ has_symbol: TRUE - {card_name} has {symbol}")
                        return True

                logger.info(f"❌ has_symbol: FALSE - no cards have {symbol}")
                return False
            else:
                logger.info(f"❌ has_symbol: FALSE - {source} variable is empty/None")
                return False

        elif condition_type == "card_color":
            # Check if a card has a specific color
            card_variable = condition.get("card", "last_drawn")
            target_color = condition.get("color")
            card = context.get_variable(card_variable)

            if card and hasattr(card, "color"):
                card_color = str(card.color)
                return card_color == target_color
            return False

        elif condition_type == "card_name":
            # Check if a card has a specific name or ID
            expected_identifier = condition.get("name")
            card_source = condition.get("card", "selected_cards")
            card = context.get_variable(card_source)

            if card:
                # Check card_id first (preferred stable identifier), then fall back to name
                if (
                    hasattr(card, "card_id")
                    and card.card_id
                    and card.card_id == expected_identifier
                ):
                    return True
                if hasattr(card, "name") and card.name == expected_identifier:
                    return True
            return False

        elif condition_type == "is_top_card":
            # Check if a specific card is on top of any stack
            card_name = condition.get("card_name")

            if validate_player_has_board(context.player):
                return is_card_on_top_of_board(context.player.board, card_name)
            return False

        elif condition_type == "card_is_top_on_any_board":
            # Check if a card is on top of any color stack on any player's board
            # Support two modes:
            # 1. "card": variable containing the card object
            # 2. "card_name": literal card name string
            card_name = condition.get("card_name")
            if card_name:
                # Direct card name lookup
                pass
            else:
                # Variable-based lookup (existing behavior)
                card_source = condition.get("card", "last_drawn")
                cards = context.get_variable(card_source, [])

                # Get the card (handle list or single card)
                if isinstance(cards, list) and cards:
                    card = cards[0]
                elif cards:
                    card = cards
                else:
                    return False
                card_name = card.name

            # Check if this card is on top of any color stack on any player's board
            for player in context.game.players:
                if validate_player_has_board(player):
                    if is_card_on_top_of_board(player.board, card_name):
                        return True
            return False

        elif condition_type == "any_card_color":
            # Check if any card in a variable has a specific color
            card_source = condition.get("cards", "revealed_cards")
            target_color = condition.get("color", "red")
            cards = context.get_variable(card_source, [])

            if not isinstance(cards, list):
                cards = [cards] if cards else []

            logger.debug(
                f"any_card_color: checking {len(cards)} cards from '{card_source}' for color '{target_color}'"
            )
            for card in cards:
                if card and hasattr(card, "color"):
                    # CRITICAL FIX: Extract enum value properly, not full enum string
                    card_color = (
                        card.color.value
                        if hasattr(card.color, "value")
                        else str(card.color)
                    )
                    logger.debug(f"any_card_color: card={card.name if hasattr(card, 'name') else 'unknown'}, color={card_color}")
                    if card_color == target_color:
                        logger.debug("any_card_color: MATCH! Returning True")
                        return True
            logger.debug("any_card_color: No match found, returning False")
            return False

        elif condition_type == "at_least_n_same_color":
            # Check if at least N cards in source have same color
            n = condition.get("n", 2)
            source = condition.get("source", "last_drawn")
            cards = context.get_variable(source, [])

            if not isinstance(cards, list):
                cards = [cards] if cards else []

            # Count cards by color
            color_counts = {}
            for card in cards:
                if card and hasattr(card, "color"):
                    card_color = str(card.color)
                    color_counts[card_color] = color_counts.get(card_color, 0) + 1

            return any(count >= n for count in color_counts.values())

        elif condition_type == "card_color_in_selected":
            # Check if a card's color is in selected cards
            card_source = condition.get("card", "last_drawn")
            selected_source = condition.get("selected", "selected_cards")

            card = context.get_variable(card_source)
            selected_cards = context.get_variable(selected_source, [])

            if card and hasattr(card, "color") and selected_cards:
                card_color = str(card.color)
                for sel_card in selected_cards:
                    if hasattr(sel_card, "color"):
                        sel_color = (
                            sel_card.color.value
                            if hasattr(sel_card.color, "value")
                            else str(sel_card.color)
                        )
                        if card_color == sel_color:
                            return True
            return False

        elif condition_type == "cards_count_equals":
            # Check if number of cards equals a value
            source = condition.get("source", "selected_cards")
            expected_count = condition.get("count", 0)
            cards = context.get_variable(source, [])

            if not isinstance(cards, list):
                cards = [cards] if cards else []

            return len(cards) == expected_count

        elif condition_type == "cards_are_top_on_any_board":
            # Check if specific cards are on top of any player's board
            card_names = condition.get("cards", [])

            for card_name in card_names:
                found = False
                if hasattr(context.game, "players"):
                    for player in context.game.players:
                        if validate_player_has_board(player):
                            if is_card_on_top_of_board(player.board, card_name):
                                found = True
                                break
                        if found:
                            break
                if not found:
                    return False
            return True

        elif condition_type == "card_color_on_board":
            # Check if the card's color is on the player's board
            card_variable = condition.get("card", "last_drawn")
            card = context.get_variable(card_variable)
            logger.debug(
                f"card_color_on_board: card_variable={card_variable}, card={card}"
            )
            if card and validate_player_has_board(context.player):
                card_color = normalize_card_color(card)
                logger.debug(f"card_color_on_board: normalized card_color={card_color}")
                if card_color:
                    board_colors = get_board_colors(context.player.board)
                    logger.debug(f"card_color_on_board: board_colors={board_colors}")
                    result = card_color in board_colors
                    logger.debug(
                        f"card_color_on_board: {card_color} in {board_colors} = {result}"
                    )
                    return result
            logger.debug("card_color_on_board: returning False (no card or no board)")
            return False

        elif condition_type == "last_drawn_color_equals":
            # Check if last drawn card has a specific color
            expected_color = condition.get("color")
            last_drawn = context.get_variable("last_drawn")

            if last_drawn and hasattr(last_drawn, "color"):
                card_color = (
                    last_drawn.color.value
                    if hasattr(last_drawn.color, "value")
                    else str(last_drawn.color)
                )
                return card_color == expected_color
            return False

        elif condition_type == "last_melded_has_symbol":
            # Check if last melded card has a symbol
            symbol = condition.get("symbol")
            last_melded = context.get_variable("last_melded") or context.get_variable(
                "first_melded"
            )

            if last_melded and hasattr(last_melded, "symbols"):
                return symbol in last_melded.symbols
            return False

        elif condition_type == "last_returned_age_equals":
            # Check if last returned card has specific age
            expected_age = condition.get("age")
            last_returned = context.get_variable("last_returned")

            if last_returned and hasattr(last_returned, "age"):
                return last_returned.age == expected_age
            return False

        elif condition_type == "returned_count_equals":
            # Check if returned count equals a value
            expected_count = condition.get("count", 0)
            returned_count = context.get_variable("returned_count", 0)
            return returned_count == expected_count

        elif condition_type == "returned_most_cards_this_action":
            # Check if this player returned the most cards
            my_returned = context.get_variable("my_returned_count", 0)
            max_returned = context.get_variable("max_returned_count", 0)
            return my_returned > 0 and my_returned >= max_returned

        return False
