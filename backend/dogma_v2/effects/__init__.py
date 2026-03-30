"""
Dogma v2 Effects abstraction layer.

This package implements the ActionPrimitiveAdapter pattern specified in
DOGMA_TECHNICAL_SPECIFICATION.md, providing clean abstraction between
phases and action primitives.

Key components:
- Effect: Abstract base class for all effects
- EffectResult: Clean result interface (no internal signals)
- EffectFactory: Creates appropriate adapters for different effect types
- ActionPrimitiveAdapter: Standard adapter wrapping primitives
- DemandEffectAdapter: Specialized adapter for demand effects

Usage:
    from dogma_v2.effects import EffectFactory, EffectResult

    # Create effect from configuration
    effect = EffectFactory.create(effect_config)

    # Execute effect with dogma context
    result = effect.execute(context)

    # Check result (clean interface, no internal signals)
    if result.routes_to_demand:
        # Route to DemandPhase
    elif result.requires_interaction:
        # Handle interaction
    elif result.success:
        # Effect succeeded
"""

from .adapter import ActionPrimitiveAdapter
from .base import Effect, EffectResult, EffectType
from .demand_adapter import DemandEffectAdapter
from .factory import EffectFactory
from .failed_effect import FailedEffect

__all__ = [
    "ActionPrimitiveAdapter",
    "DemandEffectAdapter",
    "Effect",
    "EffectFactory",
    "EffectResult",
    "EffectType",
    "FailedEffect",
]
