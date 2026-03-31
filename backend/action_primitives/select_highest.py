"""SelectHighest Action Primitive.

Selects the highest value cards from a source.
"""

import logging
from typing import Any

from interaction.builder import StandardInteractionBuilder
from logging_config import EventType, activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult
from .utils import CardSourceResolver, attach_player_to_interaction

logger = logging.getLogger(__name__)


class SelectHighest(ActionPrimitive):
    """Primitive for selecting the highest value cards from a source.

    Parameters:
    - source: Where to select from ("hand", "score_pile", etc.)
    - count: Number of highest cards to select (default: 1)
    - criteria: What makes a card "highest" ("age", "score_value")
    - store_result: Variable name to store selected cards
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.source = config.get("source", "hand")
        self.count = config.get("count", 1)
        self.criteria = config.get("criteria", "age")
        # Support both 'store_result' and legacy 'store_as' field from card JSON
        self.store_result = config.get(
            "store_result", config.get("store_as", "selected_cards")
        )
        # Skip tie-breaking interaction when selection is only for reading a value
        # (e.g., Machine Tools just needs the highest age, doesn't matter which card)
        self.skip_tie_break = config.get("skip_tie_break", False)

    def execute(self, context: ActionContext) -> ActionResult:
        """Select the highest value cards."""
        # If a selection was already made during a prior interaction (e.g., tie-breaking),
        # reuse it. The interaction response is stored in self.store_result by
        # _apply_interaction_response via the pending_store_result mechanism.
        if context.has_variable(self.store_result):
            existing = context.get_variable(self.store_result, [])
            if existing is not None:  # allow empty list as valid
                # Check if we need to merge with auto-selected cards from tie-breaking
                auto_selected_key = f"{self.store_result}_auto_selected"
                if context.has_variable(auto_selected_key):
                    auto_selected = context.get_variable(auto_selected_key, [])
                    # Merge: auto-selected + player's choice
                    merged = auto_selected + (existing if isinstance(existing, list) else [existing])
                    context.set_variable(self.store_result, merged)
                    context.remove_variable(auto_selected_key)  # Clean up temp variable
                    logger.debug(
                        f"SelectHighest MERGE: Merged {len(auto_selected)} auto-selected + {len(existing) if isinstance(existing, list) else 1} player-selected = {len(merged)} total"
                    )
                    logger.debug(f"  Auto-selected: {[getattr(c, 'name', str(c)) for c in auto_selected]}")
                    logger.debug(f"  Player-selected: {[getattr(c, 'name', str(c)) for c in (existing if isinstance(existing, list) else [existing])]}")
                    logger.debug(f"  Merged result: {[getattr(c, 'name', str(c)) for c in merged]}")
                    context.add_result(
                        f"Selected {len(merged)} highest card(s) (auto + player choice)"
                    )
                else:
                    logger.debug(f"SelectHighest REUSE: Using previously selected {len(existing) if isinstance(existing, list) else 1} card(s)")
                    logger.debug(f"  Cards: {[getattr(c, 'name', str(c)) for c in (existing if isinstance(existing, list) else [existing])]}")
                    context.add_result(
                        f"Using previously selected {len(existing) if isinstance(existing, list) else 1} card(s)"
                    )
                # CRITICAL FIX: Clear the final_interaction_request to prevent re-suspension loop
                # This prevents InteractionEffectAdapter's defensive code from forcing interaction
                if context.has_variable("final_interaction_request"):
                    context.remove_variable("final_interaction_request")
                    logger.debug(
                        "SelectHighest: Cleared final_interaction_request to prevent re-suspension"
                    )
                return ActionResult.SUCCESS

        # Get source cards
        source_cards = CardSourceResolver.get_cards(context, self.source)

        if not source_cards:
            context.set_variable(self.store_result, [])
            context.add_result(f"No cards available in {self.source}")
            return ActionResult.SUCCESS

        # Sort cards by criteria (highest first)
        sorted_cards = self._sort_by_criteria(source_cards, descending=True)

        # Handle "all" count as "all cards tied for the highest value", not all cards
        if self.count == "all":
            if not sorted_cards:
                context.set_variable(self.store_result, [])
                context.add_result(f"No cards available in {self.source}")
                return ActionResult.SUCCESS
            highest_value = self._get_card_value(sorted_cards[0])
            selected = [
                c for c in sorted_cards if self._get_card_value(c) == highest_value
            ]
            context.set_variable(self.store_result, selected)
            # Compose explicit names for Action Log visibility
            names = ", ".join([getattr(c, "name", str(c)) for c in selected])
            context.add_result(
                f"Selected {len(selected)} highest card(s) by {self.criteria}: {names}"
            )
            # Activity: record selection
            try:
                if activity_logger and selected:
                    card_names = [getattr(c, "name", str(c)) for c in selected]
                    activity_logger.log_dogma_card_selection(
                        game_id=getattr(context.game, "game_id", ""),
                        player_id=getattr(context.player, "id", ""),
                        card_name=getattr(context.card, "name", "Effect"),
                        selection_type="select_highest_all",
                        selected_cards=[{"name": n} for n in card_names],
                        selection_criteria=self.criteria,
                    )
            except Exception:
                pass
            logger.debug(
                f"Selected all cards tied for highest {self.criteria} ({highest_value}); total {len(selected)}"
            )
            return ActionResult.SUCCESS
        else:
            count = self.count

        # Check for ties when selecting highest
        if count == 1 and len(sorted_cards) > 1:
            # Get the highest value
            highest_value = self._get_card_value(sorted_cards[0])

            # Find all cards with the highest value (potential ties)
            tied_cards = [
                c for c in sorted_cards if self._get_card_value(c) == highest_value
            ]

            if len(tied_cards) > 1:
                # There's a tie with multiple cards
                logger.info(
                    f"Multiple cards tied with highest {self.criteria}: {highest_value}"
                )

                # If skip_tie_break is set, auto-select the first tied card without interaction
                # This is used when the selection is only for reading a value (e.g., GetCardAge)
                if self.skip_tie_break:
                    selected = [tied_cards[0]]
                    context.set_variable(self.store_result, selected)
                    context.add_result(
                        f"Auto-selected {selected[0].name} (tied for highest {self.criteria} {highest_value})"
                    )
                    logger.debug(
                        f"SelectHighest: skip_tie_break=True, auto-selected first tied card: {selected[0].name}"
                    )
                    return ActionResult.SUCCESS

                # Create interaction request for tie-breaking selection
                selection_message = f"Choose which card to select (multiple cards with age {highest_value})"
                interaction_request = StandardInteractionBuilder.create_card_selection_request(
                    eligible_cards=tied_cards,
                    min_count=1,  # Must select exactly one card
                    max_count=1,  # Can only select one card
                    message=selection_message,
                    is_optional=False,  # Selection is required to resolve tie
                    source=self.source,  # Source location of the tied cards
                    execution_results=list(context.results)
                    if context.results
                    else None,
                    context=context,  # PHASE 1A: Pass context for eligibility metadata
                )

                # Use the player from context - phase layer has already set the correct player
                target_player_id = getattr(context.player, "id", None)
                logger.debug(f"SelectHighest: Targeting player {context.player.name}")

                interaction_request = attach_player_to_interaction(
                    interaction_request,
                    target_player_id,
                    getattr(context.game, "game_id", None),
                )

                # Store store_result so _apply_interaction_response knows where to put the response
                context.set_variable("pending_store_result", self.store_result)
                context.set_variable("final_interaction_request", interaction_request)

                # Activity log: tie-break required
                try:
                    if activity_logger:
                        game_id = getattr(context.game, "game_id", None)
                        player_id = getattr(context.player, "id", None)
                        card_name = getattr(context.card, "name", None)
                        activity_logger.log_game_event(
                            event_type=EventType.DOGMA_CARD_SELECTION,
                            game_id=str(game_id) if game_id else "test-game",
                            player_id=str(player_id) if player_id else None,
                            data={
                                "card_name": card_name,
                                "message": selection_message,
                                "tie_count": len(tied_cards),
                                "criteria": self.criteria,
                                "source": self.source,
                            },
                            message=selection_message,
                        )
                except Exception:
                    pass

                # Return REQUIRES_INTERACTION to trigger player selection
                context.add_result(
                    f"Multiple cards with {self.criteria} {highest_value} - awaiting choice"
                )
                logger.debug(
                    f"INTERACTION PATH: Returning REQUIRES_INTERACTION for tie-breaking ({len(tied_cards)} tied cards)"
                )
                return ActionResult.REQUIRES_INTERACTION
            else:
                # No tie, just one highest card
                selected = [tied_cards[0]]
        else:
            # Select the top N cards (for explicit numeric count > 1)
            # Check if the Nth card has ties with remaining cards
            if count >= len(sorted_cards):
                # Selecting all cards, no tie issue
                selected = sorted_cards[:count]
            else:
                # Check if Nth card is tied with (N+1)th card
                # Only need interaction if we're excluding a tied card
                nth_card_value = self._get_card_value(sorted_cards[count - 1])
                next_card_value = self._get_card_value(sorted_cards[count]) if count < len(sorted_cards) else None

                # Tie exists only if the card at position count has same value as card at position count-1
                if next_card_value is not None and next_card_value == nth_card_value:
                    # Find all cards with the same value as the Nth card
                    tied_cards = [
                        c for c in sorted_cards if self._get_card_value(c) == nth_card_value
                    ]

                    # There's a tie - need player interaction to choose which cards to include
                    logger.info(
                        f"Tie detected at position {count}: {len(tied_cards)} cards with {self.criteria} {nth_card_value}"
                    )

                    # FIXED: Only show tied cards for selection, auto-select non-tied cards
                    # Example: selecting 2 from [age 4, age 3, age 3, age 1]
                    # - age 4 is NOT tied → auto-select (1 card)
                    # - age 3 cards ARE tied → ask player to choose 1 from [age 3, age 3]
                    # Result: player chooses 1 from 2 tied cards, gets paired with auto-selected age 4

                    # Find first tied card position
                    first_tied_index = sorted_cards.index(tied_cards[0])

                    # Auto-select all cards before the tie
                    auto_selected = sorted_cards[:first_tied_index]

                    # Calculate how many more needed from tied cards
                    remaining_count = count - len(auto_selected)

                    # Show ONLY tied cards, ask for remaining count
                    eligible_for_selection = tied_cards

                    # CRITICAL: Store auto-selected cards so we can merge with player's choice later
                    context.set_variable(f"{self.store_result}_auto_selected", auto_selected)

                    # DEBUG: Log tie-breaking details
                    logger.debug(f"SelectHighest TIE-BREAKING:")
                    logger.debug(f"  Sorted cards: {[getattr(c, 'name', str(c)) for c in sorted_cards]}")
                    logger.debug(f"  Tied cards: {[getattr(c, 'name', str(c)) for c in tied_cards]}")
                    logger.debug(f"  Auto-selected: {[getattr(c, 'name', str(c)) for c in auto_selected]}")
                    logger.debug(f"  Eligible for selection: {[getattr(c, 'name', str(c)) for c in eligible_for_selection]}")
                    logger.debug(f"  Remaining count: {remaining_count}")

                    # Create interaction request for tie-breaking selection
                    selection_message = f"Choose {remaining_count} card(s) from {len(tied_cards)} tied with age {nth_card_value}"
                    interaction_request = StandardInteractionBuilder.create_card_selection_request(
                        eligible_cards=eligible_for_selection,
                        min_count=remaining_count,
                        max_count=remaining_count,
                        message=selection_message,
                        is_optional=False,
                        source=self.source,
                        execution_results=list(context.results) if context.results else None,
                        context=context,
                    )

                    target_player_id = getattr(context.player, "id", None)
                    logger.debug(f"SelectHighest: Targeting player {context.player.name}")

                    interaction_request = attach_player_to_interaction(
                        interaction_request,
                        target_player_id,
                        getattr(context.game, "game_id", None),
                    )

                    # Store store_result so _apply_interaction_response knows where to put the response
                    context.set_variable("pending_store_result", self.store_result)
                    context.set_variable("final_interaction_request", interaction_request)

                    # Activity log
                    try:
                        if activity_logger:
                            game_id = getattr(context.game, "game_id", None)
                            player_id = getattr(context.player, "id", None)
                            card_name = getattr(context.card, "name", None)
                            activity_logger.log_game_event(
                                event_type=EventType.DOGMA_CARD_SELECTION,
                                game_id=str(game_id) if game_id else "test-game",
                                player_id=str(player_id) if player_id else None,
                                data={
                                    "card_name": card_name,
                                    "message": selection_message,
                                    "tie_count": len(tied_cards),
                                    "count": count,
                                    "criteria": self.criteria,
                                    "source": self.source,
                                },
                                message=selection_message,
                            )
                    except Exception:
                        pass

                    context.add_result(
                        f"Multiple cards tied at position {count} ({self.criteria} {nth_card_value}) - awaiting choice"
                    )
                    return ActionResult.REQUIRES_INTERACTION
                else:
                    # No tie - card at position count has different value than card at count-1
                    # Just select the first count cards
                    selected = sorted_cards[:count]

        # If manual confirmation is forced, create an interaction even for a single candidate
        try:
            force_manual = bool(context.get_variable("force_manual_selection"))
        except Exception:
            force_manual = False

        if force_manual and len(selected) == 1:
            interaction_request = StandardInteractionBuilder.create_card_selection_request(
                eligible_cards=selected,
                min_count=1,
                max_count=1,
                message=f"Choose which card to transfer (confirm highest {self.criteria})",
                is_optional=False,
                source=self.source,
                execution_results=list(context.results) if context.results else None,
                context=context,  # PHASE 1A: Pass context for eligibility metadata
            )

            # Use the player from context - phase layer has already set the correct player
            target_player_id = getattr(context.player, "id", None)
            logger.debug(f"SelectHighest: Targeting player {context.player.name}")

            interaction_request = attach_player_to_interaction(
                interaction_request,
                target_player_id,
                getattr(context.game, "game_id", None),
            )
            # Store store_result so _apply_interaction_response knows where to put the response
            context.set_variable("pending_store_result", self.store_result)
            context.set_variable("final_interaction_request", interaction_request)
            context.add_result("Awaiting confirmation of highest card selection")
            return ActionResult.REQUIRES_INTERACTION

        # Store result
        context.set_variable(self.store_result, selected)

        if selected:
            if self.criteria == "age":
                ages = [getattr(c, "age", 0) for c in selected]
                names = ", ".join([getattr(c, "name", str(c)) for c in selected])
                context.add_result(
                    f"Selected {len(selected)} highest age card(s): age {max(ages)} — {names}"
                )
                # Activity: record selection (non-tie path)
                try:
                    if activity_logger and selected:
                        card_names = [getattr(c, "name", str(c)) for c in selected]
                        activity_logger.log_dogma_card_selection(
                            game_id=getattr(context.game, "game_id", ""),
                            player_id=getattr(context.player, "id", ""),
                            card_name=getattr(context.card, "name", "Effect"),
                            selection_type="select_highest",
                            selected_cards=[{"name": n} for n in card_names],
                            selection_criteria=self.criteria,
                        )
                except Exception:
                    pass
            else:
                context.add_result(
                    f"Selected {len(selected)} highest card(s) by {self.criteria}"
                )
        else:
            context.add_result("No cards selected")

        logger.debug(
            f"Selected {len(selected)} highest cards from {len(source_cards)} by {self.criteria}"
        )

        return ActionResult.SUCCESS

    def _get_card_value(self, card) -> int:
        """Get the value of a card based on the current criteria."""
        if self.criteria == "age" or self.criteria == "score_value":
            return getattr(card, "age", 0)
        elif self.criteria == "symbols":
            return self._count_card_symbols(card)
        else:
            return getattr(card, "age", 0)

    def _sort_by_criteria(self, cards: list, descending: bool = True) -> list:
        """Sort cards by the specified criteria."""
        if not cards:
            return []

        if self.criteria == "age":
            # Sort by age
            return sorted(cards, key=lambda c: getattr(c, "age", 0), reverse=descending)
        elif self.criteria == "score_value":
            # Score value is usually the age for The Singularity
            return sorted(cards, key=lambda c: getattr(c, "age", 0), reverse=descending)
        elif self.criteria == "symbols":
            # Sort by total symbol count
            return sorted(
                cards, key=lambda c: self._count_card_symbols(c), reverse=descending
            )
        else:
            # Default to age
            return sorted(cards, key=lambda c: getattr(c, "age", 0), reverse=descending)

    def _count_card_symbols(self, card) -> int:
        """Count total symbols on a card."""
        if not card:
            return 0

        count = 0
        # Check all symbol positions
        for attr in ["top_left", "top_center", "top_right", "bottom"]:
            if hasattr(card, attr) and getattr(card, attr):
                count += 1

        return count
