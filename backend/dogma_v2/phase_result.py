"""PhaseResult - Result of phase execution."""

from dataclasses import dataclass
from typing import Optional

from dogma_v2.core.context import DogmaContext
from dogma_v2.core.phases import DogmaPhase
from dogma_v2.interaction_request import InteractionRequest
from dogma_v2.result_type import ResultType


@dataclass(frozen=True)
class PhaseResult:
    """Result of phase execution."""

    type: ResultType  # SUCCESS, INTERACTION, ERROR, COMPLETE
    context: DogmaContext  # Updated context
    next_phase: Optional["DogmaPhase"] = None  # Next phase to execute
    interaction: InteractionRequest | None = None  # If interaction needed
    error: str | None = None  # If error occurred

    @staticmethod
    def success(next_phase: "DogmaPhase", context: DogmaContext) -> "PhaseResult":
        """Phase succeeded, continue to next."""
        return PhaseResult(
            type=ResultType.SUCCESS, next_phase=next_phase, context=context
        )

    @staticmethod
    def interaction_required(
        interaction: InteractionRequest,
        resume_phase: "DogmaPhase",
        context: DogmaContext,
    ) -> "PhaseResult":
        """Phase needs player input."""
        return PhaseResult(
            type=ResultType.INTERACTION,
            interaction=interaction,
            next_phase=resume_phase,
            context=context,
        )

    @staticmethod
    def complete(context: DogmaContext) -> "PhaseResult":
        """Dogma execution complete."""
        return PhaseResult(type=ResultType.COMPLETE, context=context)

    @staticmethod
    def error(error_message: str, context: DogmaContext) -> "PhaseResult":
        """Phase failed with error."""
        return PhaseResult(type=ResultType.ERROR, error=error_message, context=context)
