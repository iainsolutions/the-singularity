"""
WebSocket connection manager service for Innovation game server.
Handles WebSocket connections, heartbeats, and message broadcasting.
"""

import asyncio
import logging
import time
from collections import deque

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    WebSocket connection manager with improved memory management.
    Handles player connections, heartbeats, and message broadcasting.
    """

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.game_connections: dict[str, set[str]] = {}  # game_id -> set of player_ids
        self.player_games: dict[str, str] = {}  # player_id -> game_id mapping
        self.connection_tasks: dict[
            str, asyncio.Task
        ] = {}  # player_id -> heartbeat task
        self.last_heartbeat: dict[
            str, float
        ] = {}  # player_id -> last heartbeat timestamp
        self._lock = asyncio.Lock()  # Lock for thread-safe operations

        # Bounded task management to prevent resource leaks
        self._background_tasks: set = (
            set()
        )  # Track background tasks to prevent silent failures
        self._disconnect_semaphore = asyncio.Semaphore(
            10
        )  # Limit concurrent disconnect tasks
        self._max_background_tasks = 50  # Maximum background tasks allowed

        # Game manager reference - will be set externally
        self._game_manager = None

        # Lightweight in-memory WebSocket message logs for diagnostics
        # player_id -> deque of recent outbound messages (str)
        self.ws_logs: dict[str, deque[str]] = {}
        self._ws_log_max = 100

    def set_game_manager(self, game_manager):
        """Set reference to game manager for broadcast functionality"""
        self._game_manager = game_manager

    async def connect(
        self, websocket: WebSocket, player_id: str, game_id: str | None = None
    ):
        async with self._lock:
            # Clean up any existing connection for this player
            if player_id in self.active_connections:
                await self._cleanup_player_connection(player_id)

            await websocket.accept()
            self.active_connections[player_id] = websocket
            self.last_heartbeat[player_id] = time.time()

            # Track game connections
            if game_id:
                if game_id not in self.game_connections:
                    self.game_connections[game_id] = set()
                self.game_connections[game_id].add(player_id)
                self.player_games[player_id] = game_id

    async def _cleanup_player_connection(self, player_id: str):
        """Internal method to clean up a player's connection data"""
        # Cancel heartbeat task if exists
        if player_id in self.connection_tasks:
            task = self.connection_tasks[player_id]
            if not task.done():
                task.cancel()
            del self.connection_tasks[player_id]

        # Remove from active connections
        if player_id in self.active_connections:
            try:
                ws = self.active_connections[player_id]
                if ws.client_state != WebSocketState.DISCONNECTED:
                    await ws.close()
            except (WebSocketDisconnect, ConnectionError, RuntimeError) as e:
                # WebSocket already closed or connection lost
                logger.debug(f"WebSocket close failed for {player_id} (expected): {e}")
            except Exception as e:
                # Unexpected error during close - log it for debugging
                logger.warning(
                    f"Unexpected error closing WebSocket for {player_id}: {e}"
                )
            del self.active_connections[player_id]

        # Remove heartbeat tracking
        if player_id in self.last_heartbeat:
            del self.last_heartbeat[player_id]

    def disconnect(self, player_id: str, game_id: str | None = None):
        # Use the game_id from our tracking if not provided
        if not game_id and player_id in self.player_games:
            game_id = self.player_games[player_id]

        # Check if we're at the background task limit
        if len(self._background_tasks) >= self._max_background_tasks:
            logger.warning(
                f"Background task limit reached ({self._max_background_tasks}). "
                f"Executing synchronous disconnect for {player_id}"
            )
            # Execute truly synchronous cleanup to prevent resource exhaustion
            self._sync_disconnect(player_id, game_id)

            # Clean up some background tasks (but don't create new untracked tasks)
            try:
                # Check if event loop is available for cleanup tasks
                _ = asyncio.get_running_loop()  # Verify loop exists
                if len(self._background_tasks) > 0:
                    # Create tracked cleanup task
                    cleanup_task = asyncio.create_task(self._cleanup_oldest_tasks())
                    self._background_tasks.add(cleanup_task)
                    cleanup_task.add_done_callback(self._handle_disconnect_completion)
            except RuntimeError:
                # No event loop running, skip async cleanup
                logger.debug("No event loop running, skipping background task cleanup")
            return

        # Create managed background task with concurrency limiting
        task = asyncio.create_task(self._bounded_disconnect(player_id, game_id))
        self._background_tasks.add(task)

        # Add completion callback to handle errors and cleanup
        task.add_done_callback(self._handle_disconnect_completion)

    def _sync_disconnect(self, player_id: str, game_id: str | None = None):
        """Synchronous version of disconnect for when background tasks are saturated"""
        try:
            logger.debug(f"Executing synchronous disconnect for player {player_id}")

            # Synchronous cleanup of player connection data
            self._sync_cleanup_player_connection(player_id)

            # Clean up game connections
            if game_id and game_id in self.game_connections:
                self.game_connections[game_id].discard(player_id)
                if not self.game_connections[game_id]:
                    del self.game_connections[game_id]

            # Clean up player-game mapping
            if player_id in self.player_games:
                del self.player_games[player_id]

            logger.debug(f"Successfully disconnected player {player_id} synchronously")

        except Exception as e:
            logger.error(
                f"Error during synchronous disconnect for player {player_id}: {e}",
                exc_info=True,
            )

    def _sync_cleanup_player_connection(self, player_id: str):
        """Synchronous cleanup of player connection data (no WebSocket close)"""
        # Cancel heartbeat task if exists
        if player_id in self.connection_tasks:
            task = self.connection_tasks[player_id]
            if not task.done():
                task.cancel()
            del self.connection_tasks[player_id]

        # Remove from active connections (skip async WebSocket close)
        if player_id in self.active_connections:
            # Note: We don't call ws.close() here since it's async
            # The WebSocket will be closed by the client or network timeout
            logger.debug(
                f"Removing WebSocket connection for {player_id} (close skipped in sync mode)"
            )
            del self.active_connections[player_id]

        # Remove heartbeat tracking
        if player_id in self.last_heartbeat:
            del self.last_heartbeat[player_id]

    def _handle_disconnect_completion(self, task: asyncio.Task):
        """Handle completion of disconnect tasks with proper error logging"""
        # Remove task from tracking set
        self._background_tasks.discard(task)

        # Check for exceptions and log them
        try:
            exception = task.exception()
            if exception:
                logger.error(f"Disconnect task failed: {exception}", exc_info=exception)
        except asyncio.CancelledError:
            logger.debug("Disconnect task was cancelled")
        except Exception as e:
            logger.error(f"Error checking disconnect task completion: {e}")

    async def _bounded_disconnect(self, player_id: str, game_id: str | None = None):
        """Bounded async disconnect with semaphore to limit concurrency"""
        async with self._disconnect_semaphore:  # Limit concurrent disconnect operations
            await self._async_disconnect(player_id, game_id)

    async def _async_disconnect(self, player_id: str, game_id: str | None = None):
        """Async version of disconnect with proper cleanup and error handling"""
        try:
            async with self._lock:
                await self._cleanup_player_connection(player_id)

                # Clean up game connections
                if game_id and game_id in self.game_connections:
                    self.game_connections[game_id].discard(player_id)
                    if not self.game_connections[game_id]:
                        del self.game_connections[game_id]

                # Clean up player-game mapping
                if player_id in self.player_games:
                    del self.player_games[player_id]

                logger.debug(
                    f"Successfully disconnected player {player_id} from game {game_id}"
                )

        except Exception as e:
            # Log error but don't re-raise to prevent task failure propagation
            logger.error(
                f"Error during async disconnect for player {player_id}: {e}",
                exc_info=True,
            )

    async def _cleanup_oldest_tasks(self):
        """Clean up completed background tasks to prevent unbounded growth"""
        completed_tasks = [task for task in self._background_tasks if task.done()]
        for task in completed_tasks:
            self._background_tasks.discard(task)

        if completed_tasks:
            logger.debug(
                f"Cleaned up {len(completed_tasks)} completed background tasks"
            )

    async def send_personal_message(self, message: str, player_id: str):
        logger.debug(f"Attempting to send personal message to {player_id}")
        logger.debug(f"Active connections: {list(self.active_connections.keys())}")
        logger.debug(f"Player ID type: {type(player_id)}, value: '{player_id}'")
        logger.debug(
            f"Connection keys types: {[type(k) for k in self.active_connections]}"
        )

        if player_id in self.active_connections:
            try:
                ws = self.active_connections[player_id]
                logger.info(
                    f"Found WebSocket for {player_id}, state: {ws.client_state if hasattr(ws, 'client_state') else 'unknown'}"
                )
                logger.info(f"Sending message to {player_id}: {message[:200]}...")
                # Capture outbound message for diagnostics
                try:
                    log = self.ws_logs.setdefault(
                        player_id, deque(maxlen=self._ws_log_max)
                    )
                    log.append(message)
                except Exception:
                    pass
                await ws.send_text(message)
                logger.info(
                    f"Successfully sent message to {player_id} - message was: {message[:500]}..."
                )
            except Exception as e:
                logger.error(
                    f"Failed to send message to {player_id}: {e}", exc_info=True
                )
                self.disconnect(player_id)
        else:
            logger.warning(f"Player {player_id} not in active connections")
            logger.warning(
                f"Available player IDs: {list(self.active_connections.keys())}"
            )
            # Check if player_id exists in player_games mapping
            if player_id in self.player_games:
                logger.warning(
                    f"Player {player_id} is in game {self.player_games[player_id]} but has no active connection"
                )

    async def cleanup_stale_connections(self):
        """Remove stale WebSocket connections with improved detection"""
        current_time = time.time()
        stale_connections = []

        # Also clean up completed tasks periodically
        await self._cleanup_oldest_tasks()

        async with self._lock:
            for player_id, last_hb in list(self.last_heartbeat.items()):
                # Consider connection stale if no heartbeat response in 90 seconds
                if current_time - last_hb > 90:
                    stale_connections.append(player_id)
                    continue

                # Also check if WebSocket is actually connected
                if player_id in self.active_connections:
                    ws = self.active_connections[player_id]
                    if ws.client_state == WebSocketState.DISCONNECTED:
                        stale_connections.append(player_id)

        # Clean up stale connections using bounded disconnect
        for player_id in stale_connections:
            logger.info(f"Cleaning up stale connection for player {player_id}")
            # Use the bounded disconnect method to respect resource limits
            self.disconnect(player_id)

    def track_heartbeat(self, player_id: str):
        """Update heartbeat timestamp for a player"""
        if player_id in self.last_heartbeat:
            self.last_heartbeat[player_id] = time.time()

    async def shutdown(self):
        """Gracefully shutdown connection manager and wait for background tasks"""
        logger.info(
            f"Shutting down connection manager with {len(self._background_tasks)} background tasks"
        )

        # First, stop accepting new disconnect tasks by maxing out the semaphore
        for _ in range(self._disconnect_semaphore._value):
            await self._disconnect_semaphore.acquire()

        # Cancel all background tasks
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()

        # Wait for all tasks to complete or timeout after 5 seconds
        if self._background_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._background_tasks, return_exceptions=True),
                    timeout=5.0,
                )
            except TimeoutError:
                logger.warning(
                    "Some background tasks did not complete within timeout during shutdown"
                )
            except Exception as e:
                logger.error(f"Error during background task shutdown: {e}")

        self._background_tasks.clear()
        logger.info("Connection manager shutdown complete")

    def register_heartbeat_task(self, player_id: str, task: asyncio.Task):
        """Register a heartbeat task for a player"""
        self.connection_tasks[player_id] = task

    async def broadcast_to_game(self, message: str, game_id: str):
        """Broadcast message to all players in a game concurrently"""
        if not self._game_manager:
            logger.error("Game manager not set in connection manager")
            return

        game = self._game_manager.get_game(game_id)
        if not game:
            return

        # Collect send tasks for concurrent execution
        send_tasks = []
        connected_players = []

        for player in game.players:
            if player.id in self.active_connections:
                # Create a task for each player
                task = self._send_to_player(player.id, message, game_id)
                send_tasks.append(task)
                connected_players.append(player.id)

        if not send_tasks:
            logger.debug(f"No connected players to broadcast to in game {game_id}")
            return

        # Execute all sends concurrently
        try:
            results = await asyncio.gather(*send_tasks, return_exceptions=True)

            # Log any failures (exceptions are returned, not raised)
            failed_players = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    player_id = connected_players[i]
                    failed_players.append(player_id)
                    logger.error(
                        f"Failed to send message to player {player_id}: {result}"
                    )

            # Log success stats
            success_count = len(send_tasks) - len(failed_players)
            logger.debug(
                f"Broadcast to game {game_id}: {success_count}/{len(send_tasks)} players succeeded"
            )

        except Exception as e:
            logger.error(f"Unexpected error during broadcast to game {game_id}: {e}")

    async def _send_to_player(self, player_id: str, message: str, game_id: str) -> None:
        """Send message to a single player with error handling"""
        try:
            # Capture outbound message for diagnostics
            try:
                log = self.ws_logs.setdefault(player_id, deque(maxlen=self._ws_log_max))
                log.append(message)
            except Exception:
                pass
            await self.active_connections[player_id].send_text(message)
        except Exception as e:
            # Disconnect player on send failure
            logger.warning(f"Send failed for player {player_id}, disconnecting: {e}")
            self.disconnect(player_id, game_id)
            raise  # Re-raise to be caught by gather

    def get_ws_logs(self, player_id: str, limit: int = 50) -> list[str]:
        """Retrieve recent outbound WS messages for a player (most recent last)."""
        try:
            if player_id in self.ws_logs:
                logs = list(self.ws_logs[player_id])
                return logs[-limit:]
            return []
        except Exception:
            return []

    def get_game_player_connections(self, game_id: str) -> dict[str, WebSocket]:
        """
        Get all active WebSocket connections for players in a game.

        Returns:
            dict mapping player_id -> WebSocket for all connected players in the game
        """
        connections = {}
        if game_id not in self.game_connections:
            return connections

        player_ids = self.game_connections[game_id]
        for player_id in player_ids:
            if player_id in self.active_connections:
                connections[player_id] = self.active_connections[player_id]

        return connections
