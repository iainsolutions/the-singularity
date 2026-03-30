"""
Atomic Transaction Manager for Week 4 Phase Streamlining.

Provides enhanced transaction management with atomic operations,
rollback capabilities, and optimized state management.
"""

import copy
import logging
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from ..core.context import DogmaContext
from ..core.transaction import TransactionManager

logger = logging.getLogger(__name__)


class AtomicOperationType(Enum):
    """Types of atomic operations that can be performed"""

    STATE_CHANGE = "state_change"
    CONTEXT_UPDATE = "context_update"
    PHASE_TRANSITION = "phase_transition"
    VARIABLE_SET = "variable_set"
    RESULT_ADD = "result_add"
    GAME_MODIFICATION = "game_modification"


@dataclass
class AtomicOperation:
    """Represents an atomic operation that can be committed or rolled back"""

    operation_id: str
    operation_type: AtomicOperationType
    target: str  # What is being modified (context, game, etc.)
    before_state: Any  # State before operation
    after_state: Any  # State after operation
    apply_func: Callable | None = None  # Function to apply the change
    rollback_func: Callable | None = None  # Function to rollback the change
    timestamp: datetime = field(default_factory=datetime.utcnow)
    committed: bool = False
    rolled_back: bool = False

    def can_commit(self) -> bool:
        """Check if operation can be committed"""
        return not self.committed and not self.rolled_back

    def can_rollback(self) -> bool:
        """Check if operation can be rolled back"""
        return self.committed and not self.rolled_back


@dataclass
class TransactionCheckpoint:
    """Represents a transaction checkpoint for rollback"""

    checkpoint_id: str
    transaction_id: str
    context_snapshot: DogmaContext
    operations_count: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


