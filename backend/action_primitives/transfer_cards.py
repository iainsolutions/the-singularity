"""
TransferCards Action Primitive

Transfers cards between different locations.
"""

import logging
from typing import Any

from utils.card_utils import get_card_name

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class TransferCards(ActionPrimitive):
    """
    Primitive for moving cards between locations.

    Parameters:
    - cards: Variable name containing cards to transfer (default: "selected_cards")
    - target: Destination ("hand", "board", "score_pile", "age_deck", "discard")
    - from_location: Source location for the cards (optional, for direct transfers)
    - store_count: Variable name to store number of cards transferred
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.cards_var = config.get("cards", config.get("source", "selected_cards"))
        self.target = config.get("target", "hand")
        self.from_location = config.get("from_location")
        self.store_count = config.get("store_count")

        # Handle special selection types
        self.selection = config.get("selection")

    def execute(self, context: ActionContext) -> ActionResult:
        """Transfer cards to the target location"""
        logger.info(
            f"=== TransferCards.execute() called: cards_var={self.cards_var}, target={self.target}, from_location={self.from_location}"
        )

        # Get cards to transfer
        if self.selection == "last_drawn":
            # Special case for last drawn cards
            cards_to_transfer = context.get_variable("last_drawn", [])
        elif self.cards_var == "dogma_card":
            # Special case: reference to the card that activated this dogma
            # Use context.card which is the card object itself
            logger.info(f"=== TransferCards: dogma_card requested, context.card = {context.card}")
            if hasattr(context, 'card') and context.card:
                logger.info(f"=== TransferCards: Found context.card: {context.card.name}")
            else:
                logger.warning(f"=== TransferCards: context.card is None or missing!")
            cards_to_transfer = [context.card] if context.card else []
        else:
            cards_to_transfer = context.get_variable(self.cards_var, [])

        logger.info(
            f"=== TransferCards: cards_to_transfer={cards_to_transfer}, type={type(cards_to_transfer)}"
        )

        if not cards_to_transfer:
            logger.info(
                "=== TransferCards: cards_to_transfer is empty, returning SUCCESS"
            )
            if self.store_count:
                context.set_variable(self.store_count, 0)
            return ActionResult.SUCCESS

        # Ensure it's a list
        if not isinstance(cards_to_transfer, list):
            logger.info("=== TransferCards: Converting single card to list")
            cards_to_transfer = [cards_to_transfer]

        logger.info(
            f"=== TransferCards: About to transfer {len(cards_to_transfer)} card(s)"
        )

        # Perform transfers
        transferred_count = 0
        for i, card in enumerate(cards_to_transfer):
            logger.info(
                f"=== TransferCards: Processing card {i+1}/{len(cards_to_transfer)}: {card}"
            )
            logger.info(f"=== TransferCards: Card has age={getattr(card, 'age', 'MISSING')}, card_id={getattr(card, 'card_id', 'MISSING')}")
            success = self._transfer_card(context, card)
            logger.info(f"=== TransferCards: _transfer_card returned {success}")
            if success:
                # Record state change
                from_loc = self.from_location or "unknown"
                context.state_tracker.record_transfer(
                    card_name=card.name,
                    from_player=context.player.name,
                    to_player=context.player.name,
                    from_location=from_loc,
                    to_location=self.target,
                    context=context.get_variable("current_effect_context", "transfer"),
                )
                transferred_count += 1
            else:
                logger.warning(f"=== TransferCards: Failed to transfer card {card.name} (age={getattr(card, 'age', '?')}, id={getattr(card, 'card_id', '?')})")

        # Store result count
        if self.store_count:
            context.set_variable(self.store_count, transferred_count)

        # Set a flag to indicate cards were transferred (for compliance detection)
        if transferred_count > 0:
            actually_transferred = cards_to_transfer[:transferred_count]
            context.set_variable("transferred_cards", actually_transferred)
            context.add_result(
                f"Transferred {transferred_count} cards to {self.target}"
            )

            # Add detailed logging
            if self.target == "score_pile":
                # Cards going to score pile are public
                card_names = [
                    context.get_public_card_name(card)
                    for card in cards_to_transfer[:transferred_count]
                ]
                context.add_result(f"Scored: {', '.join(card_names)}")

        return ActionResult.SUCCESS

    def _transfer_card(self, context: ActionContext, card) -> bool:
        """
        Transfer a single card to the target location.

        Returns:
            True if card was successfully transferred
        """
        logger.info(
            f"=== _transfer_card: card={card}, target={self.target}, from_location={self.from_location}"
        )
        if not card:
            logger.info("=== _transfer_card: No card provided, returning False")
            return False

        # Remove from current location if specified
        if self.from_location:
            logger.info(
                f"=== _transfer_card: Attempting to remove from location: {self.from_location}"
            )
            if not self._remove_from_location(context, card, self.from_location):
                return False
        else:
            # Try to find and remove from common locations
            self._remove_card_from_any_location(context, card)

        # Add to target location
        if self.target == "hand":
            # When transferring to hand from reveal, card becomes private
            # unless the effect specifically keeps it revealed
            if self.from_location == "reveal" and hasattr(card, "is_revealed"):
                card.is_revealed = False
            context.player.hand.append(card)
            logger.debug(f"Added {get_card_name(card)} to hand")
            return True
        elif self.target == "score_pile":
            if not hasattr(context.player, "score_pile"):
                context.player.score_pile = []
            context.player.score_pile.append(card)
            logger.debug(f"Added {get_card_name(card)} to score pile")
            return True
        elif self.target == "board":
            # For board, add_card() determines color automatically
            if hasattr(context.player, "board") and hasattr(
                context.player.board, "add_card"
            ):
                context.player.board.add_card(card)
                logger.debug(f"Added {get_card_name(card)} to board")
                return True
            else:
                logger.warning(
                    "Cannot add card to board: missing board or add_card method"
                )
                return False
        elif self.target == "age_deck":
            # Return to age deck (handled elsewhere in game logic)
            logger.debug(f"Returned {get_card_name(card)} to age deck")
            return True
        elif self.target == "discard":
            # Discard pile (may need to be implemented)
            logger.debug(f"Discarded {get_card_name(card)}")
            return True
        elif self.target == "junk" or self.target == "junk_pile":
            # Transfer to junk pile
            if not hasattr(context.game.deck_manager, "junk_pile"):
                context.game.deck_manager.junk_pile = []
            context.game.deck_manager.junk_pile.append(card)
            logger.debug(f"Added {get_card_name(card)} to junk pile")
            return True
        else:
            logger.warning(f"Unknown target location: {self.target}")
            return False

    def _remove_from_location(
        self, context: ActionContext, card, location: str
    ) -> bool:
        """Remove card from specified location"""
        logger.info(f"=== _remove_from_location: location={location}, card={card}")
        logger.info(f"=== _remove_from_location: location type={type(location)}, repr={repr(location)}")
        if location == "hand":
            if card in context.player.hand:
                context.player.hand.remove(card)
                return True
        elif location == "score_pile":
            if (
                hasattr(context.player, "score_pile")
                and card in context.player.score_pile
            ):
                context.player.score_pile.remove(card)
                return True
        elif location == "achievements":
            logger.info("=== _remove_from_location: ACHIEVEMENTS branch entered")
            # CRITICAL FIX: Check BOTH player.achievements (already achieved)
            # AND game.available_achievements (being junked from sharing effects like Archery)
            # Achievements can be junked from either location depending on the effect
            removed = False

            # CRITICAL FIX: Use card_id matching instead of object identity (`in` operator)
            # After Redis reload, card objects become stale - they're different Python objects
            # even though they represent the same card. We must match by card_id!
            card_id = getattr(card, "card_id", None) or getattr(card, "name", None)
            logger.info(f"=== _remove_from_location: Looking for card_id={card_id}")

            # Try player's achievements first (for already-achieved achievements)
            try:
                logger.info(
                    "=== _remove_from_location: Checking player.achievements..."
                )
                if hasattr(context.player, "achievements"):
                    logger.info(
                        f"=== _remove_from_location: player has achievements attribute, count={len(context.player.achievements)}"
                    )
                    for ach in list(context.player.achievements):
                        ach_id = getattr(ach, "card_id", None) or getattr(
                            ach, "name", None
                        )
                        if ach_id and ach_id == card_id:
                            context.player.achievements.remove(ach)
                            removed = True
                            logger.debug(
                                f"Removed {get_card_name(card)} from player.achievements (matched by card_id={card_id})"
                            )
                            break
                else:
                    logger.info(
                        "=== _remove_from_location: player does NOT have achievements attribute"
                    )

                # Try game's achievement_cards (for achievements being junked during selection)
                if not removed and hasattr(context.game.deck_manager, "achievement_cards"):
                    logger.info(
                        "=== _remove_from_location: Checking game.deck_manager.achievement_cards"
                    )
                    # achievement_cards is a dict: {age: [achievement_card_objects]}
                    for age, achievements in context.game.deck_manager.achievement_cards.items():
                        for ach in list(achievements):
                            ach_id = getattr(ach, "card_id", None) or getattr(
                                ach, "name", None
                            )
                            logger.info(
                                f"=== _remove_from_location: Comparing ach_id={ach_id} with card_id={card_id}"
                            )
                            if ach_id and ach_id == card_id:
                                achievements.remove(ach)
                                removed = True
                                logger.debug(
                                    f"Removed {get_card_name(card)} from game.achievement_cards[{age}] (matched by card_id={card_id})"
                                )
                                break
                        if removed:
                            break
                else:
                    logger.info(
                        "=== _remove_from_location: Either already removed or game has no achievement_cards"
                    )

                logger.info(f"=== _remove_from_location: Returning removed={removed}")
                return removed
            except Exception as e:
                logger.error(
                    f"=== _remove_from_location: EXCEPTION: {type(e).__name__}: {e}",
                    exc_info=True,
                )
                return False
        elif location == "board":
            # CRITICAL FIX: Use manual removal with card_id matching
            # The board.remove_card() method may fail silently due to object identity issues
            # After Redis reload or context.card usage, objects may differ
            card_id = getattr(card, "card_id", None) or getattr(card, "name", None)
            logger.info(f"=== _remove_from_location: BOARD removal, looking for card_id={card_id}")
            
            for color in ["red", "yellow", "green", "blue", "purple"]:
                stack = getattr(context.player.board, f"{color}_cards", [])
                # Try object identity first (fast path)
                if card in stack:
                    stack.remove(card)
                    logger.debug(f"Removed {get_card_name(card)} from board {color} stack (by identity)")
                    return True
                # Fall back to card_id matching
                if card_id:
                    for i, stack_card in enumerate(stack):
                        stack_card_id = getattr(stack_card, "card_id", None) or getattr(stack_card, "name", None)
                        logger.info(f"=== _remove_from_location: Comparing board card {i} card_id={stack_card_id} with target={card_id}")
                        if stack_card_id and stack_card_id == card_id:
                            stack.pop(i)
                            logger.debug(f"Removed {get_card_name(card)} from board {color} stack (by card_id={card_id})")
                            return True
            
            logger.warning(f"Could not remove {get_card_name(card)} from board - not found in any color stack")
            return False
        elif location == "reveal":
            # Cards in reveal location are just in last_drawn variable
            # No need to remove, just transfer the card
            return True
        elif location == "junk" or location == "junk_pile":
            # Remove from junk pile
            if hasattr(context.game, "junk_pile") and card in context.game.junk_pile:
                context.game.junk_pile.remove(card)
                return True
        elif location == "deck":
            # Remove from age deck
            logger.info(f"=== _remove_from_location: DECK branch entered for card={card}")
            logger.info(f"=== DECK DEBUG: Card object id={id(card)}, card_id={getattr(card, 'card_id', 'MISSING')}, name={getattr(card, 'name', 'MISSING')}")
            # CRITICAL FIX: Use card_id matching instead of object identity
            # After FilterCards gets cards, they might be different Python objects
            # even though they represent the same card. Match by card_id!
            if hasattr(context.game.deck_manager, "age_decks") and hasattr(card, "age"):
                age_key = card.age
                # Support both int and string keys (in case of Redis serialization inconsistency)
                if age_key in context.game.deck_manager.age_decks:
                    age_deck = context.game.deck_manager.age_decks[age_key]
                elif str(age_key) in context.game.deck_manager.age_decks:
                    age_key = str(age_key)
                    age_deck = context.game.deck_manager.age_decks[age_key]
                else:
                    logger.warning(f"Could not find age {age_key} (or '{age_key}') in age_decks keys: {list(context.game.deck_manager.age_decks.keys())}")
                    return False

                card_id = getattr(card, "card_id", None) or getattr(card, "name", None)

                logger.info(f"=== DECK DEBUG: Looking for card_id={card_id} in age {age_key} deck with {len(age_deck)} cards")
                logger.info(f"=== DECK DEBUG: Deck is same object as age_decks[{age_key}]? {age_deck is context.game.deck_manager.age_decks[age_key]}")
                logger.info(f"=== DECK DEBUG: First 3 deck card ids: {[id(c) for c in age_deck[:3]]}")
                logger.info(f"=== DECK DEBUG: First 3 deck card_ids: {[(getattr(c, 'card_id', None), getattr(c, 'name', None)) for c in age_deck[:3]]}")

                # Try object identity first (fast path)
                logger.info(f"=== DECK DEBUG: Checking if card {id(card)} in deck...")
                if card in age_deck:
                    logger.info(f"=== DECK DEBUG: Found by identity! Removing...")
                    age_deck.remove(card)
                    logger.info(f"=== DECK DEBUG: Removed. New deck length: {len(age_deck)}")
                    logger.debug(f"Removed {get_card_name(card)} from age {age_key} deck (by identity)")
                    return True
                else:
                    logger.info(f"=== DECK DEBUG: NOT found by identity, trying card_id matching...")

                # Fall back to card_id matching
                if card_id:
                    for i, deck_card in enumerate(age_deck):
                        deck_card_id = getattr(deck_card, "card_id", None) or getattr(deck_card, "name", None)
                        logger.info(f"=== DECK DEBUG: Comparing deck_card[{i}] id={id(deck_card)} card_id={deck_card_id} with target card_id={card_id}")
                        if deck_card_id and deck_card_id == card_id:
                            logger.info(f"=== DECK DEBUG: MATCH! Removing index {i}...")
                            age_deck.pop(i)
                            logger.info(f"=== DECK DEBUG: Removed. New deck length: {len(age_deck)}")
                            logger.debug(f"Removed {get_card_name(card)} from age {age_key} deck (by card_id={card_id})")
                            return True

            logger.warning(f"Could not remove {get_card_name(card)} from deck - not found in age {getattr(card, 'age', '?')} deck")
            return False
        return False

    def _remove_card_from_any_location(self, context: ActionContext, card):
        """Try to remove card from any common location"""
        # Try hand first
        if card in context.player.hand:
            context.player.hand.remove(card)
            return

        # Try score pile
        if hasattr(context.player, "score_pile") and card in context.player.score_pile:
            context.player.score_pile.remove(card)
            return

        # Try board
        if hasattr(context.player, "board"):
            if hasattr(context.player.board, "remove_card"):
                try:
                    context.player.board.remove_card(card)
                    return
                except (ValueError, AttributeError):
                    pass
            # Fallback to manual removal
            for color in ["red", "yellow", "green", "blue", "purple"]:
                stack = getattr(context.player.board, f"{color}_cards", [])
                if card in stack:
                    stack.remove(card)
                    return
