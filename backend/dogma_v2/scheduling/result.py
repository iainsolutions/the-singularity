"""
Execution results for action scheduling.
"""

from dataclasses import dataclass
from typing import Any

from dogma_v2.interaction_request import InteractionRequest


@dataclass
class ActionExecutionResult:
    """
    Result of executing a single PlannedAction.

    This standardizes the return value from action execution, replacing
    the EffectExecutionResult variants in SharingPhase and ExecutionPhase.
    """

    success: bool
    context: "DogmaContext"  # type: ignore
    results: list[Any]

    # Suspension state
    requires_interaction: bool = False
    interaction: InteractionRequest | None = None
    resume_action_index: int = 0  # For mid-effect resumption

    # Demand routing state
    routes_to_demand: bool = False
    demand_config: dict | None = None

    # Error state
    error: str | None = None
