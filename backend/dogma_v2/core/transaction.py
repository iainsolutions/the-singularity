"""
Transaction management for dogma execution.

This module provides transaction tracking and management capabilities
for dogma execution, including rollback and recovery functionality.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .context import StateSnapshot

logger = logging.getLogger(__name__)


class TransactionStatus(Enum):
    """Status of dogma transaction"""

    PENDING = "pending"  # Transaction in progress
    SUSPENDED = "suspended"  # Transaction suspended for interaction
    COMPLETE = "complete"  # Transaction completed successfully
    ERROR = "error"  # Transaction failed
    ABANDONED = "abandoned"  # Transaction abandoned (timeout/cancel)
    ROLLED_BACK = "rolled_back"  # Transaction rolled back  # Transaction rolled back


@dataclass
class PhaseRecord:
    """Record of single phase execution"""

    phase_name: str
    started_at: datetime
    completed_at: datetime | None = None
    input_variables: dict[str, Any] = field(default_factory=dict)
    output_variables: dict[str, Any] = field(default_factory=dict)
    results_added: list[str] = field(default_factory=list)
    error_message: str | None = None
    sub_phases: list[PhaseRecord] = field(default_factory=list)

    def mark_complete(self, output_vars: dict[str, Any], results: list[str]) -> None:
        """Mark phase as completed with results"""
        self.completed_at = datetime.now()
        self.output_variables = output_vars.copy()
        self.results_added = results.copy()

    def mark_error(self, error_message: str) -> None:
        """Mark phase as failed with error"""
        self.completed_at = datetime.now()
        self.error_message = error_message

    def duration_ms(self) -> float | None:
        """Get phase duration in milliseconds"""
        if self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds() * 1000
        return None


@dataclass
class InteractionRecord:
    """Record of player interaction"""

    interaction_id: str
    player_id: str
    interaction_type: str
    requested_at: datetime
    responded_at: datetime | None = None
    response_data: dict[str, Any] | None = None
    timeout_seconds: int | None = None
    was_timeout: bool = False

    def mark_response(self, response: dict[str, Any]) -> None:
        """Mark interaction as responded to"""
        self.responded_at = datetime.now()
        self.response_data = response.copy()

    def mark_timeout(self) -> None:
        """Mark interaction as timed out"""
        self.responded_at = datetime.now()
        self.was_timeout = True

    def response_time_ms(self) -> float | None:
        """Get response time in milliseconds"""
        if self.responded_at:
            delta = self.responded_at - self.requested_at
            return delta.total_seconds() * 1000
        return None


@dataclass
class DogmaTransaction:
    """
    Complete record of dogma execution.

    This class tracks all aspects of a dogma transaction including
    phases executed, interactions, state changes, and final results.
    """

    # Identification
    id: str
    game_id: str
    player_id: str
    card_name: str

    # Timing
    started_at: datetime
    completed_at: datetime | None = None

    # Execution tracking
    phases_executed: list[PhaseRecord] = field(default_factory=list)
    interactions: list[InteractionRecord] = field(default_factory=list)

    # Results
    status: TransactionStatus = TransactionStatus.PENDING
    final_results: list[str] = field(default_factory=list)
    error_message: str | None = None

    # State management
    initial_state: StateSnapshot | None = None
    final_state: StateSnapshot | None = None
    checkpoints: dict[str, StateSnapshot] = field(default_factory=dict)

    @classmethod
    def create(cls, game_id: str, player_id: str, card_name: str) -> DogmaTransaction:
        """Create new transaction"""
        return cls(
            id=str(uuid.uuid4()),
            game_id=game_id,
            player_id=player_id,
            card_name=card_name,
            started_at=datetime.now(),
        )

    def add_phase(self, phase_name: str, input_vars: dict[str, Any]) -> PhaseRecord:
        """Start new phase and return record for tracking"""
        record = PhaseRecord(
            phase_name=phase_name,
            started_at=datetime.now(),
            input_variables=input_vars.copy(),
        )
        self.phases_executed.append(record)
        return record

    def add_interaction(
        self,
        interaction_id: str,
        player_id: str,
        interaction_type: str,
        timeout: int | None = None,
    ) -> InteractionRecord:
        """Start new interaction and return record for tracking"""
        record = InteractionRecord(
            interaction_id=interaction_id,
            player_id=player_id,
            interaction_type=interaction_type,
            requested_at=datetime.now(),
            timeout_seconds=timeout,
        )
        self.interactions.append(record)
        return record

    def create_checkpoint(self, name: str, snapshot: StateSnapshot) -> None:
        """Create named checkpoint for potential rollback"""
        self.checkpoints[name] = snapshot

    def mark_complete(
        self, results: list[str], final_state: StateSnapshot | None = None
    ) -> None:
        """Mark transaction as completed successfully"""
        self.completed_at = datetime.now()
        self.status = TransactionStatus.COMPLETE
        self.final_results = results.copy()
        self.final_state = final_state

    def mark_error(self, error_message: str) -> None:
        """Mark transaction as failed with error"""
        self.completed_at = datetime.now()
        self.status = TransactionStatus.ERROR
        self.error_message = error_message

    def mark_abandoned(self, reason: str = "abandoned") -> None:
        """Mark transaction as abandoned"""
        self.completed_at = datetime.now()
        self.status = TransactionStatus.ABANDONED
        self.error_message = reason

    def mark_rolled_back(self, checkpoint: str | None = None) -> None:
        """Mark transaction as rolled back"""
        self.completed_at = datetime.now()
        self.status = TransactionStatus.ROLLED_BACK
        if checkpoint:
            self.error_message = f"Rolled back to checkpoint: {checkpoint}"

    def set_suspended_state(self, phase: str, context: Any) -> None:
        """Set the suspended phase and context for interaction handling"""
        # DEBUG: Log what we're storing
        logger.debug("TRANSACTION DEBUG: set_suspended_state called")
        logger.debug(f"TRANSACTION DEBUG: phase = {phase}")
        logger.debug(f"TRANSACTION DEBUG: context = {context}")
        logger.debug(f"TRANSACTION DEBUG: context is None? {context is None}")

        self.status = TransactionStatus.SUSPENDED
        # Store suspended state information for later resumption
        # Store the actual context object, not a string representation
        suspended_info = {
            "phase": phase,
            "context": context,  # Store the actual object
            "timestamp": datetime.now().isoformat(),
        }
        self.checkpoints["suspended_state"] = suspended_info

        # DEBUG: Verify it was stored
        logger.debug(
            f"TRANSACTION DEBUG: Stored suspended_info with context={suspended_info.get('context')}"
        )

    def get_suspended_phase(self) -> str | None:
        """Get the phase name where execution was suspended"""
        suspended_info = self.checkpoints.get("suspended_state")
        if suspended_info and isinstance(suspended_info, dict):
            return suspended_info.get("phase")
        return None

    def get_suspended_context(self) -> Any:
        """Get the context object from when execution was suspended"""
        suspended_info = self.checkpoints.get("suspended_state")

        # DEBUG: Log what we're retrieving
        logger.debug("TRANSACTION DEBUG: get_suspended_context called")
        logger.debug(
            f"TRANSACTION DEBUG: suspended_info exists? {suspended_info is not None}"
        )
        logger.debug(
            f"TRANSACTION DEBUG: suspended_info is dict? {isinstance(suspended_info, dict)}"
        )

        if suspended_info and isinstance(suspended_info, dict):
            context = suspended_info.get("context")
            logger.debug(f"TRANSACTION DEBUG: Retrieved context = {context}")
            logger.debug(
                f"TRANSACTION DEBUG: Retrieved context is None? {context is None}"
            )
            return context

        logger.debug("TRANSACTION DEBUG: Returning None (suspended_info invalid)")
        return None

    def clear_suspended_state(self) -> None:
        """Clear suspended state after successful resumption"""
        if "suspended_state" in self.checkpoints:
            del self.checkpoints["suspended_state"]
        # Only clear suspended status if transaction was actually suspended
        if self.status == TransactionStatus.SUSPENDED:
            self.status = TransactionStatus.PENDING

    @property
    def is_suspended(self) -> bool:
        """Check if transaction is currently suspended"""
        return self.status == TransactionStatus.SUSPENDED

    def duration_ms(self) -> float | None:
        """Get total transaction duration in milliseconds"""
        if self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds() * 1000
        return None

    def get_current_phase(self) -> PhaseRecord | None:
        """Get currently executing phase record"""
        if self.phases_executed:
            last_phase = self.phases_executed[-1]
            if last_phase.completed_at is None:
                return last_phase
        return None

    def get_pending_interaction(self) -> InteractionRecord | None:
        """Get currently pending interaction record"""
        if self.interactions:
            last_interaction = self.interactions[-1]
            if last_interaction.responded_at is None:
                return last_interaction
        return None

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary for monitoring"""
        total_duration = self.duration_ms()
        phase_durations = {
            record.phase_name: record.duration_ms()
            for record in self.phases_executed
            if record.duration_ms() is not None
        }
        interaction_durations = {
            record.interaction_type: record.response_time_ms()
            for record in self.interactions
            if record.response_time_ms() is not None
        }

        return {
            "transaction_id": self.id,
            "status": self.status.value,
            "total_duration_ms": total_duration,
            "phase_count": len(self.phases_executed),
            "interaction_count": len(self.interactions),
            "phase_durations": phase_durations,
            "interaction_durations": interaction_durations,
            "has_error": self.error_message is not None,
            "error_message": self.error_message,
        }

    def __str__(self) -> str:
        """String representation for debugging"""
        return (
            f"Transaction(id={self.id[:8]}..., card={self.card_name}, "
            f"status={self.status.value}, phases={len(self.phases_executed)})"
        )

    def __repr__(self) -> str:
        return self.__str__()


