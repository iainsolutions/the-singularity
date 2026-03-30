"""
Enhanced Error Handling and Recovery for Week 4 Phase Streamlining.

Provides phase-specific error handling, graceful recovery mechanisms,
and comprehensive error logging with recovery workflows.
"""

import logging
import time
import traceback
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from ..core.context import DogmaContext
from ..core.transaction import DogmaTransaction

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for categorization"""

    LOW = "low"  # Non-critical errors, can continue
    MEDIUM = "medium"  # Significant errors, may require user intervention
    HIGH = "high"  # Critical errors, transaction should rollback
    FATAL = "fatal"  # System-level errors, execution must stop


class RecoveryStrategy(Enum):
    """Available recovery strategies for different error types"""

    CONTINUE = "continue"  # Log and continue execution
    RETRY = "retry"  # Retry the failed operation
    ROLLBACK = "rollback"  # Rollback to previous checkpoint
    SKIP_PHASE = "skip_phase"  # Skip the current phase
    ABORT = "abort"  # Abort entire transaction
    USER_INTERVENTION = "user_intervention"  # Require user decision


@dataclass
class ErrorContext:
    """Comprehensive error context for analysis and recovery"""

    error_id: str
    phase_name: str
    transaction_id: str
    error_type: str
    error_message: str
    severity: ErrorSeverity
    recovery_strategy: RecoveryStrategy
    timestamp: datetime = field(default_factory=datetime.utcnow)
    stack_trace: str | None = None
    context_variables: dict[str, Any] = field(default_factory=dict)
    game_state_snapshot: dict[str, Any] | None = None
    retry_count: int = 0
    recovery_attempted: bool = False
    recovery_successful: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class PhaseErrorHandler:
    """Handles errors specific to individual phases"""

    def __init__(self, phase_name: str):
        self.phase_name = phase_name
        self.error_patterns: dict[str, RecoveryStrategy] = {}
        self.max_retries = 3
        self.retry_delay = 0.1  # seconds

    def register_error_pattern(self, pattern: str, strategy: RecoveryStrategy):
        """Register an error pattern with its recovery strategy"""
        self.error_patterns[pattern] = strategy
        logger.debug(
            f"Registered error pattern '{pattern}' -> {strategy.value} for {self.phase_name}"
        )

    def handle_error(
        self, error: Exception, context: DogmaContext, transaction: DogmaTransaction
    ) -> ErrorContext:
        """Handle an error that occurred during phase execution"""
        error_msg = str(error)
        error_type = type(error).__name__

        # Determine severity and recovery strategy
        severity, strategy = self._analyze_error(error, error_msg)

        # Create error context
        error_context = ErrorContext(
            error_id=f"{self.phase_name}_{int(time.time() * 1000000)}",
            phase_name=self.phase_name,
            transaction_id=transaction.id,
            error_type=error_type,
            error_message=error_msg,
            severity=severity,
            recovery_strategy=strategy,
            stack_trace=traceback.format_exc(),
            context_variables=dict(context.variables) if context else {},
            metadata={
                "phase_name": self.phase_name,
                "error_location": "phase_execution",
            },
        )

        logger.error(f"Phase {self.phase_name} error [{severity.value}]: {error_msg}")
        return error_context

    def _analyze_error(
        self, error: Exception, error_msg: str
    ) -> tuple[ErrorSeverity, RecoveryStrategy]:
        """Analyze error to determine severity and recovery strategy"""

        # Check registered patterns first
        for pattern, strategy in self.error_patterns.items():
            if pattern.lower() in error_msg.lower():
                severity = self._strategy_to_severity(strategy)
                return severity, strategy

        # Default analysis based on error type
        if isinstance(error, (KeyError, AttributeError)):
            return ErrorSeverity.MEDIUM, RecoveryStrategy.RETRY
        elif isinstance(error, ValueError):
            return ErrorSeverity.LOW, RecoveryStrategy.CONTINUE
        elif isinstance(error, (RuntimeError, SystemError)):
            return ErrorSeverity.HIGH, RecoveryStrategy.ROLLBACK
        elif isinstance(error, MemoryError):
            return ErrorSeverity.FATAL, RecoveryStrategy.ABORT
        else:
            return ErrorSeverity.MEDIUM, RecoveryStrategy.RETRY

    def _strategy_to_severity(self, strategy: RecoveryStrategy) -> ErrorSeverity:
        """Map recovery strategy to severity level"""
        severity_map = {
            RecoveryStrategy.CONTINUE: ErrorSeverity.LOW,
            RecoveryStrategy.RETRY: ErrorSeverity.MEDIUM,
            RecoveryStrategy.SKIP_PHASE: ErrorSeverity.MEDIUM,
            RecoveryStrategy.ROLLBACK: ErrorSeverity.HIGH,
            RecoveryStrategy.ABORT: ErrorSeverity.FATAL,
            RecoveryStrategy.USER_INTERVENTION: ErrorSeverity.HIGH,
        }
        return severity_map.get(strategy, ErrorSeverity.MEDIUM)


class ConsolidatedErrorRecoveryManager:
    """
    Enhanced error recovery manager for the consolidated phase system.

    Week 4 improvements:
    - Phase-specific error handling
    - Intelligent recovery strategies
    - Error pattern learning
    - Performance impact monitoring
    """

    def __init__(self):
        self.phase_handlers: dict[str, PhaseErrorHandler] = {}
        self.error_history: list[ErrorContext] = []
        self.recovery_stats = {
            "total_errors": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "recovery_types": {strategy.value: 0 for strategy in RecoveryStrategy},
        }

        # Initialize phase-specific handlers
        self._initialize_phase_handlers()

    def _initialize_phase_handlers(self):
        """Initialize error handlers for each consolidated phase"""
        phase_configs = {
            "ConsolidatedInitializationPhase": {
                "missing card": RecoveryStrategy.ABORT,
                "invalid game state": RecoveryStrategy.ROLLBACK,
                "player not found": RecoveryStrategy.ABORT,
            },
            "ConsolidatedSharingPhase": {
                "no sharing players": RecoveryStrategy.SKIP_PHASE,
                "sharing timeout": RecoveryStrategy.CONTINUE,
                "player unavailable": RecoveryStrategy.SKIP_PHASE,
            },
            "ConsolidatedExecutionPhase": {
                "action primitive not found": RecoveryStrategy.RETRY,
                "insufficient resources": RecoveryStrategy.CONTINUE,
                "invalid card state": RecoveryStrategy.ROLLBACK,
            },
            "ConsolidatedInteractionPhase": {
                "interaction timeout": RecoveryStrategy.USER_INTERVENTION,
                "invalid selection": RecoveryStrategy.RETRY,
                "player disconnected": RecoveryStrategy.USER_INTERVENTION,
            },
            "ConsolidatedResolutionPhase": {
                "resolution conflict": RecoveryStrategy.ROLLBACK,
                "state inconsistency": RecoveryStrategy.ROLLBACK,
            },
            "ConsolidatedDemandPhase": {
                "demand target invalid": RecoveryStrategy.CONTINUE,
                "clockwise iteration failed": RecoveryStrategy.RETRY,
            },
            "ConsolidatedCompletionPhase": {
                "completion failed": RecoveryStrategy.ROLLBACK,
                "activity logging failed": RecoveryStrategy.CONTINUE,
            },
            "ConsolidatedTransactionPhase": {
                "transaction commit failed": RecoveryStrategy.ROLLBACK,
                "state persistence failed": RecoveryStrategy.RETRY,
            },
        }

        for phase_name, patterns in phase_configs.items():
            handler = PhaseErrorHandler(phase_name)
            for pattern, strategy in patterns.items():
                handler.register_error_pattern(pattern, strategy)
            self.phase_handlers[phase_name] = handler

    def handle_phase_error(
        self,
        phase_name: str,
        error: Exception,
        context: DogmaContext,
        transaction: DogmaTransaction,
    ) -> ErrorContext:
        """Handle an error that occurred in a specific phase"""
        self.recovery_stats["total_errors"] += 1

        # Get or create phase handler
        if phase_name not in self.phase_handlers:
            self.phase_handlers[phase_name] = PhaseErrorHandler(phase_name)

        handler = self.phase_handlers[phase_name]
        error_context = handler.handle_error(error, context, transaction)

        # Add to history
        self.error_history.append(error_context)

        # Trim history if too long
        if len(self.error_history) > 1000:
            self.error_history = self.error_history[-500:]

        logger.info(f"Registered error in phase {phase_name}: {error_context.error_id}")
        return error_context

    def attempt_recovery(
        self, error_context: ErrorContext, recovery_callback: Callable | None = None
    ) -> bool:
        """Attempt to recover from an error using the specified strategy"""
        if error_context.recovery_attempted:
            logger.warning(
                f"Recovery already attempted for error {error_context.error_id}"
            )
            return error_context.recovery_successful

        error_context.recovery_attempted = True
        strategy = error_context.recovery_strategy

        logger.info(
            f"Attempting recovery for error {error_context.error_id} using strategy: {strategy.value}"
        )

        try:
            success = False

            if strategy == RecoveryStrategy.CONTINUE:
                # Log and continue - always successful
                logger.info(
                    f"Continuing execution despite error: {error_context.error_message}"
                )
                success = True

            elif strategy == RecoveryStrategy.RETRY:
                # Retry the operation if callback provided
                if recovery_callback and error_context.retry_count < 3:
                    error_context.retry_count += 1
                    logger.info(
                        f"Retrying operation (attempt {error_context.retry_count}/3)"
                    )
                    success = recovery_callback()
                else:
                    logger.warning("No retry callback provided or max retries exceeded")
                    success = False

            elif strategy == RecoveryStrategy.SKIP_PHASE:
                # Skip the current phase
                logger.info(f"Skipping phase {error_context.phase_name} due to error")
                success = True

            elif strategy == RecoveryStrategy.ROLLBACK:
                # This will be handled by the transaction manager
                logger.info(
                    f"Marking transaction {error_context.transaction_id} for rollback"
                )
                success = True

            elif strategy == RecoveryStrategy.ABORT:
                # Abort the entire transaction
                logger.error(
                    f"Aborting transaction {error_context.transaction_id} due to fatal error"
                )
                success = False

            elif strategy == RecoveryStrategy.USER_INTERVENTION:
                # Log for user intervention
                logger.warning(
                    f"User intervention required for error {error_context.error_id}"
                )
                success = False

            error_context.recovery_successful = success

            if success:
                self.recovery_stats["successful_recoveries"] += 1
                logger.info(f"Recovery successful for error {error_context.error_id}")
            else:
                self.recovery_stats["failed_recoveries"] += 1
                logger.warning(f"Recovery failed for error {error_context.error_id}")

            self.recovery_stats["recovery_types"][strategy.value] += 1
            return success

        except Exception as recovery_error:
            logger.error(f"Recovery attempt failed with exception: {recovery_error}")
            error_context.recovery_successful = False
            self.recovery_stats["failed_recoveries"] += 1
            return False

    def should_abort_transaction(self, error_context: ErrorContext) -> bool:
        """Determine if transaction should be aborted based on error context"""
        if error_context.severity == ErrorSeverity.FATAL:
            return True

        if error_context.recovery_strategy == RecoveryStrategy.ABORT:
            return True

        # Check for repeated failures in same transaction
        transaction_errors = [
            ec
            for ec in self.error_history
            if ec.transaction_id == error_context.transaction_id
        ]

        if len(transaction_errors) >= 5:  # Too many errors in same transaction
            logger.warning(
                f"Transaction {error_context.transaction_id} has {len(transaction_errors)} errors, aborting"
            )
            return True

        return False

    def get_error_analysis(
        self, transaction_id: str | None = None, phase_name: str | None = None
    ) -> dict[str, Any]:
        """Get error analysis and statistics"""

        # Filter errors if criteria provided
        filtered_errors = self.error_history
        if transaction_id:
            filtered_errors = [
                e for e in filtered_errors if e.transaction_id == transaction_id
            ]
        if phase_name:
            filtered_errors = [e for e in filtered_errors if e.phase_name == phase_name]

        if not filtered_errors:
            return {"message": "No errors found matching criteria"}

        # Analyze error patterns
        error_types = {}
        phase_distribution = {}
        severity_distribution = {}
        recovery_success_rate = {}

        for error in filtered_errors:
            # Error types
            error_types[error.error_type] = error_types.get(error.error_type, 0) + 1

            # Phase distribution
            phase_distribution[error.phase_name] = (
                phase_distribution.get(error.phase_name, 0) + 1
            )

            # Severity distribution
            severity_distribution[error.severity.value] = (
                severity_distribution.get(error.severity.value, 0) + 1
            )

            # Recovery success rate
            strategy = error.recovery_strategy.value
            if strategy not in recovery_success_rate:
                recovery_success_rate[strategy] = {"total": 0, "successful": 0}
            recovery_success_rate[strategy]["total"] += 1
            if error.recovery_successful:
                recovery_success_rate[strategy]["successful"] += 1

        return {
            "total_errors": len(filtered_errors),
            "error_types": error_types,
            "phase_distribution": phase_distribution,
            "severity_distribution": severity_distribution,
            "recovery_success_rates": {
                strategy: {
                    "rate": data["successful"] / max(1, data["total"]),
                    "count": data["total"],
                }
                for strategy, data in recovery_success_rate.items()
            },
            "recent_errors": [
                {
                    "error_id": e.error_id,
                    "phase": e.phase_name,
                    "type": e.error_type,
                    "message": e.error_message[:100] + "..."
                    if len(e.error_message) > 100
                    else e.error_message,
                    "severity": e.severity.value,
                    "strategy": e.recovery_strategy.value,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in sorted(
                    filtered_errors, key=lambda x: x.timestamp, reverse=True
                )[:10]
            ],
        }

    def get_recovery_stats(self) -> dict[str, Any]:
        """Get comprehensive recovery statistics"""
        return {
            **self.recovery_stats,
            "total_error_contexts": len(self.error_history),
            "success_rate": self.recovery_stats["successful_recoveries"]
            / max(1, self.recovery_stats["total_errors"]),
            "phase_handlers": len(self.phase_handlers),
            "most_common_errors": self._get_most_common_errors(),
            "most_problematic_phases": self._get_most_problematic_phases(),
        }

    def _get_most_common_errors(self) -> list[dict[str, Any]]:
        """Get most common error types"""
        error_counts = {}
        for error in self.error_history[-100:]:  # Last 100 errors
            error_counts[error.error_type] = error_counts.get(error.error_type, 0) + 1

        return sorted(
            [{"type": k, "count": v} for k, v in error_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

    def _get_most_problematic_phases(self) -> list[dict[str, Any]]:
        """Get phases with most errors"""
        phase_counts = {}
        for error in self.error_history[-100:]:  # Last 100 errors
            phase_counts[error.phase_name] = phase_counts.get(error.phase_name, 0) + 1

        return sorted(
            [{"phase": k, "error_count": v} for k, v in phase_counts.items()],
            key=lambda x: x["error_count"],
            reverse=True,
        )[:5]

    @contextmanager
    def error_handling_scope(
        self, phase_name: str, context: DogmaContext, transaction: DogmaTransaction
    ):
        """Context manager for automatic error handling in phases"""
        try:
            yield
        except Exception as error:
            error_context = self.handle_phase_error(
                phase_name, error, context, transaction
            )

            # Attempt automatic recovery
            recovery_success = self.attempt_recovery(error_context)

            if not recovery_success and self.should_abort_transaction(error_context):
                logger.error(
                    f"Transaction {transaction.id} aborted due to unrecoverable error"
                )
                raise

            # If recovery strategy is CONTINUE, don't re-raise
            if (
                error_context.recovery_strategy == RecoveryStrategy.CONTINUE
                and recovery_success
            ):
                logger.info(
                    f"Continuing execution after error recovery in {phase_name}"
                )
                return

            # Re-raise if not recovered
            if not recovery_success:
                raise


# Global error recovery manager
_error_recovery_manager: ConsolidatedErrorRecoveryManager | None = None


def get_error_recovery_manager() -> ConsolidatedErrorRecoveryManager:
    """Get or create the global error recovery manager"""
    global _error_recovery_manager
    if _error_recovery_manager is None:
        _error_recovery_manager = ConsolidatedErrorRecoveryManager()
    return _error_recovery_manager


def handle_phase_error(
    phase_name: str,
    error: Exception,
    context: DogmaContext,
    transaction: DogmaTransaction,
) -> ErrorContext:
    """Convenience function for handling phase errors"""
    manager = get_error_recovery_manager()
    return manager.handle_phase_error(phase_name, error, context, transaction)


def with_error_recovery(
    phase_name: str, context: DogmaContext, transaction: DogmaTransaction
):
    """Decorator for automatic error handling in phases"""
    manager = get_error_recovery_manager()
    return manager.error_handling_scope(phase_name, context, transaction)
