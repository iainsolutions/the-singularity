"""
Phase implementations for Dogma v2 system.

This module contains all the concrete phase implementations:
- InitializationPhase: Set up dogma execution
- EffectExecutionPhase: Execute card effects
- DemandPhase: Handle demand effects
- DemandTargetPhase: Process individual demand targets
- InteractionPhase: Handle player interactions
- SharingPhase: Execute effects for sharing players
- CompletionPhase: Finalize dogma execution
"""

from .completion import CompletionPhase
from .demand import DemandPhase, DemandTargetPhase
from .execution import EffectExecutionPhase
from .initialization import InitializationPhase
from .interaction import CardSelectionInteraction, ChoiceInteraction, InteractionPhase
from .sharing import SharingPhase

__all__ = [
    "CardSelectionInteraction",
    "ChoiceInteraction",
    "CompletionPhase",
    "DemandPhase",
    "DemandTargetPhase",
    "EffectExecutionPhase",
    "InitializationPhase",
    "InteractionPhase",
    "SharingPhase",
]
