"""
EffectFactory - Creates appropriate Effect adapters for different effect types.

This factory determines which adapter to use based on the effect configuration,
providing specialized handling for different categories of effects through
dedicated adapters that provide enhanced validation, execution, and result handling.
"""

import logging
from typing import Any

from .achievement_adapter import AchievementEffectAdapter
from .adapter import ActionPrimitiveAdapter
from .base import Effect
from .board_adapter import BoardManipulationAdapter
from .calculation_adapter import CalculationEffectAdapter
from .control_adapter import ControlFlowAdapter
from .demand_adapter import DemandEffectAdapter
from .interaction_adapter import InteractionEffectAdapter
from .transfer_adapter import TransferEffectAdapter

logger = logging.getLogger(__name__)


class EffectFactory:
    """
    Factory for creating Effect instances.

    This factory:
    1. Analyzes effect configuration
    2. Determines the appropriate adapter type
    3. Creates and returns the correct Effect implementation
    """

    @staticmethod
    def create(config: dict[str, Any]) -> Effect:
        """
        Create an appropriate Effect adapter for the given configuration.

        This method intelligently routes effect types to specialized adapters
        that provide enhanced validation, execution handling, and result processing
        for specific categories of effects.

        Args:
            config: Effect configuration from card JSON

        Returns:
            Appropriate Effect implementation
        """
        effect_type = config.get("type", "")

        # Route to specialized adapters based on effect type

        # Demand effects - special multi-player targeting
        if effect_type == "DemandEffect":
            logger.debug(f"Creating DemandEffectAdapter for {effect_type}")
            return DemandEffectAdapter(config)

        # Interaction effects - require user input
        elif effect_type in InteractionEffectAdapter.INTERACTION_EFFECTS:
            logger.debug(f"Creating InteractionEffectAdapter for {effect_type}")
            return InteractionEffectAdapter(config)

        # Transfer effects - move cards between locations
        elif effect_type in TransferEffectAdapter.TRANSFER_EFFECTS:
            logger.debug(f"Creating TransferEffectAdapter for {effect_type}")
            return TransferEffectAdapter(config)

        # Board manipulation effects - change visual arrangement
        elif effect_type in BoardManipulationAdapter.BOARD_EFFECTS:
            logger.debug(f"Creating BoardManipulationAdapter for {effect_type}")
            return BoardManipulationAdapter(config)

        # Control flow effects - conditional and loop logic
        elif effect_type in ControlFlowAdapter.CONTROL_EFFECTS:
            logger.debug(f"Creating ControlFlowAdapter for {effect_type}")
            return ControlFlowAdapter(config)

        # Calculation effects - counting and computation
        elif effect_type in CalculationEffectAdapter.CALCULATION_EFFECTS:
            logger.debug(f"Creating CalculationEffectAdapter for {effect_type}")
            return CalculationEffectAdapter(config)

        # Achievement effects - claiming and availability
        elif effect_type in AchievementEffectAdapter.ALL_ACHIEVEMENT_EFFECTS:
            logger.debug(f"Creating AchievementEffectAdapter for {effect_type}")
            return AchievementEffectAdapter(config)

        # Fallback to standard adapter for unrecognized effects
        else:
            logger.debug(f"Creating fallback ActionPrimitiveAdapter for {effect_type}")
            return ActionPrimitiveAdapter(config)

    @staticmethod
    def create_batch(configs: list[dict[str, Any]]) -> list[Effect]:
        """
        Create multiple Effect instances from a list of configurations.

        Args:
            configs: List of effect configurations

        Returns:
            List of Effect implementations
        """
        effects = []
        for i, config in enumerate(configs):
            try:
                effect = EffectFactory.create(config)
                effects.append(effect)
            except Exception as e:
                logger.error(f"Failed to create effect {i}: {e}")
                # Create a failed effect placeholder
                from .failed_effect import FailedEffect

                effects.append(FailedEffect(config, str(e)))

        return effects

    @staticmethod
    def get_adapter_for_effect_type(effect_type: str) -> str:
        """
        Get the adapter name that would be used for a given effect type.

        This is useful for debugging, testing, and validation.

        Args:
            effect_type: The effect type string

        Returns:
            Name of the adapter class that would handle this effect
        """
        # Check each adapter in the same order as create()
        if effect_type == "DemandEffect":
            return "DemandEffectAdapter"
        elif effect_type in InteractionEffectAdapter.INTERACTION_EFFECTS:
            return "InteractionEffectAdapter"
        elif effect_type in TransferEffectAdapter.TRANSFER_EFFECTS:
            return "TransferEffectAdapter"
        elif effect_type in BoardManipulationAdapter.BOARD_EFFECTS:
            return "BoardManipulationAdapter"
        elif effect_type in ControlFlowAdapter.CONTROL_EFFECTS:
            return "ControlFlowAdapter"
        elif effect_type in CalculationEffectAdapter.CALCULATION_EFFECTS:
            return "CalculationEffectAdapter"
        elif effect_type in AchievementEffectAdapter.ALL_ACHIEVEMENT_EFFECTS:
            return "AchievementEffectAdapter"
        else:
            return "ActionPrimitiveAdapter"

    @staticmethod
    def get_routing_statistics() -> dict[str, Any]:
        """
        Get statistics about effect type routing.

        This shows which effects are handled by which adapters,
        useful for validation and debugging.

        Returns:
            Dictionary with routing statistics
        """
        stats = {
            "DemandEffectAdapter": {"DemandEffect"},
            "InteractionEffectAdapter": InteractionEffectAdapter.INTERACTION_EFFECTS,
            "TransferEffectAdapter": TransferEffectAdapter.TRANSFER_EFFECTS,
            "BoardManipulationAdapter": BoardManipulationAdapter.BOARD_EFFECTS,
            "ControlFlowAdapter": ControlFlowAdapter.CONTROL_EFFECTS,
            "CalculationEffectAdapter": CalculationEffectAdapter.CALCULATION_EFFECTS,
            "AchievementEffectAdapter": AchievementEffectAdapter.ALL_ACHIEVEMENT_EFFECTS,
        }

        # Count total effects handled by each adapter
        totals = {}
        all_specialized_effects = set()

        for adapter_name, effects in stats.items():
            totals[adapter_name] = len(effects)
            all_specialized_effects.update(effects)

        return {
            "adapters": stats,
            "totals": totals,
            "specialized_effects_count": len(all_specialized_effects),
            "fallback_adapter": "ActionPrimitiveAdapter",
        }
