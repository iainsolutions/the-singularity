"""
Broadcast Service - Centralized dual-channel broadcast for game updates.

Handles broadcasting game updates to both human players (via WebSocket) and
AI players (via Event Bus), following the hybrid architecture pattern.

Architecture Pattern:
- Human players (external): WebSocket with full game state
- AI players (internal): Event Bus with minimal metadata
"""

import json
from typing import Any, Optional

from logging_config import get_logger

logger = get_logger(__name__)


class BroadcastStats:
    """Simple statistics tracking for broadcast operations."""

    def __init__(self):
        self.total_broadcasts = 0
        self.websocket_successes = 0
        self.websocket_failures = 0
        self.event_bus_successes = 0
        self.event_bus_failures = 0

    def record_websocket_success(self):
        self.websocket_successes += 1

    def record_websocket_failure(self):
        self.websocket_failures += 1

    def record_event_bus_success(self):
        self.event_bus_successes += 1

    def record_event_bus_failure(self):
        self.event_bus_failures += 1

    def record_broadcast(self):
        self.total_broadcasts += 1

    def get_stats(self) -> dict[str, Any]:
        """Get current statistics."""
        return {
            "total_broadcasts": self.total_broadcasts,
            "websocket": {
                "successes": self.websocket_successes,
                "failures": self.websocket_failures,
                "success_rate": (
                    self.websocket_successes
                    / (self.websocket_successes + self.websocket_failures)
                    if (self.websocket_successes + self.websocket_failures) > 0
                    else 0.0
                ),
            },
            "event_bus": {
                "successes": self.event_bus_successes,
                "failures": self.event_bus_failures,
                "success_rate": (
                    self.event_bus_successes
                    / (self.event_bus_successes + self.event_bus_failures)
                    if (self.event_bus_successes + self.event_bus_failures) > 0
                    else 0.0
                ),
            },
        }


