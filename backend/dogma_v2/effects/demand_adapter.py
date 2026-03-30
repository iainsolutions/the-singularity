"""
DemandEffectAdapter - Specialized adapter for demand effects.

Demand effects require special handling because they:
1. Always route to DemandPhase instead of executing directly
2. Have specific configuration requirements
3. Need proper signal translation for phase routing
"""

import logging
from typing import Any

from ..core.context import DogmaContext
from .base import Effect, EffectResult, EffectType

logger = logging.getLogger(__name__)


class DemandEffectAdapter(Effect):
    """
    Specialized adapter for DemandEffect primitives.

    This adapter ensures demands are properly routed to DemandPhase
    without exposing internal routing signals to the phase logic.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the demand effect adapter.

        Args:
            config: Demand effect configuration
        """
        super().__init__(config)
        # Demand effects always have DEMAND type
        self.type = EffectType.DEMAND

    def execute(self, context: DogmaContext) -> EffectResult:
        """
        Execute demand effect by signaling phase routing.

        Demand effects don't execute directly - they signal the
        ExecutionPhase to route to DemandPhase for proper handling.

        Args:
            context: The dogma execution context

        Returns:
            EffectResult signaling demand routing
        """
        logger.info(f"DemandEffectAdapter signaling demand routing for {self.config}")

        # Validate the demand configuration
        is_valid, error = self.validate()
        if not is_valid:
            return EffectResult(
                success=False, error=f"Invalid demand configuration: {error}"
            )

        # Signal that this needs to route to DemandPhase
        # This is the CLEAN way to signal routing without internal variables
        return EffectResult(
            success=True,
            routes_to_demand=True,
            demand_config=self.config,
            variables={},
            results=["Demand effect ready for processing"],
        )

    def validate(self) -> tuple[bool, str | None]:
        """
        Validate demand effect configuration.

        Demands require:
        - required_symbol or symbol_requirement
        - demand_actions list

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for required symbol
        symbol = self.config.get("required_symbol") or self.config.get(
            "symbol_requirement"
        )
        if not symbol:
            return False, "Demand missing required_symbol or symbol_requirement"

        # Check for demand actions
        demand_actions = self.config.get("demand_actions", [])
        if not demand_actions:
            return False, "Demand missing demand_actions"

        # Validate action list structure
        if not isinstance(demand_actions, list):
            return False, "demand_actions must be a list"

        return True, None

    def get_description(self) -> str:
        """Get human-readable description of the demand"""
        symbol = self.config.get("required_symbol") or self.config.get(
            "symbol_requirement", "unknown"
        )
        return f"Demand effect requiring {symbol} symbol"
