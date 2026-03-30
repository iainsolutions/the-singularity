"""
FailedEffect - Placeholder for effects that failed to initialize.

This ensures the dogma can continue execution even if one effect
fails to initialize, providing better error recovery.
"""

import logging
from typing import Any

from ..core.context import DogmaContext
from .base import Effect, EffectResult, EffectType

logger = logging.getLogger(__name__)


class FailedEffect(Effect):
    """
    Placeholder effect for when effect creation fails.

    This allows dogma execution to continue and report errors
    gracefully rather than crashing entirely.
    """

    def __init__(self, config: dict[str, Any], error: str):
        """
        Initialize the failed effect.

        Args:
            config: The original effect configuration that failed
            error: Error message explaining the failure
        """
        # Handle None config gracefully
        safe_config = config if config is not None else {}
        super().__init__(safe_config)
        self.error = error
        self.type = EffectType.STANDARD

    def execute(self, context: DogmaContext) -> EffectResult:
        """
        Execute always returns failure with the initialization error.

        Args:
            context: The dogma execution context

        Returns:
            EffectResult indicating failure
        """
        logger.error(f"Attempting to execute failed effect: {self.error}")

        return EffectResult(
            success=False, error=f"Effect failed to initialize: {self.error}"
        )

    def validate(self) -> tuple[bool, str | None]:
        """
        Validation always fails with the initialization error.

        Returns:
            Tuple of (False, error_message)
        """
        return False, self.error

    def get_description(self) -> str:
        """Get description including the failure"""
        return f"Failed effect: {self.error}"
