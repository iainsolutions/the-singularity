"""
AI Event Subscriber

AI players subscribe to game events via event bus instead of WebSocket.
More efficient for in-process communication.
"""

from typing import Any

from logging_config import get_logger


logger = get_logger(__name__)


class AIEventSubscriber:
    """
    Event-based AI player that subscribes to game events.

    More efficient than WebSocket for in-process communication.
    Listens for game_state_updated events and executes turns via HTTP.
    """

    def __init__(self, game_id: str, player_id: str, event_bus, game_manager):
        self.game_id = game_id
        self.player_id = player_id
        self.event_bus = event_bus
        self.game_manager = game_manager
        self._running = False
        self._last_turn_state = None  # Track last turn state to avoid duplicates
        self._processed_events = set()  # Track processed event IDs for deduplication

    async def start(self):
        """Subscribe to game events"""
        if self._running:
            logger.warning(
                f"AI Event Subscriber already running for player {self.player_id}"
            )
            return

        self._running = True
        logger.info(
            f"DEBUG: AI Event Subscriber using event_bus instance {id(self.event_bus)}"
        )
        await self.event_bus.subscribe(self.game_id, self._handle_event)
        logger.info(
            f"AI player {self.player_id} subscribed to game {self.game_id} events"
        )

    async def stop(self):
        """Unsubscribe from game events"""
        if not self._running:
            return

        self._running = False
        await self.event_bus.unsubscribe(self.game_id, self._handle_event)
        logger.info(
            f"AI player {self.player_id} unsubscribed from game {self.game_id} events"
        )

    async def _handle_event(self, event: Any):
        """Handle game event - now accepts EventMessage or legacy format"""

        # Handle new EventMessage format
        if hasattr(event, "event_type") and hasattr(event, "data"):
            # New EventMessage format
            event_type = event.event_type
            data = event.data

            # Log with additional metadata
            logger.info(
                f"AI Event Subscriber {self.player_id} received event: {event_type} "
                f"(seq={event.sequence_num}, source={event.source}, id={event.event_id[:8]}...)"
            )

            # Check for duplicate processing (defensive - event bus should handle this)
            if hasattr(self, "_processed_events"):
                if event.event_id in self._processed_events:
                    logger.warning(
                        f"AI Event Subscriber {self.player_id} skipping duplicate event {event.event_id}"
                    )
                    return
                self._processed_events.add(event.event_id)
                # Keep only last 100 event IDs to prevent memory leak
                if len(self._processed_events) > 100:
                    self._processed_events = set(list(self._processed_events)[-100:])
            else:
                self._processed_events = {event.event_id}

        else:
            # Legacy format (event_type, data as separate parameters)
            event_type = event
            data = event if isinstance(event, dict) else {}
            logger.info(
                f"AI Event Subscriber {self.player_id} received legacy event: {event_type}"
            )

        if not self._running:
            logger.warning(
                f"AI Event Subscriber {self.player_id} not running, ignoring event {event_type}"
            )
            return

        if event_type in (
            "game_state_updated",
            "action_performed",
            "game_started",
            "setup_selection_made",
            "game_restored",
            "dogma_response",
            "dogma_response_processed",
        ):
            logger.info(
                f"AI Event Subscriber {self.player_id} handling game state update"
            )
            await self._handle_game_state_update(data)
        elif event_type == "player_interaction":
            logger.info(
                f"AI Event Subscriber {self.player_id} handling interaction request"
            )
            await self._handle_interaction_request(data)

    async def _handle_game_state_update(self, data: dict):
        """Check if it's AI's turn and execute if needed"""
        # PERFORMANCE FIX: Event Bus now sends minimal metadata, not full game_state
        # Use metadata to check if it's AI's turn BEFORE fetching expensive game state
        game = self.game_manager.get_game(self.game_id)
        if not game:
            logger.warning(
                f"Game {self.game_id} not found for AI player {self.player_id}"
            )
            return

        # Check phase and current player using game object directly (no serialization)
        phase = game.phase.value if hasattr(game.phase, "value") else game.phase

        # Handle setup phase - auto-select first card
        if phase == "setup_card_selection":
            # Only serialize for setup phase (happens once per player)
            game_state = game.to_dict()
            await self._handle_setup_phase(game_state)
            return

        # REMOVED: Duplicate pending interaction check
        # Interactions are handled via player_interaction events, not action_performed
        # Checking here causes the AI to respond multiple times to the same interaction

        # Check if it's this AI player's turn WITHOUT serializing
        current_player_index = game.state.current_player_index
        if current_player_index is None or current_player_index >= len(game.players):
            return

        current_player = game.players[current_player_index]

        if current_player.id == self.player_id:
            # Create turn state signature to avoid duplicate executions
            # DON'T include actions_remaining - we want ONE execution per turn,
            # not one per action! The AI turn executor handles the loop.
            turn_state = (
                current_player_index,
                phase,
                getattr(game, "turn_number", getattr(game.state, "turn_number", 1)),
            )

            # Only execute if turn state has changed
            if turn_state != self._last_turn_state:
                self._last_turn_state = turn_state
                logger.info(f"It's AI player {self.player_id}'s turn!")
                await self._execute_turn()
        else:
            # Not this AI's turn - reset state so next turn is treated as new
            self._last_turn_state = None

    async def _handle_setup_phase(self, game_state: dict):
        """Handle setup phase - auto-select first card"""
        import httpx
        from app_config import get_server_config

        try:
            # Find this AI player in game state
            players = game_state.get("players", [])
            ai_player = next(
                (p for p in players if p.get("id") == self.player_id), None
            )

            if not ai_player:
                return

            # Check if already made selection
            if ai_player.get("setup_selection_made"):
                return

            # Auto-select first card in hand
            hand = ai_player.get("hand", [])
            if not hand:
                return

            first_card = hand[0]
            card_id = first_card.get("card_id")

            if not card_id:
                return

            # Get API base URL from configuration
            api_base = get_server_config().get_internal_api_url()

            # Make setup selection via HTTP
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{api_base}/api/v1/games/{self.game_id}/setup-selection",
                    json={"player_id": self.player_id, "card_id": card_id},
                )

                if response.status_code == 200:
                    logger.info(
                        f"AI player {self.player_id} auto-selected {first_card.get('name')} for setup"
                    )
                elif response.status_code == 400:
                    # Check if it's because selection already made (race condition)
                    response_data = response.json()
                    error_msg = response_data.get("detail", "")

                    if "Cannot make setup selection" in error_msg:
                        # Verify if selection was already made by another event handler
                        game = self.game_manager.get_game(self.game_id)
                        if game:
                            player = game.get_player_by_id(self.player_id)
                            if player and player.setup_selection_made:
                                logger.debug(
                                    f"AI player {self.player_id} setup selection already made (race condition handled)"
                                )
                                return  # Already done - not an error

                        # Selection not made but API rejected - log as warning
                        logger.warning(
                            f"AI player {self.player_id} setup selection rejected: {error_msg}"
                        )
                    else:
                        logger.warning(
                            f"AI player {self.player_id} setup selection failed: {error_msg}"
                        )
                else:
                    logger.error(
                        f"Failed to make setup selection: {response.status_code} {response.text}"
                    )

        except Exception as e:
            logger.error(f"Error in setup phase handling: {e}", exc_info=True)

    async def _handle_interaction_request(self, data: dict):
        """Handle interaction request (dogma effect requiring player choice)"""
        # Event Bus publishes "player_id" not "target_player_id"
        target_player_id = data.get("player_id") or data.get("target_player_id")

        logger.debug(
            f"AI Event Subscriber {self.player_id[:8]}... received player_interaction event. "
            f"Target player: {target_player_id[:8] if target_player_id else 'None'}..."
        )
        logger.debug(f"AI player_id (full): {self.player_id}")
        logger.debug(f"AI Target player_id (full): {target_player_id}")
        logger.debug(f"AI Match check: {target_player_id == self.player_id}")

        if target_player_id == self.player_id:
            # REMOVED: Duplicate detection was blocking legitimate repeat iterations
            # The transaction state and game manager already handle real duplicates
            # This was causing Oars repeat_on_compliance to fail because the second
            # interaction arrived while the first HTTP response was still in flight

            logger.info(
                f"✅ AI player {self.player_id} WILL respond (player_id matches)"
            )
            await self._respond_to_interaction(data)
        else:
            logger.debug(
                f"⏭️  AI player {self.player_id[:8]}... ignoring interaction for player {target_player_id[:8]}..."
            )

    async def _execute_turn(self):
        """Execute AI turn by making HTTP requests"""
        from services.ai_turn_executor import get_ai_turn_executor

        try:
            executor = get_ai_turn_executor(self.game_manager)

            logger.info(f"Executing AI turn for player {self.player_id}")
            result = await executor.execute_ai_turn(self.game_id, self.player_id)

            if result.get("success"):
                logger.info(
                    f"AI turn completed: {len(result.get('actions_taken', []))} actions"
                )
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"AI turn failed: {error_msg}")
                # Notify players about AI failure - don't let game hang silently
                await self._notify_ai_failure("turn", error_msg)

        except Exception as e:
            logger.error(f"Error executing AI turn: {e}", exc_info=True)
            # Notify players about AI failure - don't let game hang silently
            await self._notify_ai_failure("turn", str(e))

    async def _respond_to_interaction(self, interaction_data: dict):
        """Respond to interaction request"""
        from services.ai_service import ai_service
        from services.ai_turn_executor import get_ai_turn_executor

        try:
            executor = get_ai_turn_executor(self.game_manager)

            # Get game state
            game = self.game_manager.get_game(self.game_id)
            if not game:
                logger.error(f"Game not found: {self.game_id}")
                return

            # Get AI agent from ai_service (not game_manager - it's player-agnostic)
            agent = ai_service.get_agent(self.player_id)
            if not agent:
                logger.error(f"No AI agent found for player {self.player_id}")
                return

            # Handle interaction through executor
            result = await executor._handle_interaction(
                self.game_id,
                self.player_id,
                game,
                agent,
            )

            if result and result.get("success"):
                logger.info("AI interaction response sent successfully")
            else:
                error_msg = (
                    result.get("error", "Unknown error")
                    if result
                    else "No result returned"
                )
                logger.error(f"AI interaction response failed: {error_msg}")
                # Notify players about AI failure - don't let game hang silently
                await self._notify_ai_failure("interaction", error_msg)

        except Exception as e:
            logger.error(f"Error responding to interaction: {e}", exc_info=True)
            # Notify players about AI failure - don't let game hang silently
            await self._notify_ai_failure("interaction", str(e))

    async def _notify_ai_failure(self, failure_type: str, error_message: str):
        """Notify players when AI fails - don't let game hang silently"""
        from logging_config import activity_logger

        from services.broadcast_service import broadcast_service

        try:
            # Get game and player info
            game = self.game_manager.get_game(self.game_id)
            if not game:
                logger.error(
                    f"Cannot notify AI failure - game {self.game_id} not found"
                )
                return

            player = next((p for p in game.players if p.id == self.player_id), None)
            player_name = player.name if player else "AI Player"

            # Log to activity log (visible to all players)
            if activity_logger:
                from logging_config import EventType

                activity_logger.log_game_event(
                    event_type=EventType.ERROR_OCCURRED,
                    game_id=self.game_id,
                    message=f"⚠️ {player_name} encountered an error during {failure_type}: {error_message[:100]}",
                    data={"error": error_message, "failure_type": failure_type},
                )

            # Broadcast error notification to all players via WebSocket
            error_data = {
                "type": "ai_error",
                "player_id": self.player_id,
                "player_name": player_name,
                "failure_type": failure_type,
                "error": error_message,
                "message": f"{player_name} encountered an error and cannot continue. Please end the game or wait for recovery.",
            }

            await broadcast_service.broadcast_game_update(
                self.game_id, "ai_error", error_data
            )

            logger.error(
                f"AI failure notification sent to all players in game {self.game_id}: "
                f"{player_name} failed during {failure_type}"
            )

        except Exception as notify_error:
            logger.error(f"Failed to notify AI failure: {notify_error}", exc_info=True)


