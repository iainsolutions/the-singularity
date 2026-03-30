"""
ExchangeCards Action Primitive

Exchanges cards between two locations.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class ExchangeCards(ActionPrimitive):
    """
    Primitive for exchanging cards between two locations.

    Parameters:
    - source_location: Where to get cards from ("hand", "score_pile")
    - target_location: Where to put source cards ("hand", "score_pile")
    - selection_criteria: How to select cards ("highest_age", "lowest_age", "all")
    - count: Number of cards to exchange (default: all matching criteria)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.source_location = config.get("source_location", "hand")
        self.target_location = config.get("target_location", "score_pile")
        self.selection_criteria = config.get("selection_criteria", "highest_age")
        self.count = config.get("count")  # None means all
        # Support explicit selections produced by prior effects (e.g., SelectHighest)
        self.selection1_var = config.get("selection1")
        self.selection2_var = config.get("selection2")

    def execute(self, context: ActionContext) -> ActionResult:
        """Exchange cards between two locations"""
        if self.source_location == self.target_location and not (
            self.selection1_var and self.selection2_var
        ):
            context.add_result("Cannot exchange cards with the same location")
            return ActionResult.FAILURE

        # Prefer explicit selections when provided (matches card JSON: selection1/selection2)
        if self.selection1_var and self.selection2_var:
            source_selected = context.get_variable(self.selection1_var, []) or []
            target_selected = context.get_variable(self.selection2_var, []) or []

            # Enhanced logging for troubleshooting selection-based exchanges
            try:
                from logging_config import EventType, activity_logger

                if activity_logger:
                    activity_logger.log_game_event(
                        event_type=EventType.DOGMA_EFFECT_EXECUTED,
                        game_id=getattr(context.game, "game_id", ""),
                        player_id=getattr(context.player, "id", ""),
                        data={
                            "card_name": getattr(context.card, "name", "Unknown"),
                            "exchange_phase": "using_explicit_selections",
                            "selection1_var": self.selection1_var,
                            "selection2_var": self.selection2_var,
                            "selection1_count": len(source_selected)
                            if isinstance(source_selected, list)
                            else 1,
                            "selection2_count": len(target_selected)
                            if isinstance(target_selected, list)
                            else 1,
                            "selection1_cards": [
                                getattr(c, "name", str(c))
                                for c in (
                                    source_selected
                                    if isinstance(source_selected, list)
                                    else [source_selected]
                                )
                            ],
                            "selection2_cards": [
                                getattr(c, "name", str(c))
                                for c in (
                                    target_selected
                                    if isinstance(target_selected, list)
                                    else [target_selected]
                                )
                            ],
                        },
                        message=f"Exchange using selections: {self.selection1_var}({len(source_selected) if isinstance(source_selected, list) else 1}) ↔ {self.selection2_var}({len(target_selected) if isinstance(target_selected, list) else 1})",
                    )
            except Exception:
                pass

            # Debug logging for Canal Building exchange
            logger.debug(
                f"ExchangeCards: selection1_var={self.selection1_var}, selection2_var={self.selection2_var}"
            )
            logger.debug(
                f"ExchangeCards: source_selected={[getattr(c, 'name', str(c)) for c in source_selected]}"
            )
            logger.debug(
                f"ExchangeCards: target_selected={[getattr(c, 'name', str(c)) for c in target_selected]}"
            )

            # Safety: if selections look wrong or too broad, recompute highest groups by age
            # (Observed in Canal Building where entire hand could be removed)
            def _highest_group(cards: list) -> list:
                if not cards:
                    return []
                max_age = max(getattr(c, "age", 0) for c in cards)
                return [c for c in cards if getattr(c, "age", 0) == max_age]

            try:
                # Heuristic: if selection var names signal highest_* but selected set equals the entire container,
                # recompute to only keep highest-age ties
                if self.selection1_var == "highest_hand":
                    hand_cards = list(getattr(context.player, "hand", []) or [])
                    logger.debug(
                        f"ExchangeCards: hand_cards={[getattr(c, 'name', str(c)) for c in hand_cards]}"
                    )
                    if source_selected and len(source_selected) == len(hand_cards):
                        old_selection = [
                            getattr(c, "name", str(c)) for c in source_selected
                        ]
                        source_selected = _highest_group(hand_cards)
                        new_selection = [
                            getattr(c, "name", str(c)) for c in source_selected
                        ]
                        logger.debug(
                            f"ExchangeCards: hand heuristic applied - old: {old_selection}, new: {new_selection}"
                        )
                if self.selection2_var == "highest_score":
                    score_cards = list(getattr(context.player, "score_pile", []) or [])
                    logger.debug(
                        f"ExchangeCards: score_cards={[getattr(c, 'name', str(c)) for c in score_cards]}"
                    )
                    if target_selected and len(target_selected) == len(score_cards):
                        old_selection = [
                            getattr(c, "name", str(c)) for c in target_selected
                        ]
                        target_selected = _highest_group(score_cards)
                        new_selection = [
                            getattr(c, "name", str(c)) for c in target_selected
                        ]
                        logger.debug(
                            f"ExchangeCards: score heuristic applied - old: {old_selection}, new: {new_selection}"
                        )
            except Exception:
                pass
            # Ensure lists
            if not isinstance(source_selected, list):
                source_selected = [source_selected]
            if not isinstance(target_selected, list):
                target_selected = [target_selected]

            # Create orig_loc_map for activity logging using card IDs as keys
            orig_loc_map = {}
            for card in source_selected:
                card_id = getattr(card, "card_id", id(card))
                orig_loc_map[
                    card_id
                ] = "hand"  # source_selected comes from hand (highest_hand)
            for card in target_selected:
                card_id = getattr(card, "card_id", id(card))
                orig_loc_map[
                    card_id
                ] = "score_pile"  # target_selected comes from score_pile (highest_score)
        else:
            # Fallback to location + criteria selection
            source_cards = self._get_location_cards(context, self.source_location)
            target_cards = self._get_location_cards(context, self.target_location)

            if not source_cards and not target_cards:
                context.add_result("No cards in either location for exchange")
                return ActionResult.SUCCESS

            source_selected = self._select_cards_by_criteria(
                source_cards, self.selection_criteria, self.count
            )
            target_selected = self._select_cards_by_criteria(
                target_cards, self.selection_criteria, self.count
            )

            # Create orig_loc_map for activity logging using card IDs as keys
            orig_loc_map = {}
            for card in source_selected:
                card_id = getattr(card, "card_id", id(card))
                orig_loc_map[card_id] = self.source_location
            for card in target_selected:
                card_id = getattr(card, "card_id", id(card))
                orig_loc_map[card_id] = self.target_location

        if not source_selected and not target_selected:
            context.add_result("No cards selected for exchange")
            return ActionResult.SUCCESS

        # Ensure we have lists (handle empty locations)
        source_selected = source_selected or []
        target_selected = target_selected or []

        # Move ALL selected cards from each location to the other (not just minimum)
        source_to_move = source_selected[:]
        target_to_move = target_selected[:]

        # CRITICAL FIX: Track which player each card belongs to for cross-player exchanges
        # We need to find the actual owner player for each card (could be different players in demand effects)
        def find_card_owner_and_location(
            card, possible_locations=["hand", "score_pile"]
        ):
            """Find which player owns this card and in which location."""
            # Check all players in the game
            if hasattr(context.game, "players"):
                for player in context.game.players:
                    for loc in possible_locations:
                        player_loc = getattr(player, loc, [])
                        if card in player_loc:
                            return (player, loc)
            # Fallback to context.player
            for loc in possible_locations:
                player_loc = getattr(context.player, loc, [])
                if card in player_loc:
                    return (context.player, loc)
            return (None, None)

        # SAVE owner/location info BEFORE removing cards
        source_owners = {}  # card -> (player, location)
        for card in source_to_move:
            source_owners[id(card)] = find_card_owner_and_location(card)

        target_owners = {}  # card -> (player, location)
        for card in target_to_move:
            target_owners[id(card)] = find_card_owner_and_location(card)

        # Remove cards from their current locations
        for card in source_to_move:
            owner, location = source_owners.get(id(card), (None, None))
            if owner and location:
                owner_loc = getattr(owner, location, [])
                if card in owner_loc:
                    owner_loc.remove(card)
                    logger.debug(
                        f"Removed {getattr(card, 'name', str(card))} from {owner.name}'s {location}"
                    )

        for card in target_to_move:
            owner, location = target_owners.get(id(card), (None, None))
            if owner and location:
                owner_loc = getattr(owner, location, [])
                if card in owner_loc:
                    owner_loc.remove(card)
                    logger.debug(
                        f"Removed {getattr(card, 'name', str(card))} from {owner.name}'s {location}"
                    )

        for card in target_to_move:
            owner, location = find_card_owner_and_location(card)
            if owner and location:
                owner_loc = getattr(owner, location, [])
                if card in owner_loc:
                    owner_loc.remove(card)
                    logger.debug(
                        f"Removed {getattr(card, 'name', str(card))} from {owner.name}'s {location}"
                    )

        # CRITICAL FIX: Add cards to the opposite player's location
        # For cross-player exchanges, we need to determine the target player and location for each group of cards

        # Determine where selection1 cards should go (where selection2 cards came from)
        if target_to_move:
            # Get the first target card's original owner and location (from saved info)
            target_owner, target_location = target_owners.get(
                id(target_to_move[0]), (None, None)
            )
            if target_owner and target_location:
                # Add selection1 cards to target's original location
                for card in source_to_move:
                    target_loc = getattr(target_owner, target_location, [])
                    target_loc.append(card)
                    logger.debug(
                        f"Added {getattr(card, 'name', str(card))} to {target_owner.name}'s {target_location}"
                    )
            else:
                # Fallback to using self.target_location on context.player
                for card in source_to_move:
                    self._add_to_location(context, card, self.target_location)
        else:
            # No target cards, use self.target_location
            for card in source_to_move:
                self._add_to_location(context, card, self.target_location)

        # Determine where selection2 cards should go (where selection1 cards came from)
        if source_to_move:
            # Get the first source card's original owner and location (from saved info)
            source_owner, source_location = source_owners.get(
                id(source_to_move[0]), (None, None)
            )
            if source_owner and source_location:
                # Add selection2 cards to source's original location
                for card in target_to_move:
                    source_loc = getattr(source_owner, source_location, [])
                    source_loc.append(card)
                    logger.debug(
                        f"Added {getattr(card, 'name', str(card))} to {source_owner.name}'s {source_location}"
                    )
            else:
                # Fallback to using self.source_location on context.player
                for card in target_to_move:
                    self._add_to_location(context, card, self.source_location)
        else:
            # No source cards, use self.source_location
            for card in target_to_move:
                self._add_to_location(context, card, self.source_location)

        # Action Log + Activity: record the exchange with card names
        try:
            from logging_config import activity_logger

            # Add explicit Action Log summary for UI
            try:
                names_src = ", ".join(
                    [getattr(c, "name", str(c)) for c in source_to_move]
                )
                names_tgt = ", ".join(
                    [getattr(c, "name", str(c)) for c in target_to_move]
                )
                from models.game import ActionType

                context.game.add_log_entry(
                    player_name=getattr(context.player, "name", "Player"),
                    action_type=ActionType.DOGMA,
                    description=f"Exchange: hand→score [{names_src}] | score→hand [{names_tgt}] (from {getattr(context.card,'name','Effect')})",
                )
            except Exception:
                pass
            # Log two directions for clarity
            activity_logger.log_dogma_card_action(
                game_id=getattr(context.game, "game_id", ""),
                player_id=getattr(context.player, "id", ""),
                card_name=getattr(context.card, "name", "Effect"),
                action_type="transferred",
                cards=[{"name": getattr(c, "name", str(c))} for c in source_to_move],
                location_from=self.source_location
                if not (self.selection1_var and self.selection2_var)
                else orig_loc_map.get(
                    getattr(source_to_move[0], "card_id", id(source_to_move[0])), None
                )
                if source_to_move
                else None,
                location_to=self.target_location
                if not (self.selection1_var and self.selection2_var)
                else (
                    "score_pile"
                    if orig_loc_map.get(
                        getattr(source_to_move[0], "card_id", id(source_to_move[0])),
                        None,
                    )
                    == "hand"
                    else "hand"
                )
                if source_to_move
                else None,
            )
            activity_logger.log_dogma_card_action(
                game_id=getattr(context.game, "game_id", ""),
                player_id=getattr(context.player, "id", ""),
                card_name=getattr(context.card, "name", "Effect"),
                action_type="transferred",
                cards=[{"name": getattr(c, "name", str(c))} for c in target_to_move],
                location_from=self.target_location
                if not (self.selection1_var and self.selection2_var)
                else orig_loc_map.get(
                    getattr(target_to_move[0], "card_id", id(target_to_move[0])), None
                )
                if target_to_move
                else None,
                location_to=self.source_location
                if not (self.selection1_var and self.selection2_var)
                else (
                    "score_pile"
                    if orig_loc_map.get(
                        getattr(target_to_move[0], "card_id", id(target_to_move[0])),
                        None,
                    )
                    == "hand"
                    else "hand"
                )
                if target_to_move
                else None,
            )
            # Summary message for Activity panel
            src_names = ", ".join([getattr(c, "name", str(c)) for c in source_to_move])
            tgt_names = ", ".join([getattr(c, "name", str(c)) for c in target_to_move])
            activity_logger.log_game_event(
                event_type=EventType.DOGMA_CARD_TRANSFERRED,
                game_id=getattr(context.game, "game_id", ""),
                player_id=getattr(context.player, "id", ""),
                data={
                    "card_name": getattr(context.card, "name", "Effect"),
                    "exchange_summary": {
                        "hand_to_score": [
                            getattr(c, "name", str(c)) for c in source_to_move
                        ],
                        "score_to_hand": [
                            getattr(c, "name", str(c)) for c in target_to_move
                        ],
                        "selection1_var": self.selection1_var,
                        "selection2_var": self.selection2_var,
                    },
                },
                message=f"Exchange: hand→score [{src_names}] | score→hand [{tgt_names}]",
            )
        except Exception:
            pass

        total_moved = len(source_to_move) + len(target_to_move)
        context.add_result(
            f"Exchanged cards between {self.source_location} and {self.target_location} ({len(source_to_move)} from source, {len(target_to_move)} from target)"
        )
        logger.info(
            f"Exchanged {total_moved} total cards for player {getattr(context.player, 'name', 'Player')}"
        )

        return ActionResult.SUCCESS

    def _get_location_cards(self, context: ActionContext, location: str) -> list:
        """Get cards from a specific location"""
        if location == "hand":
            return list(getattr(context.player, "hand", []))
        elif location == "score_pile":
            return list(getattr(context.player, "score_pile", []))
        else:
            return []

    def _select_cards_by_criteria(
        self, cards: list, criteria: str, count: int | None
    ) -> list:
        """Select cards based on criteria"""
        if not cards:
            return []

        if criteria == "all":
            selected = cards
        elif criteria == "highest_age":
            sorted_cards = sorted(
                cards, key=lambda c: getattr(c, "age", 0), reverse=True
            )
            selected = sorted_cards
        elif criteria == "lowest_age":
            sorted_cards = sorted(cards, key=lambda c: getattr(c, "age", 0))
            selected = sorted_cards
        else:
            selected = cards

        # Limit to count if specified
        if count is not None and count > 0:
            selected = selected[:count]

        return selected

    def _remove_from_location(self, context: ActionContext, card, location: str):
        """Remove a card from a location"""
        if location == "hand":
            if hasattr(context.player, "hand") and card in context.player.hand:
                context.player.hand.remove(card)
        elif location == "score_pile" and (
            hasattr(context.player, "score_pile") and card in context.player.score_pile
        ):
            context.player.score_pile.remove(card)

    def _add_to_location(self, context: ActionContext, card, location: str):
        """Add a card to a location"""
        if location == "hand":
            if not hasattr(context.player, "hand"):
                context.player.hand = []
            context.player.hand.append(card)
        elif location == "score_pile":
            if not hasattr(context.player, "score_pile"):
                context.player.score_pile = []
            context.player.score_pile.append(card)
