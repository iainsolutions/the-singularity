"""
Game Event Bus

In-process event bus for game state change notifications.
Used by AI players to subscribe to game events without WebSocket overhead.
"""
import asyncio
from dataclasses import dataclass
from typing import Any

from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class EventMessage:
    """
    Represents an event message with full metadata for deduplication and tracking.
    """

    event_id: str  # Unique identifier for this event
    sequence_num: int  # Game-specific sequence number for ordering
    source: str  # Source component that published the event
    timestamp: float  # Unix timestamp when event was created
    event_type: str  # Type of event (e.g., "game_state_updated")
    game_id: str  # Game this event belongs to
    data: dict[str, Any]  # Event payload
    correlation_id: str | None = None  # Optional ID to correlate related events
    duplicate: bool = False  # Whether this was detected as a duplicate


class GameEventBus:
    """
    Event bus for game events using async pub/sub pattern.
    Includes deduplication, sequence tracking, and source identification.
    """

    def __init__(self):
        self._subscribers: dict[str, list[callable]] = {}  # game_id -> callbacks
        self._lock = asyncio.Lock()
        # Deduplication tracking
        self._processed_events: dict[str, set[str]] = {}  # game_id -> set of event_ids
        self._event_sequences: dict[str, int] = {}  # game_id -> last sequence number
        self._event_history: dict[
            str, list[EventMessage]
        ] = {}  # game_id -> recent events
        self._max_history_size = 100  # Keep last N events per game for debugging
        self._dedup_ttl_seconds = 300  # 5 minutes TTL for deduplication cache

    async def publish(
        self,
        game_id: str,
        event_type: str,
        data: dict,
        source: str = "unknown",
        correlation_id: str | None = None,
        event_id: str | None = None,
    ) -> EventMessage:
        """
        Publish event to all subscribers of a specific game with deduplication.

        Args:
            game_id: Game ID to publish to
            event_type: Type of event (e.g., "game_state_updated", "action_performed")
            data: Event data dictionary
            source: Source component publishing the event (e.g., "async_game_manager")
            correlation_id: Optional ID to correlate related events
            event_id: Optional specific event ID (auto-generated if not provided)

        Returns:
            EventMessage: The published event message with metadata
        """
        import time
        import uuid

        # Generate event metadata
        event_id = event_id or str(uuid.uuid4())
        timestamp = time.time()

        # Get or initialize sequence number for this game
        async with self._lock:
            if game_id not in self._event_sequences:
                self._event_sequences[game_id] = 0
            self._event_sequences[game_id] += 1
            sequence_num = self._event_sequences[game_id]

            # Check for duplicate event ID
            if game_id not in self._processed_events:
                self._processed_events[game_id] = set()

            if event_id in self._processed_events[game_id]:
                logger.warning(
                    f"⚠️ Duplicate event detected and skipped: event_id={event_id}, "
                    f"game_id={game_id}, event_type={event_type}, source={source}"
                )
                # Create duplicate event message
                duplicate_event = EventMessage(
                    event_id=event_id,
                    sequence_num=sequence_num,
                    source=source,
                    timestamp=timestamp,
                    event_type=event_type,
                    game_id=game_id,
                    data=data,
                    correlation_id=correlation_id,
                    duplicate=True,
                )

                # Store duplicate in history for debugging
                if game_id not in self._event_history:
                    self._event_history[game_id] = []
                self._event_history[game_id].append(duplicate_event)

                # Trim history if it gets too large
                if len(self._event_history[game_id]) > self._max_history_size:
                    self._event_history[game_id] = self._event_history[game_id][
                        -self._max_history_size :
                    ]

                # Return the duplicate event message but don't publish to subscribers
                return duplicate_event

            # Add to processed events
            self._processed_events[game_id].add(event_id)

            # Store in history for debugging
            if game_id not in self._event_history:
                self._event_history[game_id] = []

            event_message = EventMessage(
                event_id=event_id,
                sequence_num=sequence_num,
                source=source,
                timestamp=timestamp,
                event_type=event_type,
                game_id=game_id,
                data=data,
                correlation_id=correlation_id,
                duplicate=False,
            )

            self._event_history[game_id].append(event_message)

            # Trim history if it gets too large
            if len(self._event_history[game_id]) > self._max_history_size:
                self._event_history[game_id] = self._event_history[game_id][
                    -self._max_history_size :
                ]

            # Clean up old events periodically (simple TTL)
            self._cleanup_old_events(game_id, timestamp)

            # Get subscribers
            if game_id in self._subscribers:
                callbacks = self._subscribers[game_id].copy()
            else:
                callbacks = None

        logger.info(
            f"🔔 Event Bus publish: game_id={game_id}, event_type={event_type}, "
            f"source={source}, sequence={sequence_num}, event_id={event_id[:8]}..., "
            f"EventBus instance: {id(self)}"
        )

        # Execute callbacks outside the lock to avoid blocking
        if callbacks:
            logger.info(
                f"📤 Publishing {event_type} to {len(callbacks)} subscriber(s) of game {game_id}"
            )
            # Pass the full event message to subscribers
            for i, callback in enumerate(callbacks):
                task = asyncio.create_task(
                    self._safe_callback(callback, event_message, i)
                )
                # Add callback for task completion tracking (debugging/observability)
                task.add_done_callback(
                    lambda t, idx=i: self._log_task_completion(
                        t, event_type, game_id, idx
                    )
                )
        else:
            logger.warning(
                f"⚠️  No subscribers found for game {game_id}, event {event_type} not delivered"
            )

        return event_message

    def _cleanup_old_events(self, game_id: str, current_time: float):
        """Remove events older than TTL from deduplication cache."""
        if game_id in self._event_history:
            # Remove events older than TTL
            cutoff_time = current_time - self._dedup_ttl_seconds
            old_event_ids = {
                event.event_id
                for event in self._event_history[game_id]
                if event.timestamp < cutoff_time
            }
            if old_event_ids and game_id in self._processed_events:
                self._processed_events[game_id] -= old_event_ids

    def _log_task_completion(
        self, task: asyncio.Task, event_type: str, game_id: str, idx: int
    ):
        """Log task completion for debugging/observability."""
        try:
            exception = task.exception()
            if exception:
                logger.error(
                    f"❌ Event callback {idx} for {event_type} in game {game_id} failed: {exception}"
                )
            else:
                logger.debug(
                    f"✅ Event callback {idx} for {event_type} in game {game_id} completed"
                )
        except asyncio.CancelledError:
            logger.debug(
                f"⚠️  Event callback {idx} for {event_type} in game {game_id} was cancelled"
            )
        except Exception as e:
            logger.error(f"Error logging task completion: {e}")

    async def _safe_callback(
        self, callback: callable, event_message: EventMessage, idx: int
    ):
        """
        Safely execute callback with error handling.
        Now passes the full EventMessage to subscribers.
        """
        try:
            logger.debug(
                f"Executing callback {idx} for event {event_message.event_type} "
                f"in game {event_message.game_id}"
            )

            # Check callback signature to maintain backward compatibility
            import inspect

            sig = inspect.signature(callback)
            params = list(sig.parameters.keys())

            # If callback expects old format (event_type, data), extract those
            if len(params) == 2 and params[0] == "event_type":
                # Legacy callback format
                result = await callback(event_message.event_type, event_message.data)
            else:
                # New format: pass the full EventMessage
                result = await callback(event_message)

            logger.debug(
                f"Callback {idx} completed for {event_message.event_type} "
                f"in game {event_message.game_id}"
            )
            return result
        except Exception as e:
            logger.error(
                f"Error in event callback {idx} for {event_message.event_type}: {e}",
                exc_info=True,
            )

    async def subscribe(
        self, game_id: str, callback: callable, subscriber_id: str | None = None
    ):
        """
        Subscribe to events for a specific game.

        Args:
            game_id: Game ID to subscribe to
            callback: Async function to call when event is published
            subscriber_id: Optional ID for the subscriber (for tracking)
        """
        import traceback

        async with self._lock:
            if game_id not in self._subscribers:
                self._subscribers[game_id] = []
            self._subscribers[game_id].append(callback)

            # DEBUG: Log stack trace to see where subscribe is being called from
            stack = "".join(traceback.format_stack()[-5:-1])
            logger.debug(f"SUBSCRIBE STACK TRACE for game {game_id}:\n{stack}")

        logger.info(
            f"✅ Subscriber added to game {game_id} "
            f"({'ID: ' + subscriber_id if subscriber_id else 'anonymous'}). "
            f"Total subscribers: {len(self._subscribers.get(game_id, []))} "
            f"Event Bus instance: {id(self)}"
        )

    async def unsubscribe(self, game_id: str, callback: callable) -> bool:
        """
        Unsubscribe from events for a specific game.

        Args:
            game_id: Game ID to unsubscribe from
            callback: The callback function to remove

        Returns:
            bool: True if callback was found and removed, False otherwise
        """
        async with self._lock:
            if game_id in self._subscribers:
                try:
                    self._subscribers[game_id].remove(callback)
                    logger.info(
                        f"✅ Subscriber removed from game {game_id}. "
                        f"Remaining subscribers: {len(self._subscribers[game_id])}"
                    )

                    # Clean up empty subscriber lists
                    if not self._subscribers[game_id]:
                        del self._subscribers[game_id]
                        # Also clean up event tracking for this game
                        if game_id in self._processed_events:
                            del self._processed_events[game_id]
                        if game_id in self._event_sequences:
                            del self._event_sequences[game_id]
                        if game_id in self._event_history:
                            del self._event_history[game_id]
                        logger.info(f"🧹 Cleaned up all tracking for game {game_id}")

                    return True
                except ValueError:
                    logger.warning(
                        f"⚠️  Callback not found in subscribers for game {game_id}"
                    )
                    return False
            else:
                logger.warning(f"⚠️  No subscribers found for game {game_id}")
                return False

    async def unsubscribe_all(self, game_id: str):
        """
        Remove all subscribers for a specific game and clean up tracking.

        Args:
            game_id: Game ID to remove all subscribers from
        """
        async with self._lock:
            if game_id in self._subscribers:
                count = len(self._subscribers[game_id])
                del self._subscribers[game_id]
                # Clean up all tracking for this game
                if game_id in self._processed_events:
                    del self._processed_events[game_id]
                if game_id in self._event_sequences:
                    del self._event_sequences[game_id]
                if game_id in self._event_history:
                    del self._event_history[game_id]
                logger.info(
                    f"✅ Removed all {count} subscribers and tracking for game {game_id}"
                )
            else:
                logger.warning(f"⚠️  No subscribers found for game {game_id}")

    def get_subscriber_count(self, game_id: str) -> int:
        """Get the number of subscribers for a specific game."""
        return len(self._subscribers.get(game_id, []))

    def get_event_history(self, game_id: str, limit: int = 50) -> list[EventMessage]:
        """
        Get recent event history for a game (for debugging).

        Args:
            game_id: Game ID to get history for
            limit: Maximum number of events to return

        Returns:
            List of recent EventMessage objects
        """
        if game_id not in self._event_history:
            return []

        history = self._event_history[game_id]
        return history[-limit:] if len(history) > limit else history.copy()

    def get_last_sequence_number(self, game_id: str) -> int:
        """Get the last sequence number for a game."""
        return self._event_sequences.get(game_id, 0)
