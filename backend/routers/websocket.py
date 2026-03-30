"""WebSocket endpoint for Innovation game server.

Handles real-time game communication with authentication.
"""

import asyncio
import contextlib
import json
import time
from typing import TYPE_CHECKING, Optional

from auth import auth_manager
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from logging_config import EventType, activity_logger, get_logger
from services.broadcast_service import get_broadcast_service
from services.dogma_response_handler import process_dogma_response
from services.rate_limiter import RateLimiter
from services.websocket_handler import WebSocketHandler
from starlette.websockets import WebSocketState


def safe_get(obj, attr, default=None):
    """Safely get attribute from Pydantic object or dictionary."""
    if hasattr(obj, attr):  # Pydantic object
        return getattr(obj, attr, default)
    elif isinstance(obj, dict):  # Dictionary
        return obj.get(attr, default)
    else:
        return default


if TYPE_CHECKING:
    from async_game_manager import AsyncGameManager
    from services.connection_manager import ConnectionManager

logger = get_logger(__name__)

# Router instance
router = APIRouter()

# Dependencies injected from main.py
game_manager: Optional["AsyncGameManager"] = None
connection_manager: Optional["ConnectionManager"] = None
event_bus = None
websocket_handler: WebSocketHandler | None = None

# Create global rate limiter instance
rate_limiter = RateLimiter(max_messages=60, window_seconds=60)  # 60 messages per minute


def set_dependencies(gm, cm, eb=None):
    """Set dependencies injected from main.py."""
    global game_manager, connection_manager, event_bus, websocket_handler
    game_manager = gm
    connection_manager = cm
    event_bus = eb  # Kept for backward compatibility

    # Initialize WebSocket handler
    websocket_handler = WebSocketHandler(game_manager, connection_manager)


async def broadcast_game_update(game_id: str, message_type: str, data: dict):
    """
    Broadcast game update to all players via BroadcastService.

    This function now delegates to the centralized BroadcastService which handles
    the dual-channel architecture (WebSocket for humans, Event Bus for AI).

    Args:
        game_id: Game identifier
        message_type: Message type (e.g., "game_state_updated", "action_performed")
        data: Message data including game_state

    Architecture Note:
        Uses the hybrid broadcast pattern via BroadcastService:
        - WebSocket channel: Human players (external, browser-based)
        - Event Bus channel: AI players (internal, in-process)
    """
    broadcast_service = get_broadcast_service()
    await broadcast_service.broadcast_game_update(game_id, message_type, data)