class AtomicTransactionManager:
    """
    Enhanced transaction manager with atomic operations and rollback capabilities.

    Week 4 improvements:
    - Atomic operation batching
    - Sophisticated rollback mechanisms
    - State checkpoint system
    - Performance optimizations
    - Thread-safe operation queuing
    """

    def __init__(self, base_manager: TransactionManager):
        self.base_manager = base_manager
        self._operation_queue: dict[str, list[AtomicOperation]] = {}
        self._checkpoints: dict[str, list[TransactionCheckpoint]] = {}
        self._transaction_locks: dict[str, threading.RLock] = {}
        self._global_lock = threading.RLock()

        # Performance tracking
        self._operation_stats = {
            "total_operations": 0,
            "committed_operations": 0,
            "rolled_back_operations": 0,
            "checkpoints_created": 0,
            "rollbacks_performed": 0,
        }

    @contextmanager
    def atomic_transaction_scope(self, transaction_id: str):
        """Context manager for atomic transaction operations"""
        with self._get_transaction_lock(transaction_id):
            try:
                self._ensure_operation_queue(transaction_id)
                yield self
                # Auto-commit on successful exit
                self._commit_pending_operations(transaction_id)
            except Exception as e:
                logger.error(f"Atomic transaction {transaction_id} failed: {e}")
                # Auto-rollback on exception
                self._rollback_pending_operations(transaction_id)
                raise

    def create_checkpoint(
        self,
        transaction_id: str,
        context: DogmaContext,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a transaction checkpoint for potential rollback"""
        with self._get_transaction_lock(transaction_id):
            checkpoint_id = f"{transaction_id}_cp_{int(time.time() * 1000)}"

            # Create deep copy of context for checkpoint
            context_snapshot = copy.deepcopy(context)

            checkpoint = TransactionCheckpoint(
                checkpoint_id=checkpoint_id,
                transaction_id=transaction_id,
                context_snapshot=context_snapshot,
                operations_count=len(self._operation_queue.get(transaction_id, [])),
                metadata=metadata or {},
            )

            if transaction_id not in self._checkpoints:
                self._checkpoints[transaction_id] = []
            self._checkpoints[transaction_id].append(checkpoint)

            self._operation_stats["checkpoints_created"] += 1
            logger.debug(
                f"Created checkpoint {checkpoint_id} for transaction {transaction_id}"
            )

            return checkpoint_id

    def add_atomic_operation(self, transaction_id: str, operation: AtomicOperation):
        """Add an atomic operation to the transaction queue"""
        with self._get_transaction_lock(transaction_id):
            self._ensure_operation_queue(transaction_id)
            self._operation_queue[transaction_id].append(operation)
            self._operation_stats["total_operations"] += 1

            logger.debug(
                f"Added {operation.operation_type.value} operation to transaction {transaction_id}"
            )

    def create_context_update_operation(
        self, transaction_id: str, old_context: DogmaContext, new_context: DogmaContext
    ) -> AtomicOperation:
        """Create an atomic operation for context updates"""
        operation_id = f"{transaction_id}_ctx_{int(time.time() * 1000000)}"

        return AtomicOperation(
            operation_id=operation_id,
            operation_type=AtomicOperationType.CONTEXT_UPDATE,
            target="context",
            before_state=old_context,
            after_state=new_context,
            apply_func=lambda: new_context,
            rollback_func=lambda: old_context,
        )

    def create_variable_operation(
        self, transaction_id: str, key: str, old_value: Any, new_value: Any
    ) -> AtomicOperation:
        """Create an atomic operation for variable changes"""
        operation_id = f"{transaction_id}_var_{key}_{int(time.time() * 1000000)}"

        return AtomicOperation(
            operation_id=operation_id,
            operation_type=AtomicOperationType.VARIABLE_SET,
            target=f"variable:{key}",
            before_state=old_value,
            after_state=new_value,
        )

    def batch_commit_operations(
        self, transaction_id: str, operation_ids: list[str] | None = None
    ) -> bool:
        """Commit multiple operations atomically"""
        with self._get_transaction_lock(transaction_id):
            try:
                operations = self._operation_queue.get(transaction_id, [])

                if operation_ids:
                    # Commit only specified operations
                    operations = [
                        op for op in operations if op.operation_id in operation_ids
                    ]

                # Apply all operations
                for operation in operations:
                    if operation.can_commit():
                        if operation.apply_func:
                            operation.apply_func()
                        operation.committed = True
                        self._operation_stats["committed_operations"] += 1

                logger.debug(
                    f"Batch committed {len(operations)} operations for transaction {transaction_id}"
                )
                return True

            except Exception as e:
                logger.error(
                    f"Batch commit failed for transaction {transaction_id}: {e}"
                )
                return False

    def rollback_to_checkpoint(self, transaction_id: str, checkpoint_id: str) -> bool:
        """Rollback transaction to a specific checkpoint"""
        with self._get_transaction_lock(transaction_id):
            try:
                checkpoints = self._checkpoints.get(transaction_id, [])
                checkpoint = next(
                    (cp for cp in checkpoints if cp.checkpoint_id == checkpoint_id),
                    None,
                )

                if not checkpoint:
                    logger.error(
                        f"Checkpoint {checkpoint_id} not found for transaction {transaction_id}"
                    )
                    return False

                # Rollback operations created after checkpoint
                operations = self._operation_queue.get(transaction_id, [])
                operations_to_rollback = [
                    op
                    for op in operations
                    if op.timestamp > checkpoint.timestamp and op.committed
                ]

                # Apply rollbacks in reverse order
                for operation in reversed(operations_to_rollback):
                    if operation.can_rollback() and operation.rollback_func:
                        operation.rollback_func()
                        operation.rolled_back = True
                        self._operation_stats["rolled_back_operations"] += 1

                self._operation_stats["rollbacks_performed"] += 1
                logger.info(
                    f"Rolled back {len(operations_to_rollback)} operations to checkpoint {checkpoint_id}"
                )
                return True

            except Exception as e:
                logger.error(f"Rollback to checkpoint failed: {e}")
                return False

    def get_transaction_state(self, transaction_id: str) -> dict[str, Any]:
        """Get detailed transaction state including pending operations"""
        with self._get_transaction_lock(transaction_id):
            operations = self._operation_queue.get(transaction_id, [])
            checkpoints = self._checkpoints.get(transaction_id, [])

            return {
                "transaction_id": transaction_id,
                "pending_operations": len(
                    [op for op in operations if not op.committed and not op.rolled_back]
                ),
                "committed_operations": len([op for op in operations if op.committed]),
                "rolled_back_operations": len(
                    [op for op in operations if op.rolled_back]
                ),
                "checkpoints": len(checkpoints),
                "last_checkpoint": checkpoints[-1].timestamp.isoformat()
                if checkpoints
                else None,
                "operation_summary": {
                    op_type.value: len(
                        [op for op in operations if op.operation_type == op_type]
                    )
                    for op_type in AtomicOperationType
                },
            }

    def optimize_transaction_performance(self, transaction_id: str) -> dict[str, Any]:
        """Optimize transaction performance by analyzing operation patterns"""
        with self._get_transaction_lock(transaction_id):
            operations = self._operation_queue.get(transaction_id, [])

            # Analyze operation patterns
            operation_types = {}
            duplicate_operations = 0

            for op in operations:
                op_type = op.operation_type.value
                operation_types[op_type] = operation_types.get(op_type, 0) + 1

                # Check for duplicate operations on same target
                duplicates = [
                    other
                    for other in operations
                    if other != op
                    and other.target == op.target
                    and other.operation_type == op.operation_type
                ]
                if duplicates:
                    duplicate_operations += 1

            # Create optimization report
            optimization_report = {
                "transaction_id": transaction_id,
                "total_operations": len(operations),
                "operation_breakdown": operation_types,
                "duplicate_operations": duplicate_operations,
                "optimization_suggestions": [],
                "memory_usage_estimate": self._estimate_memory_usage(operations),
            }

            # Add optimization suggestions
            if duplicate_operations > 0:
                optimization_report["optimization_suggestions"].append(
                    f"Consider coalescing {duplicate_operations} duplicate operations"
                )

            if len(operations) > 100:
                optimization_report["optimization_suggestions"].append(
                    "Consider more frequent commits to reduce memory usage"
                )

            return optimization_report

    def cleanup_transaction(self, transaction_id: str):
        """Clean up all transaction data"""
        with self._global_lock:
            # Remove from operation queue
            self._operation_queue.pop(transaction_id, None)
            # Remove checkpoints
            self._checkpoints.pop(transaction_id, None)
            # Remove transaction lock
            self._transaction_locks.pop(transaction_id, None)

            logger.debug(f"Cleaned up atomic transaction data for {transaction_id}")

    def get_performance_stats(self) -> dict[str, Any]:
        """Get atomic transaction manager performance statistics"""
        return {
            **self._operation_stats,
            "active_transactions": len(self._operation_queue),
            "total_checkpoints": sum(len(cps) for cps in self._checkpoints.values()),
            "memory_usage_estimate": sum(
                self._estimate_memory_usage(ops)
                for ops in self._operation_queue.values()
            ),
        }

    def _get_transaction_lock(self, transaction_id: str) -> threading.RLock:
        """Get or create a lock for a specific transaction"""
        with self._global_lock:
            if transaction_id not in self._transaction_locks:
                self._transaction_locks[transaction_id] = threading.RLock()
            return self._transaction_locks[transaction_id]

    def _ensure_operation_queue(self, transaction_id: str):
        """Ensure operation queue exists for transaction"""
        if transaction_id not in self._operation_queue:
            self._operation_queue[transaction_id] = []

    def _commit_pending_operations(self, transaction_id: str):
        """Commit all pending operations for a transaction"""
        operations = self._operation_queue.get(transaction_id, [])
        pending_ops = [
            op for op in operations if not op.committed and not op.rolled_back
        ]

        for operation in pending_ops:
            if operation.apply_func:
                operation.apply_func()
            operation.committed = True
            self._operation_stats["committed_operations"] += 1

    def _rollback_pending_operations(self, transaction_id: str):
        """Rollback all pending operations for a transaction"""
        operations = self._operation_queue.get(transaction_id, [])

        # Rollback in reverse order
        for operation in reversed(operations):
            if operation.committed and operation.rollback_func:
                operation.rollback_func()
                operation.rolled_back = True
                self._operation_stats["rolled_back_operations"] += 1

    def _estimate_memory_usage(self, operations: list[AtomicOperation]) -> int:
        """Estimate memory usage of operations (rough approximation)"""
        total_size = 0
        for op in operations:
            # Rough estimate based on state sizes
            total_size += len(str(op.before_state)) + len(str(op.after_state))
            total_size += 200  # Base overhead per operation
        return total_size


# Global atomic transaction manager instance
_atomic_transaction_manager: AtomicTransactionManager | None = None


def get_atomic_transaction_manager(
    base_manager: TransactionManager,
) -> AtomicTransactionManager:
    """Get or create the global atomic transaction manager"""
    global _atomic_transaction_manager
    if _atomic_transaction_manager is None:
        _atomic_transaction_manager = AtomicTransactionManager(base_manager)
    return _atomic_transaction_manager


def create_atomic_context_operation(
    transaction_id: str, old_context: DogmaContext, new_context: DogmaContext
) -> AtomicOperation:
    """Convenience function to create atomic context operations"""
    manager = get_atomic_transaction_manager(None)  # Manager will be set elsewhere
    return manager.create_context_update_operation(
        transaction_id, old_context, new_context
    )


def with_atomic_transaction(transaction_id: str, base_manager: TransactionManager):
    """Decorator for atomic transaction operations"""
    manager = get_atomic_transaction_manager(base_manager)
    return manager.atomic_transaction_scope(transaction_id)
