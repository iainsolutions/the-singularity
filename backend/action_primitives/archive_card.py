"""
ArchiveCard Action Primitive

Tucks cards under existing stacks on the player's board.
"""

import logging
from typing import Any

from utils.card_utils import get_card_name

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class ArchiveCard(ActionPrimitive):
    """
    Primitive for archiving cards under existing stacks on the board.

    Parameters:
    - cards: Variable name containing cards to archive (default: "selected_cards")
    - from: Where to remove cards from ("hand", "revealed_cards")
    - color_filter: Optional color restriction for archiving
    - store_color: Variable to store the color(s) archived
    - auto_splay: Whether to automatically splay after archiving
    - splay_direction: Direction to splay if auto_splay is true
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.cards_var = config.get("cards", "selected_cards")
        self.source_location = config.get("from", "hand")
        self.store_color = config.get("store_color")
        self.color_filter = config.get("color_filter")
        self.auto_splay = config.get("auto_splay", False)
        self.splay_direction = config.get("splay_direction", "left")

    def execute(self, context: ActionContext) -> ActionResult:
        """Tuck cards under existing board stacks"""
        # Get cards to archive
        # CRITICAL FIX: Handle special case of "cards": "hand" meaning all cards from player's hand
        # This supports the Socialism card pattern: {"type": "ArchiveCard", "count": "all", "cards": "hand"}
        if self.cards_var == "hand":
            # Get all cards from player's hand
            cards_to_archive = list(context.player.hand) if context.player.hand else []
            logger.debug(f"ArchiveCard: Getting all {len(cards_to_archive)} cards from player's hand")
        else:
            cards_to_archive = context.get_variable(self.cards_var, [])
            logger.debug(f"ArchiveCard: Looking for cards in variable '{self.cards_var}'")

        if not cards_to_archive:
            context.add_result("No cards to archive")
            return ActionResult.SUCCESS

        # Ensure it's a list (must be done before len() checks)
        if not isinstance(cards_to_archive, list):
            cards_to_archive = [cards_to_archive]

        logger.debug(f"ArchiveCard: Found {len(cards_to_archive)} cards")
        logger.debug(f"ArchiveCard: Cards = {[get_card_name(c) for c in cards_to_archive]}")
        logger.info(
            f"🔧 ArchiveCard: Card types = {[type(c).__name__ for c in cards_to_archive]}"
        )
        for i, card in enumerate(cards_to_archive):
            logger.info(
                f"🔧 ArchiveCard: Card {i}: hasattr name={hasattr(card, 'name')}, hasattr color={hasattr(card, 'color')}, repr={repr(card)[:100]}"
            )

        archived_count = 0
        colors_archived = set()

        for card in cards_to_archive:
            logger.debug(f"ArchiveCard: Checking if can archive {get_card_name(card)}")
            can_archive = self._can_archive_card(context, card)
            logger.debug(f"ArchiveCard: _can_archive_card returned {can_archive}")
            if can_archive:
                logger.debug(f"ArchiveCard: Attempting to archive {get_card_name(card)}")
                archived = self._archive_card(context, card)
                logger.debug(f"ArchiveCard: _archive_card returned {archived}")
                if archived:
                    archived_count += 1
                    # Track colors for auto-splay (CardColor is str enum)
                    if hasattr(card, "color"):
                        # Store the actual color value, not the enum string representation
                        color = card.color
                        if hasattr(color, "value"):
                            colors_archived.add(color.value)
                        else:
                            colors_archived.add(str(color))

        # Store results
        context.set_variable("archived_count", archived_count)

        if self.store_color and colors_archived:
            # Store the first color archived (for conditional actions)
            context.set_variable(self.store_color, next(iter(colors_archived)))

        # Auto-splay if configured
        if self.auto_splay and colors_archived:
            for color in colors_archived:
                self._splay_color(context, color)

        if archived_count > 0:
            context.add_result(f"Archived {archived_count} cards")
            logger.info(f"Archived {archived_count} cards under board stacks")

            # Track for Monument achievement
            if hasattr(context, "game") and hasattr(context, "player"):
                try:
                    from special_achievements import special_achievement_checker

                    special_achievement_checker.track_card_action(
                        context.game.game_id, context.player.id, "archive", archived_count
                    )
                except ImportError:
                    # Special achievements not available
                    pass
        else:
            context.add_result("No cards were archived")

        return ActionResult.SUCCESS

    def _can_archive_card(self, context: ActionContext, card) -> bool:
        """Check if a card can be archived"""
        logger.info(f"🔍 ArchiveCard._can_archive_card: Checking card: {get_card_name(card) if card else 'None'}")
        
        if not card:
            logger.error("ArchiveCard._can_archive_card: card is None or False")
            return False

        logger.info(f"🔍 ArchiveCard._can_archive_card: Card color: {getattr(card, 'color', 'NO_COLOR')}")
        logger.info(f"🔍 ArchiveCard._can_archive_card: color_filter: {self.color_filter}")

        # Check color filter if specified
        if self.color_filter:
            card_color = self._get_card_color(card)
            logger.info(f"🔍 ArchiveCard._can_archive_card: card_color={card_color}, color_filter={self.color_filter}")
            if card_color != self.color_filter:
                logger.info(f"🔍 ArchiveCard._can_archive_card: Card color {card_color} doesn't match filter {self.color_filter}")
                return False

        # Check if player has cards of this color on board
        if not hasattr(context.player, "board"):
            logger.error("ArchiveCard._can_archive_card: context.player has no board attribute")
            return False

        card_color = self._get_card_color(card)
        logger.info(f"🔍 ArchiveCard._can_archive_card: card_color = {card_color}")
        
        if not card_color:
            logger.error(f"ArchiveCard._can_archive_card: Could not determine card color for {get_card_name(card)}")
            return False

        # Check if there's a stack to archive under
        stack_attr = f"{card_color}_cards"
        logger.info(f"🔍 ArchiveCard._can_archive_card: Checking for stack attribute: {stack_attr}")
        logger.info(f"🔍 ArchiveCard._can_archive_card: hasattr(context.player.board, {stack_attr}) = {hasattr(context.player.board, stack_attr)}")
        
        if hasattr(context.player.board, stack_attr):
            stack = getattr(context.player.board, stack_attr)
            logger.info(f"🔍 ArchiveCard._can_archive_card: Stack length = {len(stack)}")
            logger.info(f"🔍 ArchiveCard._can_archive_card: Stack contents: {[get_card_name(c) for c in stack]}")
            # FIXED: Allow archiving to empty stack (creates new stack at bottom position)
            result = True  # Can always tuck to a color stack, even if empty
            logger.info(f"🔍 ArchiveCard._can_archive_card: Returning {result} (stack has {len(stack)} cards)")
            return result
        else:
            logger.error(f"ArchiveCard._can_archive_card: Board does not have attribute {stack_attr}")
            logger.info(f"🔍 ArchiveCard._can_archive_card: Available board attributes: {[attr for attr in dir(context.player.board) if not attr.startswith('_')]}")
            return False

    def _archive_card(self, context: ActionContext, card) -> bool:
        """Tuck a single card under the appropriate stack"""
        if not card:
            logger.error("ArchiveCard._archive_card: card is None or False")
            return False

        logger.info(f"🔧 ArchiveCard._archive_card: Starting archive for card: {get_card_name(card)}")
        logger.info(f"🔧 ArchiveCard._archive_card: Card ID: {getattr(card, 'card_id', 'NO_ID')}")
        logger.info(f"🔧 ArchiveCard._archive_card: Card color: {getattr(card, 'color', 'NO_COLOR')}")
        logger.info(f"🔧 ArchiveCard._archive_card: source_location: {self.source_location}")

        # MOVE OBJECT ARCHITECTURE: Card should already be removed by SelectCards
        # Defensive check: warn if card still in source (backward compatibility)
        if self.source_location == "hand":
            logger.info(f"🔧 ArchiveCard._archive_card: Checking if card is in player hand...")
            logger.info(f"🔧 ArchiveCard._archive_card: Player hand contents: {[get_card_name(c) for c in context.player.hand]}")
            logger.info(f"🔧 ArchiveCard._archive_card: Player hand IDs: {[getattr(c, 'card_id', 'NO_ID') for c in context.player.hand]}")
            
            if card in context.player.hand:
                logger.warning(
                    f"WARNING: Card {get_card_name(card)} still in hand - "
                    f"SelectCards should have removed it. Removing now for safety."
                )
                context.player.hand.remove(card)
                logger.info(f"🔧 ArchiveCard._archive_card: Removed card from hand. New hand: {[get_card_name(c) for c in context.player.hand]}")
            else:
                logger.info(f"🔧 ArchiveCard._archive_card: Card not found in hand (already removed)")
        # Could add other source locations here with similar defensive checks

        # Tuck under the appropriate color stack
        card_color = self._get_card_color(card)
        logger.info(f"🔧 ArchiveCard._archive_card: card_color = {card_color}")
        if not card_color:
            logger.error(f"ArchiveCard._archive_card: Failed to get card color for {get_card_name(card)}")
            return False

        stack_attr = f"{card_color}_cards"
        logger.info(f"🔧 ArchiveCard._archive_card: stack_attr = {stack_attr}")
        logger.info(f"🔧 ArchiveCard._archive_card: hasattr(context.player.board, stack_attr) = {hasattr(context.player.board, stack_attr)}")
        
        if hasattr(context.player.board, stack_attr):
            stack = getattr(context.player.board, stack_attr)
            logger.info(f"🔧 ArchiveCard._archive_card: Current stack before archive: {[get_card_name(c) for c in stack]}")
            
            # Insert at the beginning (bottom) of the stack
            stack.insert(0, card)
            logger.info(f"🔧 ArchiveCard._archive_card: Card inserted at position 0")
            logger.info(f"🔧 ArchiveCard._archive_card: Stack after archive: {[get_card_name(c) for c in stack]}")

            # Record state change
            context.state_tracker.record_archive(
                player_name=context.player.name,
                card_name=card.name,
                color=card_color,
                context=context.get_variable("current_effect_context", "archive"),
            )

            logger.info(f"✅ ArchiveCard._archive_card: Successfully archived {get_card_name(card)} under {card_color} stack")
            return True
        else:
            logger.error(f"ArchiveCard._archive_card: Board does not have attribute {stack_attr}")
            return False

    def _get_card_color(self, card) -> str | None:
        """Get the color of a card as a string (CardColor is str enum)"""
        if hasattr(card, "color"):
            # Use .value to get the string value from CardColor enum
            # str(CardColor.PURPLE) returns "CardColor.PURPLE", not "purple"
            color = card.color
            if hasattr(color, "value"):
                return color.value.lower()
            return str(color).lower()
        return None

    def _splay_color(self, context: ActionContext, color: str):
        """Auto-splay a color after archiving"""
        if not hasattr(context.player, "board"):
            return

        stack_attr = f"{color}_cards"

        if hasattr(context.player.board, stack_attr):
            stack = getattr(context.player.board, stack_attr)
            if len(stack) >= 2:  # Need at least 2 cards to splay
                if not hasattr(context.player.board, "splay_directions"):
                    context.player.board.splay_directions = {}
                context.player.board.splay_directions[color] = self.splay_direction
                context.add_result(f"Proliferated {color} cards {self.splay_direction}")
                logger.debug(f"Auto-splayed {color} cards {self.splay_direction}")
