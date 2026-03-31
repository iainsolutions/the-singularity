"""
TuckCard Action Primitive

Tucks cards under existing stacks on the player's board.
"""

import logging
from typing import Any

from utils.card_utils import get_card_name

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class TuckCard(ActionPrimitive):
    """
    Primitive for tucking cards under existing stacks on the board.

    Parameters:
    - cards: Variable name containing cards to tuck (default: "selected_cards")
    - from: Where to remove cards from ("hand", "revealed_cards")
    - color_filter: Optional color restriction for tucking
    - store_color: Variable to store the color(s) tucked
    - auto_splay: Whether to automatically splay after tucking
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
        # Get cards to tuck
        # CRITICAL FIX: Handle special case of "cards": "hand" meaning all cards from player's hand
        # This supports the Socialism card pattern: {"type": "TuckCard", "count": "all", "cards": "hand"}
        if self.cards_var == "hand":
            # Get all cards from player's hand
            cards_to_tuck = list(context.player.hand) if context.player.hand else []
            logger.debug(f"TuckCard: Getting all {len(cards_to_tuck)} cards from player's hand")
        else:
            cards_to_tuck = context.get_variable(self.cards_var, [])
            logger.debug(f"TuckCard: Looking for cards in variable '{self.cards_var}'")

        if not cards_to_tuck:
            context.add_result("No cards to tuck")
            return ActionResult.SUCCESS

        # Ensure it's a list (must be done before len() checks)
        if not isinstance(cards_to_tuck, list):
            cards_to_tuck = [cards_to_tuck]

        logger.debug(f"TuckCard: Found {len(cards_to_tuck)} cards")
        logger.debug(f"TuckCard: Cards = {[get_card_name(c) for c in cards_to_tuck]}")
        logger.info(
            f"🔧 TuckCard: Card types = {[type(c).__name__ for c in cards_to_tuck]}"
        )
        for i, card in enumerate(cards_to_tuck):
            logger.info(
                f"🔧 TuckCard: Card {i}: hasattr name={hasattr(card, 'name')}, hasattr color={hasattr(card, 'color')}, repr={repr(card)[:100]}"
            )

        tucked_count = 0
        colors_tucked = set()

        for card in cards_to_tuck:
            logger.debug(f"TuckCard: Checking if can tuck {get_card_name(card)}")
            can_tuck = self._can_tuck_card(context, card)
            logger.debug(f"TuckCard: _can_tuck_card returned {can_tuck}")
            if can_tuck:
                logger.debug(f"TuckCard: Attempting to tuck {get_card_name(card)}")
                tucked = self._tuck_card(context, card)
                logger.debug(f"TuckCard: _tuck_card returned {tucked}")
                if tucked:
                    tucked_count += 1
                    # Track colors for auto-splay (CardColor is str enum)
                    if hasattr(card, "color"):
                        # Store the actual color value, not the enum string representation
                        color = card.color
                        if hasattr(color, "value"):
                            colors_tucked.add(color.value)
                        else:
                            colors_tucked.add(str(color))

        # Store results
        context.set_variable("tucked_count", tucked_count)

        if self.store_color and colors_tucked:
            # Store the first color tucked (for conditional actions)
            context.set_variable(self.store_color, next(iter(colors_tucked)))

        # Auto-splay if configured
        if self.auto_splay and colors_tucked:
            for color in colors_tucked:
                self._splay_color(context, color)

        if tucked_count > 0:
            context.add_result(f"Archived {tucked_count} cards")
            logger.info(f"Tucked {tucked_count} cards under board stacks")

            # Track for Monument achievement
            if hasattr(context, "game") and hasattr(context, "player"):
                try:
                    from special_achievements import special_achievement_checker

                    special_achievement_checker.track_card_action(
                        context.game.game_id, context.player.id, "tuck", tucked_count
                    )
                except ImportError:
                    # Special achievements not available
                    pass
        else:
            context.add_result("No cards were archived")

        return ActionResult.SUCCESS

    def _can_tuck_card(self, context: ActionContext, card) -> bool:
        """Check if a card can be tucked"""
        logger.info(f"🔍 TuckCard._can_tuck_card: Checking card: {get_card_name(card) if card else 'None'}")
        
        if not card:
            logger.error("TuckCard._can_tuck_card: card is None or False")
            return False

        logger.info(f"🔍 TuckCard._can_tuck_card: Card color: {getattr(card, 'color', 'NO_COLOR')}")
        logger.info(f"🔍 TuckCard._can_tuck_card: color_filter: {self.color_filter}")

        # Check color filter if specified
        if self.color_filter:
            card_color = self._get_card_color(card)
            logger.info(f"🔍 TuckCard._can_tuck_card: card_color={card_color}, color_filter={self.color_filter}")
            if card_color != self.color_filter:
                logger.info(f"🔍 TuckCard._can_tuck_card: Card color {card_color} doesn't match filter {self.color_filter}")
                return False

        # Check if player has cards of this color on board
        if not hasattr(context.player, "board"):
            logger.error("TuckCard._can_tuck_card: context.player has no board attribute")
            return False

        card_color = self._get_card_color(card)
        logger.info(f"🔍 TuckCard._can_tuck_card: card_color = {card_color}")
        
        if not card_color:
            logger.error(f"TuckCard._can_tuck_card: Could not determine card color for {get_card_name(card)}")
            return False

        # Check if there's a stack to tuck under
        stack_attr = f"{card_color}_cards"
        logger.info(f"🔍 TuckCard._can_tuck_card: Checking for stack attribute: {stack_attr}")
        logger.info(f"🔍 TuckCard._can_tuck_card: hasattr(context.player.board, {stack_attr}) = {hasattr(context.player.board, stack_attr)}")
        
        if hasattr(context.player.board, stack_attr):
            stack = getattr(context.player.board, stack_attr)
            logger.info(f"🔍 TuckCard._can_tuck_card: Stack length = {len(stack)}")
            logger.info(f"🔍 TuckCard._can_tuck_card: Stack contents: {[get_card_name(c) for c in stack]}")
            # FIXED: Allow tucking to empty stack (creates new stack at bottom position)
            result = True  # Can always tuck to a color stack, even if empty
            logger.info(f"🔍 TuckCard._can_tuck_card: Returning {result} (stack has {len(stack)} cards)")
            return result
        else:
            logger.error(f"TuckCard._can_tuck_card: Board does not have attribute {stack_attr}")
            logger.info(f"🔍 TuckCard._can_tuck_card: Available board attributes: {[attr for attr in dir(context.player.board) if not attr.startswith('_')]}")
            return False

    def _tuck_card(self, context: ActionContext, card) -> bool:
        """Tuck a single card under the appropriate stack"""
        if not card:
            logger.error("TuckCard._tuck_card: card is None or False")
            return False

        logger.info(f"🔧 TuckCard._tuck_card: Starting tuck for card: {get_card_name(card)}")
        logger.info(f"🔧 TuckCard._tuck_card: Card ID: {getattr(card, 'card_id', 'NO_ID')}")
        logger.info(f"🔧 TuckCard._tuck_card: Card color: {getattr(card, 'color', 'NO_COLOR')}")
        logger.info(f"🔧 TuckCard._tuck_card: source_location: {self.source_location}")

        # MOVE OBJECT ARCHITECTURE: Card should already be removed by SelectCards
        # Defensive check: warn if card still in source (backward compatibility)
        if self.source_location == "hand":
            logger.info(f"🔧 TuckCard._tuck_card: Checking if card is in player hand...")
            logger.info(f"🔧 TuckCard._tuck_card: Player hand contents: {[get_card_name(c) for c in context.player.hand]}")
            logger.info(f"🔧 TuckCard._tuck_card: Player hand IDs: {[getattr(c, 'card_id', 'NO_ID') for c in context.player.hand]}")
            
            if card in context.player.hand:
                logger.warning(
                    f"WARNING: Card {get_card_name(card)} still in hand - "
                    f"SelectCards should have removed it. Removing now for safety."
                )
                context.player.hand.remove(card)
                logger.info(f"🔧 TuckCard._tuck_card: Removed card from hand. New hand: {[get_card_name(c) for c in context.player.hand]}")
            else:
                logger.info(f"🔧 TuckCard._tuck_card: Card not found in hand (already removed)")
        # Could add other source locations here with similar defensive checks

        # Tuck under the appropriate color stack
        card_color = self._get_card_color(card)
        logger.info(f"🔧 TuckCard._tuck_card: card_color = {card_color}")
        if not card_color:
            logger.error(f"TuckCard._tuck_card: Failed to get card color for {get_card_name(card)}")
            return False

        stack_attr = f"{card_color}_cards"
        logger.info(f"🔧 TuckCard._tuck_card: stack_attr = {stack_attr}")
        logger.info(f"🔧 TuckCard._tuck_card: hasattr(context.player.board, stack_attr) = {hasattr(context.player.board, stack_attr)}")
        
        if hasattr(context.player.board, stack_attr):
            stack = getattr(context.player.board, stack_attr)
            logger.info(f"🔧 TuckCard._tuck_card: Current stack before tuck: {[get_card_name(c) for c in stack]}")
            
            # Insert at the beginning (bottom) of the stack
            stack.insert(0, card)
            logger.info(f"🔧 TuckCard._tuck_card: Card inserted at position 0")
            logger.info(f"🔧 TuckCard._tuck_card: Stack after tuck: {[get_card_name(c) for c in stack]}")

            # Record state change
            context.state_tracker.record_tuck(
                player_name=context.player.name,
                card_name=card.name,
                color=card_color,
                context=context.get_variable("current_effect_context", "tuck"),
            )

            logger.info(f"✅ TuckCard._tuck_card: Successfully tucked {get_card_name(card)} under {card_color} stack")
            return True
        else:
            logger.error(f"TuckCard._tuck_card: Board does not have attribute {stack_attr}")
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
        """Auto-splay a color after tucking"""
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