class TransactionManager:
    """
    Manages active and completed dogma transactions.

    Provides transaction lifecycle management, performance monitoring,
    and cleanup capabilities.
    """

    def __init__(
        self,
        max_completed_transactions: int = 1000,
        transaction_timeout_seconds: int = 300,
    ):
        self.active_transactions: dict[str, DogmaTransaction] = {}
        self.completed_transactions: list[DogmaTransaction] = []
        self.max_completed_transactions = max_completed_transactions
        self.transaction_timeout_seconds = transaction_timeout_seconds

    def begin_transaction(
        self, game_id: str, player_id: str, card_name: str
    ) -> DogmaTransaction:
        """Create and register new transaction"""
        transaction = DogmaTransaction.create(game_id, player_id, card_name)
        self.active_transactions[transaction.id] = transaction

        logger.info(f"Started dogma transaction {transaction.id} for {card_name}")
        return transaction

    def get_transaction(self, transaction_id: str) -> DogmaTransaction | None:
        """Get transaction by ID"""
        return self.active_transactions.get(transaction_id)

    def complete_transaction(
        self,
        transaction_id: str,
        results: list[str],
        final_state: StateSnapshot | None = None,
    ) -> bool:
        """Mark transaction as completed and move to history"""
        transaction = self.active_transactions.pop(transaction_id, None)
        if transaction:
            transaction.mark_complete(results, final_state)
            self._add_completed_transaction(transaction)
            logger.info(f"Completed dogma transaction {transaction_id}")
            return True
        return False

    def fail_transaction(self, transaction_id: str, error_message: str) -> bool:
        """Mark transaction as failed and move to history"""
        transaction = self.active_transactions.pop(transaction_id, None)
        if transaction:
            transaction.mark_error(error_message)
            self._add_completed_transaction(transaction)
            logger.error(f"Failed dogma transaction {transaction_id}: {error_message}")
            return True
        return False

    def abandon_transaction(
        self, transaction_id: str, reason: str = "abandoned"
    ) -> bool:
        """Mark transaction as abandoned and move to history"""
        transaction = self.active_transactions.pop(transaction_id, None)
        if transaction:
            transaction.mark_abandoned(reason)
            self._add_completed_transaction(transaction)
            logger.warning(f"Abandoned dogma transaction {transaction_id}: {reason}")
            return True
        return False

    def cleanup_expired_transactions(self) -> int:
        """Clean up transactions that have exceeded timeout"""
        now = datetime.now()
        expired_ids = []

        for transaction_id, transaction in self.active_transactions.items():
            age_seconds = (now - transaction.started_at).total_seconds()
            if age_seconds > self.transaction_timeout_seconds:
                expired_ids.append(transaction_id)

        for transaction_id in expired_ids:
            self.abandon_transaction(transaction_id, "timeout")

        return len(expired_ids)

    def get_performance_stats(self) -> dict[str, Any]:
        """Get system performance statistics"""
        active_count = len(self.active_transactions)
        completed_count = len(self.completed_transactions)

        if self.completed_transactions:
            avg_duration = sum(
                t.duration_ms() or 0 for t in self.completed_transactions[-100:]
            ) / min(100, len(self.completed_transactions))

            error_count = sum(
                1
                for t in self.completed_transactions[-100:]
                if t.status == TransactionStatus.ERROR
            )
        else:
            avg_duration = 0
            error_count = 0

        return {
            "active_transactions": active_count,
            "completed_transactions": completed_count,
            "avg_duration_ms": avg_duration,
            "recent_error_rate": (
                error_count / min(100, completed_count) if completed_count > 0 else 0
            ),
            "memory_usage_estimate": self._estimate_memory_usage(),
        }

    def _add_completed_transaction(self, transaction: DogmaTransaction) -> None:
        """Add transaction to completed list with size management"""
        self.completed_transactions.append(transaction)

        # Keep only recent transactions to manage memory
        if len(self.completed_transactions) > self.max_completed_transactions:
            self.completed_transactions = self.completed_transactions[
                -self.max_completed_transactions :
            ]

    def _estimate_memory_usage(self) -> dict[str, int]:
        """Rough estimate of memory usage"""
        return {
            "active_transactions_count": len(self.active_transactions),
            "completed_transactions_count": len(self.completed_transactions),
            "total_phase_records": sum(
                len(t.phases_executed)
                for t in list(self.active_transactions.values())
                + self.completed_transactions
            ),
            "total_interaction_records": sum(
                len(t.interactions)
                for t in list(self.active_transactions.values())
                + self.completed_transactions
            ),
        }
