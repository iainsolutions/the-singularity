"""
Optimization modules for dogma_v2 Week 4 Phase Streamlining.

This package contains performance optimizations including:
- Copy-on-write context management
- Memory allocation reduction
- Phase transition optimization
- Transaction management enhancements
- Atomic operations and rollback capabilities
- Enhanced error handling and recovery
"""

from .atomic_transaction_manager import (
    AtomicOperation,
    AtomicOperationType,
    AtomicTransactionManager,
    TransactionCheckpoint,
    get_atomic_transaction_manager,
    with_atomic_transaction,
)
from .context_optimizer import (
    ContextOptimizer,
    OptimizedDogmaContext,
    cleanup_context_optimizations,
    get_context_optimization_stats,
    get_context_optimizer,
    optimize_context_for_phase,
)
from .error_recovery import (
    ConsolidatedErrorRecoveryManager,
    ErrorContext,
    ErrorSeverity,
    RecoveryStrategy,
    get_error_recovery_manager,
    handle_phase_error,
    with_error_recovery,
)

__all__ = [
    "AtomicOperation",
    "AtomicOperationType",
    # Atomic transaction management
    "AtomicTransactionManager",
    # Error recovery
    "ConsolidatedErrorRecoveryManager",
    "ContextOptimizer",
    "ErrorContext",
    "ErrorSeverity",
    # Context optimization
    "OptimizedDogmaContext",
    "RecoveryStrategy",
    "TransactionCheckpoint",
    "cleanup_context_optimizations",
    "get_atomic_transaction_manager",
    "get_context_optimization_stats",
    "get_context_optimizer",
    "get_error_recovery_manager",
    "handle_phase_error",
    "optimize_context_for_phase",
    "with_atomic_transaction",
    "with_error_recovery",
]