class BroadcastService:
    """
    Centralized service for broadcasting game updates to all player types.

    This service implements the hybrid architecture pattern:
    - WebSocket channel: For human players (external, browser-based)
    - Event Bus channel: For AI players (internal, in-process)

    Design Principles:
    1. Protocol-appropriate design: Use the right tool for each communication type
    2. Performance optimization: Full state for WebSocket, minimal metadata for Event Bus
    3. Separation of concerns: External vs internal communication
    4. Observability: Track success/failure for debugging
    """

    def __init__(self, connection_manager=None, event_bus=None):
        """
        Initialize the broadcast service.

        Args:
            connection_manager: WebSocket connection manager for human players
            event_bus: Event bus for AI players (in-process pub/sub)
        """
        self.connection_manager = connection_manager
        self.event_bus = event_bus
        self.stats = BroadcastStats()

    def set_dependencies(self, connection_manager=None, event_bus=None):
        """Update service dependencies (useful for initialization ordering)."""
        if connection_manager:
            self.connection_manager = connection_manager
        if event_bus:
            self.event_bus = event_bus

    async def broadcast_game_update(
        self, game_id: str, message_type: str, data: dict
    ) -> dict[str, bool]:
        """
        Broadcast game update to all players via appropriate channels.

        This is the main entry point for broadcasting game state changes.
        It sends messages through both channels (WebSocket and Event Bus) in parallel.

        Args:
            game_id: Game identifier
            message_type: Type of message (e.g., "game_state_updated", "action_performed")
            data: Message data (must include game_state for most message types)

        Returns:
            dict with 'websocket_success' and 'event_bus_success' booleans

        Message Format Specification:
            WebSocket: {"type": message_type, ...data}
            Event Bus: {minimal metadata extracted from game_state}

        Performance Note:
            Event Bus receives only minimal metadata to prevent "Invalid string length"
            errors from serializing massive game states. AI players fetch full game state
            from game_manager when needed.
        """
        self.stats.record_broadcast()

        websocket_success = await self._broadcast_websocket(game_id, message_type, data)
        event_bus_success = await self._broadcast_event_bus(game_id, message_type, data)

        return {
            "websocket_success": websocket_success,
            "event_bus_success": event_bus_success,
        }

    async def _broadcast_websocket(
        self, game_id: str, message_type: str, data: dict
    ) -> bool:
        """
        Broadcast to WebSocket channel (human players).

        WebSocket messages include full game_state for UI rendering.

        Args:
            game_id: Game identifier
            message_type: Message type
            data: Full message data including game_state

        Returns:
            True if successful, False otherwise
        """
        if not self.connection_manager:
            logger.warning(
                "ConnectionManager not available - skipping WebSocket broadcast"
            )
            return False

        try:
            message = json.dumps({"type": message_type, **data})
            await self.connection_manager.broadcast_to_game(message, game_id)

            logger.debug(
                f"WebSocket broadcast successful: {message_type} for game {game_id}"
            )
            self.stats.record_websocket_success()
            return True

        except Exception as e:
            logger.error(
                f"BROADCAST ERROR: WebSocket broadcast failed for game {game_id}",
                extra={
                    "game_id": game_id,
                    "message_type": message_type,
                    "error": str(e),
                },
                exc_info=True,
            )
            self.stats.record_websocket_failure()
            return False

    async def _broadcast_event_bus(
        self, game_id: str, message_type: str, data: dict
    ) -> bool:
        """
        Broadcast to Event Bus channel (AI players).

        Event Bus messages include only minimal metadata to avoid serialization overhead.
        AI players fetch full game state from game_manager when needed.

        Args:
            game_id: Game identifier
            message_type: Message type
            data: Full message data (game_state will be extracted/minimized)

        Returns:
            True if successful, False otherwise
        """
        if not self.event_bus:
            logger.debug(
                f"Event Bus not available for game {game_id} - skipping Event Bus broadcast"
            )
            return False

        try:
            # CRITICAL FIX: Skip interaction_required events - game_manager already publishes player_interaction
            # This prevents duplicate interactions being sent to AI players
            if message_type in ["interaction_required", "dogma_interaction"]:
                logger.debug(
                    f"Skipping Event Bus publish for {message_type} "
                    f"(handled by game_manager directly)"
                )
                return True  # Not a failure, just intentionally skipped

            # Extract minimal metadata from game_state if present
            # AI players can fetch full game from game_manager when needed
            event_data = self._extract_minimal_metadata(data)

            # Publish to event bus with source attribution
            source = self._determine_source()
            await self.event_bus.publish(
                game_id=game_id,
                event_type=message_type,
                data=event_data,
                source=source,
            )

            logger.debug(
                f"Event Bus publish successful: {message_type} for game {game_id}"
            )
            self.stats.record_event_bus_success()
            return True

        except Exception as e:
            logger.error(
                f"BROADCAST ERROR: Event Bus publish failed for game {game_id}",
                extra={
                    "game_id": game_id,
                    "message_type": message_type,
                    "error": str(e),
                },
                exc_info=True,
            )
            self.stats.record_event_bus_failure()
            return False

    def _extract_minimal_metadata(self, data: dict) -> dict:
        """
        Extract minimal metadata from full message data.

        This prevents "Invalid string length" errors by avoiding serialization
        of massive game states (which can exceed 500MB with long action logs).

        Args:
            data: Full message data potentially including game_state

        Returns:
            Minimal metadata dict suitable for Event Bus
        """
        game_state = data.get("game_state")

        if game_state:
            # Extract only essential fields for AI turn detection
            return {
                "current_player_id": game_state.get("current_player_id"),
                "phase": game_state.get("phase"),
                "turn_number": game_state.get("turn_number"),
                "actions_remaining": game_state.get("state", {}).get(
                    "actions_remaining"
                ),
            }
        else:
            # For non-game-state events (e.g., player_joined), pass minimal data
            return {k: v for k, v in data.items() if k != "game_state"}

    def _determine_source(self) -> str:
        """
        Determine the source component for Event Bus attribution.

        Uses stack inspection to identify the calling module.

        Returns:
            Source identifier string (e.g., "broadcast_service.games_router")
        """
        import inspect

        # Walk up the stack to find the calling router
        frame = inspect.currentframe()
        try:
            # Skip internal frames
            for _ in range(5):
                frame = frame.f_back
                if frame is None:
                    break
                filename = frame.f_code.co_filename
                if "games.py" in filename:
                    return "broadcast_service.games_router"
                elif "websocket.py" in filename:
                    return "broadcast_service.websocket_router"
        finally:
            del frame  # Avoid reference cycles

        return "broadcast_service.unknown"

    def get_stats(self) -> dict[str, Any]:
        """
        Get broadcast statistics for observability.

        Returns:
            Statistics dict with success/failure counts and rates
        """
        return self.stats.get_stats()


# Global broadcast service instance (initialized in main.py)
broadcast_service: Optional[BroadcastService] = None


def get_broadcast_service() -> BroadcastService:
    """
    Get the global broadcast service instance.

    Returns:
        BroadcastService instance

    Raises:
        RuntimeError: If broadcast service not initialized
    """
    if broadcast_service is None:
        raise RuntimeError(
            "BroadcastService not initialized. Call initialize_broadcast_service first."
        )
    return broadcast_service


def initialize_broadcast_service(
    connection_manager=None, event_bus=None
) -> BroadcastService:
    """
    Initialize the global broadcast service instance.

    Args:
        connection_manager: WebSocket connection manager
        event_bus: Event bus for AI players

    Returns:
        Initialized BroadcastService instance
    """
    global broadcast_service
    broadcast_service = BroadcastService(connection_manager, event_bus)
    logger.info(
        "BroadcastService initialized with hybrid architecture (WebSocket + Event Bus)"
    )
    return broadcast_service
