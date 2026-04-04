"""
ScoreCards Action Primitive

Moves cards to a player's score pile.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class ScoreCards(ActionPrimitive):
    """
    Moves cards to the player's score pile.

    Parameters:
    - source: Source of cards ('hand', 'board', 'last_drawn', or variable name)
    - count: Number of cards to score (default 1)
    - selection_type: How to select cards ('all', 'highest', 'lowest', 'specific')
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.source = config.get("source", "hand")
        count_value = config.get("count", 1)

        # Handle count: "all" by converting to selection_type: "all"
        if count_value == "all":
            self.count = 1  # Default count for non-all cases
            self.selection_type = "all"
        else:
            self.count = count_value
            self.selection_type = config.get("selection_type", "specific")

    def execute(self, context: ActionContext) -> ActionResult:
        """Score cards by moving them to score pile"""
        # Handle 'cards' parameter (preferred), then 'selection', then fallback to source logic
        cards_param = self.config.get("cards")
        selection = self.config.get("selection")

        # RUNTIME ASSERTION: Validate expected source variable exists when specified
        # This catches cases where we try to score from a variable that doesn't exist
        if self.source == "last_drawn" and not context.has_variable("last_drawn"):
            logger.warning(
                f"VARIABLE LIFECYCLE WARNING: Scoring from 'last_drawn' but variable doesn't exist. "
                f"This may indicate a variable lifecycle bug. Available variables: {list(context.variables.keys())}"
            )

        if cards_param and not context.has_variable(cards_param):
            logger.warning(
                f"VARIABLE LIFECYCLE WARNING: Scoring from '{cards_param}' but variable doesn't exist. "
                f"Available variables: {list(context.variables.keys())}"
            )

        if cards_param and context.has_variable(cards_param):
            # Use cards variable (primary approach)
            cards_var = context.get_variable(cards_param)
            if isinstance(cards_var, list):
                source_cards = cards_var
            elif cards_var:
                source_cards = [cards_var]
            else:
                source_cards = []
        elif selection and context.has_variable(selection):
            # Use selection variable (fallback)
            cards_var = context.get_variable(selection)
            if isinstance(cards_var, list):
                source_cards = cards_var
            elif cards_var:
                source_cards = [cards_var]
            else:
                source_cards = []
        elif selection:
            # CRITICAL FIX: If selection parameter is specified but variable doesn't exist,
            # return SUCCESS without scoring (like MeldCard does). This prevents the fallback
            # to hand which would score ALL cards instead of just the selected one.
            logger.warning(
                f"ScoreCards: selection variable '{selection}' specified but doesn't exist. "
                f"Returning without scoring. Available variables: {list(context.variables.keys())}"
            )
            return ActionResult.SUCCESS
        elif self.source == "hand":
            source_cards = list(context.player.hand)
        elif self.source == "last_drawn":
            # Get from variables
            last_drawn = context.get_variable("last_drawn", [])
            if isinstance(last_drawn, list):
                source_cards = last_drawn
            elif last_drawn:
                source_cards = [last_drawn]
            else:
                source_cards = []
        elif context.has_variable(self.source):
            cards_var = context.get_variable(self.source)
            if isinstance(cards_var, list):
                source_cards = cards_var
            elif cards_var:
                source_cards = [cards_var]
            else:
                source_cards = []
        else:
            source_cards = []

        # RUNTIME ASSERTION: Validate we have cards when we expected to have them
        # This catches cases where source resolution failed silently
        if self.source == "last_drawn" and not source_cards:
            logger.warning(
                "VARIABLE LIFECYCLE WARNING: Expected cards from 'last_drawn' but got empty list. "
                "This may indicate the variable was cleared prematurely or never set."
            )

        # Select cards to score
        if self.selection_type == "all":
            cards_to_score = source_cards
        elif self.selection_type == "highest":
            # Sort by age descending
            sorted_cards = sorted(
                source_cards, key=lambda c: getattr(c, "age", 0), reverse=True
            )
            cards_to_score = sorted_cards[: self.count]
        elif self.selection_type == "lowest":
            # Sort by age ascending
            sorted_cards = sorted(source_cards, key=lambda c: getattr(c, "age", 0))
            cards_to_score = sorted_cards[: self.count]
        else:
            # Take all cards if scoring from a variable (cards, selection, or variable sources like last_drawn)
            # Only limit by count when scoring from player locations (hand)
            if cards_param or selection or self.source not in ["hand"]:
                cards_to_score = source_cards
            else:
                cards_to_score = source_cards[: self.count]

        # Move cards to score pile
        scored_count = 0
        for card in cards_to_score:
            # Remove from hand if present
            if card in context.player.hand:
                context.player.hand.remove(card)
                logger.debug(f"Removed {card.name} from hand for scoring")
            else:
                # Check board stacks - card might be a top card being scored
                for color in ["red", "blue", "green", "yellow", "purple"]:
                    stack = getattr(context.player.board, f"{color}_cards", [])
                    if stack and card in stack:
                        stack.remove(card)
                        logger.debug(f"Removed {card.name} from {color} stack for scoring")
                        break

            # Add to score pile
            if not hasattr(context.player, "score_pile"):
                context.player.score_pile = []
            context.player.score_pile.append(card)

            # Record state change
            context.state_tracker.record_score(
                player_name=context.player.name,
                card_name=card.name,
                context=context.get_variable("current_effect_context", "score"),
            )

            scored_count += 1
            context.add_result(f"Scoreed {card.name} (era {getattr(card, 'age', 0)})")
            logger.info(f"Scored {card.name} to {context.player.name}'s score pile")

            # Activity: card scored
            try:
                if activity_logger:
                    activity_logger.log_dogma_card_action(
                        game_id=getattr(context.game, "game_id", "test-game"),
                        player_id=getattr(context.player, "id", None) or "player",
                        card_name=getattr(context.card, "name", "Card"),
                        action_type="scored",
                        cards=[{"name": getattr(card, "name", str(card))}],
                        location_from=self.source,
                        location_to="score_pile",
                        is_sharing=bool(
                            context.get_variable("is_sharing_phase", False)
                        ),
                    )
            except Exception:
                pass

        context.add_result(f"Scoreed {scored_count} card(s)")

        # NOTE: We do NOT clear last_drawn here because LoopAction needs to check
        # the card's properties after scoring to determine if it should repeat.
        # The next DrawCards action will overwrite last_drawn anyway, so no duplication risk.

        # Track for Monument achievement
        if scored_count > 0 and hasattr(context, "game") and hasattr(context, "player"):
            try:
                from special_achievements import special_achievement_checker

                special_achievement_checker.track_card_action(
                    context.game.game_id, context.player.id, "score", scored_count
                )
            except ImportError:
                # Special achievements not available
                pass

        return ActionResult.SUCCESS
