"""
RepeatEffect Action Primitive

Signals that the current dogma effect should be repeated.
Part of the Unseen expansion mechanics.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class RepeatEffect(ActionPrimitive):
    """
    Signals that the current dogma effect should be repeated.

    This primitive sets a flag that the dogma executor checks.
    When the flag is set, the executor will re-execute the current effect.

    Parameters:
    - effect_index: Index of the effect to repeat (0-based)
                    If not specified, repeats the current effect
    - max_repeats: Maximum number of times to repeat (default: 1)
                   Set to -1 for unlimited (careful with this!)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.effect_index = config.get("effect_index")
        self.max_repeats = config.get("max_repeats", 1)

    def execute(self, context: ActionContext) -> ActionResult:
        """Signal that the effect should be repeated"""
        logger.debug(
            f"RepeatEffect.execute: effect_index={self.effect_index}, max_repeats={self.max_repeats}"
        )

        # Set repeat flag in context variables
        # The dogma executor will check for this and repeat the effect
        context.set_variable("_repeat_effect", True)

        if self.effect_index is not None:
            context.set_variable("_repeat_effect_index", self.effect_index)

        # Track repeat count to prevent infinite loops
        current_repeat_count = context.get_variable("_repeat_count", 0)

        if self.max_repeats >= 0 and current_repeat_count >= self.max_repeats:
            logger.debug(
                f"RepeatEffect: Max repeats ({self.max_repeats}) reached, not repeating"
            )
            context.set_variable("_repeat_effect", False)
            return ActionResult.SUCCESS

        context.set_variable("_repeat_count", current_repeat_count + 1)

        logger.info(f"{context.player.name} repeats the effect")
        context.add_result("Effect will be repeated")

        logger.debug("RepeatEffect: Set repeat flag")
        return ActionResult.SUCCESS

    def get_required_fields(self) -> list[str]:
        return []

    def get_optional_fields(self) -> list[str]:
        return ["effect_index", "max_repeats"]
