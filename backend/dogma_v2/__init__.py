"""
Dogma System v2.0

A phase-based, transaction-oriented system for executing dogma actions
in the The Singularity card game.

This system replaces the monolithic state machine with a modular,
testable architecture that properly implements all requirements from
DOGMA_SPECIFICATION.md.
"""

from .consolidated_executor import ConsolidatedDogmaExecutor as DogmaExecutor
from .core.context import DogmaContext
from .core.phases import DogmaPhase, PhaseResult, ResultType
from .core.transaction import DogmaTransaction, TransactionStatus
from .execution_result import DogmaExecutionResult

__version__ = "2.0.0"

__all__ = [
    "DogmaContext",
    "DogmaExecutionResult",
    "DogmaExecutor",
    "DogmaPhase",
    "DogmaTransaction",
    "PhaseResult",
    "ResultType",
    "TransactionStatus",
]
