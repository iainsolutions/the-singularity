"""
SelectCards Action Primitive

Allows players to select cards from various sources.
"""

import contextlib
import logging
import os
from typing import Any

from interaction.builder import StandardInteractionBuilder
from logging_config import EventType, activity_logger
from models.board_utils import BoardColorIterator

# Handle StandardInteractionBuilder import - ensure it works in backend context
from .base import ActionContext, ActionPrimitive, ActionResult
from .utils import attach_player_to_interaction


def safe_get(obj, attr, default=None):
    """Safely get attribute from Pydantic object or dictionary."""
    if hasattr(obj, attr):  # Pydantic object
        return getattr(obj, attr, default)
    elif isinstance(obj, dict):  # Dictionary
        return obj.get(attr, default)
    else:
        return default


logger = logging.getLogger(__name__)


class SelectCards(ActionPrimitive):
    """
    Allows players to select cards from various sources.

    Parameters:
    - source: "hand", "board", "score_pile", "age_deck"
    - min_count: Minimum cards to select (default: 0)
    - max_count: Maximum cards to select (default: unlimited)
    - filter_criteria: Dict with filtering rules
    - is_optional: Whether selection can be declined
    - store_result: Variable name to store selected cards
    - dynamic_filter: Dict with dynamic filter rules (re-evaluated at selection time)
    - selection_type: Type of automatic selection ("highest_age", "lowest_age", etc.)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.source = config.get("source", "hand")
        self.min_count = config.get("min_count", 0)
        self.max_count = config.get("max_count", 999)
        # Support both 'filter' and 'filter_criteria' parameters
        self.filter_criteria = config.get("filter_criteria", config.get("filter", {}))
        self.dynamic_filter = config.get("dynamic_filter")
        self.is_optional = config.get("is_optional", False)
        # Support both 'store_result' and 'store_as' parameters
        self.store_result = config.get("store_result") or config.get("store_as", "selected_cards")
        self.selection_type = config.get("selection_type")
        self.target = config.get("target")
        self.target_player = config.get("target_player")
        self.player = config.get("player")  # "active" or "opponent"
        self.message = config.get("message")  # Custom message for interaction prompt
        # reveal_only: True means card stays in source after selection (for "reveal" actions)
        self.reveal_only = config.get("reveal_only", False)

        # Support legacy "count" parameter
        if "count" in config:
            count = config["count"]
            # Ensure count is an integer
            if isinstance(count, str):
                if count == "all":
                    count = 999  # Unlimited selection
                else:
                    count = int(count) if count.isdigit() else 1
            self.max_count = count
            # Only set min_count from count if min_count wasn't explicitly provided
            if "min_count" not in config:
                if self.is_optional:
                    self.min_count = 0
                else:
                    self.min_count = count

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute card selection"""

        # DEBUG: Track SelectCards execution from the start
        logger.debug(
            f"SelectCards EXECUTE START: source={self.source}, min={self.min_count}, max={self.max_count}, optional={self.is_optional}, store_result={self.store_result}"
        )

        try:
            result = self._execute_internal(context)
            logger.debug(f"SelectCards RESULT: {result}")
            return result
        except Exception as e:
            err_msg = f"SelectCards failed: {type(e).__name__}: {e}"
            logger.error(f"{err_msg}")
            logger.error("SelectCards TRACEBACK:", exc_info=True)
            # Provide actionable error to adapter via context and return FAILURE
            with contextlib.suppress(Exception):
                context.set_variable("error", err_msg)
            return ActionResult.FAILURE

    def _execute_internal(self, context: ActionContext) -> ActionResult:
        """Internal execution with exception handling"""

        # CRITICAL FIX: Define treat_as_optional at the very beginning to prevent UnboundLocalError
        # In a demand context, selection is mandatory if eligible cards exist
        is_demand_context = (
            hasattr(context, "demanding_player") and context.demanding_player
        )
        treat_as_optional = self.is_optional and not is_demand_context
        # Check if cards were already selected (during resume from interaction)
        logger.debug(
            f"SelectCards: Checking for existing selection in variable '{self.store_result}'"
        )
        logger.debug(
            f"SelectCards: has_variable({self.store_result}) = {context.has_variable(self.store_result)}"
        )

        if context.has_variable(self.store_result):
            logger.debug(
                f"SelectCards: About to call get_variable for '{self.store_result}'"
            )
            logger.debug(f"SelectCards: Context type: {type(context)}")
            logger.debug(f"SelectCards: Context ID: {id(context)}")

            existing_selection = context.get_variable(self.store_result, [])

            logger.debug(f"SelectCards: get_variable returned: {existing_selection}")
            logger.debug(f"SelectCards: Return value type: {type(existing_selection)}")
            logger.debug(
                f"SelectCards: Return value length: {len(existing_selection) if existing_selection else 0}"
            )

            if existing_selection:
                logger.debug(
                    f"SelectCards: First item type: {type(existing_selection[0])}"
                )
                logger.debug(
                    f"SelectCards: First item repr: {repr(existing_selection[0])[:200]}"
                )
                logger.debug(
                    f"SelectCards: First item dir: {[a for a in dir(existing_selection[0]) if not a.startswith('_')][:10]}"
                )
                logger.debug(
                    f"SelectCards: First item hasattr name: {hasattr(existing_selection[0], 'name')}"
                )
                if hasattr(existing_selection[0], "name"):
                    logger.debug(
                        f"SelectCards: First item name: {existing_selection[0].name}"
                    )
                    logger.debug(
                        f"SelectCards: First item name type: {type(existing_selection[0].name)}"
                    )
                    logger.debug(
                        f"SelectCards: First item name repr: {existing_selection[0].name!r}"
                    )

            if existing_selection is not None:  # Allow empty list as valid selection
                logger.debug(
                    f"SelectCards: Found existing selection, using {len(existing_selection)} cards"
                )
                # Handle both Card objects and string IDs
                if existing_selection and hasattr(existing_selection[0], "name"):
                    selection_names = [c.name for c in existing_selection]
                else:
                    selection_names = existing_selection  # Already string IDs
                context.add_result(
                    f"DEBUG SelectCards: Found {self.store_result}={selection_names} in context"
                )
                context.add_result(
                    f"Using previously selected {len(existing_selection)} cards"
                )

                # DEFENSIVE CHECK: Verify cards ARE still in source (SelectCards doesn't remove them)
                # This is a resume scenario - cards should still be in source until subsequent actions remove them
                if existing_selection and hasattr(existing_selection[0], "name"):
                    for card in existing_selection:
                        if self.source == "hand" and card not in context.player.hand:
                            logger.warning(
                                f"RESUME: Card {card.name} NOT in hand - should still be there for subsequent action to remove!"
                            )
                        elif self.source == "board" or self.source == "board_top":
                            # Check all color stacks
                            found = False
                            for color in ["red", "blue", "green", "yellow", "purple"]:
                                stack = getattr(
                                    context.player.board, f"{color}_cards", []
                                )
                                if card in stack:
                                    found = True
                                    break
                            if not found:
                                logger.warning(
                                    f"RESUME: Card {card.name} NOT on board - should still be there for subsequent action to remove!"
                                )

                # CRITICAL FIX: Clear the final_interaction_request to prevent re-suspension loop
                # This prevents InteractionEffectAdapter's defensive code from forcing interaction
                if context.has_variable("final_interaction_request"):
                    context.remove_variable("final_interaction_request")
                    logger.debug(
                        "SelectCards: Cleared final_interaction_request to prevent re-suspension"
                    )

                return ActionResult.SUCCESS

        # Also check if 'selected_cards' variable exists as a fallback
        # Only use fallback if store_result is the default 'selected_cards'
        if self.store_result == "selected_cards" and context.has_variable(
            "selected_cards"
        ):
            existing_selection = context.get_variable("selected_cards", [])
            if existing_selection is not None and len(existing_selection) > 0:
                logger.debug(
                    f"SelectCards: Found existing selection via fallback, using {len(existing_selection)} cards"
                )
                # Copy to the proper store_result variable
                context.set_variable(self.store_result, existing_selection)
                context.add_result(
                    f"Using previously selected {len(existing_selection)} cards"
                )
                # Clear the final_interaction_request here too
                if context.has_variable("final_interaction_request"):
                    context.remove_variable("final_interaction_request")
                    logger.debug(
                        "SelectCards: Cleared final_interaction_request via fallback to prevent re-suspension"
                    )

                return ActionResult.SUCCESS

        # Check if we're in test mode - if so, auto-select
        test_mode = context.get_variable("test_mode", False)

        # Get source cards
        logger.debug(
            f"SELECT_CARDS DEBUG: About to get source cards from {self.source}"
        )
        logger.debug(
            f"SELECT_CARDS DEBUG: context.player = {context.player.name} (ID: {context.player.id})"
        )
        source_cards = self._get_source_cards(context)
        logger.debug(
            f"SELECT_CARDS DEBUG: Got {len(source_cards)} source cards: {[c.name for c in source_cards[:5]]}"
        )

        # Apply filters
        logger.info(
            f"SelectCards: source={self.source}, source_cards = {[c.name if c else 'None' for c in source_cards]}"
        )
        logger.info(f"SelectCards: filter_criteria = {self.filter_criteria}")
        eligible_cards = self._apply_filters(
            context, source_cards, self.filter_criteria
        )
        logger.info(
            f"SelectCards: eligible_cards after filter = {[c.name if c else 'None' for c in eligible_cards]}"
        )

        # Apply dynamic filters if present
        if self.dynamic_filter:
            eligible_cards = self._apply_dynamic_filters(context, eligible_cards)

        # Check if minimum requirements can be met
        if len(eligible_cards) < self.min_count:
            if self.is_optional:
                context.set_variable(self.store_result, [])
                context.add_result(
                    "Not enough eligible cards for optional selection, skipping"
                )
                return ActionResult.SUCCESS
            else:
                # For non-optional selections with no eligible cards, set empty result and continue
                # This allows dogma effects to continue even when intermediate selections fail
                context.set_variable(self.store_result, [])
                context.add_result(
                    f"Not enough eligible cards (need {self.min_count}, have {len(eligible_cards)}), skipping"
                )
                return ActionResult.SUCCESS

        # Handle automatic selection types
        if self.selection_type:
            candidates = self._get_selection_candidates(eligible_cards)

            # Auto-select if conditions are met
            if (
                len(candidates) == 1
                or len(candidates) <= self.max_count
                or self.target == "opponent"
            ):
                selected_cards = candidates[: self.max_count]

                # SelectCards only SELECTS cards - removal is done by subsequent actions
                # (TransferBetweenPlayers, ScoreCards, JunkCard, etc.)
                context.set_variable(self.store_result, selected_cards)

                # CRITICAL LOGGING: Track card selection for Tools card debugging
                card_names = [c.name for c in selected_cards]
                card_ids = [getattr(c, "card_id", "no-id") for c in selected_cards]
                logger.info(
                    f"SelectCards: Auto-selected and stored {len(selected_cards)} cards in variable '{self.store_result}': {card_names} (IDs: {card_ids})"
                )
                logger.debug(
                    f"SelectCards: Variable state after auto-selection - {self.store_result}: {context.get_variable(self.store_result)}"
                )

                context.add_result(
                    f"Auto-selected {len(selected_cards)} cards by {self.selection_type}"
                )
                logger.debug(f"Auto-selected {len(selected_cards)} cards")
                return ActionResult.SUCCESS

        # Check if we're in test mode and should auto-select
        if test_mode and len(eligible_cards) > 0:
            # Auto-select based on test strategy
            test_strategy = context.get_variable("test_auto_select", "first")
            selected = []

            if test_strategy == "first":
                # Select first eligible card(s) up to max_count
                selected = eligible_cards[: min(self.max_count, len(eligible_cards))]
            elif test_strategy == "all":
                # Select all eligible cards up to max_count
                selected = eligible_cards[: self.max_count]
            elif test_strategy == "none":
                # Select no cards (for optional selections)
                selected = []

            # SelectCards only SELECTS cards - removal is done by subsequent actions
            # Store the selection
            context.set_variable(self.store_result, selected)
            context.set_variable("selected_cards", selected)

            # CRITICAL LOGGING: Track card selection for Tools card debugging
            card_names = [c.name for c in selected]
            card_ids = [getattr(c, "card_id", "no-id") for c in selected]
            logger.info(
                f"SelectCards: Stored {len(selected)} cards in variable '{self.store_result}': {card_names} (IDs: {card_ids})"
            )
            logger.debug(
                f"SelectCards: Context variables after interaction - {self.store_result}: {context.get_variable(self.store_result)}, selected_cards: {context.get_variable('selected_cards')}"
            )

            if selected:
                context.add_result(
                    f"Test mode: auto-selected {', '.join([c.name for c in selected])}"
                )
            else:
                context.add_result("Test mode: selected no cards")
            return ActionResult.SUCCESS

        # If not enough eligible cards to meet the minimum (handled earlier for both optional/non-optional)
        # Do NOT fail here; zero/insufficient cards should gracefully no-op to allow dogma to proceed.
        # This avoids breaking demands when opponents cannot comply.

        # Check if we need player interaction
        if len(eligible_cards) == 0:
            # For no cards available, just auto-skip without creating invalid interaction
            # Pydantic validation requires max_count >= 1, so we can't create interaction with max_count=0
            context.set_variable(self.store_result, [])
            if self.is_optional:
                context.add_result("No cards available to select (optional)")
            else:
                context.add_result("No cards available to select")
            return ActionResult.SUCCESS

        # Auto-select if there's exactly one eligible card and max_count is 1
        # BUT ONLY if the selection is NOT optional (optional selections should always ask)
        # AND not forcing manual selection for demands
        force_manual = False
        try:
            force_manual = bool(context.get_variable("force_manual_selection"))
        except Exception:
            force_manual = False

        if (
            len(eligible_cards) == 1
            and self.max_count == 1
            and not treat_as_optional
            and not force_manual
        ):
            selected_card = eligible_cards[0]

            # SelectCards only SELECTS cards - removal is done by subsequent actions
            context.set_variable(self.store_result, [selected_card])
            context.set_variable("selected_cards", [selected_card])
            context.add_result(
                f"Auto-selected {selected_card.name} (only eligible card)"
            )
            logger.debug(
                f"Auto-selected {selected_card.name} as it's the only eligible card"
            )
            return ActionResult.SUCCESS

        if (
            force_manual  # CRITICAL FIX: Create interaction when manual selection is forced (demands)
            or (self.max_count > 1 and len(eligible_cards) > self.max_count)
            or (self.max_count == 1 and len(eligible_cards) > 1)
            or (
                treat_as_optional
                and len(eligible_cards) > 0
                and len(eligible_cards) >= self.min_count
            )
        ):
            # Create final interaction request using StandardInteractionBuilder
            logger.debug(
                "SelectCards requires interaction - creating final interaction request"
            )

            # Build message
            max_available = min(self.max_count, len(eligible_cards))

            # Use custom message if provided, otherwise build default
            if self.message:
                message = self.message
            else:
                if self.min_count == max_available:
                    count_text = str(self.min_count)
                else:
                    count_text = f"{self.min_count}-{max_available}"

                # Indicate DEMAND context for AI players to understand they're giving up cards
                if force_manual:
                    message = f"DEMAND: Select {count_text} cards from {self.source} to transfer to opponent"
                else:
                    message = f"Select {count_text} cards from {self.source}"

            # Create the final interaction request - no more translations needed!

            # PHASE 1A FIX: Map "active"/"opponent" to "current_player" for clickability metadata
            # SelectCards uses "active"/"opponent" but StandardInteractionBuilder expects
            # "current_player" or actual player IDs.
            # In demand contexts, context.player is ALREADY set to the specific opponent,
            # so "opponent" should also map to "current_player" (the current context player).
            source_player_normalized = self.player
            if self.player in ["active", "opponent"]:
                source_player_normalized = "current_player"

            interaction_request = StandardInteractionBuilder.create_card_selection_request(
                eligible_cards=eligible_cards,
                min_count=self.min_count,
                max_count=max_available,
                message=message,
                is_optional=treat_as_optional,
                source=self.source,
                source_player=source_player_normalized,  # Pass normalized source_player for clickability
                execution_results=list(context.results) if context.results else None,
                context=context,  # PHASE 1A: Pass context for eligibility metadata
            )

            # Use the player from context - phase layer has already set the correct player
            target_player_id = getattr(context.player, "id", None)
            logger.debug(
                f"SELECT_CARDS DEBUG: Building interaction for player {context.player.name} (ID: {context.player.id})"
            )
            logger.debug(
                f"SELECT_CARDS DEBUG: eligible_cards = {[c.name for c in eligible_cards[:5]]}"
            )
            logger.debug(f"SelectCards: Targeting player {context.player.name}")

            interaction_request = attach_player_to_interaction(
                interaction_request,
                target_player_id,
                getattr(context.game, "game_id", None),
            )

            if os.getenv("DOGMA_INTERACTION_DEBUG", "false").lower() == "true":
                logger.info(
                    f"DEBUG SelectCards Interaction: eligible={len(eligible_cards)}, min={self.min_count}, max={max_available}, optional={treat_as_optional}, store={self.store_result}"
                )
                # Handle both DogmaInteractionRequest objects and dictionaries
                if hasattr(interaction_request, "type"):
                    # DogmaInteractionRequest object
                    request_type = interaction_request.type
                    data_type = (
                        safe_get(interaction_request.data, "type", "unknown")
                        if interaction_request.data
                        else "unknown"
                    )
                else:
                    # Dictionary
                    request_type = safe_get(interaction_request, "type")
                    data_type = safe_get(
                        safe_get(interaction_request, "data", {}), "type"
                    )

                logger.info(
                    f"DEBUG SelectCards Interaction Request: type={request_type}, data_type={data_type}"
                )

            # Activity log: card selection interaction
            try:
                if activity_logger:
                    game_id = getattr(context.game, "game_id", None)
                    player_id = getattr(context.player, "id", None)
                    card_name = getattr(context.card, "name", None)

                    # Construct human-readable message
                    if treat_as_optional:
                        msg = f"Select up to {max_available} cards from {self.source} (optional)"
                    elif self.min_count == max_available:
                        msg = f"Select {max_available} cards from {self.source}"
                    else:
                        msg = f"Select {self.min_count}-{max_available} cards from {self.source}"

                    activity_logger.log_game_event(
                        event_type=EventType.DOGMA_CARD_SELECTION,
                        game_id=str(game_id) if game_id else "test-game",
                        player_id=str(player_id) if player_id else None,
                        data={
                            "card_name": card_name,
                            "eligible_count": len(eligible_cards),
                            "min": self.min_count,
                            "max": max_available,
                            "is_optional": bool(treat_as_optional),
                            "source": self.source,
                            "store_result": self.store_result,
                            "selection_type": self.selection_type or "manual",
                        },
                        message=msg,
                    )
            except Exception:
                pass

            # Store store_result so _apply_interaction_response knows where to put the response
            # CRITICAL: This must be set BEFORE final_interaction_request to avoid race conditions
            context.set_variable("pending_store_result", self.store_result)

            # Store the final WebSocket-ready request
            context.set_variable("final_interaction_request", interaction_request)

            # Validate the request (defensive programming)
            is_valid, error = StandardInteractionBuilder.validate_interaction_request(
                interaction_request
            )
            if not is_valid:
                logger.error(f"Created invalid interaction request: {error}")
                # Fall back to auto-select rather than break the game
                context.set_variable(
                    self.store_result, eligible_cards[: self.max_count]
                )
                context.add_result(
                    f"Auto-selected {len(eligible_cards[:self.max_count])} cards due to validation error"
                )
                return ActionResult.SUCCESS

            return ActionResult.REQUIRES_INTERACTION

        # Auto-select if we have exactly the right number of cards or if selection is mandatory with limited options
        # But only if we didn't already set up a pending action above
        # IMPORTANT: Don't auto-select if this is an optional selection - always ask the user

        # DEBUG: Log the critical auto-select logic decision
        logger.debug(
            f"SelectCards DEBUG - Auto-select decision: eligible_cards={len(eligible_cards)}, min_count={self.min_count}, max_count={self.max_count}, treat_as_optional={treat_as_optional}"
        )

        # Allow forcing manual selection via context flag to support cases where
        # the UI must confirm even when there is an exact match.
        force_manual = False
        try:
            force_manual = bool(context.get_variable("force_manual_selection"))
        except Exception:
            force_manual = False

        if (
            not force_manual
            and len(eligible_cards) == self.min_count
            and len(eligible_cards) == self.max_count
            and not treat_as_optional  # Only auto-select if NOT optional
        ):
            # Exact match - auto-select (but only for mandatory selections)
            logger.debug(
                f"SelectCards DEBUG - EXACT MATCH AUTO-SELECT: {[c.name for c in eligible_cards]}"
            )
            selected = eligible_cards

            # SelectCards only SELECTS cards - removal is done by subsequent actions
            context.set_variable(self.store_result, selected)
            context.add_result(
                f"Auto-selected {len(selected)} cards from {self.source} (exact match)"
            )
            return ActionResult.SUCCESS
        elif (
            not force_manual
            and not treat_as_optional
            and len(eligible_cards) <= self.max_count
        ):
            # Mandatory selection with all cards fitting - auto-select all
            selected = eligible_cards

            # SelectCards only SELECTS cards - removal is done by subsequent actions
            context.set_variable(self.store_result, selected)
            context.add_result(
                f"Auto-selected all {len(selected)} available cards from {self.source}"
            )
            return ActionResult.SUCCESS

        # No cards available or optional with no selection made
        context.set_variable(self.store_result, [])
        return ActionResult.SUCCESS

    def _get_source_cards(self, context: ActionContext) -> list:
        """Get cards from the specified source"""
        from action_primitives.utils import CardSourceResolver

        # Handle explicit player parameter first
        if self.player:
            if self.player == "active":
                # Get cards from the active player (same logic as TransferBetweenPlayers)
                # In a demand context, active means the demanding player, not context.player
                active_player = self._get_active_player(context)
                if self.source == "board_top" or self.source == "board":
                    return active_player.board.get_top_cards()
                elif self.source == "hand":
                    return active_player.hand
                elif self.source == "score" or self.source == "score_pile":
                    return active_player.score_pile
            elif self.player == "opponent":
                # Get cards from opponent(s)
                all_cards = []
                if hasattr(context.game, "players"):
                    for player in context.game.players:
                        if player.id != context.player.id:
                            if self.source == "board_top" or self.source == "board":
                                all_cards.extend(player.board.get_top_cards())
                            elif self.source == "hand":
                                all_cards.extend(player.hand)
                            elif self.source == "score" or self.source == "score_pile":
                                all_cards.extend(player.score_pile)
                return all_cards

        # Handle target_player for multi-player sources
        if self.target_player:
            all_cards = []
            if self.target_player == "opponent" or self.target_player == "any_opponent":
                # In a demand context, "opponent" means the current player (victim)
                # This is because demands are executed FROM the victim's perspective
                if hasattr(context, "demanding_player") and context.demanding_player:
                    # We're in a demand context - get cards from current player (the victim)
                    if self.source == "board_top" or self.source == "board":
                        top_cards = context.player.board.get_top_cards()
                        logger.info(
                            f"SelectCards: demand context, getting board_top cards from victim {context.player.name}: {[c.name for c in top_cards]}"
                        )
                        all_cards.extend(top_cards)
                    elif self.source == "hand":
                        all_cards.extend(context.player.hand)
                    elif self.source == "score" or self.source == "score_pile":
                        all_cards.extend(context.player.score_pile)
                else:
                    # Normal context - get cards from all opponents
                    if hasattr(context.game, "players"):
                        for player in context.game.players:
                            if player.id != context.player.id:
                                if self.source == "board_top" or self.source == "board":
                                    all_cards.extend(player.board.get_top_cards())
                                elif self.source == "hand":
                                    all_cards.extend(player.hand)
                                elif (
                                    self.source == "score"
                                    or self.source == "score_pile"
                                ):
                                    all_cards.extend(player.score_pile)
                return all_cards
            elif self.target_player == "all":
                # Get cards from all players including current
                if hasattr(context.game, "players"):
                    for player in context.game.players:
                        if self.source == "board_top" or self.source == "board":
                            all_cards.extend(player.board.get_top_cards())
                        elif self.source == "hand":
                            all_cards.extend(player.hand)
                        elif self.source == "score" or self.source == "score_pile":
                            all_cards.extend(player.score_pile)
                return all_cards

        # Default to current player's cards
        return CardSourceResolver.get_cards(context, self.source)

    def _apply_filters(
        self, context: ActionContext, cards: list, criteria: dict[str, Any]
    ) -> list:
        """Apply filtering criteria to cards"""
        # First filter out any None cards
        filtered = [card for card in cards if card is not None]

        if not criteria:
            return filtered

        # Filter by color (support both singular and plural forms)
        if "color" in criteria:
            # Handle singular form
            allowed_colors = [criteria["color"]]
        elif "colors" in criteria:
            # Handle plural form
            allowed_colors = criteria["colors"]
        else:
            allowed_colors = None

        if allowed_colors:
            filtered = [
                c
                for c in filtered
                if hasattr(c, "color")
                and (c.color.value if hasattr(c.color, "value") else str(c.color))
                in allowed_colors
            ]

        # Filter by NOT color
        if "not_color" in criteria:
            excluded_color = criteria["not_color"]
            filtered = [
                c
                for c in filtered
                if hasattr(c, "color")
                and (c.color.value if hasattr(c.color, "value") else str(c.color))
                != excluded_color
            ]

        # Filter by symbol requirements
        if "symbols" in criteria:
            required_symbols = criteria["symbols"]
            filtered = [
                c
                for c in filtered
                if hasattr(c, "symbols")
                and any(sym in c.symbols for sym in required_symbols)
            ]

        # Filter by specific symbol
        if "symbol" in criteria:
            from models.card import Symbol

            symbol_name = criteria["symbol"].upper()
            if hasattr(Symbol, symbol_name):
                required_symbol = getattr(Symbol, symbol_name)
                filtered = [
                    c
                    for c in filtered
                    if hasattr(c, "symbols") and required_symbol in c.symbols
                ]

        # Filter by specific symbol using has_symbol key
        if "has_symbol" in criteria:
            from models.card import Symbol

            symbol_name = criteria["has_symbol"].upper()
            logger.info(f"Filter: checking for symbol {symbol_name}")
            if hasattr(Symbol, symbol_name):
                required_symbol = getattr(Symbol, symbol_name)
                logger.info(f"Filter: required_symbol = {required_symbol}")
                for c in filtered:
                    if hasattr(c, "symbols"):
                        logger.info(f"  Card {c.name} has symbols: {c.symbols}")
                filtered = [
                    c
                    for c in filtered
                    if hasattr(c, "symbols") and required_symbol in c.symbols
                ]
                logger.info(
                    f"Filter: after has_symbol filter, {len(filtered)} cards remain"
                )

        # Filter by NOT having specific symbol
        if "not_has_symbol" in criteria:
            from models.card import Symbol

            symbol_name = criteria["not_has_symbol"].upper()
            if hasattr(Symbol, symbol_name):
                excluded_symbol = getattr(Symbol, symbol_name)
                filtered = [
                    c
                    for c in filtered
                    if hasattr(c, "symbols") and excluded_symbol not in c.symbols
                ]

        # Filter by age range
        if "age" in criteria:
            # Exact age match
            filtered = [
                c for c in filtered if hasattr(c, "age") and c.age == criteria["age"]
            ]
        if "min_age" in criteria:
            filtered = [
                c
                for c in filtered
                if hasattr(c, "age") and c.age >= criteria["min_age"]
            ]
        if "max_age" in criteria:
            filtered = [
                c
                for c in filtered
                if hasattr(c, "age") and c.age <= criteria["max_age"]
            ]

        # Filter by name pattern
        if "name_contains" in criteria:
            pattern = criteria["name_contains"].lower()
            filtered = [
                c for c in filtered if hasattr(c, "name") and pattern in c.name.lower()
            ]

        # Filter by color ON board (for cards like Code of Laws)
        if criteria.get("color_on_board"):
            # Get colors on the player's board
            board_colors = set()
            if hasattr(context, "player") and hasattr(context.player, "board"):
                board = context.player.board
                for color, _ in BoardColorIterator.iterate_non_empty_stacks(board):
                    board_colors.add(color)

            logger.debug(f"Board colors for color_on_board filter: {board_colors}")
            logger.debug(
                f"Cards before filter: {[(c.name, c.color.value if hasattr(c.color, 'value') else str(c.color)) for c in filtered if hasattr(c, 'color')]}"
            )

            # If no colors on board, allow all cards (since tucking would start a new color)
            if board_colors:
                # Filter to cards with colors ON board
                filtered = [
                    c
                    for c in filtered
                    if hasattr(c, "color")
                    and (c.color.value if hasattr(c.color, "value") else str(c.color))
                    in board_colors
                ]
            # else: keep all cards since any can be tucked to start a new color stack

            logger.debug(
                f"Cards after color_on_board filter: {[c.name for c in filtered]}"
            )

        # Filter by color not on board
        if criteria.get("color_not_on_board"):
            # Get colors on the player's board
            board_colors = set()
            if hasattr(context, "player") and hasattr(context.player, "board"):
                board = context.player.board
                for color, _ in BoardColorIterator.iterate_non_empty_stacks(board):
                    board_colors.add(color)

            logger.debug(f"Board colors: {board_colors}")
            logger.debug(
                f"Cards before filter: {[(c.name, c.color.value if hasattr(c.color, 'value') else str(c.color)) for c in filtered if hasattr(c, 'color')]}"
            )

            # Filter to cards with colors not on board
            filtered = [
                c
                for c in filtered
                if hasattr(c, "color")
                and (c.color.value if hasattr(c.color, "value") else str(c.color))
                not in board_colors
            ]

            logger.debug(
                f"Cards after color_not_on_board filter: {[c.name for c in filtered]}"
            )

        # Filter by color not on demanding player's board (for demands like Monotheism)
        if criteria.get("color_not_on_demanding_board"):
            # Get colors on the demanding player's board
            board_colors = set()
            demanding_player = context.get_variable("demanding_player")
            if demanding_player and hasattr(demanding_player, "board"):
                board = demanding_player.board
                for color, _ in BoardColorIterator.iterate_non_empty_stacks(board):
                    board_colors.add(color)

            logger.debug(f"Demanding player board colors: {board_colors}")
            logger.debug(
                f"Cards before filter: {[(c.name, c.color.value if hasattr(c.color, 'value') else str(c.color)) for c in filtered if hasattr(c, 'color')]}"
            )

            # Filter to cards with colors not on demanding player's board
            filtered = [
                c
                for c in filtered
                if hasattr(c, "color")
                and (c.color.value if hasattr(c.color, "value") else str(c.color))
                not in board_colors
            ]

            logger.debug(
                f"Cards after color_not_on_demanding_board filter: {[c.name for c in filtered]}"
            )

        return filtered

    def _get_active_player(self, context: ActionContext):
        """Get the active/demanding player using the same logic as TransferBetweenPlayers"""
        # First check if demanding_player is directly set in context
        demanding_player = context.get_variable("demanding_player")
        if demanding_player:
            return demanding_player
        # Also check if it's set as an attribute
        if hasattr(context, "demanding_player") and context.demanding_player:
            return context.demanding_player
        # Otherwise, get from pending action context
        if hasattr(context.game, "state") and hasattr(
            context.game.state, "pending_dogma_action"
        ):
            pending_action = context.game.state.pending_dogma_action
            if pending_action and hasattr(pending_action, "original_player_id"):
                demanding_id = pending_action.original_player_id
                return next(
                    (p for p in context.game.players if p.id == demanding_id), None
                )
        # Fallback to context.player
        return context.player

    def _apply_dynamic_filters(self, context: ActionContext, cards: list) -> list:
        """Apply dynamic filters that need runtime evaluation"""
        if not self.dynamic_filter:
            return cards

        # Dynamic filters can reference variables
        filtered = cards

        if "variable_age" in self.dynamic_filter:
            age_var = self.dynamic_filter["variable_age"]
            if context.has_variable(age_var):
                target_age = context.get_variable(age_var)
                filtered = [
                    c for c in filtered if hasattr(c, "age") and c.age == target_age
                ]

        return filtered

    def _remove_card_from_source(self, context: ActionContext, card) -> bool:
        """
        Remove card from its source location (implements "move object" semantics).

        This is called when a card is selected to remove it from the player's hand/board/score_pile
        BEFORE storing it in the context variable. This ensures cards truly "move" rather than
        being copied.

        Args:
            context: Action context
            card: Card to remove from source

        Returns:
            True if card was successfully removed, False otherwise
        """
        from utils.card_utils import get_card_name

        if self.source == "hand":
            if card in context.player.hand:
                context.player.hand.remove(card)
                logger.debug(f"Removed {get_card_name(card)} from hand")
                return True
            else:
                logger.warning(
                    f"Card {get_card_name(card)} not found in hand for removal"
                )
                return False

        elif self.source == "board" or self.source == "board_top":
            # Need to find which color stack the card is in
            board = context.player.board
            for color in ["red", "blue", "green", "yellow", "purple"]:
                stack = getattr(board, f"{color}_cards", [])
                if card in stack:
                    stack.remove(card)
                    logger.debug(f"Removed {get_card_name(card)} from {color} board")
                    return True
            logger.warning(f"Card {get_card_name(card)} not found on board for removal")
            return False

        elif self.source == "score_pile" or self.source == "score":
            if (
                hasattr(context.player, "score_pile")
                and card in context.player.score_pile
            ):
                context.player.score_pile.remove(card)
                logger.debug(f"Removed {get_card_name(card)} from score pile")
                return True
            else:
                logger.warning(
                    f"Card {get_card_name(card)} not found in score pile for removal"
                )
                return False

        # Unknown source or not handled
        logger.warning(f"Unknown source '{self.source}' for card removal")
        return False

    def _get_selection_candidates(self, cards: list) -> list:
        """Get cards that match the selection criteria"""
        if not cards:
            return []

        if self.selection_type == "highest_age":
            # Find all cards with the highest age
            max_age = max(getattr(card, "age", 0) for card in cards)
            return [card for card in cards if getattr(card, "age", 0) == max_age]
        elif self.selection_type == "lowest_age":
            # Find all cards with the lowest age
            min_age = min(getattr(card, "age", 0) for card in cards)
            return [card for card in cards if getattr(card, "age", 0) == min_age]
        elif self.selection_type == "random":
            # For random selection, all cards are candidates
            return cards
        else:
            # Default to all cards if selection type unknown
            return cards
