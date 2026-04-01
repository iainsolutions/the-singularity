"""Game state and action result condition evaluators."""

import logging
from typing import Any

from .base import BaseConditionEvaluator

logger = logging.getLogger(__name__)


class GameStateConditions(BaseConditionEvaluator):
    """Evaluates conditions related to game state and action results."""

    @property
    def supported_conditions(self) -> set[str]:
        return {
            "tucked_under_age_11",
            "option_chosen",
            "user_choice",
            "true",
            "last_drawn_color_equals",
            "last_evaluation_true",
            "last_melded_has_symbol",
            "last_returned_age_equals",
            "returned_count_equals",
            "returned_most_cards_this_action",
        }

    def evaluate(self, condition: dict[str, Any], context) -> bool:
        """Evaluate game state related conditions."""
        condition_type = condition.get("type")

        if condition_type == "tucked_under_age_11":
            # Check if card was tucked under age 11
            tucked_age = context.get_variable("tucked_under_age")
            return tucked_age == 11

        elif condition_type == "option_chosen":
            # Check if an option was chosen
            option = condition.get("option")
            chosen = context.get_variable("chosen_option")

            # Enhanced debugging for option_chosen condition - always log at INFO level for Canal Building
            logger.debug("DEBUG:")
            logger.info(f"  Expected option: '{option}' (type: {type(option)})")
            logger.info(f"  Actual chosen: '{chosen}' (type: {type(chosen)})")
            logger.info(f"  Direct comparison result: {chosen == option}")

            # Also check other related variables for debugging
            selected_color = context.get_variable("selected_color")
            player_choice = context.get_variable("player_choice")
            pending_options = context.get_variable("pending_option_configs")
            logger.info(f"  selected_color: '{selected_color}'")
            logger.info(f"  player_choice: '{player_choice}'")
            logger.info(
                f"  pending_option_configs: {[opt.get('value') for opt in (pending_options or [])]}"
            )

            if option:
                # CRITICAL FIX: Handle both index-based and value-based comparisons
                # If chosen is an integer (index) and option is a string (value),
                # try to resolve the index to the corresponding option value
                if isinstance(chosen, int) and isinstance(option, str):
                    # Look for pending_option_configs to resolve index to value
                    if pending_options and 0 <= chosen < len(pending_options):
                        chosen_option_config = pending_options[chosen]
                        chosen_value = chosen_option_config.get(
                            "value", f"option_{chosen}"
                        )
                        logger.info(
                            f"🔧 option_chosen: resolved index {chosen} to value '{chosen_value}'"
                        )
                        result = chosen_value == option
                        logger.info(
                            f"🔧 option_chosen: resolved comparison result: {result}"
                        )
                    else:
                        logger.warning(
                            f"WARNING: option_chosen: cannot resolve index {chosen} - no pending_option_configs or index out of range"
                        )
                        result = chosen == option  # Fallback to direct comparison
                        logger.warning(
                            f"WARNING: option_chosen: fallback comparison result: {result}"
                        )
                else:
                    # Direct comparison (for backward compatibility or when types match)
                    result = chosen == option
                    logger.info(f"🔧 option_chosen: direct comparison result: {result}")

                logger.info(f"🎯 FINAL option_chosen condition result: {result}")
                return result
            else:
                # Just check if any option was chosen
                result = bool(chosen)
                logger.info(
                    f"🎯 FINAL option_chosen condition result (any option): {result}"
                )
                return result

        elif condition_type == "user_choice":
            # Check if user made a choice - requires interaction
            prompt = condition.get("prompt")
            # This would require interaction, store for later
            context.set_variable("user_choice_prompt", prompt)
            # For now, assume false (will be handled by interaction)
            return False

        elif condition_type == "true":
            # Always true condition
            return True

        elif condition_type == "last_drawn_color_equals":
            # Check if last drawn card has a specific color
            expected_color = condition.get("color")
            last_drawn = context.get_variable("last_drawn")

            if last_drawn and hasattr(last_drawn, "color"):
                card_color = (
                    last_drawn.color.value
                    if hasattr(last_drawn.color, "value")
                    else last_drawn.color.value
                )
                return card_color == expected_color
            return False

        elif condition_type == "last_evaluation_true":
            # Check if last evaluation was true
            last_eval = context.get_variable("last_evaluation", False)
            return bool(last_eval)

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
