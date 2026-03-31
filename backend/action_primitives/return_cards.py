"""
ReturnCards Action Primitive

Returns cards from hand to the appropriate age deck.
"""

from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult


class ReturnCards(ActionPrimitive):
    """
    Returns cards from a player's hand to the age decks.

    Parameters:
    - source: Variable containing the cards to return, or 'hand' for all cards
    - store_count: Variable name to store the count of returned cards
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        # Support both 'selection' (variable name) and 'source' ('hand', etc.)
        self.selection_var = config.get("selection")
        self.source = config.get("source", "hand")
        self.store_count = config.get("store_count", "returned_count")

    def execute(self, context: ActionContext) -> ActionResult:
        """Return cards to the age decks

        CRITICAL FIX: Enhanced validation and logging to fix Tools card bug
        where cards were reported as returned but remained in hand.
        """
        from logging_config import get_logger

        logger = get_logger(__name__)

        # Get cards to return
        cards_to_return = []

        # Prefer explicit selection variable when provided (e.g., FilterCards -> store_as)
        if self.selection_var and context.has_variable(self.selection_var):
            cards_var = context.get_variable(self.selection_var)
            if isinstance(cards_var, list):
                cards_to_return = cards_var
            elif cards_var:
                cards_to_return = [cards_var]
            logger.debug(
                f"ReturnCards: Using selection '{self.selection_var}' with {len(cards_to_return)} cards"
            )

        # Fallback to returning from a source location
        elif self.source == "hand":
            cards_to_return = list(context.player.hand)
            logger.debug(
                f"ReturnCards: Returning all {len(cards_to_return)} cards from hand"
            )
        elif context.has_variable(self.source):
            cards_var = context.get_variable(self.source)
            if isinstance(cards_var, list):
                cards_to_return = cards_var
            elif cards_var:
                cards_to_return = [cards_var]
            else:
                cards_to_return = []

            logger.debug(
                f"ReturnCards: Found {len(cards_to_return)} cards in variable '{self.source}': {[c.name for c in cards_to_return]}"
            )
        else:
            cards_to_return = []
            logger.debug(
                f"ReturnCards: No cards found - variable '{self.source}' not present"
            )

        # Defensive: resolve identifiers/dicts into actual Card objects if needed
        try:
            from models.card import Card  # Local import to avoid circulars
        except Exception:
            Card = None  # type: ignore

        resolved_cards: list = []
        for item in cards_to_return:
            # Already a Card instance
            if Card and isinstance(item, Card):
                resolved_cards.append(item)
                continue

            identifier = None
            if isinstance(item, str):
                identifier = item
            elif isinstance(item, dict):
                identifier = item.get("card_id") or item.get("id") or item.get("name")

            if not identifier:
                # Unknown entry; keep as-is to let removal attempt and logging surface details
                resolved_cards.append(item)
                continue

            # Try to find the exact object, prioritizing current player's hand
            found = None
            # Prefer hand
            for c in getattr(context.player, "hand", []) or []:
                cid = getattr(c, "card_id", None)
                if (cid and cid == identifier) or getattr(
                    c, "name", None
                ) == identifier:
                    found = c
                    break
            # Fall back to player's board and score pile
            if not found and hasattr(context.player, "board"):
                for c in context.player.board.get_all_cards():
                    cid = getattr(c, "card_id", None)
                    if (cid and cid == identifier) or getattr(
                        c, "name", None
                    ) == identifier:
                        found = c
                        break
            if not found:
                for c in getattr(context.player, "score_pile", []) or []:
                    cid = getattr(c, "card_id", None)
                    if (cid and cid == identifier) or getattr(
                        c, "name", None
                    ) == identifier:
                        found = c
                        break
            # As a last resort, scan all age decks (in case state drifted)
            if (
                not found
                and hasattr(context.game, "deck_manager")
                and hasattr(context.game.deck_manager, "age_decks")
            ):
                for _age, deck in context.game.deck_manager.age_decks.items():
                    for c in deck:
                        cid = getattr(c, "card_id", None)
                        if (cid and cid == identifier) or getattr(
                            c, "name", None
                        ) == identifier:
                            found = c
                            break
                    if found:
                        break

            resolved_cards.append(found or item)

        cards_to_return = resolved_cards

        if not cards_to_return:
            logger.warning("ReturnCards: No cards to return")
            context.set_variable(self.store_count, 0)
            context.add_result("No cards to return")
            return ActionResult.SUCCESS

        # Log hand state before removal
        hand_before = [
            f"{c.name}(id:{getattr(c, 'card_id', 'none')})" for c in context.player.hand
        ]
        logger.info(f"ReturnCards: Hand before removal: {hand_before}")

        # Return each card with comprehensive validation
        returned_count = 0
        failed_removals = []

        for i, card in enumerate(cards_to_return):
            if not hasattr(card, "age"):
                logger.error(
                    f"ReturnCards: Card {getattr(card, 'name', 'unnamed')} has no age attribute"
                )
                failed_removals.append(
                    f"Card {getattr(card, 'name', 'unnamed')} has no age"
                )
                continue

            logger.debug(
                f"ReturnCards: Processing card {i+1}/{len(cards_to_return)}: {card.name}"
            )

            # Try to remove from player's hand, board, or score_pile
            removal_success = context.player.remove_from_hand(card)
            removal_location = "hand"

            # If not in hand, try board
            if not removal_success and hasattr(context.player, "board"):
                try:
                    removal_success = context.player.board.remove_card(card)
                    removal_location = "board"
                except Exception:
                    pass

            # If not in hand or board, try score_pile
            if not removal_success and hasattr(context.player, "score_pile"):
                try:
                    if card in context.player.score_pile:
                        context.player.score_pile.remove(card)
                        removal_success = True
                        removal_location = "score_pile"
                except Exception:
                    pass

            if removal_success:
                # Add the card back to the appropriate age deck
                context.game.return_card(card, card.age)

                # Record state change
                context.state_tracker.record_return_to_deck(
                    player_name=context.player.name,
                    card_name=card.name,
                    age=card.age,
                    position="bottom",
                    context=context.get_variable("current_effect_context", "return"),
                )

                returned_count += 1
                logger.info(
                    f"ReturnCards: Successfully returned {card.name} from {removal_location} to age {card.age} deck"
                )
                context.add_result(f"Recalled {card.name} to era {card.age} supply")
            else:
                # Not in hand — check if card is in any age deck (deck-return/junk workflows)
                removed_from_deck = False
                deck_age = None
                try:
                    age_decks = (
                        getattr(context.game.deck_manager, "age_decks", {})
                        if hasattr(context.game, "deck_manager")
                        else {}
                    )
                    for age, deck in age_decks.items():
                        if card in deck:
                            deck.remove(card)
                            deck_age = age
                            removed_from_deck = True
                            break
                except Exception:
                    pass

                if removed_from_deck:
                    # By convention for deck-sourced returns in dogma configs, remove from deck and place into junk
                    if (
                        not hasattr(context.game, "junk_pile")
                        or context.game.junk_pile is None
                    ):
                        context.game.junk_pile = []
                    context.game.junk_pile.append(card)
                    returned_count += 1
                    logger.info(
                        f"ReturnCards: Junked {card.name} from age {deck_age} deck"
                    )
                    context.add_result(f"Junked {card.name} from era {deck_age} supply")
                    # Activity log entry for visibility in UI
                    try:
                        from logging_config import EventType, activity_logger

                        activity_logger.log_game_event(
                            event_type=EventType.DOGMA_CARD_REVEALED,  # Use an existing dogma event channel
                            game_id=context.game.game_id,
                            player_id=getattr(context.player, "id", None),
                            data={
                                "action": "junk_from_deck",
                                "card_name": getattr(card, "name", None),
                                "age": int(deck_age) if deck_age is not None else None,
                            },
                            message=f"Junked {getattr(card, 'name', 'card')} from era {deck_age} supply",
                        )
                    except Exception:
                        pass
                    continue

                # CRITICAL ERROR: Card removal failed
                # Attempt robust fallback removal by id or name
                identifier = None
                if isinstance(card, str):
                    identifier = card
                else:
                    identifier = getattr(card, "card_id", None) or getattr(
                        card, "name", None
                    )

                removed_fallback = False
                removed_card_name = getattr(card, "name", str(card))
                if identifier:
                    try:
                        # Try by id first
                        by_id = None
                        if hasattr(
                            context.player, "remove_from_hand_by_id"
                        ) and isinstance(identifier, str):
                            by_id = context.player.remove_from_hand_by_id(identifier)
                        if by_id:
                            removed_fallback = True
                            removed_card_name = getattr(
                                by_id, "name", removed_card_name
                            )
                        else:
                            # Try by name (case-sensitive)
                            if hasattr(
                                context.player, "remove_from_hand_by_name"
                            ) and isinstance(identifier, str):
                                by_name = context.player.remove_from_hand_by_name(
                                    identifier
                                )
                                if by_name:
                                    removed_fallback = True
                                    removed_card_name = getattr(
                                        by_name, "name", removed_card_name
                                    )
                            # Try case-insensitive match if still not found
                            if not removed_fallback and isinstance(identifier, str):
                                for i, c in enumerate(list(context.player.hand)):
                                    if (
                                        getattr(c, "name", "").lower()
                                        == identifier.lower()
                                    ):
                                        context.player.hand.pop(i)
                                        removed_fallback = True
                                        removed_card_name = getattr(
                                            c, "name", removed_card_name
                                        )
                                        break
                    except Exception:
                        pass

                if removed_fallback:
                    # Add back to age deck and record success
                    context.game.return_card(
                        card if hasattr(card, "age") else by_id if by_id else c,
                        getattr(
                            card, "age", getattr(by_id, "age", getattr(c, "age", 1))
                        ),
                    )
                    returned_count += 1
                    logger.info(
                        f"ReturnCards: Fallback removed {removed_card_name} from hand; returned to age deck"
                    )
                    context.add_result(f"Recalled {removed_card_name} to era supply")
                else:
                    logger.error(
                        f"ReturnCards: FAILED to remove {removed_card_name} from hand!"
                    )
                    failed_removals.append(f"{removed_card_name} not found in hand")
                    context.add_result(
                        f"ERROR: Failed to return {removed_card_name} - not found in hand"
                    )

        # Log final hand state for verification
        hand_after = [
            f"{c.name}(id:{getattr(c, 'card_id', 'none')})" for c in context.player.hand
        ]
        logger.info(f"ReturnCards: Hand after removal: {hand_after}")

        # Store count and validate results
        context.set_variable(self.store_count, returned_count)

        # VALIDATION: Report results with error details
        if failed_removals:
            error_details = "; ".join(failed_removals)
            context.add_result(
                f"Partial recall: {returned_count}/{len(cards_to_return)} cards recalled. Errors: {error_details}"
            )
            logger.error(
                f"ReturnCards: Partial failure - {returned_count}/{len(cards_to_return)} returned. Errors: {error_details}"
            )
        elif returned_count > 0:
            context.add_result(f"Successfully recalled {returned_count} card(s)")
            logger.info(
                f"ReturnCards: All {returned_count} cards returned successfully"
            )
        else:
            context.add_result("No cards recalled - all removal attempts failed")
            logger.error("ReturnCards: All card removal attempts failed!")

        return ActionResult.SUCCESS
