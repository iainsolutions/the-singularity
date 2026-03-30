"""
Core components for Dogma v2 system.

This module contains the fundamental building blocks:
- DogmaContext: Immutable execution context
- DogmaPhase: Abstract base for all phases
- PhaseResult: Result of phase execution
- DogmaTransaction: Transaction management
"""

from .context import DogmaContext
from .phases import DogmaPhase, PhaseResult, ResultType
from .transaction import DogmaTransaction, TransactionStatus

__all__ = [
    "DogmaContext",
    "DogmaPhase",
    "DogmaTransaction",
    "PhaseResult",
    "ResultType",
    "TransactionStatus",
]