@router.websocket("/ws/{game_id}/{player_id}")
async def websocket_endpoint(
    websocket: WebSocket, game_id: str, player_id: str, token: str = Query(...)
):
    """Handle WebSocket connections for real-time game communication.

    Requires JWT token for authentication.
    """
    # Ensure dependencies are injected
    if game_manager is None or connection_manager is None:
        logger.error(
            "Dependencies not injected - game_manager or connection_manager is None"
        )
        await websocket.close(code=4003, reason="Server not ready")
        return

    # Verify the token before accepting connection
    token_data = auth_manager.verify_game_token(token, game_id, player_id)
    if not token_data:
        logger.warning(
            f"WebSocket authentication failed for player {player_id} in game {game_id}"
        )
        await websocket.close(code=4001, reason="Authentication failed")
        return

    # Token is valid, accept the connection
    await connection_manager.connect(websocket, player_id, game_id)

    # Log WebSocket connection
    activity_logger.log_websocket_event("connected", player_id, game_id)

    # Ensure AI Event Subscribers are active when human player connects
    try:
        game = game_manager.get_game(game_id)
        if game:
            for player in game.players:
                if player.is_ai:
                    try:
                        from services.ai_event_subscriber import (
                            create_ai_event_subscriber,
                        )
                        from services.ai_service import ai_service

                        # Check if AI agent exists
                        if not ai_service.get_agent(player.id):
                            difficulty = getattr(player, "ai_difficulty", "beginner")
                            ai_service.create_agent(
                                player_id=player.id, difficulty=difficulty
                            )
                            logger.info(
                                f"Recreated AI agent for {player.name} "
                                f"(difficulty={difficulty}) on player reconnection"
                            )

                        # Reconnect AI Event Subscriber (if event bus is available)
                        if event_bus:
                            await create_ai_event_subscriber(
                                game_id, player.id, event_bus, game_manager
                            )
                            logger.info(
                                f"Reconnected AI Event Subscriber for {player.name} on player reconnection"
                            )
                    except Exception as e:
                        logger.error(
                            f"Failed to reconnect AI player {player.name}: {e}"
                        )
    except Exception as e:
        logger.error(f"Error reconnecting AI players: {e}")

    # Send game state on reconnect
    try:
        game = game_manager.get_game(game_id)
        if game:
            # First send game state to everyone
            await websocket.send_json(
                {"type": "game_state_update", "game_state": game.to_dict()}
            )

            # If there's a pending player interaction for this player, send the proper message
            # This mimics what happens during normal dogma execution
            if (
                game.state.pending_dogma_action
                and game.state.pending_dogma_action.target_player_id == player_id
                and game.state.pending_dogma_action.action_type
                == "dogma_v2_interaction"
            ):
                # Format the message exactly like the normal dogma flow does
                interaction_data = {
                    "type": "player_interaction",
                    "target_player_id": player_id,
                    "interaction_data": {
                        "type": "player_interaction",
                        "transaction_id": game.state.pending_dogma_action.context.get(
                            "transaction_id"
                        ),
                        "target_player_id": player_id,
                        "interaction_data": {
                            "card_name": game.state.pending_dogma_action.card_name,
                            "data": game.state.pending_dogma_action.context,
                        },
                    },
                }
                await websocket.send_json(interaction_data)
                logger.info(
                    f"Sent player_interaction for pending {game.state.pending_dogma_action.card_name}"
                )
    except Exception as e:
        logger.error(f"Error sending game state on reconnect: {e}")

    # Create heartbeat task with better tracking and cleanup
    heartbeat_task = None

    async def heartbeat():
        """Send periodic heartbeat to keep connection alive."""
        try:
            while True:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(
                        {"type": "heartbeat", "timestamp": time.time()}
                    )
                else:
                    logger.debug(
                        f"WebSocket disconnected, stopping heartbeat for {player_id}"
                    )
                    break  # Stop if disconnected
        except asyncio.CancelledError:
            logger.debug(f"Heartbeat task cancelled for player {player_id}")
            raise  # Re-raise to properly mark task as cancelled
        except Exception as e:
            logger.error(f"Heartbeat error for player {player_id}: {e}")
            # Don't continue on unexpected errors
            raise
        finally:
            logger.debug(f"Heartbeat task cleanup for {player_id}")

    try:
        heartbeat_task = asyncio.create_task(heartbeat())
        connection_manager.register_heartbeat_task(player_id, heartbeat_task)
    except Exception as e:
        logger.error(f"Failed to create heartbeat task for {player_id}: {e}")
        # Continue without heartbeat rather than failing the connection
        heartbeat_task = None

    try:
        while True:
            data = await websocket.receive_text()

            # Apply rate limiting
            if not rate_limiter.is_allowed(player_id):
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Rate limit exceeded. Please slow down.",
                        "code": "RATE_LIMITED",
                    }
                )
                logger.warning(f"Rate limit exceeded for player {player_id}")
                continue

            # Handle incoming WebSocket messages
            message = json.loads(data)

            if message["type"] == "ping":
                await connection_manager.send_personal_message(
                    json.dumps({"type": "pong", "timestamp": time.time()}), player_id
                )
                connection_manager.track_heartbeat(
                    player_id
                )  # Track that client is alive
            elif message["type"] == "pong":
                # Client responded to heartbeat, connection is alive
                connection_manager.track_heartbeat(player_id)
            elif message["type"] == "game_action":
                # Process game action
                result = await game_manager.perform_action(
                    game_id, {"player_id": player_id, **message["data"]}
                )

                # Check for unified interaction
                if "interaction_request" in result:
                    interaction_request = result["interaction_request"]

                    # Validate interaction request format
                    if not await websocket_handler.validate_interaction_request(
                        interaction_request
                    ):
                        logger.error(
                            f"Received interaction_request in unexpected format. "
                            f"Type: {type(interaction_request)}, "
                            f"Keys: {list(interaction_request.keys()) if isinstance(interaction_request, dict) else 'N/A'}, "
                            f"Request type field: {interaction_request.get('type') if isinstance(interaction_request, dict) else 'N/A'}"
                        )
                        continue

                    # Create enhanced interaction message
                    final_message = await websocket_handler.create_interaction_message(
                        interaction_request, result, game_id
                    )

                    # Broadcast interaction message
                    await websocket_handler.broadcast_interaction_message(
                        final_message, game_id
                    )

                    # Log activity event for interaction required (for UI activity panel)
                    with contextlib.suppress(Exception):
                        activity_logger.log_game_event(
                            event_type=EventType.DOGMA_INTERACTION_REQUIRED,
                            game_id=game_id,
                            player_id=safe_get(interaction_request, "player_id"),
                            data={
                                "interaction_type": final_message["data"][
                                    "interaction_type"
                                ],
                                "card_name": result.get("card_name"),
                                "transaction_id": result.get("transaction_id"),
                            },
                        )
                else:
                    # Send full legacy event to initiating player (frontend expects 'action_performed')
                    await connection_manager.send_personal_message(
                        json.dumps({"type": "action_performed", "result": result}),
                        player_id,
                    )

                    # For other players: avoid surfacing failures as toasts.
                    # - On failure: send only a game_state update (no action_performed error)
                    # - On success: broadcast a sanitized action_performed
                    if not result.get("success", False):
                        await broadcast_game_update(
                            game_id=game_id,
                            message_type="game_state_updated",
                            data={"game_state": result.get("game_state")},
                        )
                    else:
                        sanitized = {
                            "success": True,
                            "game_state": result.get("game_state"),
                        }
                        await broadcast_game_update(
                            game_id=game_id,
                            message_type="action_performed",
                            data={"result": sanitized},
                        )
            elif message["type"] == "setup_selection":
                # Handle setup card selection
                # Support both card_id (preferred) and card_name (backward compat)
                card_identifier = message["data"].get("card_id") or message["data"].get(
                    "card_name"
                )
                result = await game_manager.make_setup_selection(
                    game_id, player_id, card_identifier
                )
                await broadcast_game_update(
                    game_id=game_id,
                    message_type="setup_selection_made",
                    data={"result": result},
                )
            elif message["type"] == "dogma_response":
                # Handle dogma v2 interaction response via WebSocket
                # Uses shared handler (same as REST path) to avoid dual-path bugs
                logger.debug(f"Received dogma_response message: {message}")

                # VALIDATION: Validate incoming dogma_response using Pydantic models
                try:
                    (
                        is_valid,
                        validated_response,
                        validation_error,
                    ) = websocket_handler.validate_dogma_response(message)
                    if not is_valid:
                        await websocket_handler.send_validation_error(
                            websocket,
                            f"Invalid dogma_response: {validation_error}",
                            "DOGMA_RESPONSE_INVALID",
                        )
                        # Broadcast fresh state so other players aren't left hanging
                        game = game_manager.get_game(game_id)
                        if game:
                            await broadcast_game_update(
                                game_id=game_id,
                                message_type="game_state_updated",
                                data={"game_state": game.to_dict()},
                            )
                        logger.warning(
                            f"Rejected invalid dogma_response from {player_id}: {validation_error}"
                        )
                        continue
                    selected_cards = validated_response.selected_cards
                    decline = validated_response.cancelled
                    chosen_option = validated_response.chosen_option
                    transaction_id = validated_response.interaction_id
                except Exception as e:
                    logger.warning(f"Validation failed, using original data: {e}")
                    selected_cards = message.get("selected_cards")
                    decline = message.get("decline", False)
                    chosen_option = message.get("chosen_option")
                    transaction_id = message.get("transaction_id")

                action_data = {
                    "player_id": player_id,
                    "selected_cards": selected_cards,
                    "selected_achievements": message.get("selected_achievements"),
                    "card_id": message.get("card_id"),
                    "decline": decline,
                    "chosen_option": chosen_option,
                    "selected_color": (
                        validated_response.selected_color
                        if validated_response
                        else message.get("selected_color")
                    ),
                    "transaction_id": transaction_id,
                }

                result = await process_dogma_response(
                    game_manager, game_id, action_data, broadcast_game_update,
                    connection_manager=connection_manager,
                )

                # Send completion or error to the submitting client
                if result.get("success"):
                    await connection_manager.send_personal_message(
                        json.dumps({
                            "type": "dogma_response_processed",
                            "result": result,
                        }),
                        player_id,
                    )
                else:
                    await connection_manager.send_personal_message(
                        json.dumps({
                            "type": "error",
                            "message": result.get("error", "Dogma response failed"),
                        }),
                        player_id,
                    )
            elif message["type"] == "sync_request":
                # Handle reconnection sync request
                game = game_manager.get_game(game_id)
                if game:
                    await connection_manager.send_personal_message(
                        json.dumps(
                            {
                                "type": "connection_restored",
                                "game_state": game.to_dict(),
                            }
                        ),
                        player_id,
                    )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for player {player_id}")
    except Exception as e:
        logger.error(f"WebSocket error for player {player_id}: {e}")
        activity_logger.log_websocket_event("error", player_id, game_id, error=str(e))
    finally:
        # CRITICAL: Ensure cleanup happens in all cases to prevent memory leaks
        cleanup_success = True

        # 1. Cancel and await heartbeat task with timeout
        if heartbeat_task:
            try:
                if not heartbeat_task.done():
                    heartbeat_task.cancel()
                    # Use wait_for to prevent hanging on task cleanup
                    await asyncio.wait_for(heartbeat_task, timeout=1.0)
            except TimeoutError:
                logger.warning(f"Heartbeat task cleanup timeout for {player_id}")
                cleanup_success = False
            except asyncio.CancelledError:
                pass  # Expected when task is cancelled
            except Exception as e:
                logger.error(
                    f"Error during heartbeat task cleanup for {player_id}: {e}"
                )
                cleanup_success = False
            finally:
                # Ensure task is removed from connection manager even if cleanup failed
                if player_id in connection_manager.connection_tasks:
                    del connection_manager.connection_tasks[player_id]

        # 2. Clean up rate limiter data
        try:
            rate_limiter.cleanup(player_id)
        except Exception as e:
            logger.error(f"Error during rate limiter cleanup for {player_id}: {e}")

        # 3. Disconnect and clean up using bounded disconnect
        try:
            connection_manager.disconnect(player_id, game_id)
        except Exception as e:
            logger.error(
                f"Error during connection manager disconnect for {player_id}: {e}"
            )
            cleanup_success = False

        # 4. Log disconnection (but don't fail if logging fails)
        try:
            activity_logger.log_websocket_event("disconnected", player_id, game_id)
        except Exception as e:
            logger.error(f"Failed to log disconnection event for {player_id}: {e}")

        # 5. Notify other players that someone disconnected (best effort)
        try:
            await broadcast_game_update(
                game_id=game_id,
                message_type="player_disconnected",
                data={"player_id": player_id},
            )
        except Exception as e:
            # Log broadcast failures but don't let them prevent disconnect cleanup
            logger.warning(
                f"Failed to broadcast disconnect notification for {player_id}: {e}"
            )

        if not cleanup_success:
            logger.warning(f"Cleanup for {player_id} completed with some errors")