# Global registry of AI Event Subscribers
_ai_subscribers = {}


async def create_ai_event_subscriber(
    game_id: str, player_id: str, event_bus, game_manager
) -> AIEventSubscriber:
    """Create and start an AI Event Subscriber"""
    subscriber_key = f"{game_id}:{player_id}"

    if subscriber_key in _ai_subscribers:
        logger.warning(f"AI Event Subscriber already exists for {subscriber_key}")
        return _ai_subscribers[subscriber_key]

    subscriber = AIEventSubscriber(game_id, player_id, event_bus, game_manager)
    await subscriber.start()
    _ai_subscribers[subscriber_key] = subscriber

    return subscriber


async def stop_ai_event_subscriber(game_id: str, player_id: str):
    """Stop an AI Event Subscriber"""
    subscriber_key = f"{game_id}:{player_id}"

    if subscriber_key in _ai_subscribers:
        subscriber = _ai_subscribers[subscriber_key]
        await subscriber.stop()
        del _ai_subscribers[subscriber_key]
        logger.info(f"Stopped AI Event Subscriber for {subscriber_key}")


async def cleanup_game_subscribers(game_id: str):
    """
    Stop all AI Event Subscribers for a game.

    Called when game finishes or is deleted to prevent resource leaks.
    """
    subscribers_to_stop = [
        key for key in _ai_subscribers if key.startswith(f"{game_id}:")
    ]

    for subscriber_key in subscribers_to_stop:
        try:
            subscriber = _ai_subscribers[subscriber_key]
            await subscriber.stop()
            del _ai_subscribers[subscriber_key]
            logger.info(f"Cleaned up AI Event Subscriber: {subscriber_key}")
        except Exception as e:
            logger.error(f"Error cleaning up subscriber {subscriber_key}: {e}")

    if subscribers_to_stop:
        logger.info(
            f"Cleaned up {len(subscribers_to_stop)} AI subscribers for game {game_id}"
        )


def get_ai_event_subscriber(game_id: str, player_id: str) -> AIEventSubscriber | None:
    """Get an AI Event Subscriber"""
    subscriber_key = f"{game_id}:{player_id}"
    return _ai_subscribers.get(subscriber_key)


def get_active_subscriber_count() -> int:
    """Get count of active AI Event Subscribers (for monitoring)"""
    return len(_ai_subscribers)
