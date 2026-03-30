"""
Unified dogma response handler.

Shared between WebSocket and REST paths to eliminate dual-path divergence.
Both paths call process_dogma_response() which handles:
1. Calling game_manager.perform_action()
2. Refreshing game_state from authoritative game object
3. Broadcasting follow-up interactions or game_state_updated
"""

import json
from datetime import datetime

from logging_config import get_logger


class _DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

logger = get_logger(__name__)


async def process_dogma_response(
    game_manager,
    game_id: str,
    action_data: dict,
    broadcast_game_update,
    connection_manager=None,
) -> dict:
    """Process a dogma response and broadcast results.

    Args:
        game_manager: AsyncGameManager instance
        game_id: Game ID
        action_data: Dict with action_type, player_id, selected_cards, etc.
        broadcast_game_update: Async function to broadcast game updates

    Returns:
        Result dict from perform_action, with refreshed game_state
    """
    # Verify the responding player is the intended recipient
    player_id = action_data.get("player_id")
    game = game_manager.get_game(game_id)
    if not game:
        return {"success": False, "error": "Game not found"}

    if game.state.pending_dogma_action:
        target = getattr(game.state.pending_dogma_action, "target_player_id", None)
        if target and player_id and target != player_id:
            logger.warning(
                f"Player {player_id[:8]} tried to respond but target is {target[:8]}"
            )
            return {"success": False, "error": "Not your turn to respond"}

    # Log to activity timeline
    try:
        from logging_config import EventType, activity_logger
        activity_logger.log_game_event(
            event_type=EventType.DOGMA_RESPONSE_RECEIVED,
            game_id=game_id,
            player_id=player_id,
            data={
                "selected_cards": action_data.get("selected_cards") or [],
                "decline": bool(action_data.get("decline", False)),
                "chosen_option": action_data.get("chosen_option"),
            },
            message="Dogma response received",
        )
    except Exception:
        pass

    action_data["action_type"] = "dogma_response"
    # Remove None transaction_id — perform_action validates it strictly
    # and will extract it from the pending action context instead
    if action_data.get("transaction_id") is None:
        action_data.pop("transaction_id", None)
    result = await game_manager.perform_action(game_id, action_data)

    if not result.get("success"):
        return result

    # Single post-action refresh from authoritative game object.
    # The result's game_state may be stale if post-processing
    # (special achievements, turn advancement) modified the game
    # after _handle_dogma_v2_response built its return value.
    fresh_game = game  # fallback if refresh fails
    try:
        fresh_game = game_manager.get_game(game_id)
        if fresh_game:
            result["game_state"] = fresh_game.to_dict()
        else:
            logger.error(f"Game {game_id} not found when refreshing state")
            result["success"] = False
            result["error"] = "Game not found"
            result.pop("game_state", None)
            return result
    except (AttributeError, ValueError, TypeError) as e:
        # State refresh failed — result may contain stale game_state.
        logger.warning(
            f"State refresh failed for game {game_id}, broadcasting stale state: {e}",
        )

    has_followup = "interaction_request" in result

    # If another interaction is needed, broadcast it
    if has_followup:
        try:
            await _broadcast_followup_interaction(
                fresh_game, game_id, result, broadcast_game_update, connection_manager
            )
        except Exception as e:
            logger.error(
                f"Failed to broadcast follow-up interaction: {e}",
                exc_info=True,
            )
            result["broadcast_failed"] = True

    # Always broadcast game_state_updated when dogma completes (no pending interaction).
    if not has_followup:
        game_state = result.get("game_state")
        if game_state:
            await broadcast_game_update(
                game_id=game_id,
                message_type="game_state_updated",
                data={"game_state": game_state},
            )

    return result


async def _broadcast_followup_interaction(
    game, game_id: str, result: dict, broadcast_game_update, connection_manager=None
):
    """Broadcast a follow-up interaction request to the target player.

    Args:
        game: Game object (already fetched, avoids redundant lookup)
        connection_manager: Optional ConnectionManager for personal WS messages
    """
    interaction_request = result.get("interaction_request", {})
    interaction_type = result.get("interaction_type", "unknown")

    # Normalize interaction_request to dict
    if hasattr(interaction_request, "to_dict"):
        interaction_payload = interaction_request.to_dict()
    elif isinstance(interaction_request, dict):
        interaction_payload = interaction_request
    else:
        interaction_payload = {}

    target_player_id = interaction_payload.get("player_id")
    interaction_data = interaction_payload.get("data", {})

    # Get activating player from pending action (game already fetched)
    activating_player_id = None
    if game and game.state.pending_dogma_action:
        activating_player_id = game.state.pending_dogma_action.original_player_id

    dogma_message = json.dumps(
        {
            "type": "dogma_interaction",
            "data": {
                "interaction_type": interaction_type,
                "transaction_id": result.get("transaction_id"),
                "interaction": {
                    "player_id": target_player_id,
                    "message": interaction_data.get("message")
                    or interaction_payload.get("message", "Interaction required"),
                    "card_name": interaction_payload.get("card_name"),
                    "data": interaction_data,
                },
                "activating_player_id": activating_player_id,
                "game_state": result.get("game_state"),
            },
        },
        cls=_DateTimeEncoder,
    )

    # Send to target player via WebSocket
    if target_player_id and connection_manager:
        await connection_manager.send_personal_message(
            dogma_message, target_player_id
        )

    # Also broadcast via event bus for AI players
    await broadcast_game_update(
        game_id=game_id,
        message_type="dogma_interaction",
        data={"interaction": interaction_payload, "game_state": result.get("game_state")},
    )
