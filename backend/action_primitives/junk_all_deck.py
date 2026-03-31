"""
JunkAllDeck Action Primitive

Moves all cards from a specified age deck to the junk pile.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class JunkAllDeck(ActionPrimitive):
    """
    Moves all cards from a specified age deck to the junk pile.

    Parameters:
    - age: The age deck to junk (1-10)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.age = config.get("age")

    def execute(self, context: ActionContext) -> ActionResult:
        """Move all cards from the specified age deck to junk pile"""
        if not self.age:
            context.add_result("Error: No age specified for JunkAllDeck")
            return ActionResult.FAILURE

        # Access junk pile via deck_manager (deck refactor migration)
        deck_manager = context.game.deck_manager
        if not hasattr(deck_manager, "junk_pile") or deck_manager.junk_pile is None:
            deck_manager.junk_pile = []

        # Get the age deck via deck_manager
        age_decks = deck_manager.age_decks
        if self.age not in age_decks:
            context.add_result(f"Era {self.age} supply not found")
            return ActionResult.SUCCESS

        deck = age_decks[self.age]
        if not deck:
            context.add_result(f"Era {self.age} supply is already empty")
            return ActionResult.SUCCESS

        # Move all cards from deck to junk pile
        cards_to_junk = list(deck)  # Create a copy to iterate over
        junked_count = 0

        for card in cards_to_junk:
            # Remove from deck
            if card in deck:
                deck.remove(card)
            # Add to junk pile (via deck_manager)
            deck_manager.junk_pile.append(card)
            junked_count += 1
            logger.info(
                f"JunkAllDeck: Junked {getattr(card, 'name', 'card')} from age {self.age} deck"
            )

        context.add_result(f"Junked all {junked_count} cards from era {self.age} supply")

        # Activity log entry for visibility in UI
        try:
            from logging_config import EventType, activity_logger

            activity_logger.log_game_event(
                event_type=EventType.DOGMA_CARD_REVEALED,  # Use an existing dogma event channel
                game_id=context.game.game_id,
                player_id=getattr(context.player, "id", None),
                data={
                    "action": "junk_all_deck",
                    "age": int(self.age),
                    "count": junked_count,
                },
                message=f"Junked all {junked_count} cards from era {self.age} supply",
            )
        except Exception:
            pass

        return ActionResult.SUCCESS
