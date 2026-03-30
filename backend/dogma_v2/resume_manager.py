"""
ResumeManager - Handles suspending and resuming dogma execution
"""

import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .interaction_request import InteractionRequest

logger = logging.getLogger(__name__)


def safe_get(obj, attr, default=None):
    """Safely get attribute from Pydantic object or dictionary."""
    if hasattr(obj, attr):  # Pydantic object
        return getattr(obj, attr, default)
    elif isinstance(obj, dict):  # Dictionary
        return obj.get(attr, default)
    else:
        return default


@dataclass
class SuspendedContext:
    """Context suspended for interaction"""

    context: Any  # DogmaContext
    resume_phase: Any  # DogmaPhase
    interaction: InteractionRequest
    suspended_at: datetime


class ResumeManager:
    """Handles resuming from interactions"""

    def __init__(self):
        self.suspended_contexts: dict[str, SuspendedContext] = {}

    def suspend_for_interaction(
        self,
        transaction_id: str,
        context,
        resume_phase,
        interaction: InteractionRequest,
    ):
        """Save state for resume"""
        self.suspended_contexts[transaction_id] = SuspendedContext(
            context=context,
            resume_phase=resume_phase,
            interaction=interaction,
            suspended_at=datetime.now(),
        )

    def resume_with_response(
        self, transaction_id: str, response: dict[str, Any]
    ) -> tuple[Any, Any]:
        """Resume with player response"""
        if transaction_id not in self.suspended_contexts:
            raise ValueError(f"No suspended context for {transaction_id}")

        suspended = self.suspended_contexts.pop(transaction_id)

        # Apply the player's response to the context
        updated_context = self._apply_response_to_context(
            suspended.context, suspended.interaction, response
        )

        return updated_context, suspended.resume_phase

    def _apply_response_to_context(
        self, context, interaction: InteractionRequest, response: dict[str, Any]
    ):
        """Apply player response data to the context"""
        from .interaction_request import InteractionType

        # Helper: unwrap StandardInteractionBuilder wrapper if present
        def _unwrap_data(data: dict[str, Any]) -> dict[str, Any]:
            try:
                if (
                    isinstance(data, dict)
                    and data.get("type") == "dogma_interaction"
                    and isinstance(data.get("data"), dict)
                ):
                    return data.get("data", {})
            except Exception:
                pass
            return data or {}

        # CONSOLIDATION FIX: Handle decline responses uniformly across all interaction types
        # This consolidates legacy decline logic into the v2 system architecture
        declined = response.get("decline", False)

        if declined:
            # CRITICAL FIX: Enforce mandatory demand compliance (Innovation Ultimate rules)
            # IMPORTANT: Only DEMAND effects are mandatory - normal dogma actions can be declined if optional
            is_demand_target = context.get_variable("is_demand_target", False)

            if is_demand_target and interaction.type == InteractionType.SELECT_CARDS:
                # This is a DEMAND interaction - demands are NEVER optional in Innovation Ultimate
                # If a player can comply with a demand (has valid cards), they MUST comply
                eligible_cards = safe_get(interaction.data, "eligible_cards", [])
                if not eligible_cards:
                    # Fallback to legacy field names for compatibility
                    eligible_cards = safe_get(interaction.data, "cards", [])
                    if not eligible_cards:
                        eligible_cards = safe_get(
                            interaction.data, "selection_cards", []
                        )

                if eligible_cards:
                    # Player has valid cards but is trying to decline a DEMAND - this violates Innovation rules
                    logger.error(
                        f"Player {interaction.player_id} attempted to decline DEMAND but has {len(eligible_cards)} valid cards - demands are mandatory!"
                    )
                    raise ValueError(
                        f"Invalid decline: Demands are mandatory in Innovation Ultimate. "
                        f"Player has {len(eligible_cards)} eligible card(s) and must select one to comply with the demand."
                    )
                else:
                    # Player has no valid cards for demand, decline is allowed (shouldn't normally happen as they wouldn't be targeted)
                    logger.info(
                        "Player declined demand interaction with no eligible cards (unusual but allowed)"
                    )

            # For non-demand interactions, check if they're optional
            inner_data = _unwrap_data(interaction.data)
            is_optional = inner_data.get("is_optional", False)

            if is_optional:
                # Optional interactions can be declined - return empty results
                logger.info(
                    f"Player declined optional interaction: {interaction.type.value}"
                )

                # Set appropriate empty values based on interaction type
                if interaction.type == InteractionType.SELECT_CARDS:
                    store_result_key = inner_data.get("store_result", "selected_cards")
                    updated_context = context.with_variable(store_result_key, [])
                    updated_context = updated_context.with_variable(
                        "selected_cards", []
                    )
                    updated_context = updated_context.with_results(
                        ("Declined card selection",)
                    )
                elif interaction.type == InteractionType.CHOOSE_OPTION:
                    updated_context = context.with_variable(
                        "chosen_option_choice", None
                    )
                    updated_context = updated_context.with_results(
                        ("Declined option selection",)
                    )
                elif interaction.type == InteractionType.SELECT_ACHIEVEMENT:
                    updated_context = context.with_variable("selected_achievements", [])
                    updated_context = updated_context.with_variable(
                        "selected_cards", []
                    )
                    updated_context = updated_context.with_results(
                        ("Declined achievement selection",)
                    )
                elif interaction.type == InteractionType.SELECT_COLOR:
                    store_result_key = safe_get(
                        interaction.data, "store_result", "selected_color"
                    )
                    updated_context = context.with_variable(store_result_key, None)
                    updated_context = updated_context.with_results(
                        ("Declined color selection",)
                    )
                elif interaction.type == InteractionType.SELECT_SYMBOL:
                    store_result_key = safe_get(
                        interaction.data, "store_result", "selected_symbol"
                    )
                    updated_context = context.with_variable(store_result_key, None)
                    updated_context = updated_context.with_results(
                        ("Declined symbol selection",)
                    )
                else:
                    # Generic decline handling for unknown interaction types
                    updated_context = context.with_results(("Declined interaction",))

                return updated_context
            else:
                # Required interaction was declined - this shouldn't happen in normal gameplay
                # but we handle it gracefully
                logger.warning(
                    f"Player declined required interaction: {interaction.type.value}"
                )
                # Return original context unchanged - let the phase handle the error
                return context

        # Handle normal (non-declined) responses for each interaction type
        if interaction.type == InteractionType.SELECT_CARDS:
            # For card selection, store the selected cards
            selected_cards = response.get("selected_cards", [])

            logger.info(
                f"ResumeManager: Processing card selection response - received {len(selected_cards)} selection entries"
            )
            logger.debug(f"ResumeManager: Raw selection entries: {selected_cards}")

            # Convert identifiers/dicts back to card objects when needed
            if selected_cards:
                # Normalize to identifiers when entries are dicts
                if isinstance(selected_cards[0], dict):
                    identifiers = []
                    for item in selected_cards:
                        if not isinstance(item, dict):
                            continue
                        identifiers.append(
                            item.get("card_id") or item.get("id") or item.get("name")
                        )
                    identifiers = [i for i in identifiers if isinstance(i, str) and i]
                    if identifiers:
                        logger.debug(
                            "ResumeManager: Resolving dict selections to card objects via identifiers"
                        )
                        selected_cards = self._resolve_selected_cards(
                            context, identifiers
                        )
                        logger.info(
                            f"ResumeManager: Resolved {len(selected_cards)} card objects from dict identifiers"
                        )
                elif isinstance(selected_cards[0], str):
                    logger.debug("ResumeManager: Resolving string IDs to card objects")
                    selected_cards = self._resolve_selected_cards(
                        context, selected_cards
                    )
                    logger.info(
                        f"ResumeManager: Resolved {len(selected_cards)} card objects from string IDs"
                    )

            # Get the store_result key from interaction data (unwrap wrapper), default to "selected_cards"
            inner_data = _unwrap_data(interaction.data)
            store_result_key = inner_data.get("store_result", "selected_cards")

            # Update context with selected cards
            updated_context = context.with_variable(store_result_key, selected_cards)
            updated_context = updated_context.with_variable(
                "selected_cards", selected_cards
            )
            # Clear any lingering interaction request to avoid re-prompt loops
            updated_context = updated_context.without_variable(
                "final_interaction_request"
            )

            # Add result message
            if selected_cards:
                card_names = [
                    c.name if hasattr(c, "name") else str(c) for c in selected_cards
                ]
                result_message = (
                    f"Selected {len(selected_cards)} cards: {', '.join(card_names)}"
                )
            else:
                result_message = "No cards selected"

            updated_context = updated_context.with_results((result_message,))

            return updated_context

        elif interaction.type == InteractionType.CHOOSE_OPTION:
            # For option selection
            chosen = response.get("chosen_option")
            inner_data = _unwrap_data(interaction.data)

            # Coerce numeric strings to int for robustness
            if isinstance(chosen, str) and chosen.isdigit():
                with contextlib.suppress(Exception):
                    chosen = int(chosen)

            # Set primitive-specific resume variable (standardization: Option 1)
            updated_context = context.with_variable("chosen_option_choice", chosen)

            try:
                # If this choose_option originated from a SelectColor flow, map to selected_color
                options = inner_data.get("options") or []
                store_key = inner_data.get("store_result") or "selected_choice"

                # Enhanced debugging for option selection
                logger.debug("ResumeManager CHOOSE_OPTION debug:")
                logger.debug(f"  chosen: {chosen} (type: {type(chosen)})")
                logger.debug(f"  options count: {len(options)}")
                for i, opt in enumerate(options):
                    logger.debug(f"  option[{i}]: {opt}")

                selected_value = None
                if isinstance(chosen, int) and 0 <= chosen < len(options):
                    # Index into options
                    opt = options[chosen]
                    selected_value = opt.get("value") if isinstance(opt, dict) else None
                    logger.debug(
                        f"  selected by index {chosen}: opt={opt}, selected_value={selected_value}"
                    )
                elif isinstance(chosen, str):
                    # Chosen is a string - could be label or value
                    # First try to find by matching label (StandardInteractionBuilder uses "label" not "description")
                    for opt in options:
                        if isinstance(opt, dict) and opt.get("label") == chosen:
                            selected_value = opt.get("value")
                            break
                    # If not found by label, try to find by value
                    if selected_value is None:
                        for opt in options:
                            if isinstance(opt, dict) and opt.get("value") == chosen:
                                selected_value = opt.get("value")
                                break
                    # Fallback: assume chosen is already the value (for legacy compatibility)
                    if selected_value is None:
                        selected_value = chosen

                if isinstance(selected_value, str) and selected_value:
                    # Also set generic chosen_option for condition evaluators (option_chosen)
                    updated_context = updated_context.with_variable(
                        "chosen_option", selected_value
                    )
                    # Set selected_color for downstream SplayCards or other effects
                    updated_context = updated_context.with_variable(
                        "selected_color", selected_value
                    )
                    # CRITICAL FIX: Always set the store_key variable for SelectColor compatibility
                    # SelectColor checks for "selected_color_choice" first, so we must set it
                    updated_context = updated_context.with_variable(
                        store_key, selected_value
                    )
                    # Preserve explicit choice index when available
                    if isinstance(chosen, int):
                        updated_context = updated_context.with_variable(
                            f"{store_key}_index", chosen
                        )
                    # Add a friendly result message
                    updated_context = updated_context.with_results(
                        (f"Selected color: {selected_value}",)
                    )
            except Exception:
                # Non-fatal; keep generic choice only
                pass

            # Clear any lingering interaction request to avoid re-prompt loops
            updated_context = updated_context.without_variable(
                "final_interaction_request"
            )

            return updated_context

        elif interaction.type == InteractionType.SELECT_ACHIEVEMENT:
            # Handle achievement selection responses
            selected_ids = response.get("selected_achievements", [])
            # Support single value
            if isinstance(selected_ids, str | int):
                selected_ids = [selected_ids]

            # Resolve to achievement objects using validation framework's helpers
            try:
                from .validation.framework import (
                    AchievementSelectionConstraints,
                    ValidationFramework,
                )

                inner_data = _unwrap_data(interaction.data)
                constraints = AchievementSelectionConstraints(
                    min_count=inner_data.get("min_count", 0),
                    max_count=inner_data.get("max_count", 1),
                    eligible_achievements=inner_data.get("eligible_achievements", []),
                    is_optional=inner_data.get("is_optional", False),
                )
                # Build a faux response for validation
                faux_response = {
                    "selected_achievements": selected_ids,
                    "player_id": context.current_player.id,
                }
                validation = ValidationFramework.validate_achievement_selection(
                    faux_response, constraints, context.game.to_dict()
                )
                if validation.is_valid:
                    resolved = validation.validated_data or []
                else:
                    resolved = []
            except Exception:
                # Fallback: try to match by name in achievement decks
                resolved = []
                ach_map = (
                    context.game.deck_manager.achievement_cards
                    if hasattr(context.game, "achievement_cards")
                    else {}
                )
                for sid in selected_ids:
                    name = str(sid)
                    for age_list in ach_map.values():
                        for ach in age_list:
                            if getattr(ach, "name", None) == name:
                                resolved.append(ach)
                                break

            inner_data = _unwrap_data(interaction.data)
            store_key = inner_data.get("store_result", "selected_achievements")
            # Update context with resolved achievements and compatibility keys
            updated_context = context.with_variable(
                store_key,
                resolved
                if not store_key.endswith("_achievement")
                else (resolved[0] if resolved else None),
            )
            updated_context = updated_context.with_variable(
                "selected_achievements", resolved
            )

            if resolved:
                achievement_names = [
                    a.name if hasattr(a, "name") else str(a) for a in resolved
                ]
                result_message = f"Selected {len(resolved)} achievement(s): {', '.join(achievement_names)}"
            else:
                result_message = "No achievements selected"

            updated_context = updated_context.with_results((result_message,))
            return updated_context

        elif interaction.type == InteractionType.SELECT_COLOR:
            # Handle color selection responses
            selected_color = response.get("selected_color")
            inner_data = _unwrap_data(interaction.data)
            store_result_key = inner_data.get("store_result", "selected_color")

            # Set primitive-specific resume variable (standardization: Option 1)
            updated_context = context.with_variable(
                "selected_color_choice", selected_color
            )
            # Also set the configured store_result_key for backward compatibility
            updated_context = updated_context.with_variable(
                store_result_key, selected_color
            )

            result_message = (
                f"Selected color: {selected_color}"
                if selected_color
                else "No color selected"
            )
            updated_context = updated_context.with_results((result_message,))
            return updated_context

        elif interaction.type == InteractionType.SELECT_SYMBOL:
            # Handle symbol selection responses
            selected_symbol = response.get("selected_symbol")
            inner_data = _unwrap_data(interaction.data)
            store_result_key = inner_data.get("store_result", "selected_symbol")

            # Set primitive-specific resume variable (standardization: Option 1)
            updated_context = context.with_variable(
                "selected_symbol_choice", selected_symbol
            )
            # Also set the configured store_result_key for backward compatibility
            updated_context = updated_context.with_variable(
                store_result_key, selected_symbol
            )

            result_message = (
                f"Selected symbol: {selected_symbol}"
                if selected_symbol
                else "No symbol selected"
            )
            updated_context = updated_context.with_results((result_message,))
            return updated_context

        elif interaction.type == InteractionType.CHOOSE_HIGHEST_TIE:
            # Tie-breaker for SelectHighest: treat as single-card selection
            selected = response.get("selected_cards", [])
            if isinstance(selected, str | int):
                selected = [selected]

            # Resolve to actual card objects when needed (support dicts and strings)
            selected_cards = []
            if selected:
                if isinstance(selected[0], dict):
                    identifiers = []
                    for item in selected:
                        if isinstance(item, dict):
                            identifiers.append(
                                item.get("card_id")
                                or item.get("id")
                                or item.get("name")
                            )
                    identifiers = [i for i in identifiers if isinstance(i, str) and i]
                    if identifiers:
                        selected_cards = self._resolve_selected_cards(
                            context, identifiers
                        )
                elif isinstance(selected[0], str):
                    selected_cards = self._resolve_selected_cards(context, selected)
                else:
                    selected_cards = selected or []

            inner_data = _unwrap_data(interaction.data)
            store_result_key = inner_data.get("store_result", "selected_cards")

            updated_context = context.with_variable(store_result_key, selected_cards)
            updated_context = updated_context.with_variable(
                "selected_cards", selected_cards
            )
            # Clear any lingering interaction request to avoid re-prompt loops
            updated_context = updated_context.without_variable(
                "final_interaction_request"
            )

            if selected_cards:
                names = [getattr(c, "name", str(c)) for c in selected_cards]
                updated_context = updated_context.with_results(
                    (f"Tie resolved: {', '.join(names)}",)
                )
            else:
                updated_context = updated_context.with_results(
                    ("No card chosen for tie-break",)
                )

            return updated_context

        else:
            # For unknown interaction types, just return the original context
            logger.warning(f"Unknown interaction type: {interaction.type}")
            return context

    def _resolve_selected_cards(self, context, card_ids: list[str]):
        """Resolve card IDs to actual card objects from game state"""
        resolved_cards = []

        logger.debug(f"ResumeManager: Resolving {len(card_ids)} card IDs: {card_ids}")

        # Search through all possible card locations to find the selected cards
        for card_id in card_ids:
            card = self._find_card_by_id(context, card_id)
            if card:
                resolved_cards.append(card)
                logger.debug(
                    f"ResumeManager: Successfully resolved card ID '{card_id}' to card '{card.name}'"
                )
            else:
                logger.warning(f"ResumeManager: Card not found for ID: {card_id}")

        logger.info(
            f"ResumeManager: Resolved {len(resolved_cards)}/{len(card_ids)} cards successfully"
        )
        return resolved_cards

    def _matches_card_identifier(self, card, identifier: str) -> bool:
        """Helper function to check if card matches identifier (card_id or name).

        Args:
            card: Card instance
            identifier: Card identifier (card_id or name)

        Returns:
            True if card matches identifier
        """
        # Check card_id first (preferred stable identifier)
        if hasattr(card, "card_id") and card.card_id and card.card_id == identifier:
            return True
        # Fall back to name for backwards compatibility
        return hasattr(card, "name") and card.name == identifier

    def _find_card_by_id(self, context, card_id: str):
        """Find a card by ID or name in the game state

        CRITICAL: Returns the exact card reference to ensure proper removal from hand.
        This fixes the recurring Tools card bug where cards remained in hand.
        """
        from logging_config import get_logger

        logger = get_logger(__name__)

        logger.debug(f"Looking for card ID: {card_id}")

        # PRIORITY 1: Check current player's hand FIRST
        # This is critical for card selection/removal operations
        for i, card in enumerate(context.current_player.hand):
            if self._matches_card_identifier(card, card_id):
                logger.debug(
                    f"Found card {card_id} in current player's hand at index {i}"
                )
                return card

        # PRIORITY 2: Check current player's board
        for card in context.current_player.board.get_all_cards():
            if self._matches_card_identifier(card, card_id):
                logger.debug(f"Found card {card_id} on current player's board")
                return card

        # PRIORITY 3: Check current player's score pile
        for card in context.current_player.score_pile:
            if self._matches_card_identifier(card, card_id):
                logger.debug(f"Found card {card_id} in current player's score pile")
                return card

        # PRIORITY 4: Check age decks if needed
        for age, age_deck in context.game.deck_manager.age_decks.items():
            for card in age_deck:
                if self._matches_card_identifier(card, card_id):
                    logger.debug(f"Found card {card_id} in age {age} deck")
                    return card

        # PRIORITY 5: Check other players if needed (for demand effects)
        for player in context.game.players:
            if player.id != context.current_player.id:
                # Check their hand
                for card in player.hand:
                    if self._matches_card_identifier(card, card_id):
                        logger.debug(
                            f"Found card {card_id} in player {player.name}'s hand"
                        )
                        return card

                # Check their board
                for card in player.board.get_all_cards():
                    if self._matches_card_identifier(card, card_id):
                        logger.debug(
                            f"Found card {card_id} on player {player.name}'s board"
                        )
                        return card

                # Check their score pile
                for card in player.score_pile:
                    if self._matches_card_identifier(card, card_id):
                        logger.debug(
                            f"Found card {card_id} in player {player.name}'s score pile"
                        )
                        return card

        logger.warning(f"Card {card_id} not found anywhere in game state")
        return None

    def clear_suspended(self, transaction_id: str):
        """Clear suspended context"""
        self.suspended_contexts.pop(transaction_id, None)
