"""
SelectLowest Action Primitive

Selects the lowest value cards from a source.
"""

import logging
from typing import Any

from interaction.builder import StandardInteractionBuilder
from logging_config import EventType, activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult
from .utils import CardSourceResolver, attach_player_to_interaction

logger = logging.getLogger(__name__)


class SelectLowest(ActionPrimitive):
    """
    Primitive for selecting the lowest value cards from a source.

    Parameters:
    - source: Where to select from ("hand", "score_pile", "achievements", etc.)
    - count: Number of lowest cards to select (default: 1)
    - criteria: What makes a card "lowest" ("age", "score_value")
    - store_result: Variable name to store selected cards
    - max_age: Maximum age of cards to consider (optional)
    - min_age: Minimum age of cards to consider (optional)
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
        self.max_age = config.get("max_age")
        self.min_age = config.get("min_age")
        # "active" = use activating player (demanding_player) instead of context.player
        self.target_player = config.get("target_player")

    def execute(self, context: ActionContext) -> ActionResult:
        """Select the lowest value cards"""
        # If a selection was already made during a prior interaction (e.g., tie-breaking),
        # reuse it. The interaction response is stored in self.store_result by
        # _apply_interaction_response via the pending_store_result mechanism.
        if context.has_variable(self.store_result):
            existing = context.get_variable(self.store_result, [])
            if existing is not None:  # allow empty list as valid
                context.add_result(
                    f"Using previously selected {len(existing) if isinstance(existing, list) else 1} card(s)"
                )
                # Clear final_interaction_request to prevent re-suspension loop
                if context.has_variable("final_interaction_request"):
                    context.remove_variable("final_interaction_request")
                return ActionResult.SUCCESS

        # Get source cards — optionally from a different player
        if self.target_player == "active" and context.demanding_player:
            # In demand context, get cards from the activating player instead
            original_player = context.player
            context.player = context.demanding_player
            try:
                source_cards = CardSourceResolver.get_cards(context, self.source)
            finally:
                context.player = original_player
        else:
            source_cards = CardSourceResolver.get_cards(context, self.source)

        if not source_cards:
            context.set_variable(self.store_result, [])
            context.add_result(f"No cards available in {self.source}")
            return ActionResult.SUCCESS

        # Apply age filtering if specified
        if self.min_age is not None or self.max_age is not None:
            filtered_cards = []
            for card in source_cards:
                card_age = getattr(card, "age", 0)
                if self.min_age is not None and card_age < self.min_age:
                    continue
                if self.max_age is not None and card_age > self.max_age:
                    continue
                filtered_cards.append(card)

            source_cards = filtered_cards

            # If no cards match the age filter
            if not source_cards:
                context.set_variable(self.store_result, [])
                age_range = ""
                if self.min_age and self.max_age:
                    age_range = f" (age {self.min_age}-{self.max_age})"
                elif self.min_age:
                    age_range = f" (age {self.min_age}+)"
                elif self.max_age:
                    age_range = f" (age up to {self.max_age})"
                context.add_result(f"No cards available in {self.source}{age_range}")
                return ActionResult.SUCCESS

            logger.debug(
                f"Filtered to {len(source_cards)} cards with age constraints (min={self.min_age}, max={self.max_age})"
            )

        # Sort cards by criteria (lowest first)
        sorted_cards = self._sort_by_criteria(source_cards, ascending=True)

        # Handle "all" count as "all cards tied for the lowest value", not all cards
        if self.count == "all":
            if not sorted_cards:
                context.set_variable(self.store_result, [])
                context.add_result(f"No cards available in {self.source}")
                return ActionResult.SUCCESS
            lowest_value = self._get_card_value(sorted_cards[0])
            selected = [
                c for c in sorted_cards if self._get_card_value(c) == lowest_value
            ]
            context.set_variable(self.store_result, selected)
            # Compose explicit names for Action Log visibility
            names = ", ".join([getattr(c, "name", str(c)) for c in selected])
            context.add_result(
                f"Selected {len(selected)} lowest card(s) by {self.criteria}: {names}"
            )
            # Activity: record selection
            try:
                if activity_logger and selected:
                    card_names = [getattr(c, "name", str(c)) for c in selected]
                    activity_logger.log_dogma_card_selection(
                        game_id=getattr(context.game, "game_id", ""),
                        player_id=getattr(context.player, "id", ""),
                        card_name=getattr(context.card, "name", "Effect"),
                        selection_type="select_lowest_all",
                        selected_cards=[{"name": n} for n in card_names],
                        selection_criteria=self.criteria,
                    )
            except Exception:
                pass
            logger.debug(
                f"Selected all cards tied for lowest {self.criteria} ({lowest_value}); total {len(selected)}"
            )
            return ActionResult.SUCCESS
        else:
            count = self.count

        # Check for ties when selecting lowest
        if count == 1 and len(sorted_cards) > 1:
            # Get the lowest value
            lowest_value = self._get_card_value(sorted_cards[0])

            # Find all cards with the lowest value (potential ties)
            tied_cards = [
                c for c in sorted_cards if self._get_card_value(c) == lowest_value
            ]

            if len(tied_cards) > 1:
                # There's a tie - need player interaction
                logger.info(
                    f"Multiple cards tied with lowest {self.criteria}: {lowest_value}"
                )

                # Create interaction request for tie-breaking selection
                selection_message = f"Choose which card to meld (multiple cards with age {lowest_value})"
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
                logger.debug(f"SelectLowest: Targeting player {context.player.name}")

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
                    f"Multiple cards with {self.criteria} {lowest_value} - awaiting choice"
                )
                return ActionResult.REQUIRES_INTERACTION
            else:
                # No tie, just one lowest card
                selected = [tied_cards[0]]
        else:
            # Select the first N cards (for explicit numeric count > 1)
            selected = sorted_cards[:count]

        # Store result
        context.set_variable(self.store_result, selected)

        if selected:
            if self.criteria == "age":
                ages = [getattr(c, "age", 0) for c in selected]
                names = ", ".join([getattr(c, "name", str(c)) for c in selected])
                context.add_result(
                    f"Selected {len(selected)} lowest age card(s): age {min(ages)} — {names}"
                )
                # Activity: record selection (non-tie path)
                try:
                    if activity_logger and selected:
                        card_names = [getattr(c, "name", str(c)) for c in selected]
                        activity_logger.log_dogma_card_selection(
                            game_id=getattr(context.game, "game_id", ""),
                            player_id=getattr(context.player, "id", ""),
                            card_name=getattr(context.card, "name", "Effect"),
                            selection_type="select_lowest",
                            selected_cards=[{"name": n} for n in card_names],
                            selection_criteria=self.criteria,
                        )
                except Exception:
                    pass
            else:
                context.add_result(
                    f"Selected {len(selected)} lowest card(s) by {self.criteria}"
                )
        else:
            context.add_result("No cards selected")

        logger.debug(
            f"Selected {len(selected)} lowest cards from {len(source_cards)} by {self.criteria}"
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

    def _sort_by_criteria(self, cards: list, ascending: bool = True) -> list:
        """Sort cards by the specified criteria"""
        if not cards:
            return []

        if self.criteria == "age":
            # Sort by age
            return sorted(
                cards, key=lambda c: getattr(c, "age", 0), reverse=not ascending
            )
        elif self.criteria == "score_value":
            # Score value is usually the age for The Singularity
            return sorted(
                cards, key=lambda c: getattr(c, "age", 0), reverse=not ascending
            )
        elif self.criteria == "symbols":
            # Sort by total symbol count
            return sorted(
                cards, key=lambda c: self._count_card_symbols(c), reverse=not ascending
            )
        else:
            # Default to age
            return sorted(
                cards, key=lambda c: getattr(c, "age", 0), reverse=not ascending
            )

    def _count_card_symbols(self, card) -> int:
        """Count total symbols on a card"""
        if not card:
            return 0

        count = 0
        # Check all symbol positions
        for attr in ["top_left", "top_center", "top_right", "bottom"]:
            if hasattr(card, attr) and getattr(card, attr):
                count += 1

        return count
