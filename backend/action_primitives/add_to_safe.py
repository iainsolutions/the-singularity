"""
AddToSafe Action Primitive

Add a card or cards to a player's Safe (as secrets).
Part of the Unseen expansion mechanics.

This primitive takes specified cards and adds them to a player's Safe,
making them hidden secrets. This is the "safeguard a card" action (different
from "safeguard an achievement").
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class AddToSafe(ActionPrimitive):
    """
    Add cards to a player's Safe as secrets.

    Takes cards from a variable (typically cards just drawn, selected, etc.)
    and moves them to the specified player's Safe.

    Parameters:
    - cards: Variable name containing card(s) to add to Safe (default: "drawn_cards")
    - source: Source location to remove cards from ("hand", "board_top", "revealed", etc.)
    - target_player: Which player's Safe ("self", "opponent", "selected_player")
    - count: Number of cards to add (default: all cards in variable)
    - store_result: Variable name to store count of cards added
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.cards_var = config.get("cards", config.get("source", "drawn_cards"))
        self.source = config.get("source")
        self.target_player = config.get("target_player", "self")
        self.count = config.get("count")
        self.store_result = config.get("store_result", "safeguarded_count")

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the add to safe action"""
        logger.debug(
            f"AddToSafe.execute: cards_var={self.cards_var}, "
            f"target_player={self.target_player}"
        )

        # Get target player
        if self.target_player == "opponent":
            target_player = context.target_player or context.get_opponent()
        elif self.target_player == "selected_player":
            selected_id = context.get_variable("selected_player")
            target_player = context.game.get_player_by_id(selected_id) if selected_id else None
        else:
            target_player = context.player

        if not target_player:
            context.add_result("Error: No target player found")
            return ActionResult.FAILURE

        # Ensure player has a Safe
        if not hasattr(target_player, "safe") or not target_player.safe:
            context.add_result(f"{target_player.name} has no Safe (Unseen expansion required)")
            return ActionResult.FAILURE

        # Get cards to add
        cards = context.get_variable(self.cards_var, [])
        if not cards:
            logger.debug(f"No cards found in variable '{self.cards_var}'")
            if self.store_result:
                context.set_variable(self.store_result, 0)
            return ActionResult.SUCCESS

        # Ensure it's a list
        if not isinstance(cards, list):
            cards = [cards]

        # Limit count if specified
        if self.count is not None:
            cards = cards[:self.count]

        # Add each card to Safe
        added_count = 0
        for card in cards:
            if not card:
                continue

            # Remove from source location if specified
            if self.source:
                self._remove_from_source(context, card, target_player)

            # Add to Safe
            target_player.safe.add_secret(card)
            added_count += 1

            activity_logger.info(
                f"🔒 {target_player.name} safeguarded {card.name} (age {card.age}) to Safe"
            )

        # Store result
        if self.store_result:
            context.set_variable(self.store_result, added_count)

        if added_count > 0:
            context.add_result(
                f"{target_player.name} added {added_count} card(s) to Safe"
            )

        return ActionResult.SUCCESS

    def _remove_from_source(self, context: ActionContext, card, target_player):
        """Remove card from source location before adding to Safe"""
        if self.source == "hand":
            if card in target_player.hand:
                target_player.hand.remove(card)
        elif self.source == "board_top":
            # Remove from top of board stack (color determined by card)
            if hasattr(target_player, "board") and hasattr(target_player.board, "remove_card"):
                target_player.board.remove_card(card)
        elif self.source == "revealed":
            # Remove from revealed cards
            revealed = context.get_variable("revealed_cards", [])
            if card in revealed:
                revealed.remove(card)
                context.set_variable("revealed_cards", revealed)
        elif self.source == "score_pile":
            if hasattr(target_player, "score_pile") and card in target_player.score_pile:
                target_player.score_pile.remove(card)
        # Add more source types as needed

    def get_required_fields(self) -> list[str]:
        """No required fields - cards_var defaults to 'drawn_cards'"""
        return []

    def get_optional_fields(self) -> list[str]:
        return ["cards", "source", "target_player", "count", "store_result"]
