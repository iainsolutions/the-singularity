"""
MeldCard Action Primitive

Melds cards to the player's board.
"""

import logging
from typing import Any

from logging_config import activity_logger
from utils.card_utils import get_card_name

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class MeldCard(ActionPrimitive):
    """
    Primitive for melding cards to the player's board.

    Parameters:
    - selection: Variable name containing cards to meld (default: "selected_cards")
    - source: Where cards come from ("hand", "score_pile", or "safe" for Unseen expansion)
    - safe_index: Index in Safe to meld from (only used when source="safe")
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.cards_var = config.get("selection", "selected_cards")
        self.source = config.get("source", "hand")
        self.store_color = config.get("store_color")
        self.safe_index = config.get("safe_index")  # NEW: For Unseen expansion

    def execute(self, context: ActionContext) -> ActionResult:
        """Meld cards to the player's board"""
        logger.debug(f"MeldCard.execute: looking for variable '{self.cards_var}'")
        logger.debug(
            f"MeldCard: Current context variables: {list(context.variables.keys())}"
        )

        # Get cards to meld
        cards_to_meld = context.get_variable(self.cards_var, [])

        # Handle empty cards
        if not cards_to_meld:
            context.add_result("No cards to meld")
            return ActionResult.SUCCESS

        # Ensure cards_to_meld is a list
        if not isinstance(cards_to_meld, list):
            cards_to_meld = [cards_to_meld]

        melded_count = 0
        # Get existing melded_cards list to accumulate across multiple MeldCard calls
        # This supports cards like Software that meld sequentially and reference "second_melded"
        melded_cards = context.get_variable("melded_cards", [])
        if not isinstance(melded_cards, list):
            melded_cards = []

        # Track colors melded for store_color parameter
        colors_melded = set()

        for card in cards_to_meld:
            if self._meld_card(context, card):
                melded_count += 1
                melded_cards.append(card)
                # Track color for store_color (CardColor is str enum, can use directly)
                if card and hasattr(card, "color"):
                    colors_melded.add(str(card.color))

        if melded_count > 0:
            # Add detailed logging with card names (melded cards are public)
            card_names = [context.get_public_card_name(card) for card in melded_cards]
            context.add_result(f"Melded {', '.join(card_names)}")

            # Store melded cards for reference by other actions
            context.set_variable("melded_cards", melded_cards)
            if len(melded_cards) >= 1:
                context.set_variable("first_melded", melded_cards[0])
            if len(melded_cards) >= 2:
                context.set_variable("second_melded", melded_cards[1])

            # Store color if requested (for conditional actions)
            if self.store_color and colors_melded:
                context.set_variable(self.store_color, next(iter(colors_melded)))
        else:
            context.add_result("No cards melded")

        return ActionResult.SUCCESS

    def _meld_card(self, context: ActionContext, card) -> bool:
        """
        Meld a single card to the board.

        Returns:
            True if card was successfully melded
        """
        if not card:
            return False

        # DEBUG: Log player context at meld time
        logger.debug(f"MELD_CARD DEBUG: About to meld {get_card_name(card)}")
        logger.debug(
            f"MELD_CARD DEBUG: context.player = {context.player.name if context.player else 'None'}"
        )
        logger.debug(
            f"MELD_CARD DEBUG: context.player.id = {context.player.id if context.player else 'None'}"
        )

        # CRITICAL: Validate destination exists BEFORE removing from source
        if not (
            hasattr(context.player, "board")
            and hasattr(context.player.board, "add_card")
        ):
            logger.error("Player has no board or board.add_card method")
            return False

        # MOVE OBJECT ARCHITECTURE: Card should already be removed by SelectCards
        # Defensive check: warn if card still in source (backward compatibility)
        if self.source == "hand" and card in context.player.hand:
            logger.warning(
                f"WARNING: Card {get_card_name(card)} still in hand - "
                f"SelectCards should have removed it. Removing now for safety."
            )
            context.player.hand.remove(card)
        elif self.source == "score_pile" and hasattr(context.player, "score_pile"):
            if card in context.player.score_pile:
                logger.warning(
                    f"WARNING: Card {get_card_name(card)} still in score pile - "
                    f"SelectCards should have removed it. Removing now for safety."
                )
                context.player.score_pile.remove(card)
        elif self.source == "safe":
            # UNSEEN EXPANSION: Meld from Safe
            # Card should have been removed by SelectCards, but we handle it here
            # since Safe uses index-based removal rather than card object matching
            if hasattr(context.player, "safe") and context.player.safe:
                # Safe index should be provided in config or via variable
                safe_idx = self.safe_index
                if isinstance(safe_idx, str) and context.has_variable(safe_idx):
                    safe_idx = context.get_variable(safe_idx)

                if safe_idx is not None:
                    try:
                        # Remove from Safe (card object passed in should match)
                        removed_card = context.player.remove_from_safe(int(safe_idx))
                        if removed_card != card:
                            logger.warning(
                                f"WARNING: Card mismatch - expected {get_card_name(card)}, "
                                f"got {get_card_name(removed_card)} from Safe index {safe_idx}"
                            )
                            card = removed_card  # Use the actual card from Safe
                    except (ValueError, IndexError) as e:
                        logger.error(f"Failed to remove card from Safe: {e}")
                        return False

        # Get covered card BEFORE melding (for dig event detection - Artifacts expansion)
        covered_card = None
        if hasattr(card, "color"):
            color_stack = context.player.board.get_cards_by_color(str(card.color.value))
            if color_stack:
                covered_card = color_stack[-1]  # Top card before meld

        # Add to board - PlayerBoard.add_card() determines color automatically
        context.player.board.add_card(card)

        # Check for dig event (Artifacts expansion)
        self._check_dig_event(context, card, covered_card)

        # Record state change
        color = None
        try:
            color = str(card.color)
        except (AttributeError, TypeError) as e:
            logger.debug(f"Could not extract color from card: {e}")
            color = None
        context.state_tracker.record_meld(
            player_name=context.player.name,
            card_name=card.name,
            color=color or "unknown",
            context=context.get_variable("current_effect_context", "meld"),
        )

        logger.info(f"Melded {get_card_name(card)} to board")

        # UNSEEN EXPANSION: Rebuild Safeguards when melding from Safe
        # Card may now be visible on board, affecting Safeguard status
        if self.source == "safe" and hasattr(context.game, "expansion_config"):
            if context.game.expansion_config.is_enabled("unseen"):
                try:
                    from game_logic.unseen.safeguard_tracker import SafeguardTracker
                    tracker = SafeguardTracker(context.game)
                    tracker.rebuild_all_safeguards()
                    logger.debug("Rebuilt Safeguards after melding from Safe")
                except Exception as e:
                    logger.error(f"Failed to rebuild Safeguards: {e}")

        # Activity: card melded to board
        try:
            if activity_logger:
                activity_color = None
                try:
                    activity_color = str(card.color)
                except (AttributeError, TypeError) as e:
                    logger.debug(f"Could not extract color for activity log: {e}")
                    activity_color = None
                activity_logger.log_dogma_card_action(
                    game_id=getattr(context.game, "game_id", "test-game"),
                    player_id=getattr(context.player, "id", None) or "player",
                    card_name=getattr(context.card, "name", "Card"),
                    action_type="melded",
                    cards=[{"name": getattr(card, "name", str(card))}],
                    location_from=self.source,
                    location_to=(
                        f"board:{activity_color}" if activity_color else "board"
                    ),
                    is_sharing=bool(context.get_variable("is_sharing_phase", False)),
                )
        except Exception:
            pass

        return True

    def _check_dig_event(self, context: ActionContext, melded_card, covered_card):
        """
        Check if a dig event should trigger (Artifacts expansion).

        Args:
            context: The action context
            melded_card: The card that was just melded
            covered_card: The card that was covered (None if first in stack)
        """
        # Only check if Artifacts expansion is enabled
        if not context.game.expansion_config.is_enabled("artifacts"):
            return

        try:
            from game_logic.artifacts.dig_event_detector import DigEventDetector

            dig_age = DigEventDetector.check_dig_event(
                game=context.game,
                melded_card=melded_card,
                covered_card=covered_card,
                player_id=context.player.id,
            )

            if dig_age is not None:
                # Store dig event for handling after action completes
                # Multiple dig events can accumulate if multiple cards melded
                dig_events = context.get_variable("pending_dig_events", [])
                if not isinstance(dig_events, list):
                    dig_events = []

                dig_events.append(
                    {
                        "dig_age": dig_age,
                        "player_id": context.player.id,
                        "melded_card": melded_card.name,
                        "covered_card": covered_card.name if covered_card else None,
                    }
                )

                context.set_variable("pending_dig_events", dig_events)
                logger.info(
                    f"ARTIFACTS: Dig event detected (age {dig_age}) - stored for processing"
                )
        except Exception as e:
            logger.error(f"ARTIFACTS: Error checking dig event: {e}", exc_info=True)
