"""
Transaction pool management for high-performance transaction handling.

Provides efficient pooling and reuse of transaction managers for
concurrent operations with minimal overhead.
"""

import logging
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from typing import ContextManager

from .nested_manager import NestedTransactionManager

logger = logging.getLogger(__name__)


@dataclass
class PooledTransaction:
    """Wrapper for pooled transaction manager"""

    manager: NestedTransactionManager
    acquired_at: float
    pool_id: str
    in_use: bool = True

    def get_usage_duration(self) -> float:
        """Get how long transaction has been in use"""
        return time.time() - self.acquired_at


class TransactionPoolManager:
    """
    Advanced transaction pool manager with monitoring and optimization.

    Features:
    - Dynamic pool sizing based on load
    - Transaction manager reuse and lifecycle management
    - Pool health monitoring and statistics
    - Automatic cleanup of stale transactions
    """

    def __init__(
        self,
        initial_pool_size: int = 10,
        max_pool_size: int = 50,
        min_pool_size: int = 2,
        cleanup_interval: float = 60.0,
        max_idle_time: float = 300.0,
    ):
        """
        Initialize transaction pool manager.

        Args:
            initial_pool_size: Initial number of pooled managers
            max_pool_size: Maximum pool size
            min_pool_size: Minimum pool size
            cleanup_interval: Cleanup interval in seconds
            max_idle_time: Maximum idle time before cleanup
        """
        self.initial_pool_size = initial_pool_size
        self.max_pool_size = max_pool_size
        self.min_pool_size = min_pool_size
        self.cleanup_interval = cleanup_interval
        self.max_idle_time = max_idle_time

        # Pool management
        self._available_managers: deque = deque()
        self._active_managers: dict[str, PooledTransaction] = {}
        self._pool_lock = threading.RLock()
        self._manager_counter = 0

        # Statistics
        self._stats = {
            "managers_created": 0,
            "managers_acquired": 0,
            "managers_released": 0,
            "pool_hits": 0,
            "pool_misses": 0,
            "peak_active_managers": 0,
            "total_acquisition_time": 0.0,
            "avg_acquisition_time": 0.0,
        }

        # Initialize pool
        self._initialize_pool()

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_worker, daemon=True, name="TransactionPoolCleanup"
        )
        self._cleanup_thread.start()

        logger.info(f"TransactionPoolManager initialized (size: {initial_pool_size})")

    def _initialize_pool(self):
        """Initialize the transaction manager pool"""
        with self._pool_lock:
            for _ in range(self.initial_pool_size):
                manager = self._create_new_manager()
                self._available_managers.append(manager)

    def _create_new_manager(self) -> NestedTransactionManager:
        """Create new transaction manager"""
        self._manager_counter += 1
        self._stats["managers_created"] += 1

        manager = NestedTransactionManager()
        manager._pool_manager_id = f"pool_manager_{self._manager_counter}"

        return manager

    def acquire_transaction_manager(
        self, timeout: float = 5.0
    ) -> NestedTransactionManager:
        """
        Acquire transaction manager from pool.

        Args:
            timeout: Maximum wait time for acquisition

        Returns:
            NestedTransactionManager instance

        Raises:
            TimeoutError: If manager cannot be acquired within timeout
        """
        start_time = time.time()

        with self._pool_lock:
            # Try to get from available pool first
            if self._available_managers:
                manager = self._available_managers.popleft()
                pool_id = f"active_{int(time.time())}_{len(self._active_managers)}"

                pooled_transaction = PooledTransaction(
                    manager=manager, acquired_at=time.time(), pool_id=pool_id
                )

                self._active_managers[pool_id] = pooled_transaction
                self._stats["managers_acquired"] += 1
                self._stats["pool_hits"] += 1

                # Update peak active count
                active_count = len(self._active_managers)
                if active_count > self._stats["peak_active_managers"]:
                    self._stats["peak_active_managers"] = active_count

                acquisition_time = time.time() - start_time
                self._update_acquisition_time(acquisition_time)

                logger.debug(f"Acquired manager from pool (ID: {pool_id})")
                return manager

            # Pool is empty, create new if under max size
            elif len(self._active_managers) < self.max_pool_size:
                manager = self._create_new_manager()
                pool_id = f"active_{int(time.time())}_{len(self._active_managers)}"

                pooled_transaction = PooledTransaction(
                    manager=manager, acquired_at=time.time(), pool_id=pool_id
                )

                self._active_managers[pool_id] = pooled_transaction
                self._stats["managers_acquired"] += 1
                self._stats["pool_misses"] += 1

                active_count = len(self._active_managers)
                if active_count > self._stats["peak_active_managers"]:
                    self._stats["peak_active_managers"] = active_count

                acquisition_time = time.time() - start_time
                self._update_acquisition_time(acquisition_time)

                logger.debug(f"Created new manager (ID: {pool_id})")
                return manager

            else:
                # Pool exhausted and at max size
                raise RuntimeError("Transaction pool exhausted and at maximum size")

    def release_transaction_manager(self, manager: NestedTransactionManager):
        """
        Release transaction manager back to pool.

        Args:
            manager: Manager to release
        """
        pool_manager_id = getattr(manager, "_pool_manager_id", None)
        if not pool_manager_id:
            logger.warning("Attempted to release manager not from pool")
            return

        with self._pool_lock:
            # Find the pooled transaction
            pooled_transaction = None
            pool_id_to_remove = None

            for pool_id, pooled_tx in self._active_managers.items():
                if pooled_tx.manager is manager:
                    pooled_transaction = pooled_tx
                    pool_id_to_remove = pool_id
                    break

            if not pooled_transaction:
                logger.warning("Manager not found in active pool")
                return

            # Remove from active
            del self._active_managers[pool_id_to_remove]

            # Reset manager state
            self._reset_manager(manager)

            # Return to available pool if under max size
            if len(self._available_managers) < self.initial_pool_size:
                self._available_managers.append(manager)
                self._stats["managers_released"] += 1
                logger.debug(f"Released manager back to pool (ID: {pool_id_to_remove})")
            else:
                # Pool is full, let manager be garbage collected
                self._stats["managers_released"] += 1
                logger.debug(f"Manager released (pool full) (ID: {pool_id_to_remove})")

    def _reset_manager(self, manager: NestedTransactionManager):
        """Reset manager state for reuse"""
        try:
            # Clear any active transactions (force rollback)
            for tx_id in list(manager._active_transactions.keys()):
                try:
                    manager.rollback_nested_transaction(tx_id)
                except Exception as e:
                    logger.warning(
                        f"Failed to rollback transaction {tx_id} during reset: {e}"
                    )

            # Clear state
            manager._active_transactions.clear()
            manager._transaction_stack.clear()
            manager._completed_transactions.clear()

            # Reset optimistic locking
            if manager._optimistic_lock:
                manager._optimistic_lock._resource_versions.clear()
                manager._optimistic_lock._lock_holders.clear()

        except Exception as e:
            logger.error(f"Failed to reset manager: {e}")

    def _update_acquisition_time(self, acquisition_time: float):
        """Update acquisition time statistics"""
        self._stats["total_acquisition_time"] += acquisition_time
        acquired_count = self._stats["managers_acquired"]
        self._stats["avg_acquisition_time"] = (
            self._stats["total_acquisition_time"] / acquired_count
        )

    def _cleanup_worker(self):
        """Background worker for cleanup operations"""
        while True:
            try:
                time.sleep(self.cleanup_interval)
                self._cleanup_stale_managers()
                self._adjust_pool_size()
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")

    def _cleanup_stale_managers(self):
        """Clean up managers that have been active too long"""
        current_time = time.time()
        stale_managers = []

        with self._pool_lock:
            for pool_id, pooled_tx in self._active_managers.items():
                if current_time - pooled_tx.acquired_at > self.max_idle_time:
                    stale_managers.append((pool_id, pooled_tx))

            for pool_id, pooled_tx in stale_managers:
                logger.warning(f"Cleaning up stale manager (ID: {pool_id})")
                try:
                    self._reset_manager(pooled_tx.manager)
                    del self._active_managers[pool_id]
                except Exception as e:
                    logger.error(f"Failed to cleanup stale manager {pool_id}: {e}")

    def _adjust_pool_size(self):
        """Dynamically adjust pool size based on usage patterns"""
        with self._pool_lock:
            available_count = len(self._available_managers)
            active_count = len(self._active_managers)

            # If pool is consistently empty, grow it
            if available_count == 0 and active_count > 0:
                growth_target = min(
                    self.initial_pool_size, self.max_pool_size - active_count
                )

                for _ in range(growth_target):
                    manager = self._create_new_manager()
                    self._available_managers.append(manager)

                if growth_target > 0:
                    logger.info(f"Grew pool by {growth_target} managers")

            # If pool is too large and usage is low, shrink it
            elif (
                available_count > self.initial_pool_size
                and active_count < self.min_pool_size
            ):
                shrink_count = available_count - self.initial_pool_size
                for _ in range(shrink_count):
                    if self._available_managers:
                        self._available_managers.popleft()

                if shrink_count > 0:
                    logger.info(f"Shrunk pool by {shrink_count} managers")

    @contextmanager
    def transaction_manager(self) -> ContextManager[NestedTransactionManager]:
        """
        Context manager for acquiring/releasing transaction manager.

        Example:
            with pool.transaction_manager() as manager:
                with manager.transaction("update_game_state"):
                    # Transaction operations
                    pass
        """
        manager = self.acquire_transaction_manager()
        try:
            yield manager
        finally:
            self.release_transaction_manager(manager)

    def get_pool_statistics(self) -> dict[str, any]:
        """Get comprehensive pool statistics"""
        with self._pool_lock:
            time.time()
            active_usage_times = [
                pooled_tx.get_usage_duration()
                for pooled_tx in self._active_managers.values()
            ]

            return {
                **self._stats,
                "pool_config": {
                    "initial_size": self.initial_pool_size,
                    "max_size": self.max_pool_size,
                    "min_size": self.min_pool_size,
                    "cleanup_interval": self.cleanup_interval,
                    "max_idle_time": self.max_idle_time,
                },
                "current_state": {
                    "available_managers": len(self._available_managers),
                    "active_managers": len(self._active_managers),
                    "total_managers": len(self._available_managers)
                    + len(self._active_managers),
                    "utilization_rate": len(self._active_managers) / self.max_pool_size,
                },
                "usage_statistics": {
                    "avg_active_usage_time": sum(active_usage_times)
                    / len(active_usage_times)
                    if active_usage_times
                    else 0,
                    "max_active_usage_time": max(active_usage_times)
                    if active_usage_times
                    else 0,
                    "pool_hit_rate": self._stats["pool_hits"]
                    / max(self._stats["managers_acquired"], 1),
                },
            }

    def get_health_status(self) -> dict[str, any]:
        """Get pool health status"""
        stats = self.get_pool_statistics()
        utilization = stats["current_state"]["utilization_rate"]
        hit_rate = stats["usage_statistics"]["pool_hit_rate"]

        health_score = 1.0
        issues = []

        # Check utilization
        if utilization > 0.9:
            health_score -= 0.3
            issues.append("High utilization - consider increasing pool size")
        elif (
            utilization < 0.1
            and stats["current_state"]["available_managers"] > self.initial_pool_size
        ):
            health_score -= 0.1
            issues.append("Low utilization - pool may be oversized")

        # Check hit rate
        if hit_rate < 0.7:
            health_score -= 0.2
            issues.append("Low pool hit rate - pool may be undersized")

        # Check acquisition time
        if stats["avg_acquisition_time"] > 0.001:  # 1ms
            health_score -= 0.1
            issues.append("High acquisition time")

        return {
            "health_score": max(0, health_score),
            "status": "healthy"
            if health_score > 0.7
            else "warning"
            if health_score > 0.3
            else "critical",
            "issues": issues,
            "recommendations": self._generate_recommendations(stats),
        }

    def _generate_recommendations(self, stats: dict[str, any]) -> list[str]:
        """Generate optimization recommendations"""
        recommendations = []
        utilization = stats["current_state"]["utilization_rate"]
        hit_rate = stats["usage_statistics"]["pool_hit_rate"]

        if utilization > 0.8:
            recommendations.append("Consider increasing max_pool_size")

        if hit_rate < 0.8:
            recommendations.append("Consider increasing initial_pool_size")

        if stats["avg_acquisition_time"] > 0.001:
            recommendations.append(
                "Consider reducing cleanup_interval for better responsiveness"
            )

        return recommendations


# Global pool instance
_transaction_pool_manager: TransactionPoolManager | None = None


def get_transaction_pool_manager() -> TransactionPoolManager:
    """Get global transaction pool manager instance"""
    global _transaction_pool_manager
    if _transaction_pool_manager is None:
        _transaction_pool_manager = TransactionPoolManager()
    return _transaction_pool_manager
