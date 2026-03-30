"""
Base classes for dogma phases and result types.

This module provides the abstract base class for all dogma phases
and the result types used throughout the phase pipeline.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ResultType(Enum):
    """Types of phase results"""

    SUCCESS = "success"  # Phase succeeded, continue to next
    INTERACTION = "interaction"  # Phase needs player input
    COMPLETE = "complete"  # Dogma execution complete
    ERROR = "error"  # Phase failed with error


@dataclass(frozen=True)
class InteractionRequest:
    """Request for player interaction"""

    id: str  # Unique interaction ID
    player_id: str  # Player who must respond
    type: str  # Interaction type
    data: dict[str, Any]  # Type-specific data
    message: str  # Human-readable message
    timeout: int | None = None  # Seconds before auto-resolve

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "id": self.id,
            "player_id": self.player_id,
            "type": self.type,
            "data": self.data,
            "message": self.message,
            "timeout": self.timeout,
        }


@dataclass(frozen=True)
class ValidationResult:
    """Result of validation check"""

    is_valid: bool
    message: str = ""
    data: Any = None

    @classmethod
    def valid(cls, data: Any = None) -> ValidationResult:
        """Create successful validation result"""
        return cls(is_valid=True, data=data)

    @classmethod
    def invalid(cls, message: str) -> ValidationResult:
        """Create failed validation result"""
        return cls(is_valid=False, message=message)


@dataclass(frozen=True)
class PhaseResult:
    """Result of phase execution"""

    type: ResultType  # Type of result
    next_phase: DogmaPhase | None  # Next phase to execute
    context: DogmaContext  # Updated context
    interaction: InteractionRequest | None = None  # If interaction needed
    error: str | None = None  # If error occurred

    @classmethod
    def success(cls, next_phase: DogmaPhase, context: DogmaContext) -> PhaseResult:
        """Phase succeeded, continue to next"""
        return cls(type=ResultType.SUCCESS, next_phase=next_phase, context=context)

    @classmethod
    def interaction_required(
        cls,
        interaction: InteractionRequest,
        resume_phase: DogmaPhase,
        context: DogmaContext,
    ) -> PhaseResult:
        """Phase needs player input"""
        return cls(
            type=ResultType.INTERACTION,
            next_phase=resume_phase,
            context=context,
            interaction=interaction,
        )

    @classmethod
    def complete(cls, context: DogmaContext) -> PhaseResult:
        """Dogma execution complete"""
        return cls(type=ResultType.COMPLETE, next_phase=None, context=context)

    @classmethod
    def error(cls, error_message: str, context: DogmaContext) -> PhaseResult:
        """Phase failed with error"""
        return cls(
            type=ResultType.ERROR, next_phase=None, context=context, error=error_message
        )


class DogmaPhase(ABC):
    """
    Abstract base for all dogma phases.

    Each phase represents a discrete step in dogma execution and
    is responsible for:
    1. Validating it can execute in the current context
    2. Executing its logic and updating the context
    3. Determining the next phase or requesting interaction
    """

    @abstractmethod
    def execute(self, context: DogmaContext) -> PhaseResult:
        """
        Execute this phase with given context.

        Args:
            context: Immutable context containing game state and variables

        Returns:
            PhaseResult indicating success, interaction needed, completion, or error
        """
        pass

    def validate(self, context: DogmaContext) -> ValidationResult:
        """
        Validate phase can execute in current context.

        Default implementation returns valid. Subclasses can override
        to add specific validation logic.

        Args:
            context: Current execution context

        Returns:
            ValidationResult indicating if execution should proceed
        """
        return ValidationResult.valid()

    def get_phase_name(self) -> str:
        """Return human-readable phase name for logging"""
        return self.__class__.__name__

    def estimate_remaining_phases(self) -> int:
        """
        Estimate phases remaining for progress tracking.

        Default implementation returns 1. Complex phases can override
        to provide better estimates.
        """
        return 1

    def log_phase_start(self, context: DogmaContext) -> None:
        """Log phase execution start"""
        logger.debug(
            f"Starting phase {self.get_phase_name()} for transaction {context.transaction_id}"
        )

    def log_phase_complete(self, context: DogmaContext, result: PhaseResult) -> None:
        """Log phase execution completion"""
        logger.debug(
            f"Phase {self.get_phase_name()} completed with result {result.type.value}"
        )

    def create_error_context(
        self, context: DogmaContext, error_message: str
    ) -> DogmaContext:
        """Create context with error information for debugging"""
        return context.with_variable(
            "last_error",
            {
                "phase": self.get_phase_name(),
                "message": error_message,
                "transaction_id": context.transaction_id,
            },
        )


# Import here to avoid circular imports
from .context import DogmaContext
