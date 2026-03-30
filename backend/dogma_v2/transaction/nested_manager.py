"""
Nested transaction management system.

Provides:
- Nested transaction support with savepoints
- Transaction pooling for performance
- Optimistic locking for concurrent operations
- Transaction metrics and monitoring
"""

import copy
import logging
import time
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TransactionStatus(str, Enum):
    """Transaction status enumeration"""

    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    SUSPENDED = "suspended"
    FAILED = "failed"


@dataclass
class TransactionSavepoint:
    """Transaction savepoint for nested transactions"""

    name: str
    transaction_id: str
    state_snapshot: dict[str, Any]
    timestamp: float
    parent_savepoint: Optional["TransactionSavepoint"] = None

    def __post_init__(self):
        """Ensure immutable state snapshot"""
        self.state_snapshot = copy.deepcopy(self.state_snapshot)


@dataclass
class TransactionOperation:
    """Individual transaction operation"""

    operation_id: str
    operation_type: str
    target: str
    parameters: dict[str, Any]
    timestamp: float
    rollback_data: dict[str, Any] | None = None


@dataclass
class NestedTransaction:
    """Nested transaction with savepoint support"""

    transaction_id: str
    name: str
    status: TransactionStatus = TransactionStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    parent_transaction: Optional["NestedTransaction"] = None
    child_transactions: list["NestedTransaction"] = field(default_factory=list)
    savepoints: list[TransactionSavepoint] = field(default_factory=list)
    operations: list[TransactionOperation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        """Check if transaction is active"""
        return self.status == TransactionStatus.ACTIVE

    def is_top_level(self) -> bool:
        """Check if this is a top-level transaction"""
        return self.parent_transaction is None

    def get_depth(self) -> int:
        """Get nesting depth"""
        depth = 0
        current = self.parent_transaction
        while current:
            depth += 1
            current = current.parent_transaction
        return depth


class OptimisticLock:
    """Optimistic locking for concurrent operations"""

    def __init__(self):
        self._resource_versions: dict[str, int] = {}
        self._lock_holders: dict[str, str] = {}

    def acquire_lock(self, resource_id: str, transaction_id: str) -> bool:
        """
        Acquire optimistic lock on resource.

        Args:
            resource_id: Resource identifier
            transaction_id: Transaction attempting lock

        Returns:
            True if lock acquired, False if resource modified
        """
        if resource_id not in self._resource_versions:
            self._resource_versions[resource_id] = 0

        # Check if resource is already locked by different transaction
        current_holder = self._lock_holders.get(resource_id)
        if current_holder and current_holder != transaction_id:
            return False

        self._lock_holders[resource_id] = transaction_id
        return True

    def release_lock(self, resource_id: str, transaction_id: str):
        """Release lock if held by transaction"""
        if self._lock_holders.get(resource_id) == transaction_id:
            del self._lock_holders[resource_id]
            self._resource_versions[resource_id] += 1

    def check_version(self, resource_id: str, expected_version: int) -> bool:
        """Check if resource version matches expected"""
        return self._resource_versions.get(resource_id, 0) == expected_version

    def get_version(self, resource_id: str) -> int:
        """Get current resource version"""
        return self._resource_versions.get(resource_id, 0)


class NestedTransactionManager:
    """
    Advanced transaction manager with nested transaction support.

    Features:
    - Nested transactions with savepoints
    - Automatic rollback on failure
    - Transaction metrics and monitoring
    - Integration with optimistic locking
    """

    def __init__(self, enable_optimistic_locking: bool = True):
        """
        Initialize nested transaction manager.

        Args:
            enable_optimistic_locking: Enable optimistic locking support
        """
        self._active_transactions: dict[str, NestedTransaction] = {}
        self._transaction_stack: list[str] = []  # Stack of transaction IDs
        self._completed_transactions: deque = deque(maxlen=1000)  # History

        # Optimistic locking
        self._optimistic_lock = OptimisticLock() if enable_optimistic_locking else None

        # Metrics
        self._metrics = {
            "transactions_created": 0,
            "transactions_committed": 0,
            "transactions_rolled_back": 0,
            "savepoints_created": 0,
            "max_nesting_depth": 0,
            "avg_transaction_duration": 0.0,
        }

        logger.info("NestedTransactionManager initialized")

    def begin_nested_transaction(
        self,
        name: str,
        initial_state: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Begin a new nested transaction.

        Args:
            name: Human-readable transaction name
            initial_state: Initial state snapshot
            metadata: Additional transaction metadata

        Returns:
            Transaction ID
        """
        transaction_id = str(uuid.uuid4())
        parent_id = self._transaction_stack[-1] if self._transaction_stack else None
        parent_transaction = (
            self._active_transactions.get(parent_id) if parent_id else None
        )

        transaction = NestedTransaction(
            transaction_id=transaction_id,
            name=name,
            parent_transaction=parent_transaction,
            metadata=metadata or {},
        )

        # Create initial savepoint
        if initial_state:
            savepoint = TransactionSavepoint(
                name=f"{name}_initial",
                transaction_id=transaction_id,
                state_snapshot=initial_state,
                timestamp=time.time(),
            )
            transaction.savepoints.append(savepoint)
            self._metrics["savepoints_created"] += 1

        # Add to parent's children
        if parent_transaction:
            parent_transaction.child_transactions.append(transaction)

        # Update tracking
        self._active_transactions[transaction_id] = transaction
        self._transaction_stack.append(transaction_id)
        self._metrics["transactions_created"] += 1

        # Update max nesting depth
        current_depth = transaction.get_depth()
        if current_depth > self._metrics["max_nesting_depth"]:
            self._metrics["max_nesting_depth"] = current_depth

        logger.debug(
            f"Started nested transaction '{name}' (ID: {transaction_id}, depth: {current_depth})"
        )
        return transaction_id

    def create_savepoint(
        self, transaction_id: str, savepoint_name: str, state_snapshot: dict[str, Any]
    ) -> str:
        """
        Create savepoint within transaction.

        Args:
            transaction_id: Transaction to create savepoint in
            savepoint_name: Savepoint name
            state_snapshot: State to save

        Returns:
            Savepoint identifier
        """
        transaction = self._get_active_transaction(transaction_id)

        # Find parent savepoint
        parent_savepoint = (
            transaction.savepoints[-1] if transaction.savepoints else None
        )

        savepoint = TransactionSavepoint(
            name=savepoint_name,
            transaction_id=transaction_id,
            state_snapshot=state_snapshot,
            timestamp=time.time(),
            parent_savepoint=parent_savepoint,
        )

        transaction.savepoints.append(savepoint)
        self._metrics["savepoints_created"] += 1

        logger.debug(
            f"Created savepoint '{savepoint_name}' in transaction {transaction_id}"
        )
        return f"{transaction_id}:{savepoint_name}"

    def add_operation(
        self,
        transaction_id: str,
        operation_type: str,
        target: str,
        parameters: dict[str, Any],
        rollback_data: dict[str, Any] | None = None,
    ):
        """
        Add operation to transaction.

        Args:
            transaction_id: Transaction ID
            operation_type: Type of operation
            target: Operation target
            parameters: Operation parameters
            rollback_data: Data needed for rollback
        """
        transaction = self._get_active_transaction(transaction_id)

        operation = TransactionOperation(
            operation_id=str(uuid.uuid4()),
            operation_type=operation_type,
            target=target,
            parameters=parameters,
            timestamp=time.time(),
            rollback_data=rollback_data,
        )

        transaction.operations.append(operation)

    def commit_nested_transaction(self, transaction_id: str | None = None) -> bool:
        """
        Commit nested transaction.

        Args:
            transaction_id: Specific transaction to commit, or current if None

        Returns:
            True if successfully committed
        """
        if not transaction_id:
            transaction_id = (
                self._transaction_stack[-1] if self._transaction_stack else None
            )

        if not transaction_id:
            raise ValueError("No active transaction to commit")

        transaction = self._get_active_transaction(transaction_id)

        try:
            # Commit all child transactions first
            for child_transaction in transaction.child_transactions:
                if child_transaction.is_active():
                    if not self.commit_nested_transaction(
                        child_transaction.transaction_id
                    ):
                        raise RuntimeError(
                            f"Failed to commit child transaction {child_transaction.transaction_id}"
                        )

            # Mark as committed
            transaction.status = TransactionStatus.COMMITTED
            duration = time.time() - transaction.created_at

            # Update metrics
            self._metrics["transactions_committed"] += 1
            self._update_avg_duration(duration)

            # Remove from active tracking
            self._active_transactions.pop(transaction_id, None)
            if transaction_id in self._transaction_stack:
                self._transaction_stack.remove(transaction_id)

            # Add to completed history
            self._completed_transactions.append(
                {
                    "transaction_id": transaction_id,
                    "name": transaction.name,
                    "status": transaction.status,
                    "duration": duration,
                    "operations_count": len(transaction.operations),
                    "completed_at": time.time(),
                }
            )

            logger.debug(
                f"Committed transaction '{transaction.name}' (ID: {transaction_id}) in {duration:.3f}s"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to commit transaction {transaction_id}: {e}")
            self.rollback_nested_transaction(transaction_id)
            return False

    def rollback_nested_transaction(
        self, transaction_id: str | None = None, savepoint_name: str | None = None
    ) -> bool:
        """
        Rollback nested transaction or to specific savepoint.

        Args:
            transaction_id: Transaction to rollback, or current if None
            savepoint_name: Rollback to specific savepoint, or full rollback if None

        Returns:
            True if successfully rolled back
        """
        if not transaction_id:
            transaction_id = (
                self._transaction_stack[-1] if self._transaction_stack else None
            )

        if not transaction_id:
            raise ValueError("No active transaction to rollback")

        transaction = self._get_active_transaction(transaction_id)

        try:
            if savepoint_name:
                # Rollback to specific savepoint
                self._rollback_to_savepoint(transaction, savepoint_name)
                logger.debug(
                    f"Rolled back transaction {transaction_id} to savepoint '{savepoint_name}'"
                )
            else:
                # Full transaction rollback
                self._rollback_full_transaction(transaction)

                # Mark as rolled back
                transaction.status = TransactionStatus.ROLLED_BACK
                duration = time.time() - transaction.created_at

                # Update metrics
                self._metrics["transactions_rolled_back"] += 1
                self._update_avg_duration(duration)

                # Remove from active tracking
                self._active_transactions.pop(transaction_id, None)
                if transaction_id in self._transaction_stack:
                    self._transaction_stack.remove(transaction_id)

                logger.debug(
                    f"Rolled back transaction '{transaction.name}' (ID: {transaction_id})"
                )

            return True

        except Exception as e:
            logger.error(f"Failed to rollback transaction {transaction_id}: {e}")
            transaction.status = TransactionStatus.FAILED
            return False

    def _rollback_to_savepoint(
        self, transaction: NestedTransaction, savepoint_name: str
    ):
        """Rollback to specific savepoint"""
        # Find the savepoint
        target_savepoint = None
        for savepoint in transaction.savepoints:
            if savepoint.name == savepoint_name:
                target_savepoint = savepoint
                break

        if not target_savepoint:
            raise ValueError(f"Savepoint '{savepoint_name}' not found")

        # Rollback operations after savepoint timestamp
        operations_to_rollback = [
            op
            for op in transaction.operations
            if op.timestamp > target_savepoint.timestamp
        ]

        for operation in reversed(operations_to_rollback):
            self._rollback_operation(operation)

        # Remove operations after savepoint
        transaction.operations = [
            op
            for op in transaction.operations
            if op.timestamp <= target_savepoint.timestamp
        ]

        # Remove savepoints after target
        transaction.savepoints = [
            sp
            for sp in transaction.savepoints
            if sp.timestamp <= target_savepoint.timestamp
        ]

    def _rollback_full_transaction(self, transaction: NestedTransaction):
        """Rollback entire transaction"""
        # Rollback all child transactions first
        for child_transaction in reversed(transaction.child_transactions):
            if child_transaction.is_active():
                self.rollback_nested_transaction(child_transaction.transaction_id)

        # Rollback all operations in reverse order
        for operation in reversed(transaction.operations):
            self._rollback_operation(operation)

    def _rollback_operation(self, operation: TransactionOperation):
        """Rollback individual operation"""
        if operation.rollback_data:
            logger.debug(
                f"Rolling back operation {operation.operation_id} ({operation.operation_type})"
            )
            # Implementation would depend on operation type
            # This is a placeholder for actual rollback logic

    def acquire_optimistic_lock(self, transaction_id: str, resource_id: str) -> bool:
        """Acquire optimistic lock for transaction"""
        if not self._optimistic_lock:
            return True  # Locking disabled

        self._get_active_transaction(transaction_id)
        return self._optimistic_lock.acquire_lock(resource_id, transaction_id)

    def release_optimistic_lock(self, transaction_id: str, resource_id: str):
        """Release optimistic lock"""
        if self._optimistic_lock:
            self._optimistic_lock.release_lock(resource_id, transaction_id)

    def get_current_transaction(self) -> NestedTransaction | None:
        """Get current active transaction"""
        if not self._transaction_stack:
            return None
        current_id = self._transaction_stack[-1]
        return self._active_transactions.get(current_id)

    def get_transaction_info(self, transaction_id: str) -> dict[str, Any]:
        """Get detailed transaction information"""
        transaction = self._active_transactions.get(transaction_id)
        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")

        return {
            "transaction_id": transaction.transaction_id,
            "name": transaction.name,
            "status": transaction.status,
            "created_at": transaction.created_at,
            "duration": time.time() - transaction.created_at,
            "depth": transaction.get_depth(),
            "is_top_level": transaction.is_top_level(),
            "savepoints_count": len(transaction.savepoints),
            "operations_count": len(transaction.operations),
            "child_transactions": len(transaction.child_transactions),
            "metadata": transaction.metadata,
        }

    def get_metrics(self) -> dict[str, Any]:
        """Get transaction manager metrics"""
        return {
            **self._metrics,
            "active_transactions": len(self._active_transactions),
            "transaction_stack_depth": len(self._transaction_stack),
            "completed_transactions_cached": len(self._completed_transactions),
        }

    def _get_active_transaction(self, transaction_id: str) -> NestedTransaction:
        """Get active transaction or raise error"""
        transaction = self._active_transactions.get(transaction_id)
        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found or not active")
        if not transaction.is_active():
            raise ValueError(
                f"Transaction {transaction_id} is not active (status: {transaction.status})"
            )
        return transaction

    def _update_avg_duration(self, duration: float):
        """Update average transaction duration"""
        total_transactions = (
            self._metrics["transactions_committed"]
            + self._metrics["transactions_rolled_back"]
        )
        if total_transactions == 1:
            self._metrics["avg_transaction_duration"] = duration
        else:
            # Moving average
            self._metrics["avg_transaction_duration"] = (
                self._metrics["avg_transaction_duration"] * (total_transactions - 1)
                + duration
            ) / total_transactions

    @contextmanager
    def transaction(
        self,
        name: str,
        initial_state: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Context manager for nested transactions.

        Args:
            name: Transaction name
            initial_state: Initial state snapshot
            metadata: Transaction metadata

        Example:
            with manager.transaction("update_player_score"):
                # Transaction operations
                pass
        """
        transaction_id = self.begin_nested_transaction(name, initial_state, metadata)
        try:
            yield transaction_id
            if not self.commit_nested_transaction(transaction_id):
                raise RuntimeError(f"Failed to commit transaction {transaction_id}")
        except Exception as e:
            logger.error(f"Transaction '{name}' failed: {e}")
            self.rollback_nested_transaction(transaction_id)
            raise


class TransactionPool:
    """Pool of reusable transaction managers for high concurrency"""

    def __init__(self, pool_size: int = 10):
        """
        Initialize transaction pool.

        Args:
            pool_size: Number of transaction managers to pool
        """
        self.pool_size = pool_size
        self._available_managers: deque = deque()
        self._active_managers: dict[str, NestedTransactionManager] = {}

        # Pre-populate pool
        for _ in range(pool_size):
            manager = NestedTransactionManager()
            self._available_managers.append(manager)

        logger.info(f"TransactionPool initialized with {pool_size} managers")

    def acquire_manager(self) -> NestedTransactionManager:
        """Acquire transaction manager from pool"""
        if self._available_managers:
            manager = self._available_managers.popleft()
        else:
            # Pool exhausted, create new manager
            manager = NestedTransactionManager()
            logger.warning("Transaction pool exhausted, creating new manager")

        manager_id = str(uuid.uuid4())
        self._active_managers[manager_id] = manager
        manager._pool_id = manager_id  # Track for return

        return manager

    def release_manager(self, manager: NestedTransactionManager):
        """Return transaction manager to pool"""
        pool_id = getattr(manager, "_pool_id", None)
        if pool_id and pool_id in self._active_managers:
            del self._active_managers[pool_id]

            # Reset manager state before returning to pool
            manager._active_transactions.clear()
            manager._transaction_stack.clear()

            if len(self._available_managers) < self.pool_size:
                self._available_managers.append(manager)
            # If pool is full, let manager be garbage collected

    def get_pool_statistics(self) -> dict[str, Any]:
        """Get pool usage statistics"""
        return {
            "pool_size": self.pool_size,
            "available_managers": len(self._available_managers),
            "active_managers": len(self._active_managers),
            "utilization": len(self._active_managers) / self.pool_size,
        }


# Global instances
_nested_transaction_manager: NestedTransactionManager | None = None
_transaction_pool: TransactionPool | None = None


def get_nested_transaction_manager() -> NestedTransactionManager:
    """Get global nested transaction manager instance"""
    global _nested_transaction_manager
    if _nested_transaction_manager is None:
        _nested_transaction_manager = NestedTransactionManager()
    return _nested_transaction_manager


def get_transaction_pool() -> TransactionPool:
    """Get global transaction pool instance"""
    global _transaction_pool
    if _transaction_pool is None:
        _transaction_pool = TransactionPool()
    return _transaction_pool
