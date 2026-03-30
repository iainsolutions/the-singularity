"""
SelfExecute Action Primitive

Executes a card's dogma effect in a special context.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class SelfExecute(ActionPrimitive):
    """
    Executes a card's non-demand dogma effects.

    Parameters:
    - card: Card to execute (card object or variable name)
    - card_variable: Alternative way to specify card via variable name
    - effect_index: Which effect to execute (default: 0 for first non-demand effect)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.card = config.get("card")
        self.card_variable = config.get("card_variable")
        self.effect_index = config.get("effect_index", 0)

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the specified card's dogma effect"""
        logger.debug(f"SelfExecute.execute: card={self.card}, card_variable={self.card_variable}")

        # Get the card
        card = None
        if self.card_variable:
            card = context.get_variable(self.card_variable)
        elif self.card:
            if isinstance(self.card, str) and context.has_variable(self.card):
                card = context.get_variable(self.card)
            else:
                card = self.card

        if not card:
            context.add_result("No card specified for self-execute")
            return ActionResult.FAILURE

        # Verify card has dogma effects
        if not hasattr(card, 'dogma_effects') or not card.dogma_effects:
            context.add_result(f"Card {card.name} has no dogma effects")
            return ActionResult.FAILURE

        # Find non-demand effects
        non_demand_effects = [e for e in card.dogma_effects if not e.get('is_demand', False)]

        if not non_demand_effects:
            context.add_result(f"Card {card.name} has no non-demand effects")
            return ActionResult.FAILURE

        # Get the specified effect
        if self.effect_index >= len(non_demand_effects):
            context.add_result(f"Effect index {self.effect_index} out of range for {card.name}")
            return ActionResult.FAILURE

        effect = non_demand_effects[self.effect_index]

        activity_logger.info(
            f"⚡ {context.current_player.name} self-executes {card.name}"
        )

        # Execute the effect's actions
        if 'actions' in effect:
            for action_config in effect['actions']:
                # Create and execute the action primitive
                action_type = action_config.get('type')
                if not action_type:
                    continue

                try:
                    # Import the primitive class
                    from . import create_primitive
                    primitive = create_primitive(action_config)

                    if primitive:
                        result = primitive.execute(context)
                        if result == ActionResult.FAILURE:
                            logger.warning(f"SelfExecute: Action {action_type} failed")
                            return ActionResult.FAILURE
                        elif result == ActionResult.SUSPENDED:
                            # If any action suspends, we suspend the whole self-execute
                            return ActionResult.SUSPENDED
                except Exception as e:
                    logger.error(f"SelfExecute: Error executing action {action_type}: {e}")
                    return ActionResult.FAILURE

        return ActionResult.SUCCESS
