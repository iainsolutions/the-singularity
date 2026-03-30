"""DogmaPhase - Abstract base for all dogma phases."""

from abc import ABC, abstractmethod

from dogma_v2.core.context import DogmaContext
from dogma_v2.phase_result import PhaseResult


class DogmaPhase(ABC):
    """Abstract base for all dogma phases."""

    @abstractmethod
    async def execute(self, context: DogmaContext) -> PhaseResult:
        """Execute this phase with given context."""
        pass

    def get_phase_name(self) -> str:
        """Return human-readable phase name for logging."""
        return self.__class__.__name__

    def estimate_remaining_phases(self) -> int:
        """Estimate phases remaining for progress tracking."""
        return 1
