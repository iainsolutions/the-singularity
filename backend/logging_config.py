"""
Comprehensive logging and monitoring configuration for The Singularity game.
Combines activity logging, system monitoring, and game event tracking.
"""

import contextlib
import json
import logging
import logging.handlers
import os
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def serialize_for_json(obj):
    """Helper function to serialize complex objects for JSON logging."""
    # Handle Card objects
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()

    # Handle lists of objects
    if isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]

    # Handle dictionaries
    if isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}

    # Handle enum values
    if hasattr(obj, "value"):
        return obj.value

    # For other objects, try to get a string representation
    if hasattr(obj, "__dict__"):
        return str(obj)

    # Return as-is for primitive types
    return obj


class LogLevel(Enum):
    """Log levels for different types of events"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    GAME_EVENT = "GAME_EVENT"
    PLAYER_ACTION = "PLAYER_ACTION"
    SYSTEM_METRIC = "SYSTEM_METRIC"


class EventType(Enum):
    """Types of events we track"""

    # Game lifecycle events
    GAME_CREATED = "game_created"
    GAME_STARTED = "game_started"
    GAME_ENDED = "game_ended"
    GAME_ABANDONED = "game_abandoned"

    # Player events
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    PLAYER_ACTION = "player_action"
    PLAYER_DISCONNECTED = "player_disconnected"
    PLAYER_RECONNECTED = "player_reconnected"

    # Game action events
    ACTION_DRAW = "action_draw"
    ACTION_MELD = "action_meld"
    ACTION_DOGMA = "action_dogma"
    ACTION_ACHIEVE = "action_achieve"
    TURN_STARTED = "turn_started"
    TURN_ENDED = "turn_ended"

    # Dogma events
    DOGMA_STARTED = "dogma_started"

    # Unseen expansion events
    SAFE_CARD_ADDED = "safe_card_added"
    SAFE_CARD_REMOVED = "safe_card_removed"
    SAFE_LIMIT_CHANGED = "safe_limit_changed"
    SAFEGUARD_ACTIVATED = "safeguard_activated"
    SAFEGUARD_DEACTIVATED = "safeguard_deactivated"
    SAFEGUARD_DEADLOCK = "safeguard_deadlock"
    DOGMA_COMPLETED = "dogma_completed"
    DOGMA_FAILED = "dogma_failed"
    DOGMA_INTERACTION_REQUIRED = "dogma_interaction_required"
    DOGMA_RESPONSE_RECEIVED = "dogma_response_received"

    # Detailed dogma execution events
    DOGMA_DEMAND_EXECUTED = "dogma_demand_executed"
    DOGMA_DEMAND_TRANSFERRED = "dogma_demand_transferred"
    DOGMA_DEMAND_DECLINED = "dogma_demand_declined"
    DOGMA_FALLBACK_ACTIVATED = "dogma_fallback_activated"
    DOGMA_SYMBOL_CHECK = "dogma_symbol_check"
    DOGMA_CARD_SELECTION = "dogma_card_selection"
    DOGMA_SHARING_BENEFIT = "dogma_sharing_benefit"
    DOGMA_SHARING_COMPLETED = "dogma_sharing_completed"
    DOGMA_EFFECT_EXECUTED = "dogma_effect_executed"
    DOGMA_CARD_DRAWN = "dogma_card_drawn"
    DOGMA_CARD_REVEALED = "dogma_card_revealed"
    DOGMA_CARD_SCORED = "dogma_card_scored"
    DOGMA_CARD_MELDED = "dogma_card_melded"
    DOGMA_CARD_TRANSFERRED = "dogma_card_transferred"

    # System events
    WEBSOCKET_CONNECTED = "websocket_connected"
    WEBSOCKET_DISCONNECTED = "websocket_disconnected"
    WEBSOCKET_ERROR = "websocket_error"
    HEARTBEAT_SENT = "heartbeat_sent"
    HEARTBEAT_RECEIVED = "heartbeat_received"

    # Performance events
    SLOW_OPERATION = "slow_operation"
    MEMORY_WARNING = "memory_warning"
    ERROR_OCCURRED = "error_occurred"


class GameActivityLogger:
    """
    Unified logger for game activity and system monitoring.
    Combines structured logging with activity tracking.
    """

    def __init__(self, log_dir: str = "logs", enable_file_logging: bool = True):
        self.log_dir = log_dir
        self.enable_file_logging = enable_file_logging

        # Connection manager for WebSocket broadcasting (set externally)
        self._connection_manager = None

        # Set up structured logging
        self.logger = logging.getLogger("game_activity")
        self.logger.setLevel(logging.INFO)

        # Clear existing handlers to avoid duplicates
        self.logger.handlers.clear()

        # Add console handler for all activity logging
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Use structured formatter for activity logs
        formatter = logging.Formatter(
            fmt="%(asctime)s | ACTIVITY | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Optional file logging
        if self.enable_file_logging:
            self._setup_file_logging()
        else:
            # Use main logger for activity when file logging is disabled
            self.activity_logger = self.logger

        # Track activity events in structured format
        self._activity_events: list[dict] = []
        self._game_manager = None

    def set_connection_manager(self, connection_manager):
        """Set reference to connection manager for WebSocket broadcasting."""
        self._connection_manager = connection_manager

    def set_game_manager(self, game_manager):
        """Set reference to game manager for persisting events to game action_log."""
        self._game_manager = game_manager

    def _setup_file_logging(self):
        """Set up file-based logging handlers."""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)

        # Activity log file handler
        activity_handler = logging.handlers.RotatingFileHandler(
            os.path.join(self.log_dir, "game_activity.log"),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        activity_handler.setLevel(logging.INFO)
        activity_formatter = logging.Formatter("%(asctime)s | %(message)s")
        activity_handler.setFormatter(activity_formatter)

        # Create separate activity logger
        self.activity_logger = logging.getLogger("game_activity.events")
        self.activity_logger.setLevel(logging.INFO)
        self.activity_logger.handlers.clear()
        self.activity_logger.addHandler(activity_handler)
        self.activity_logger.propagate = False

        # AI interaction log file handler
        ai_handler = logging.handlers.RotatingFileHandler(
            os.path.join(self.log_dir, "ai_interactions.log"),
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=10,
        )
        ai_handler.setLevel(logging.INFO)
        ai_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        ai_handler.setFormatter(ai_formatter)

        # Create separate AI interaction logger
        self.ai_interaction_logger = logging.getLogger("ai.interactions")
        self.ai_interaction_logger.setLevel(logging.INFO)
        self.ai_interaction_logger.handlers.clear()
        self.ai_interaction_logger.addHandler(ai_handler)
        self.ai_interaction_logger.propagate = False

    async def _broadcast_activity_event(
        self, event_data: dict, game_id: str | None = None
    ):
        """Broadcast activity event to connected players via WebSocket."""

        # DEBUG: Log that broadcast method is called
        self.logger.debug(
            f"_broadcast_activity_event called: game_id={game_id}, event_type={event_data.get('event_type', 'unknown')}"
        )

        if not self._connection_manager:
            self.logger.debug("No connection manager set! Cannot broadcast.")
            return

        try:
            # Create WebSocket message for activity event
            activity_message = {
                "type": "activity_event",
                "data": serialize_for_json(event_data),
            }

            message_json = json.dumps(activity_message)
            self.logger.debug(f"Created WebSocket message: {message_json[:200]}...")

            # Broadcast to all players in the game
            if game_id and hasattr(self._connection_manager, "game_connections"):
                game_players = self._connection_manager.game_connections.get(
                    game_id, set()
                )
                self.logger.debug(
                    f"Found {len(game_players)} players in game {game_id}: {list(game_players)}"
                )

                for player_id in game_players:
                    try:
                        await self._connection_manager.send_personal_message(
                            message_json, player_id
                        )
                        self.logger.debug(f"Successfully sent to player {player_id}")
                    except Exception as e:
                        # Don't let WebSocket errors break logging
                        self.logger.debug(
                            f"Failed to send activity event to {player_id}: {e}"
                        )

        except Exception as e:
            # Don't let broadcasting errors break the logging system
            self.logger.debug(f"Failed to broadcast activity event: {e}")

    def _setup_handlers(self):
        """Setup logging handlers"""
        # Console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(self.console_formatter)
        self.logger.addHandler(console_handler)

        if self.enable_file_logging:
            # File handler for all logs
            file_handler = logging.handlers.RotatingFileHandler(
                os.path.join(self.log_dir, "innovation.log"),
                maxBytes=50 * 1024 * 1024,  # 50MB
                backupCount=5,
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(self.json_formatter)
            self.logger.addHandler(file_handler)

            # Error file handler
            error_handler = logging.handlers.RotatingFileHandler(
                os.path.join(self.log_dir, "errors.log"),
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(self.json_formatter)
            self.logger.addHandler(error_handler)

    def log_game_event(
        self,
        event_type: EventType,
        game_id: str,
        player_id: str | None = None,
        data: dict[str, Any] | None = None,
        message: str | None = None,
    ):
        """Log a game event with structured data"""
        event_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type.value,
            "game_id": game_id,
            "player_id": player_id,
            "data": data or {},
            "message": message,
        }

        # Append to in-memory activity list for fast API access
        try:
            self._activity_events.append(serialize_for_json(event_data))
            # Keep last 500 entries max
            if len(self._activity_events) > 500:
                self._activity_events = self._activity_events[-500:]
        except Exception:
            pass

        # Log to file-backed activity logger (best-effort; may not be parsed by reader)
        with contextlib.suppress(Exception):
            self.activity_logger.info(json.dumps(serialize_for_json(event_data)))

        # Also log to main logger for monitoring
        self.logger.info(
            f"Game Event: {event_type.value}", extra={"event_data": event_data}
        )

        # Broadcast to connected players via WebSocket (fire and forget)
        if self._connection_manager:
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self._broadcast_activity_event(event_data, game_id))
            except RuntimeError:
                # No event loop running - skip broadcasting
                pass

        # Persist to game's action_log for frontend display
        if self._game_manager and game_id:
            try:
                from async_game_manager import AsyncGameManager

                if isinstance(self._game_manager, AsyncGameManager):
                    game = self._game_manager.games.get(game_id)
                    if game:
                        # Convert activity event to action_log format
                        game.add_to_action_log(
                            player_name=message or event_type.value,
                            action_type=event_type.value,
                            description=message or f"{event_type.value}",
                            turn_number=getattr(
                                game.state,
                                "turn_number",
                                game.state.current_player_index + 1,
                            )
                            if hasattr(game, "state")
                            else 1,
                            phase_name="activity",
                            context_snapshot=None,
                            transaction_id=event_data.get("timestamp"),
                            state_changes=[],
                        )
            except Exception as e:
                # Don't break logging if action_log persistence fails
                self.logger.debug(f"Failed to persist event to game action_log: {e}")

    def log_player_action(
        self,
        game_id: str,
        player_id: str,
        action_type: str,
        action_data: dict[str, Any],
        result: dict[str, Any] | None = None,
        duration_ms: float | None = None,
    ):
        """Log a player action with performance metrics"""
        event_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": EventType.PLAYER_ACTION.value,
            "game_id": game_id,
            "player_id": player_id,
            "action_type": action_type,
            "action_data": action_data,
            "result": result,
            "duration_ms": duration_ms,
        }

        # Log to activity logger
        self.activity_logger.info(json.dumps(serialize_for_json(event_data)))

        # Check for slow operations
        if duration_ms and duration_ms > 1000:  # More than 1 second
            self.log_performance_warning(
                "Slow action detected",
                game_id=game_id,
                player_id=player_id,
                action_type=action_type,
                duration_ms=duration_ms,
            )

        # (No mirroring into action log; avoid duplicates.)

    def log_websocket_event(
        self,
        event_type: str,
        player_id: str,
        game_id: str | None = None,
        error: str | None = None,
    ):
        """Log WebSocket events"""
        event_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": f"websocket_{event_type}",
            "player_id": player_id,
            "game_id": game_id,
            "error": error,
        }

        level = logging.ERROR if error else logging.INFO
        self.logger.log(
            level, f"WebSocket {event_type}", extra={"event_data": event_data}
        )

    def log_performance_warning(self, message: str, **kwargs):
        """Log performance warnings"""
        event_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": EventType.SLOW_OPERATION.value,
            "message": message,
            **kwargs,
        }

        self.logger.warning(
            f"Performance Warning: {message}", extra={"event_data": event_data}
        )

    def log_error(self, message: str, error: Exception, **kwargs):
        """Log errors with full context"""
        event_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": EventType.ERROR_OCCURRED.value,
            "message": message,
            "error_type": type(error).__name__,
            "error_message": str(error),
            **kwargs,
        }

        self.logger.error(
            f"Error: {message}", exc_info=True, extra={"event_data": event_data}
        )

    def log_dogma_demand_executed(
        self,
        game_id: str,
        demanding_player_id: str,
        target_player_id: str,
        card_name: str,
        symbol_requirement: str,
        target_symbol_count: int,
        has_sufficient_symbols: bool,
        **kwargs,
    ):
        """Log detailed dogma demand execution"""
        event_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": EventType.DOGMA_DEMAND_EXECUTED.value,
            "game_id": game_id,
            "demanding_player_id": demanding_player_id,
            "target_player_id": target_player_id,
            "card_name": card_name,
            "symbol_requirement": symbol_requirement,
            "target_symbol_count": target_symbol_count,
            "has_sufficient_symbols": has_sufficient_symbols,
            **kwargs,
        }

        self.activity_logger.info(json.dumps(event_data))
        self.logger.info(
            f"Dogma Demand: {card_name} executed by {demanding_player_id} on {target_player_id}",
            extra={"event_data": event_data},
        )

    def log_dogma_demand_outcome(
        self,
        game_id: str,
        demanding_player_id: str,
        target_player_id: str,
        card_name: str,
        transferred: bool,
        cards_transferred: list | None = None,
        transfer_count: int = 0,
        decline_reason: str | None = None,
        **kwargs,
    ):
        """Log dogma demand transfer outcome"""
        event_type = (
            EventType.DOGMA_DEMAND_TRANSFERRED
            if transferred
            else EventType.DOGMA_DEMAND_DECLINED
        )

        event_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type.value,
            "game_id": game_id,
            "demanding_player_id": demanding_player_id,
            "target_player_id": target_player_id,
            "card_name": card_name,
            "transferred": transferred,
            "cards_transferred": cards_transferred or [],
            "transfer_count": transfer_count,
            "decline_reason": decline_reason,
            **kwargs,
        }

        self.activity_logger.info(json.dumps(event_data))

        if transferred:
            message = f"Dogma Demand Transfer: {transfer_count} cards from {target_player_id} to {demanding_player_id}"
        else:
            message = f"Dogma Demand Declined: {target_player_id} could not transfer cards - {decline_reason}"

        self.logger.info(message, extra={"event_data": event_data})

    def log_dogma_fallback_activated(
        self,
        game_id: str,
        player_id: str,
        card_name: str,
        fallback_reason: str,
        fallback_effect: str,
        **kwargs,
    ):
        """Log dogma fallback effect activation"""
        event_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": EventType.DOGMA_FALLBACK_ACTIVATED.value,
            "game_id": game_id,
            "player_id": player_id,
            "card_name": card_name,
            "fallback_reason": fallback_reason,
            "fallback_effect": fallback_effect,
            **kwargs,
        }

        self.activity_logger.info(json.dumps(event_data))
        self.logger.info(
            f"Dogma Fallback: {card_name} fallback activated - {fallback_reason}",
            extra={"event_data": event_data},
        )

    def log_dogma_symbol_check(
        self,
        game_id: str,
        player_id: str,
        card_name: str,
        symbol: str,
        player_count: int,
        required_count: int | None = None,
        meets_requirement: bool | None = None,
        **kwargs,
    ):
        """Log dogma symbol count checks"""
        event_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": EventType.DOGMA_SYMBOL_CHECK.value,
            "game_id": game_id,
            "player_id": player_id,
            "card_name": card_name,
            "symbol": symbol,
            "player_count": player_count,
            "required_count": required_count,
            "meets_requirement": meets_requirement,
            **kwargs,
        }

        self.activity_logger.info(json.dumps(event_data))

        if required_count is not None:
            result = "meets" if meets_requirement else "does not meet"
            message = f"Symbol Check: {player_id} has {player_count} {symbol} symbols, {result} requirement of {required_count}"
        else:
            message = f"Symbol Count: {player_id} has {player_count} {symbol} symbols"

        self.logger.info(message, extra={"event_data": event_data})

    def log_dogma_sharing_benefit(
        self,
        game_id: str,
        sharing_player_id: str,
        triggering_player_id: str,
        card_name: str,
        benefit_description: str,
        **kwargs,
    ):
        """Log dogma sharing benefits"""
        # Funnel through the unified game event logger so the UI timeline and
        # in-memory buffer receive this event (append + broadcast).
        data = {
            "sharing_player_id": sharing_player_id,
            "triggering_player_id": triggering_player_id,
            "card_name": card_name,
            "benefit_description": benefit_description,
            **kwargs,
        }
        message = (
            f"Sharing Benefit: {sharing_player_id} from {triggering_player_id}'s {card_name}"
            f" - {benefit_description}"
        )
        self.log_game_event(
            event_type=EventType.DOGMA_SHARING_BENEFIT,
            game_id=game_id,
            player_id=sharing_player_id if isinstance(sharing_player_id, str) else None,
            data=data,
            message=message,
        )

    def log_dogma_card_selection(
        self,
        game_id: str,
        player_id: str,
        card_name: str,
        selection_type: str,
        selected_cards: list,
        selection_criteria: str | None = None,
        **kwargs,
    ):
        """Log dogma card selections (broadcast to UI)"""
        # Normalize selected card names as strings for UI
        names = []
        for item in selected_cards or []:
            if isinstance(item, dict):
                names.append(item.get("name") or str(item))
            else:
                names.append(str(item))

        data = {
            "card_name": card_name,
            "selection_type": selection_type,
            "selected_cards": names,
            "selection_criteria": selection_criteria,
            **kwargs,
        }
        msg = f"Card Selection: selected {len(names)} for {card_name} - {', '.join(names)}"
        self.log_game_event(
            event_type=EventType.DOGMA_CARD_SELECTION,
            game_id=game_id,
            player_id=player_id,
            data=data,
            message=msg,
        )

    def log_dogma_effect_executed(
        self,
        game_id: str,
        player_id: str,
        card_name: str,
        effect_index: int,
        effect_description: str,
        effect_type: str = "self_effect",
        **kwargs,
    ):
        """Log dogma effect execution start"""
        event_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": EventType.DOGMA_EFFECT_EXECUTED.value,
            "game_id": game_id,
            "player_id": player_id,
            "card_name": card_name,
            "effect_index": effect_index,
            "effect_description": effect_description,
            "effect_type": effect_type,
            **kwargs,
        }

        self.activity_logger.info(json.dumps(event_data))
        self.logger.info(
            f"Dogma Effect: {card_name} effect {effect_index} executed by player {player_id}",
            extra={"event_data": event_data},
        )

    def log_dogma_card_action(
        self,
        game_id: str,
        player_id: str,
        card_name: str,
        action_type: str,  # "drawn", "revealed", "scored", "melded", "transferred"
        cards: list,
        location_from: str | None = None,
        location_to: str | None = None,
        **kwargs,
    ):
        """Log dogma card actions (draw, reveal, score, meld, transfer) and broadcast"""
        event_type_map = {
            "drawn": EventType.DOGMA_CARD_DRAWN,
            "revealed": EventType.DOGMA_CARD_REVEALED,
            "scored": EventType.DOGMA_CARD_SCORED,
            "melded": EventType.DOGMA_CARD_MELDED,
            "transferred": EventType.DOGMA_CARD_TRANSFERRED,
        }
        evt = event_type_map.get(action_type, EventType.DOGMA_CARD_TRANSFERRED)

        # Normalize cards as names for the UI
        names = []
        for c in cards or []:
            if isinstance(c, dict):
                names.append(c.get("name") or str(c))
            else:
                names.append(getattr(c, "name", str(c)))

        data = {
            "card_name": card_name,
            "action_type": action_type,
            "cards": names,
            "card_count": len(names),
            "location_from": location_from,
            "location_to": location_to,
            **kwargs,
        }
        loc = (
            f" from {location_from} to {location_to}"
            if location_from and location_to
            else ""
        )
        reason = kwargs.get("reason")
        reason_suffix = f" ({str(reason).replace('_', ' ')})" if reason else ""
        msg = f"Dogma Action: {len(names)} cards {action_type}{loc}{reason_suffix} - {', '.join(names)}"

        self.log_game_event(
            event_type=evt,
            game_id=game_id,
            player_id=player_id,
            data=data,
            message=msg,
        )

    def get_game_activity(self, game_id: str, limit: int = 100) -> list:
        """
        Retrieve recent game activity from logs.
        This would typically query a database or log aggregation service.
        """
        # Prefer in-memory events for speed and reliability
        try:
            filtered = [e for e in self._activity_events if e.get("game_id") == game_id]
            return filtered[-limit:]
        except Exception:
            return []

    def get_player_activity(self, player_id: str, limit: int = 50) -> list:
        """Retrieve recent player activity"""
        activities = []
        if self.enable_file_logging:
            log_file = os.path.join(self.log_dir, "game_activity.log")
            if os.path.exists(log_file):
                with open(log_file) as f:
                    for line in f:
                        try:
                            event = json.loads(line)
                            # The activity logger stores structured data in the 'message' field
                            message = event.get("message")
                            if not message:
                                continue
                            message_data = json.loads(message)
                            if message_data.get("player_id") == player_id:
                                activities.append(message_data)
                        except json.JSONDecodeError:
                            continue

        # Return the most recent entries up to the limit
        return activities[-limit:]

    def log_phase_transition(
        self,
        game_id: str,
        transaction_id: str,
        player_id: str,
        card_name: str,
        phase_name: str,
        transition_type: str,  # "enter", "exit", "suspend", "resume", "error"
        context_variables: dict | None = None,
        duration_ms: float | None = None,
        error_message: str | None = None,
        **kwargs,
    ):
        """Log dogma phase transitions with context"""
        event_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": f"dogma_phase_{transition_type}",
            "game_id": game_id,
            "transaction_id": transaction_id,
            "player_id": player_id,
            "card_name": card_name,
            "phase_name": phase_name,
            "transition_type": transition_type,
            "context_variables": context_variables or {},
            "duration_ms": duration_ms,
            "error_message": error_message,
            **kwargs,
        }

        self.activity_logger.info(json.dumps(event_data))

        # Log to main logger based on transition type
        message = (
            f"Phase {transition_type}: {phase_name} [{transaction_id[:8]}] {card_name}"
        )
        if error_message:
            self.logger.error(
                f"{message} - ERROR: {error_message}", extra={"event_data": event_data}
            )
        elif transition_type == "suspend":
            self.logger.info(f"{message} - Suspended", extra={"event_data": event_data})
        else:
            self.logger.debug(message, extra={"event_data": event_data})

        # Broadcast to connected players via WebSocket (fire and forget)
        if self._connection_manager:
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self._broadcast_activity_event(event_data, game_id))
            except RuntimeError:
                # No event loop running - skip broadcasting
                pass

    def log_context_snapshot(
        self,
        game_id: str,
        transaction_id: str,
        player_id: str,
        card_name: str,
        phase_name: str,
        context_variables: dict,
        results_summary: list,
        **kwargs,
    ):
        """Log context snapshots for debugging"""
        event_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": "dogma_context_snapshot",
            "game_id": game_id,
            "transaction_id": transaction_id,
            "player_id": player_id,
            "card_name": card_name,
            "phase_name": phase_name,
            "context_variables": context_variables,
            "results_summary": results_summary,
            **kwargs,
        }

        self.activity_logger.info(json.dumps(event_data))
        self.logger.debug(
            f"Context Snapshot: {phase_name} [{transaction_id[:8]}] - {len(results_summary)} results",
            extra={"event_data": event_data},
        )

    def log_suspension_point(
        self,
        game_id: str,
        transaction_id: str,
        player_id: str,
        card_name: str,
        phase_name: str,
        interaction_type: str,
        interaction_data: dict,
        **kwargs,
    ):
        """Log execution suspension points for interaction"""
        event_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": "dogma_suspension_point",
            "game_id": game_id,
            "transaction_id": transaction_id,
            "player_id": player_id,
            "card_name": card_name,
            "phase_name": phase_name,
            "interaction_type": interaction_type,
            "interaction_data": interaction_data,
            **kwargs,
        }

        self.activity_logger.info(json.dumps(event_data))
        self.logger.info(
            f"Suspension Point: {phase_name} [{transaction_id[:8]}] - {interaction_type}",
            extra={"event_data": event_data},
        )

    def log_resumption(
        self,
        game_id: str,
        transaction_id: str,
        player_id: str,
        card_name: str,
        phase_name: str,
        interaction_response: dict,
        **kwargs,
    ):
        """Log execution resumption from interaction"""
        event_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": "dogma_resumption",
            "game_id": game_id,
            "transaction_id": transaction_id,
            "player_id": player_id,
            "card_name": card_name,
            "phase_name": phase_name,
            "interaction_response": interaction_response,
            **kwargs,
        }

        self.activity_logger.info(json.dumps(event_data))
        self.logger.info(
            f"Resumption: {phase_name} [{transaction_id[:8]}] - response received",
            extra={"event_data": event_data},
        )


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""

    def format(self, record):
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "event_data"):
            log_data["event_data"] = record.event_data

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


# Global logger instance
activity_logger = GameActivityLogger()

# Global AI interaction logger
ai_interaction_logger = logging.getLogger("ai.interactions")


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance"""
    if name:
        return logging.getLogger(f"innovation.{name}")
    return logging.getLogger("innovation")


def log_game_action(game_id: str, player_id: str, action: str, **kwargs):
    """Convenience function for logging game actions"""
    activity_logger.log_player_action(
        game_id=game_id, player_id=player_id, action_type=action, action_data=kwargs
    )


def log_game_event(event_type: EventType, game_id: str, **kwargs):
    """Convenience function for logging game events"""
    activity_logger.log_game_event(event_type=event_type, game_id=game_id, **kwargs)
