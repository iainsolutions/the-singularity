"""
RevealAndProcess Action Primitive

Draws/reveals cards and conditionally processes them.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class RevealAndProcess(ActionPrimitive):
    """
    Draws/reveals cards and conditionally processes them.

    Parameters:
    - source_age: Age to draw from, or variable name
    - count: Number of cards to draw (default: 1)
    - condition_check: What to check on revealed cards
    - success_action: Action to take if condition met
    - failure_action: Action to take if condition not met
    - store_revealed: Variable name to store revealed cards
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        # Support both selection-based and draw-based modes
        self.selection = config.get("selection")  # NEW: Process existing selection
        self.actions = config.get("actions", [])  # NEW: Nested actions to execute
        # Original draw-based parameters
        self.source_age = config.get("source_age", 1)
        self.count = config.get("count", 1)
        self.condition_check = config.get("condition_check")
        self.success_action = config.get("success_action")
        self.failure_action = config.get("failure_action")
        self.store_revealed = config.get("store_revealed", "revealed_cards")

    def execute(self, context: ActionContext) -> ActionResult:
        """Process cards - either from selection or by drawing"""
        # Import here to avoid circular dependency
        from . import create_action_primitive

        # MODE 1: Selection-based (Escapism pattern)
        if self.selection:
            return self._process_selection(context, create_action_primitive)

        # MODE 2: Draw-based (original pattern)
        # Resolve age if it's a variable
        if isinstance(self.source_age, str) and context.has_variable(self.source_age):
            source_age = context.get_variable(self.source_age)
        else:
            source_age = self.source_age

        # Draw cards
        revealed_cards = []
        for _ in range(self.count):
            card = context.game.draw_card(source_age)
            if card:
                revealed_cards.append(card)
            else:
                break  # No more cards available

        context.set_variable(self.store_revealed, revealed_cards)

        if not revealed_cards:
            context.add_result(f"No cards available to draw from age {source_age}")
            logger.info(f"No cards available in age {source_age}")
            return ActionResult.SUCCESS

        context.add_result(
            f"Revealed {len(revealed_cards)} cards from age {source_age}"
        )
        logger.debug(f"Revealed {len(revealed_cards)} cards")

        # Check condition on revealed cards
        condition_met = self._check_condition_on_cards(
            revealed_cards, self.condition_check
        )

        # Store condition result for potential loop mechanics
        context.set_variable("last_condition_met", condition_met)

        # Execute appropriate action
        action_config = self.success_action if condition_met else self.failure_action
        if action_config:
            context.add_result(
                f"Condition {'met' if condition_met else 'not met'}, executing action"
            )
            action = create_action_primitive(action_config)
            return action.execute(context)
        else:
            # If no action specified, add cards to hand (default behavior)
            for card in revealed_cards:
                if hasattr(context.player, "add_to_hand"):
                    context.player.add_to_hand(card)
                elif hasattr(context.player, "hand"):
                    context.player.hand.append(card)
            context.add_result(f"Added {len(revealed_cards)} cards to hand")

        return ActionResult.SUCCESS

    def _check_condition_on_cards(self, cards: list, condition_check: str) -> bool:
        """Check condition on revealed cards"""
        if not condition_check:
            return True  # No condition means always succeed
        if not cards:
            return False

        from models.card import Symbol

        for card in cards:
            if condition_check == "has_castles":
                if hasattr(card, "symbols") and Symbol.CASTLE in card.symbols:
                    return True
            elif condition_check == "has_crowns":
                if hasattr(card, "symbols") and Symbol.CROWN in card.symbols:
                    return True
            elif condition_check == "has_leafs" or condition_check == "has_leaves":
                if hasattr(card, "symbols") and Symbol.LEAF in card.symbols:
                    return True
            elif condition_check == "has_lightbulbs":
                if hasattr(card, "symbols") and Symbol.LIGHTBULB in card.symbols:
                    return True
            elif condition_check == "has_factories":
                if hasattr(card, "symbols") and Symbol.FACTORY in card.symbols:
                    return True
            elif condition_check == "has_clocks":
                if hasattr(card, "symbols") and Symbol.CLOCK in card.symbols:
                    return True
            elif condition_check.startswith("color_"):
                required_color = condition_check.split("_", 1)[1]
                if hasattr(card, "color"):
                    card_color = str(card.color)
                    if card_color.lower() == required_color.lower():
                        return True
            elif condition_check.startswith("age_"):
                try:
                    required_age = int(condition_check.split("_", 1)[1])
                    if hasattr(card, "age") and card.age == required_age:
                        return True
                except (ValueError, IndexError):
                    pass
            elif condition_check == "all":
                # Always true for any card
                return True

        return False

    def _process_selection(self, context: ActionContext, create_action_primitive) -> ActionResult:
        """Process existing selection with nested actions (Escapism pattern)"""
        # Get cards from selection variable
        selection = context.get_variable(self.selection, [])

        if not selection:
            context.add_result(f"No cards in selection '{self.selection}'")
            logger.info(f"No cards in selection '{self.selection}'")
            return ActionResult.SUCCESS

        # Store as 'revealed' for nested actions to reference
        context.set_variable("revealed", selection)
        context.add_result(f"Processing {len(selection)} selected cards")
        logger.debug(f"Processing {len(selection)} cards from selection '{self.selection}'")

        # Execute nested actions sequentially
        for action_config in self.actions:
            action = create_action_primitive(action_config)
            result = action.execute(context)

            if result == ActionResult.FAILURE:
                context.add_result("Nested action failed")
                logger.warning("Nested action in RevealAndProcess failed")
                return ActionResult.FAILURE

        return ActionResult.SUCCESS
