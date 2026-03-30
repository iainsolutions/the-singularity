"""
NoOp Action Primitive

Placeholder primitive that does nothing but logs a warning.
Used for cards that are not yet fully implemented.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class NoOp(ActionPrimitive):
    """
    No Operation primitive - does nothing.

    This is a placeholder for card effects that are not yet implemented.
    It logs a warning when executed so we can track incomplete implementations.

    Parameters:
    - _metadata: Optional metadata about the original intended primitive
    - TODO: Optional TODO description for what needs to be implemented
    - reason: Optional reason why this is a NoOp
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.metadata = config.get("_metadata", {})
        self.todo = config.get("TODO")
        self.reason = config.get("reason", "Not yet implemented")

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the no-op (does nothing)"""

        # Log warning
        warning_msg = f"NoOp executed in card effect"

        if self.metadata:
            original_type = self.metadata.get("original_type")
            if original_type:
                warning_msg += f" (intended: {original_type})"

        if self.todo:
            warning_msg += f" - TODO: {self.todo}"

        logger.warning(warning_msg)

        # Also log to activity logger so it's visible in game logs
        activity_logger.warning(
            f"⚠️ Incomplete card effect: {self.reason}"
        )

        # Add result to context
        context.add_result(f"Incomplete effect: {self.reason}")

        # Return SUCCESS so execution continues
        # (Don't want to fail the whole dogma because one effect is incomplete)
        return ActionResult.SUCCESS

    def get_required_fields(self) -> list[str]:
        return []

    def get_optional_fields(self) -> list[str]:
        return ["_metadata", "TODO", "reason"]
