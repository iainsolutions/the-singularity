"""
Execution Tracing - Record and replay action executions for debugging.

This module implements Phase 10 from the Action Scheduler specification,
providing systematic execution tracing for debugging, testing, and AI analysis.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TraceEvent:
    """Single event in an execution trace."""

    timestamp: str
    event_type: str  # "action_start", "action_complete", "suspension", "error"
    player_id: str
    player_name: str
    effect_index: int
    is_sharing: bool

    # Action details
    primitive_type: str | None = None
    primitive_index: int | None = None  # Index within effect

    # Result details
    success: bool = True
    error: str | None = None
    results_count: int = 0

    # Suspension details
    requires_interaction: bool = False
    interaction_type: str | None = None

    # Context snapshot (optional, for deep debugging)
    context_snapshot: dict | None = None


@dataclass
class ExecutionTrace:
    """
    Complete trace of an action plan execution.

    Records all events during execution for debugging, testing, and analysis.
    Supports serialization for bug reproduction and AI player analysis.
    """

    trace_id: str
    game_id: str
    card_name: str
    plan_type: str  # "sharing" or "execution"
    started_at: str

    # Trace events
    events: list[TraceEvent] = field(default_factory=list)

    # Summary
    completed: bool = False
    suspended: bool = False
    failed: bool = False
    error: str | None = None
    total_actions: int = 0
    completed_actions: int = 0

    def add_event(self, event: TraceEvent) -> None:
        """Add an event to the trace."""
        self.events.append(event)

    def mark_complete(self) -> None:
        """Mark trace as completed successfully."""
        self.completed = True
        self.completed_actions = self.total_actions

    def mark_suspended(self) -> None:
        """Mark trace as suspended (requires interaction)."""
        self.suspended = True

    def mark_failed(self, error: str) -> None:
        """Mark trace as failed with error."""
        self.failed = True
        self.error = error

    def to_dict(self) -> dict:
        """
        Serialize trace to dictionary for storage/export.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "trace_id": self.trace_id,
            "game_id": self.game_id,
            "card_name": self.card_name,
            "plan_type": self.plan_type,
            "started_at": self.started_at,
            "events": [
                {
                    "timestamp": e.timestamp,
                    "event_type": e.event_type,
                    "player_id": e.player_id,
                    "player_name": e.player_name,
                    "effect_index": e.effect_index,
                    "is_sharing": e.is_sharing,
                    "primitive_type": e.primitive_type,
                    "primitive_index": e.primitive_index,
                    "success": e.success,
                    "error": e.error,
                    "results_count": e.results_count,
                    "requires_interaction": e.requires_interaction,
                    "interaction_type": e.interaction_type,
                    "context_snapshot": e.context_snapshot,
                }
                for e in self.events
            ],
            "completed": self.completed,
            "suspended": self.suspended,
            "failed": self.failed,
            "error": self.error,
            "total_actions": self.total_actions,
            "completed_actions": self.completed_actions,
        }

    @staticmethod
    def from_dict(data: dict) -> "ExecutionTrace":
        """
        Deserialize trace from dictionary.

        Args:
            data: Dictionary representation from to_dict()

        Returns:
            ExecutionTrace with restored state
        """
        trace = ExecutionTrace(
            trace_id=data["trace_id"],
            game_id=data["game_id"],
            card_name=data["card_name"],
            plan_type=data["plan_type"],
            started_at=data["started_at"],
            completed=data["completed"],
            suspended=data["suspended"],
            failed=data["failed"],
            error=data.get("error"),
            total_actions=data["total_actions"],
            completed_actions=data["completed_actions"],
        )

        for event_data in data["events"]:
            event = TraceEvent(
                timestamp=event_data["timestamp"],
                event_type=event_data["event_type"],
                player_id=event_data["player_id"],
                player_name=event_data["player_name"],
                effect_index=event_data["effect_index"],
                is_sharing=event_data["is_sharing"],
                primitive_type=event_data.get("primitive_type"),
                primitive_index=event_data.get("primitive_index"),
                success=event_data["success"],
                error=event_data.get("error"),
                results_count=event_data["results_count"],
                requires_interaction=event_data["requires_interaction"],
                interaction_type=event_data.get("interaction_type"),
                context_snapshot=event_data.get("context_snapshot"),
            )
            trace.events.append(event)

        return trace

    def to_json(self, indent: int = 2) -> str:
        """
        Export trace as JSON string.

        Args:
            indent: JSON indentation (default: 2)

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=indent)

    @staticmethod
    def from_json(json_str: str) -> "ExecutionTrace":
        """
        Import trace from JSON string.

        Args:
            json_str: JSON string from to_json()

        Returns:
            ExecutionTrace with restored state
        """
        data = json.loads(json_str)
        return ExecutionTrace.from_dict(data)

    def format_summary(self) -> str:
        """
        Generate human-readable summary of trace.

        Returns:
            Formatted summary string
        """
        status = (
            "COMPLETED"
            if self.completed
            else ("SUSPENDED" if self.suspended else "FAILED")
        )

        lines = [
            f"Execution Trace: {self.card_name} ({self.plan_type})",
            f"Status: {status}",
            f"Actions: {self.completed_actions}/{self.total_actions}",
            f"Events: {len(self.events)}",
        ]

        if self.error:
            lines.append(f"Error: {self.error}")

        return "\n".join(lines)

    def format_timeline(self, max_events: int | None = None) -> str:
        """
        Generate human-readable timeline of events.

        Args:
            max_events: Maximum number of events to show (default: all)

        Returns:
            Formatted timeline string
        """
        lines = [
            self.format_summary(),
            "",
            "Timeline:",
            "─" * 60,
        ]

        events_to_show = self.events[:max_events] if max_events else self.events

        for i, event in enumerate(events_to_show, 1):
            timestamp = event.timestamp.split("T")[1][:12]  # HH:MM:SS.mmm
            player = event.player_name
            effect_num = event.effect_index + 1
            sharing_indicator = "sharing" if event.is_sharing else "activating"

            if event.event_type == "action_start":
                primitive = event.primitive_type or "unknown"
                lines.append(
                    f"{i:3}. [{timestamp}] {player} ({sharing_indicator}) "
                    f"Effect {effect_num}: {primitive}"
                )
            elif event.event_type == "action_complete":
                results = (
                    f"{event.results_count} results"
                    if event.results_count
                    else "no results"
                )
                lines.append(f"     └─ Completed: {results}")
            elif event.event_type == "suspension":
                interaction = event.interaction_type or "unknown"
                lines.append(f"     └─ ⏸️  Suspended: {interaction}")
            elif event.event_type == "error":
                lines.append(f"     └─ ❌ Error: {event.error}")

        if max_events and len(self.events) > max_events:
            lines.append(f"... ({len(self.events) - max_events} more events)")

        return "\n".join(lines)


class TraceRecorder:
    """
    Records execution traces for ActionScheduler.

    Design:
    - Lightweight wrapper around ExecutionTrace
    - Optional - only records if enabled
    - Can be attached to ActionScheduler instance
    """

    def __init__(self, enabled: bool = True):
        """
        Initialize trace recorder.

        Args:
            enabled: Whether to record traces (default: True)
        """
        self.enabled = enabled
        self.current_trace: ExecutionTrace | None = None

    def start_trace(
        self,
        game_id: str,
        card_name: str,
        plan_type: str,
        total_actions: int,
    ) -> ExecutionTrace:
        """
        Start a new trace.

        Args:
            game_id: Game ID
            card_name: Name of card being executed
            plan_type: Type of plan ("sharing" or "execution")
            total_actions: Total number of actions in plan

        Returns:
            New ExecutionTrace
        """
        if not self.enabled:
            return None  # type: ignore

        import uuid

        self.current_trace = ExecutionTrace(
            trace_id=str(uuid.uuid4()),
            game_id=game_id,
            card_name=card_name,
            plan_type=plan_type,
            started_at=datetime.now().isoformat(),
            total_actions=total_actions,
        )

        return self.current_trace

    def record_event(self, event: TraceEvent) -> None:
        """Record an event in the current trace."""
        if self.enabled and self.current_trace:
            self.current_trace.add_event(event)

    def complete_trace(self) -> ExecutionTrace | None:
        """Mark current trace as complete and return it."""
        if self.enabled and self.current_trace:
            self.current_trace.mark_complete()
            trace = self.current_trace
            self.current_trace = None
            return trace
        return None

    def suspend_trace(self) -> ExecutionTrace | None:
        """Mark current trace as suspended and return it."""
        if self.enabled and self.current_trace:
            self.current_trace.mark_suspended()
            trace = self.current_trace
            self.current_trace = None
            return trace
        return None

    def fail_trace(self, error: str) -> ExecutionTrace | None:
        """Mark current trace as failed and return it."""
        if self.enabled and self.current_trace:
            self.current_trace.mark_failed(error)
            trace = self.current_trace
            self.current_trace = None
            return trace
        return None
