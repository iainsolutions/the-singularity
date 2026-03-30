"""
Phase Transition Logger for Dogma v2 System

This module provides comprehensive logging for dogma phase transitions,
context snapshots, and interaction handling to aid in debugging complex
multi-step dogma executions.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from logging_config import serialize_for_json

from .core.context import DogmaContext
from .core.transaction import DogmaTransaction

logger = logging.getLogger(__name__)


@dataclass
class PhaseTransitionEvent:
    """Represents a single phase transition event"""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    transaction_id: str = ""
    phase_name: str = ""
    transition_type: str = ""  # "enter", "exit", "suspend", "resume", "error"
    player_id: str = ""
    card_name: str = ""
    game_id: str = ""

    # Context information
    context_variables: dict[str, Any] = field(default_factory=dict)
    results_count: int = 0
    phase_duration_ms: float | None = None

    # Error information
    error_message: str | None = None

    # Interaction information
    interaction_type: str | None = None
    interaction_data: dict[str, Any] | None = None


@dataclass
class ContextSnapshot:
    """Captures the state of a DogmaContext at a point in time"""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    transaction_id: str = ""
    phase_name: str = ""

    # Core context data
    current_player_id: str = ""
    activating_player_id: str = ""
    card_name: str = ""

    # Variable state (filtered for relevance)
    key_variables: dict[str, Any] = field(default_factory=dict)
    results_summary: list[str] = field(default_factory=list)

    # Phase history
    phases_executed: list[str] = field(default_factory=list)

    # Sharing state
    sharing_active: bool = False
    sharing_players: list[str] = field(default_factory=list)


class PhaseTransitionLogger:
    """
    Comprehensive logger for dogma phase transitions and context snapshots.

    This class provides detailed logging of phase execution, context state,
    and interaction points to help debug complex dogma sequences.
    """

    def __init__(self, activity_logger=None):
        """Initialize with optional activity logger integration"""
        self.activity_logger = activity_logger
        self.logger = logging.getLogger(f"{__name__}.PhaseTransitionLogger")

        # In-memory storage for recent events (for debugging)
        self.recent_events: list[PhaseTransitionEvent] = []
        self.recent_snapshots: list[ContextSnapshot] = []
        self.max_stored_events = 1000

    def log_phase_enter(
        self, context: DogmaContext, transaction: DogmaTransaction, phase_name: str
    ) -> None:
        """Log when a phase is entered"""

        event = PhaseTransitionEvent(
            transaction_id=transaction.id,
            phase_name=phase_name,
            transition_type="enter",
            player_id=context.current_player.id if context.current_player else "",
            card_name=context.card.name if context.card else "",
            game_id=transaction.game_id,
            context_variables=self._extract_key_variables(context),
            results_count=len(context.results),
        )

        self._store_event(event)
        self._log_structured_event(event)

        # Create context snapshot
        snapshot = self._create_context_snapshot(context, transaction, phase_name)
        self._store_snapshot(snapshot)

    def log_phase_exit(
        self,
        context: DogmaContext,
        transaction: DogmaTransaction,
        phase_name: str,
        duration_ms: float | None = None,
    ) -> None:
        """Log when a phase exits normally"""

        event = PhaseTransitionEvent(
            transaction_id=transaction.id,
            phase_name=phase_name,
            transition_type="exit",
            player_id=context.current_player.id if context.current_player else "",
            card_name=context.card.name if context.card else "",
            game_id=transaction.game_id,
            context_variables=self._extract_key_variables(context),
            results_count=len(context.results),
            phase_duration_ms=duration_ms,
        )

        self._store_event(event)
        self._log_structured_event(event)

    def log_phase_suspend(
        self,
        context: DogmaContext,
        transaction: DogmaTransaction,
        phase_name: str,
        interaction_type: str,
        interaction_data: dict[str, Any],
    ) -> None:
        """Log when a phase suspends for interaction"""

        event = PhaseTransitionEvent(
            transaction_id=transaction.id,
            phase_name=phase_name,
            transition_type="suspend",
            player_id=context.current_player.id if context.current_player else "",
            card_name=context.card.name if context.card else "",
            game_id=transaction.game_id,
            context_variables=self._extract_key_variables(context),
            results_count=len(context.results),
            interaction_type=interaction_type,
            interaction_data=interaction_data,
        )

        self._store_event(event)
        self._log_structured_event(event)

        # Create detailed snapshot at suspension point
        snapshot = self._create_context_snapshot(context, transaction, phase_name)
        self._store_snapshot(snapshot)

    def log_phase_resume(
        self,
        context: DogmaContext,
        transaction: DogmaTransaction,
        phase_name: str,
        interaction_response: dict[str, Any],
    ) -> None:
        """Log when a phase resumes from interaction"""

        event = PhaseTransitionEvent(
            transaction_id=transaction.id,
            phase_name=phase_name,
            transition_type="resume",
            player_id=context.current_player.id if context.current_player else "",
            card_name=context.card.name if context.card else "",
            game_id=transaction.game_id,
            context_variables=self._extract_key_variables(context),
            results_count=len(context.results),
            interaction_data=interaction_response,
        )

        self._store_event(event)
        self._log_structured_event(event)

    def log_phase_error(
        self,
        context: DogmaContext,
        transaction: DogmaTransaction,
        phase_name: str,
        error_message: str,
    ) -> None:
        """Log when a phase encounters an error"""

        event = PhaseTransitionEvent(
            transaction_id=transaction.id,
            phase_name=phase_name,
            transition_type="error",
            player_id=context.current_player.id if context.current_player else "",
            card_name=context.card.name if context.card else "",
            game_id=transaction.game_id,
            context_variables=self._extract_key_variables(context),
            results_count=len(context.results),
            error_message=error_message,
        )

        self._store_event(event)
        self._log_structured_event(event)

        # Create error snapshot
        snapshot = self._create_context_snapshot(context, transaction, phase_name)
        self._store_snapshot(snapshot)

    def get_transaction_history(
        self, transaction_id: str
    ) -> list[PhaseTransitionEvent]:
        """Get all phase transition events for a transaction"""
        return [
            event
            for event in self.recent_events
            if event.transaction_id == transaction_id
        ]

    def get_game_phase_history(
        self, game_id: str, limit: int = 100
    ) -> list[PhaseTransitionEvent]:
        """Get recent phase transition events for a game"""
        game_events = [
            event for event in self.recent_events if event.game_id == game_id
        ]
        return game_events[-limit:]

    def get_context_snapshots(self, transaction_id: str) -> list[ContextSnapshot]:
        """Get all context snapshots for a transaction"""
        return [
            snapshot
            for snapshot in self.recent_snapshots
            if snapshot.transaction_id == transaction_id
        ]

    def _extract_key_variables(self, context: DogmaContext) -> dict[str, Any]:
        """Extract key variables from context for logging"""
        key_vars = {}

        # Always include these if present
        important_keys = [
            "selected_cards",
            "cards_to_transfer",
            "target_player",
            "demand_target",
            "sharing_players",
            "in_demand_phase",
            "in_sharing_phase",
            "effect_index",
            "interaction_type",
            "eligible_cards",
            "transfer_count",
        ]

        for key in important_keys:
            if key in context.variables:
                value = context.variables[key]
                # Serialize complex objects
                if hasattr(value, "to_dict"):
                    key_vars[key] = value.to_dict()
                elif isinstance(value, (list, dict, str, int, float, bool)):
                    key_vars[key] = value
                else:
                    key_vars[key] = str(value)

        return key_vars

    def _create_context_snapshot(
        self, context: DogmaContext, transaction: DogmaTransaction, phase_name: str
    ) -> ContextSnapshot:
        """Create a comprehensive context snapshot"""

        return ContextSnapshot(
            transaction_id=transaction.id,
            phase_name=phase_name,
            current_player_id=context.current_player.id
            if context.current_player
            else "",
            activating_player_id=context.activating_player.id
            if context.activating_player
            else "",
            card_name=context.card.name if context.card else "",
            key_variables=self._extract_key_variables(context),
            results_summary=[str(result) for result in context.results],
            phases_executed=list(context.phase_history),
            sharing_active=context.is_sharing_active(),
            sharing_players=list(context.sharing.completed_sharing)
            if context.sharing
            else [],
        )

    def _store_event(self, event: PhaseTransitionEvent) -> None:
        """Store event in memory with rotation"""
        self.recent_events.append(event)

        if len(self.recent_events) > self.max_stored_events:
            # Keep most recent 75%
            keep_count = int(self.max_stored_events * 0.75)
            self.recent_events = self.recent_events[-keep_count:]

    def _store_snapshot(self, snapshot: ContextSnapshot) -> None:
        """Store snapshot in memory with rotation"""
        self.recent_snapshots.append(snapshot)

        if len(self.recent_snapshots) > self.max_stored_events:
            # Keep most recent 75%
            keep_count = int(self.max_stored_events * 0.75)
            self.recent_snapshots = self.recent_snapshots[-keep_count:]

    def _log_structured_event(self, event: PhaseTransitionEvent) -> None:
        """Log event using structured logging"""

        # Log to standard logger
        log_message = (
            f"Phase {event.transition_type}: {event.phase_name} "
            f"[{event.transaction_id[:8]}] {event.card_name}"
        )

        if event.error_message:
            self.logger.error(f"{log_message} - ERROR: {event.error_message}")
        elif event.transition_type == "suspend":
            self.logger.info(f"{log_message} - Suspended for {event.interaction_type}")
        else:
            self.logger.debug(log_message)

        # Log to activity logger if available
        if self.activity_logger:
            try:
                event_data = {
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": f"dogma_phase_{event.transition_type}",
                    "transaction_id": event.transaction_id,
                    "phase_name": event.phase_name,
                    "game_id": event.game_id,
                    "player_id": event.player_id,
                    "card_name": event.card_name,
                    "context_variables": event.context_variables,
                    "results_count": event.results_count,
                    "phase_duration_ms": event.phase_duration_ms,
                    "interaction_type": event.interaction_type,
                    "interaction_data": event.interaction_data,
                    "error_message": event.error_message,
                }

                # Use activity logger's structured logging
                if hasattr(self.activity_logger, "activity_logger"):
                    self.activity_logger.activity_logger.info(
                        json.dumps(serialize_for_json(event_data))
                    )

            except Exception as e:
                self.logger.warning(f"Failed to log to activity logger: {e}")
