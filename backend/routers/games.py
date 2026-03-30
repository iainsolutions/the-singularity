"""
Game-related API endpoints for Innovation game server.
Handles game creation, joining, actions, and WebSocket connections.
"""

import json
import uuid
from typing import Any

from action_primitives.utils import (
    INTERACTION_DATA_FIELD,
    PLAYER_ID_FIELD,
    TARGET_PLAYER_FIELDS,
)


def safe_get(obj, attr, default=None):
    """Safely get attribute from Pydantic object or dictionary."""
    if hasattr(obj, attr):  # Pydantic object
        return getattr(obj, attr, default)
    elif isinstance(obj, dict):  # Dictionary
        return obj.get(attr, default)
    else:
        return default


from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.achievement_formatter import format_achievements_for_display
from async_game_manager import AsyncGameManager
from auth import auth_manager
from logging_config import activity_logger, get_logger
from models.game import Game
from schemas import (
    ActionRequest,
    ActionResponse,
    CreateGameRequest,
    CreateGameResponse,
    DogmaResponseRequest,
    JoinGameRequest,
    JoinGameResponse,
    StartGameResponse,
)
from services.broadcast_service import get_broadcast_service
from services.dogma_response_handler import process_dogma_response

logger = get_logger(__name__)

# Router instance
router = APIRouter(prefix="/api/v1")

# Import game manager - will be set by main.py
game_manager: AsyncGameManager | None = None


def set_dependencies(gm: AsyncGameManager):
    """Set dependencies injected from main.py"""
    global game_manager
    game_manager = gm


def _get_connection_manager():
    """Get ConnectionManager from BroadcastService.

    This provides access to the ConnectionManager without storing it as a global.
    The ConnectionManager is managed by BroadcastService.
    """
    return get_broadcast_service().connection_manager


def _get_event_bus():
    """Get Event Bus from BroadcastService.

    This provides access to the Event Bus without storing it as a global.
    The Event Bus is managed by BroadcastService.
    """
    return get_broadcast_service().event_bus


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


@router.post("/games", response_model=CreateGameResponse)
async def create_game(request: CreateGameRequest = CreateGameRequest()):
    """Create a new game"""
    result = await game_manager.create_game(
        request.created_by, enabled_expansions=request.enabled_expansions
    )

    # If a creator was provided, return full response with player_id and game_state
    if request.created_by and "player_id" in result:
        # Generate JWT token for the player
        from auth import auth_manager

        token = auth_manager.create_game_token(
            result["game_id"], result["player_id"], request.created_by
        )

        return CreateGameResponse(
            game_id=result["game_id"],
            player_id=result["player_id"],
            game_state=result.get("game_state"),
            token=token,
        )

    # Otherwise just return game_id
    return CreateGameResponse(game_id=result["game_id"])


@router.get("/games")
async def list_games():
    """List all active games"""
    return game_manager.list_games()


@router.get("/games/{game_id}")
async def get_game(game_id: str):
    """Get game state"""
    game = game_manager.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Use async_game_manager's formatting method for consistent state_changes formatting
    # This ensures REST API and WebSocket broadcasts both send formatted data
    return game_manager._format_game_state_for_frontend(game.to_dict())


@router.get("/games/{game_id}/safeguards")
async def get_safeguards(game_id: str):
    """
    Get all active Safeguards for a game (Unseen expansion).

    Returns:
        Dictionary mapping achievement_id to list of player IDs who Safeguard it.
        Example: {"age_4": ["player1", "player2"], "age_7": ["player1"]}
    """
    game = game_manager.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Check if Unseen expansion is enabled
    if not hasattr(game, "expansion_config") or not game.expansion_config.is_enabled("unseen"):
        return {"safeguards": {}}

    # Get Safeguard data from tracker
    try:
        from game_logic.unseen.safeguard_tracker import SafeguardTracker
        tracker = SafeguardTracker(game)
        tracker.rebuild_all_safeguards()  # Ensure up-to-date
        safeguards = tracker.get_safeguarded_achievements()

        return {"safeguards": safeguards}
    except Exception as e:
        logger.error(f"Error fetching Safeguards for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch Safeguards: {str(e)}")


@router.get("/games/{game_id}/safe/limit")
async def get_safe_limit(game_id: str, player_id: str = Query(..., description="ID of the player")):
    """
    Get Safe limit for a player (Unseen expansion).

    Returns:
        {
            "limit": 5,  # Current Safe limit based on splay state
            "count": 3,  # Current number of cards in Safe
            "can_add": true  # Whether player can add more cards
        }
    """
    game = game_manager.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    player = game.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Check if Unseen expansion is enabled
    if not hasattr(game, "expansion_config") or not game.expansion_config.is_enabled("unseen"):
        return {
            "limit": 0,
            "count": 0,
            "can_add": False,
            "message": "Unseen expansion not enabled"
        }

    # Get Safe data
    try:
        limit = player.get_safe_limit()
        count = player.safe.get_card_count() if player.safe else 0
        can_add = player.can_add_to_safe()

        return {
            "limit": limit,
            "count": count,
            "can_add": can_add
        }
    except Exception as e:
        logger.error(f"Error fetching Safe limit for player {player_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch Safe limit: {str(e)}")


@router.post("/games/{game_id}/players/{player_id}/safe/achieve")
async def achieve_from_safe(game_id: str, player_id: str, secret_index: int = Query(..., description="Index of secret in Safe (0-based)")):
    """
    Achieve a secret card from the player's Safe (Unseen expansion).

    Args:
        game_id: ID of the game
        player_id: ID of the player
        secret_index: Index of secret in Safe to achieve (0-based)

    Returns:
        {
            "success": true,
            "achieved_card": {...},  # The achieved card details (age-only for privacy)
            "achievement_age": 5,
            "game_state": {...}
        }
    """
    game = game_manager.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    player = game.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Check if Unseen expansion is enabled
    if not hasattr(game, "expansion_config") or not game.expansion_config.is_enabled("unseen"):
        raise HTTPException(status_code=400, detail="Unseen expansion not enabled")

    # Check if player has a Safe
    if not player.safe:
        raise HTTPException(status_code=400, detail="Player has no Safe")

    # Validate secret_index
    if secret_index < 0 or secret_index >= player.safe.get_card_count():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid secret index {secret_index} (Safe has {player.safe.get_card_count()} cards)"
        )

    try:
        # Get the secret card (for logging and response)
        secret_card = player.safe.get_card_at_index(secret_index)
        if not secret_card:
            raise HTTPException(status_code=400, detail=f"No card at index {secret_index}")

        # Check if achievement is available for this age
        achievement_age = secret_card.age
        if achievement_age not in game.deck_manager.achievement_cards or len(game.deck_manager.achievement_cards[achievement_age]) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"No achievements available for age {achievement_age}"
            )

        # Check if player meets achievement requirements
        if player.score < player.required_score_for_achievement(achievement_age):
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient score to achieve age {achievement_age} (need {player.required_score_for_achievement(achievement_age)}, have {player.score})"
            )

        if player.board.get_highest_age() < achievement_age:
            raise HTTPException(
                status_code=400,
                detail=f"No top card with age >= {achievement_age}"
            )

        # Check Safeguard protection
        from game_logic.unseen.safeguard_tracker import SafeguardTracker
        tracker = SafeguardTracker(game)
        tracker.rebuild_all_safeguards()

        # Get the specific achievement card
        achievement_card = game.deck_manager.achievement_cards[achievement_age][0]
        safeguarding_players = tracker.get_safeguarding_players(achievement_card.card_id)

        if safeguarding_players and player_id not in safeguarding_players:
            safeguarding_names = [game.get_player_by_id(pid).name for pid in safeguarding_players if game.get_player_by_id(pid)]
            raise HTTPException(
                status_code=409,
                detail=f"Achievement age {achievement_age} is Safeguarded by: {', '.join(safeguarding_names)}"
            )

        # Remove secret from Safe
        removed_card = player.safe.remove_card(secret_index)

        # Remove achievement from available pool
        claimed_achievement = game.deck_manager.achievement_cards[achievement_age].pop(0)

        # Add achievement to player
        player.achievements.append(claimed_achievement)

        # Log achievement
        activity_logger.info(
            f"{player.name} achieved secret card (age {achievement_age}) from Safe"
        )

        # Check victory condition
        if len(player.achievements) >= 6:
            from models.game import GamePhase
            game.winner = player
            game.phase = GamePhase.FINISHED
            activity_logger.info(f"🏆 {player.name} wins by achieving 6+ achievements!")

        # Broadcast game state update
        broadcast_service = get_broadcast_service()
        if broadcast_service:
            await broadcast_service.broadcast_game_state(game_id, game.to_dict())

        # Return success response with privacy-filtered data
        return {
            "success": True,
            "achievement_age": achievement_age,
            "achieved_card": {
                "age": removed_card.age,
                "expansion": removed_card.expansion,
                # Card identity hidden for security
            },
            "game_state": game.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error achieving from Safe for player {player_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to achieve from Safe: {str(e)}")


@router.get("/games/{game_id}/achievements")
async def get_achievements(
    game_id: str, player_id: str = Query(..., description="ID of the viewing player")
):
    """
    Get formatted achievement display data for a player.

    This endpoint centralizes all achievement display logic in the backend,
    implementing the "dumb frontend" architectural principle. The frontend
    should just render what the backend tells it to display.

    Returns:
        {
            "regular": [...],  # Ages 1-10 with display states
            "special": [...],  # 6 special achievements with display states
            "ui_hints": {...}  # Interaction hints
        }
    """
    game = game_manager.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Validate player exists in game
    player = game.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found in game")

    # Format achievements for display
    achievement_data = format_achievements_for_display(game, player_id)

    return achievement_data


@router.post("/games/{game_id}/join", response_model=JoinGameResponse)
async def join_game(game_id: str, request: JoinGameRequest):
    """Join a game"""
    player_name = request.name or f"Player_{uuid.uuid4().hex[:6]}"
    result = await game_manager.join_game(game_id, player_name)
    if not result["success"]:
        status = 404 if result["error"] == "Game not found" else 400
        raise HTTPException(status_code=status, detail=result["error"])

    # Generate JWT token for WebSocket authentication
    token = auth_manager.create_game_token(
        game_id=game_id, player_id=result["player_id"], player_name=player_name
    )

    # Broadcast player joined event to all connected players
    await broadcast_game_update(
        game_id=game_id,
        message_type="player_joined",
        data={
            "player_id": result["player_id"],
            "player_name": player_name,
            "game_state": result["game_state"],
        },
    )

    return JoinGameResponse(
        player_id=result["player_id"],
        game_state=result["game_state"],
        token=token,
    )


@router.post("/games/{game_id}/start", response_model=StartGameResponse)
async def start_game(game_id: str):
    """Start the game"""
    result = await game_manager.start_game(game_id)
    if not result["success"]:
        status = 404 if result["error"] == "Game not found" else 400
        raise HTTPException(status_code=status, detail=result["error"])

    # Broadcast game start to all players
    await broadcast_game_update(
        game_id=game_id,
        message_type="game_started",
        data={"game_state": result["game_state"]},
    )

    # AI Turn Orchestrator will automatically detect and execute AI turns
    # No need to manually trigger here - maintains player-agnostic design

    return StartGameResponse(game_state=result["game_state"], success=True)


class SetupSelectionRequest(BaseModel):
    player_id: str
    card_name: str | None = None  # Backward compat
    card_id: str | None = None  # Preferred


@router.post("/games/{game_id}/setup-selection")
async def make_setup_selection(game_id: str, request: SetupSelectionRequest):
    """Make setup card selection (choose which card to meld)"""
    # Support both card_id (preferred) and card_name (backward compat)
    card_identifier = request.card_id or request.card_name
    result = await game_manager.make_setup_selection(
        game_id, request.player_id, card_identifier
    )
    if not result["success"]:
        status = 404 if result["error"] == "Game not found" else 400
        raise HTTPException(status_code=status, detail=result["error"])

    # Broadcast the updated game state to all players
    await broadcast_game_update(
        game_id=game_id,
        message_type="setup_selection_made",
        data={"game_state": result["game_state"]},
    )

    # If setup is complete and phase transitioned to PLAYING, broadcast that too
    game_state = result["game_state"]
    if game_state.get("phase") == "PLAYING":
        await broadcast_game_update(
            game_id=game_id,
            message_type="game_state_updated",
            data={"game_state": game_state},
        )

    return {"success": True, "game_state": result["game_state"]}


@router.post("/games/{game_id}/leave")
async def leave_game(game_id: str, player_id: str = Query(...)):
    """Leave a game"""
    result = await game_manager.leave_game(game_id, player_id)
    if not result["success"]:
        status = 404 if result["error"] == "Game not found" else 400
        raise HTTPException(status_code=status, detail=result["error"])

    # Broadcast the updated game state if game still exists
    if "game_state" in result:
        await broadcast_game_update(
            game_id=game_id,
            message_type="player_left",
            data={"game_state": result["game_state"]},
        )

    return {"success": True, "message": result.get("message", "Left game successfully")}


@router.post(
    "/games/{game_id}/action",
    response_model=ActionResponse,
    response_model_exclude_none=True,
)
async def perform_action(game_id: str, request: ActionRequest):
    """Perform a game action"""
    result = await game_manager.perform_action(game_id, request.model_dump())
    if not result["success"]:
        if result["error"] == "Game not found":
            raise HTTPException(status_code=404, detail=result["error"])
        elif "interaction is pending" in result["error"].lower():
            raise HTTPException(status_code=409, detail=result["error"])
        game = game_manager.get_game(game_id)
        game_state = Game.model_validate(game.to_dict()) if game else None
        return ActionResponse(
            success=False, error=result["error"], game_state=game_state
        )

    # Ensure game_state is always present
    game = game_manager.get_game(game_id)
    if "game_state" not in result and game:
        result["game_state"] = game.to_dict()

    # Check for demand and sharing interactions that need to be sent to specific players
    interactions_sent = False

    # Handle unified interaction targeting (Dogma v2 system)
    if "interaction_request" in result and "interaction_type" in result:
        interaction_request = result["interaction_request"]
        interaction_type = result["interaction_type"]
        target_player_id = safe_get(interaction_request, PLAYER_ID_FIELD)
        if not target_player_id:
            interaction_data = safe_get(interaction_request, INTERACTION_DATA_FIELD, {})
            for field in TARGET_PLAYER_FIELDS:
                target_player_id = safe_get(interaction_data, field)
                if target_player_id:
                    break

        if not target_player_id:
            logger.error(
                "interaction_request missing player_id",
                extra={
                    "interaction_request": interaction_request,
                    "initiating_player_id": request.player_id,
                },
            )
            raise HTTPException(
                status_code=500,
                detail="Dogma interaction is missing target player information",
            )

        if not game or not game.get_player_by_id(target_player_id):
            logger.error(
                "interaction_request referenced a player outside this game",
                extra={
                    "game_id": game_id,
                    "target_player_id": target_player_id,
                    "initiating_player_id": request.player_id,
                },
            )
            raise HTTPException(
                status_code=403,
                detail="Dogma interaction referenced a player outside this game",
            )

        logger.info(
            f"Sending {interaction_type} interaction to specific player: {target_player_id}"
        )

        # Build unified dogma_interaction message for the frontend
        try:
            from datetime import datetime

            # Custom JSON encoder to handle datetime objects
            class DateTimeEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    return super().default(obj)

            interaction_data = safe_get(interaction_request, "data", {})
            dogma_message = json.dumps(
                {
                    "type": "dogma_interaction",
                    "data": {
                        "interaction_type": interaction_type,
                        "transaction_id": result.get("transaction_id"),
                        "interaction": {
                            "player_id": target_player_id,
                            "message": safe_get(interaction_data, "message")
                            or safe_get(
                                interaction_request, "message", "Interaction required"
                            ),
                            "card_name": safe_get(interaction_request, "card_name"),
                            "data": interaction_data,
                        },
                        # Help UI verify control is with the activator/expected player
                        "activating_player_id": request.player_id,
                        "game_state": result.get("game_state"),
                    },
                },
                cls=DateTimeEncoder,
            )
        except Exception as e:
            logger.warning(
                f"Failed to build dogma_interaction message: {e}; using simplified format"
            )
            dogma_message = json.dumps(
                {
                    "type": "dogma_interaction",
                    "data": {
                        "interaction_type": interaction_type,
                        "interaction": interaction_request,
                        "game_state": result.get("game_state"),
                    },
                },
                cls=DateTimeEncoder,
            )

        # Send targeted message to the specific player
        logger.info(
            f"Sending interaction to {target_player_id}: {dogma_message[:200]}..."
        )
        await _get_connection_manager().send_personal_message(dogma_message, target_player_id)
        # Mirror to activity timeline so it is visible without WS capture
        try:
            from logging_config import EventType, activity_logger

            activity_logger.log_game_event(
                event_type=EventType.DOGMA_INTERACTION_REQUIRED,
                game_id=game_id,
                player_id=target_player_id,
                data={
                    "card_name": result.get("card_name")
                    or (
                        safe_get(interaction_request, "card_name")
                        if isinstance(interaction_request, dict)
                        else None
                    ),
                    "interaction_type": interaction_type,
                    "activating_player_id": request.player_id,
                },
                message="Targeted dogma interaction sent",
            )
        except Exception:
            pass
        logger.info(f"Personal message sent to {target_player_id}")
        interactions_sent = True

    # Handle legacy interaction fields for backward compatibility (if any still exist)
    elif any(k in result for k in ("demand_interaction", "sharing_interaction", "player_interaction")):
        # Legacy interaction keys — these should not appear with the unified dogma_interaction path.
        # Log a warning so we can track if they still fire.
        legacy_key = next(k for k in ("demand_interaction", "sharing_interaction", "player_interaction") if k in result)
        logger.warning(f"Legacy interaction key '{legacy_key}' in result — unified path should handle this")

    if interactions_sent:
        # Send general update to all players (without interaction details)
        result_without_interactions = {
            k: v
            for k, v in result.items()
            if k
            not in [
                "interaction_request",
                "interaction_type",
                "demand_interaction",
                "sharing_interaction",
                "player_interaction",
            ]
        }
        try:
            logger.info(
                f"Broadcasting action_performed (with interactions) for game {game_id}"
            )
            await broadcast_game_update(
                game_id=game_id,
                message_type="action_performed",
                data={"result": result_without_interactions},
            )
        except Exception as e:
            logger.error(
                f"CRITICAL: Failed to broadcast action_performed for game {game_id}",
                extra={
                    "game_id": game_id,
                    "action_type": (
                        request.action_type
                        if hasattr(request, "action_type")
                        else "unknown"
                    ),
                    "player_id": (
                        request.player_id
                        if hasattr(request, "player_id")
                        else "unknown"
                    ),
                    "error": str(e),
                },
                exc_info=True,
            )
            raise  # Re-raise to return error to client
    else:
        # Normal broadcast for non-interaction results
        try:
            logger.info(f"Broadcasting action_performed (normal) for game {game_id}")
            await broadcast_game_update(
                game_id=game_id,
                message_type="action_performed",
                data={"result": result},
            )
        except Exception as e:
            logger.error(
                f"CRITICAL: Failed to broadcast action_performed for game {game_id}",
                extra={
                    "game_id": game_id,
                    "action_type": (
                        request.action_type
                        if hasattr(request, "action_type")
                        else "unknown"
                    ),
                    "player_id": (
                        request.player_id
                        if hasattr(request, "player_id")
                        else "unknown"
                    ),
                    "error": str(e),
                },
                exc_info=True,
            )
            raise  # Re-raise to return error to client

    game_state = Game.model_validate(result.pop("game_state"))

    # Convert card dictionaries to Card objects for ActionResponse
    response_data = {"game_state": game_state, "success": result.get("success", True)}

    # Back-compat: include a simplified pending_interaction in HTTP response for tests/tools
    try:
        if "interaction_request" in result and "interaction_type" in result:
            ir = result.get("interaction_request", {})
            # Provide minimal shape expected by tests
            response_data["pending_interaction"] = {
                "interaction_id": ir.get("id"),
                "target_player_id": ir.get("player_id") or request.player_id,
                "interaction_type": result.get("interaction_type"),
                "message": (ir.get("data", {}) or {}).get("message")
                or ir.get("message"),
                "prompt": (ir.get("data", {}) or {}).get("message")
                or ir.get("message"),
                "timeout": (ir.get("timeout") or 30),
            }
    except Exception:
        pass

    # Map the card fields properly
    if "card_drawn" in result:
        from models.card import Card

        response_data["card_drawn"] = Card.model_validate(result["card_drawn"])
    if "card_melded" in result:
        from models.card import Card

        response_data["card_melded"] = Card.model_validate(result["card_melded"])
    if "action" in result:
        response_data["action"] = result["action"]
    if "results" in result:
        response_data["effects"] = result["results"]
    if "interaction" in result:
        # Don't pass interaction to ActionResponse, it's handled separately
        pass
    if "error" in result:
        response_data["error"] = result["error"]

    return ActionResponse(**response_data)


@router.post(
    "/games/{game_id}/interactions/{interaction_id}",
    response_model=ActionResponse,
    response_model_exclude_none=True,
)
async def respond_to_interaction(game_id: str, interaction_id: str, payload: dict):
    """Compatibility endpoint to respond to a pending interaction by ID.

    Maps simple inputs like {"player_id": ..., "choice": 0} to dogma-response format.
    """
    try:
        # Derive card selection from pending action if a simple choice index is provided
        player_id = payload.get("player_id")
        if not player_id:
            raise HTTPException(status_code=400, detail="player_id is required")

        # Build dogma response payload
        response_payload: dict[str, Any] = {"player_id": player_id}

        # Pass through selected_cards if provided (for API callers using card names)
        if "selected_cards" in payload:
            response_payload["selected_cards"] = payload["selected_cards"]

        # Map "choice" index to the selected card_id, if present
        try:
            from main import game_manager as gm

            game = gm.get_game(game_id)
            if game and game.state.pending_dogma_action:
                interaction_data = (
                    game.state.pending_dogma_action.context.get("interaction_data", {})
                    if hasattr(game.state.pending_dogma_action, "context")
                    else {}
                )
                data = interaction_data.get("data", {})
                eligible = data.get("eligible_cards") or []
                if "choice" in payload and isinstance(payload["choice"], int):
                    idx = payload["choice"]
                    if 0 <= idx < len(eligible):
                        chosen = eligible[idx]
                        card_id = chosen.get("card_id") or chosen.get("name")
                        if card_id:
                            response_payload["card_id"] = card_id
        except Exception:
            pass

        # Use existing dogma-response endpoint to process
        action_data = response_payload
        action_data["action_type"] = "dogma_response"
        result = await game_manager.perform_action(game_id, action_data)
        if not result.get("success"):
            status = 400
            if result.get("error") == "Game not found":
                status = 404
            raise HTTPException(
                status_code=status, detail=result.get("error", "Interaction failed")
            )

        # Ensure game_state exists
        if "game_state" not in result:
            game = game_manager.get_game(game_id)
            if game:
                result["game_state"] = game.to_dict()

        # Build ActionResponse with optional pending_interaction for next step
        game_state = Game.model_validate(result.pop("game_state"))
        response_data = {
            "game_state": game_state,
            "success": result.get("success", True),
        }
        # Include pending_interaction if present in result
        if "interaction_request" in result and "interaction_type" in result:
            ir = result.get("interaction_request", {})
            response_data["pending_interaction"] = {
                "interaction_id": ir.get("id"),
                "target_player_id": ir.get("player_id") or player_id,
                "interaction_type": result.get("interaction_type"),
                "message": (ir.get("data", {}) or {}).get("message")
                or ir.get("message"),
                "prompt": (ir.get("data", {}) or {}).get("message")
                or ir.get("message"),
                "timeout": (ir.get("timeout") or 30),
            }

        return ActionResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process interaction response: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to process interaction response"
        )


@router.post("/games/{game_id}/dogma-response")
async def respond_to_dogma(game_id: str, request: DogmaResponseRequest):
    """Respond to a pending dogma action"""
    logger.debug(f"dogma-response: game={game_id}, player={request.player_id}")

    # Use shared dogma response handler (same as WebSocket path)
    action_data = request.model_dump(mode="python", exclude_unset=False)

    result = await process_dogma_response(
        game_manager, game_id, action_data, broadcast_game_update,
        connection_manager=_get_connection_manager(),
    )

    if not result.get("success"):
        if result.get("error") == "Game not found":
            raise HTTPException(status_code=404, detail=result["error"])
        game = game_manager.get_game(game_id)
        game_state = Game.model_validate(game.to_dict()) if game else None
        return ActionResponse(
            success=False, error=result.get("error"), game_state=game_state
        )

    game_state = Game.model_validate(result.pop("game_state"))

    # Convert card dictionaries to Card objects for ActionResponse
    response_data = {"game_state": game_state, "success": result.get("success", True)}

    # Map the card fields properly
    if "card_drawn" in result:
        from models.card import Card

        response_data["card_drawn"] = Card.model_validate(result["card_drawn"])
    if "card_melded" in result:
        from models.card import Card

        response_data["card_melded"] = Card.model_validate(result["card_melded"])
    if "action" in result:
        response_data["action"] = result["action"]
    if "results" in result:
        response_data["effects"] = result["results"]
    if "interaction" in result:
        # Don't pass interaction to ActionResponse, it's handled separately
        pass
    if "error" in result:
        response_data["error"] = result["error"]

    return ActionResponse(**response_data)


@router.get("/games/{game_id}/activity")
async def get_game_activity(game_id: str, limit: int = Query(100, gt=0, le=1000)):
    """Get activity log for a game"""
    activities = activity_logger.get_game_activity(game_id, limit)
    return {"activities": activities}


@router.get("/players/{player_id}/activity")
async def get_player_activity(player_id: str, limit: int = Query(50, gt=0, le=500)):
    """Get activity log for a player"""
    activities = activity_logger.get_player_activity(player_id, limit)
    return {"activities": activities}


@router.get("/games/{game_id}/dogma-debug")
async def get_dogma_debug_info(game_id: str, transaction_id: str = Query(None)):
    """Get detailed dogma execution debug information"""
    try:
        debug_info = await game_manager.get_dogma_debug_info(game_id, transaction_id)
        return {"debug_info": debug_info}
    except Exception as e:
        logger.error(f"Error retrieving dogma debug info: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve debug information"
        )


@router.get("/games/{game_id}/debug")
async def get_comprehensive_debug(game_id: str):
    """Get comprehensive debug information for a game - unified debug endpoint"""
    try:
        game = game_manager.get_game(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")

        # Get current game state
        game_dict = game.to_dict()
        current_player = game_dict.get("current_player", {})

        # Build comprehensive debug info
        debug_data = {
            "game_id": game_id,
            "game_state": {
                "phase": game_dict.get("phase"),
                "current_player": current_player.get("name")
                if current_player
                else None,
                "current_player_id": current_player.get("id")
                if current_player
                else None,
                "actions_remaining": game_dict.get("actions_remaining"),
                "turn_number": game_dict.get("turn_number"),
            },
            "player_states": {
                player.get("name"): {
                    "hand_size": len(player.get("hand", [])),
                    "score_pile_size": len(player.get("score_pile", [])),
                    "achievements": len(player.get("achievements", [])),
                    "board_colors": [
                        color
                        for color in ["red", "blue", "green", "yellow", "purple"]
                        if player.get("board", {}).get(f"{color}_cards")
                    ],
                }
                for player in game_dict.get("players", [])
            },
            "execution_state": {
                "pending_dogma_action": game_dict.get("state", {}).get(
                    "pending_dogma_action"
                )
                is not None,
                "pending_interaction": game_dict.get("pending_interaction") is not None,
            },
            "recent_actions": [
                {
                    "player": entry.get("player_name"),
                    "action": entry.get("action_type"),
                    "description": entry.get("description")[
                        :100
                    ],  # Truncate long descriptions
                    "turn": entry.get("turn_number"),
                    "state_changes_count": len(entry.get("state_changes", [])),
                }
                for entry in game_dict.get("action_log", [])[-10:]  # Last 10 actions
            ],
        }

        # Add dogma debug info if available
        try:
            dogma_debug = await game_manager.get_dogma_debug_info(game_id)
            debug_data["dogma_metrics"] = dogma_debug.get("consolidated_metrics", {})
        except Exception:
            pass

        return debug_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving comprehensive debug info: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve debug information"
        )


def _parse_ai_interaction_log(lines, game_id: str | None = None) -> list[dict]:
    """Parse AI interaction log with multi-line prompts.

    Log format:
    2025-... | INFO | DECISION REQUEST | game=... | player=... | difficulty=... | actions=...
    PROMPT: <first line of prompt>
    <continuation lines...>
    TOOL: tool_name | INPUT: {...}
    TOKENS: input=..., output=..., cached=... | COST: $... | LATENCY: ...ms
    """
    interactions = []
    current = None
    in_prompt = False
    prompt_lines = []

    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            if in_prompt:
                prompt_lines.append("")  # preserve blank lines in prompt
            continue

        # New interaction header
        if "DECISION REQUEST" in stripped or "INTERACTION REQUEST" in stripped:
            # Finalize previous entry
            if current:
                if prompt_lines:
                    current["prompt"] = "\n".join(prompt_lines)
                interactions.append(current)

            # Parse: timestamp | level | type | game=... | player=... | ...
            parts = stripped.split(" | ")
            timestamp = parts[0] if parts else ""
            req_type = "DECISION" if "DECISION REQUEST" in stripped else "INTERACTION"

            # Extract metadata from key=value pairs
            metadata = {}
            for part in parts[2:]:
                if "=" in part:
                    key, val = part.split("=", 1)
                    metadata[key.strip()] = val.strip()

            current = {
                "timestamp": timestamp,
                "type": req_type,
                "metadata": metadata,
                "prompt": "",
                "tool": "",
                "input": "",
                "stats": "",
            }
            in_prompt = False
            prompt_lines = []
        elif current:
            if stripped.startswith("PROMPT:"):
                in_prompt = True
                prompt_lines = [stripped.replace("PROMPT: ", "", 1)]
            elif stripped.startswith("TOOL:"):
                # End of prompt, save accumulated lines
                in_prompt = False
                if prompt_lines:
                    current["prompt"] = "\n".join(prompt_lines)
                # Parse TOOL line
                if " | INPUT: " in stripped:
                    tool_part, input_part = stripped.split(" | INPUT: ", 1)
                    current["tool"] = tool_part.replace("TOOL: ", "").strip()
                    current["input"] = input_part.strip()
                else:
                    current["tool"] = stripped.replace("TOOL: ", "").strip()
            elif stripped.startswith("TOKENS:"):
                in_prompt = False
                current["stats"] = stripped
            elif in_prompt:
                # Accumulate multi-line prompt content
                prompt_lines.append(stripped)

    # Finalize last entry
    if current:
        if prompt_lines:
            current["prompt"] = "\n".join(prompt_lines)
        interactions.append(current)

    # Filter by game_id
    if game_id:
        interactions = [
            i for i in interactions if i.get("metadata", {}).get("game") == game_id
        ]

    return interactions


@router.get("/ai/notes/{game_id}/{player_id}")
async def get_ai_notes(game_id: str, player_id: str):
    """Get AI notes for a specific game and player"""
    from services.ai_memory import get_memory_store

    try:
        memory_store = get_memory_store()
        notes = await memory_store.get_notes(game_id, player_id)
        return {
            "notes": [n.to_dict() for n in notes],
            "count": len(notes),
            "game_id": game_id,
            "player_id": player_id,
        }
    except Exception as e:
        logger.error(f"Failed to get AI notes: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/ai/interactions")
async def get_ai_interactions(
    limit: int = Query(100, gt=0, le=1000), game_id: str = Query(None)
):
    """Get recent AI interactions from log file"""
    import json
    import os

    from fastapi.responses import Response

    # Check both possible log locations
    log_path = "logs/ai_interactions.log"
    if not os.path.exists(log_path):
        log_path = "backend/logs/ai_interactions.log"

    if not os.path.exists(log_path):
        return Response(
            content=json.dumps({"interactions": [], "message": "No AI interactions yet"}),
            media_type="application/json; charset=utf-8",
        )

    try:
        with open(log_path, encoding="utf-8") as f:
            interactions = _parse_ai_interaction_log(f, game_id)

        interactions.reverse()
        recent = interactions[:limit] if len(interactions) > limit else interactions

        return Response(
            content=json.dumps({
                "interactions": recent,
                "total": len(recent),
                "total_in_log": len(interactions),
                "game_id_filter": game_id,
            }),
            media_type="application/json; charset=utf-8",
        )
    except Exception as e:
        logger.error(f"Failed to read AI interactions log: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/ai/interactions/view")
async def view_ai_interactions_html(
    limit: int = Query(50, gt=0, le=1000), game_id: str = Query(None)
):
    """View AI interactions in HTML format with system prompt popup and notes display"""
    import os
    from html import escape as html_escape

    from fastapi.responses import HTMLResponse

    from services.ai_prompt_builder import AIPromptBuilder

    # Check both possible log locations
    log_path = "logs/ai_interactions.log"
    if not os.path.exists(log_path):
        log_path = "backend/logs/ai_interactions.log"

    if not os.path.exists(log_path):
        return HTMLResponse(content="<html><body><h1>No AI interactions yet</h1></body></html>")

    try:
        with open(log_path, encoding="utf-8") as f:
            interactions = _parse_ai_interaction_log(f, game_id)

        interactions.reverse()
        recent = interactions[:limit] if len(interactions) > limit else interactions

        # Get system prompt for popup
        prompt_builder = AIPromptBuilder("expert")
        # get_cached_system_context returns list of content blocks, extract text
        system_context = prompt_builder.get_cached_system_context()
        system_prompt_text = "\n\n".join(
            block.get("text", "") for block in system_context if isinstance(block, dict)
        )
        system_prompt = html_escape(system_prompt_text)

        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>AI Interactions</title>
<style>
body {{ font-family: system-ui; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
.stats {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }}
.btn {{ background: #4a90e2; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }}
.btn:hover {{ background: #357abd; }}
.btn-secondary {{ background: #6c757d; }}
.btn-secondary:hover {{ background: #5a6268; }}
.interaction {{ background: white; margin-bottom: 15px; border-radius: 8px; overflow: hidden; }}
.header {{ background: #4a90e2; color: white; padding: 12px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }}
.header:hover {{ background: #357abd; }}
.type-DECISION {{ background: #4caf50; }}
.type-INTERACTION {{ background: #ff9800; }}
.content {{ padding: 15px; display: none; }}
.content.show {{ display: block; }}
pre {{ background: #2d2d2d; color: #f8f8f2; padding: 10px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; font-size: 12px; }}
.meta {{ font-size: 12px; opacity: 0.9; }}
.note-saved {{ background: #e3f2fd; color: #1565c0; padding: 4px 8px; border-radius: 4px; font-size: 11px; }}
.notes-section {{ background: #fff3e0; padding: 10px; border-radius: 4px; margin-bottom: 10px; }}
.notes-section h4 {{ margin: 0 0 8px 0; color: #e65100; }}
.modal {{ display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); }}
.modal.show {{ display: flex; align-items: center; justify-content: center; }}
.modal-content {{ background: white; padding: 20px; border-radius: 8px; max-width: 900px; max-height: 80vh; overflow-y: auto; width: 90%; }}
.modal-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }}
.close {{ font-size: 24px; cursor: pointer; }}
</style></head><body>
<h1>AI Interactions</h1>

<!-- System Prompt Modal -->
<div id="sysPromptModal" class="modal" onclick="if(event.target===this)this.classList.remove('show')">
  <div class="modal-content">
    <div class="modal-header">
      <h3>System Prompt (same for all turns)</h3>
      <span class="close" onclick="document.getElementById('sysPromptModal').classList.remove('show')">&times;</span>
    </div>
    <pre>{system_prompt}</pre>
  </div>
</div>

<div class="stats">
  <div><strong>Showing:</strong> {len(recent)} {f'for game {game_id[:8]}...' if game_id else ''} | <strong>Total:</strong> {len(interactions)}</div>
  <button class="btn btn-secondary" onclick="document.getElementById('sysPromptModal').classList.add('show')">View System Prompt</button>
</div>
"""
        for idx, i in enumerate(recent):
            meta = i.get("metadata", {})
            prompt_raw = i.get('prompt', '(none)')
            # Ensure prompt_text is always a string (could be list from old log format)
            prompt_text = prompt_raw if isinstance(prompt_raw, str) else str(prompt_raw)

            # Extract notes section if present in prompt
            notes_html = ""
            if '<my_notes>' in prompt_text:
                import re
                notes_match = re.search(r'<my_notes>(.*?)</my_notes>', prompt_text, re.DOTALL)
                if notes_match:
                    notes_content = notes_match.group(1).strip()
                    notes_html = f'<div class="notes-section"><h4>AI Notes:</h4><pre>{html_escape(notes_content)}</pre></div>'
                    # Remove notes from prompt display (since shown separately)
                    prompt_text = re.sub(r'<my_notes>.*?</my_notes>\n*', '', prompt_text, flags=re.DOTALL)

            # Check if note was saved in this interaction
            tool_input_raw = i.get('input', '')
            tool_input = tool_input_raw if isinstance(tool_input_raw, str) else str(tool_input_raw)
            note_badge = ""
            if '"note":' in tool_input or "'note':" in tool_input:
                note_badge = '<span class="note-saved">Note Saved</span>'

            html += f"""
<div class="interaction">
  <div class="header type-{i['type']}" onclick="document.getElementById('c{idx}').classList.toggle('show')">
    <div>
      <strong>{i['type']}</strong> - {i['timestamp']}
      <div class="meta">Game: {meta.get('game', 'N/A')[:8]}... | {meta.get('difficulty', '')} | {i.get('stats', '')} {note_badge}</div>
    </div>
  </div>
  <div class="content" id="c{idx}">
    {notes_html}
    <p><strong>User Prompt:</strong></p>
    <pre>{html_escape(prompt_text)}</pre>
    <p><strong>Tool:</strong> {html_escape(i.get('tool', ''))}</p>
    <pre>{html_escape(tool_input)}</pre>
  </div>
</div>"""

        html += "</body></html>"
        return HTMLResponse(content=html)

    except Exception as e:
        logger.error(f"Failed to render AI interactions: {e}")
        return HTMLResponse(content=f"<html><body><h1>Error</h1><p>{e}</p></body></html>", status_code=500)


@router.get("/ai/models")
async def get_available_models():
    """Get list of available Claude models from Anthropic API"""
    from services.ai_player_agent import _available_models

    if _available_models is None:
        return {
            "models": [],
            "message": "Models not yet fetched. Server may still be starting up.",
        }

    return {"models": _available_models, "count": len(_available_models)}


@router.get("/games/{game_id}/event-history")
async def get_game_event_history(
    game_id: str,
    limit: int = Query(100, gt=0, le=1000),
    include_duplicates: bool = Query(False),
):
    """Get event bus message history for a specific game

    Args:
        game_id: The game ID to get event history for
        limit: Maximum number of events to return (default: 100)
        include_duplicates: Whether to include duplicate events (default: False)

    Returns:
        Event history including event IDs, sequence numbers, and duplicate detection
    """
    event_bus = _get_event_bus()
    if not event_bus:
        raise HTTPException(status_code=503, detail="Event bus not available")

    try:
        history = event_bus.get_event_history(game_id)

        # Filter out duplicates if requested
        if not include_duplicates:
            history = [event for event in history if not event.duplicate]

        # Apply limit
        limited_history = history[-limit:] if len(history) > limit else history

        # Convert to JSON-serializable format
        serializable_history = []
        for event in limited_history:
            serializable_history.append(
                {
                    "event_id": event.event_id,
                    "sequence_num": event.sequence_num,
                    "source": event.source,
                    "timestamp": event.timestamp,
                    "event_type": event.event_type,
                    "duplicate": event.duplicate,
                    "correlation_id": event.correlation_id,
                    "data_summary": {
                        "keys": list(event.data.keys())
                        if isinstance(event.data, dict)
                        else None,
                        "size": len(str(event.data)) if event.data else 0,
                    },
                }
            )

        # Get current sequence number for this game
        current_seq = event_bus.get_last_sequence_number(game_id)

        return {
            "game_id": game_id,
            "current_sequence_number": current_seq,
            "events": serializable_history,
            "total_shown": len(serializable_history),
            "total_in_history": len(history),
            "duplicates_filtered": not include_duplicates,
        }
    except Exception as e:
        logger.error(f"Error retrieving event history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve event history")


@router.get("/games/{game_id}/duplicate-events")
async def get_duplicate_events(game_id: str, limit: int = Query(50, gt=0, le=500)):
    """Get duplicate events detected for a specific game

    Args:
        game_id: The game ID to check for duplicate events
        limit: Maximum number of duplicates to return (default: 50)

    Returns:
        List of duplicate events with their sources and timestamps
    """
    event_bus = _get_event_bus()
    if not event_bus:
        raise HTTPException(status_code=503, detail="Event bus not available")

    try:
        history = event_bus.get_event_history(game_id)

        # Get only duplicates
        duplicates = [event for event in history if event.duplicate]

        # Apply limit
        limited_duplicates = (
            duplicates[-limit:] if len(duplicates) > limit else duplicates
        )

        # Group duplicates by source to identify patterns
        duplicates_by_source = {}
        for event in duplicates:
            source = event.source
            if source not in duplicates_by_source:
                duplicates_by_source[source] = []
            duplicates_by_source[source].append(
                {
                    "event_id": event.event_id,
                    "sequence_num": event.sequence_num,
                    "event_type": event.event_type,
                    "timestamp": event.timestamp,
                }
            )

        return {
            "game_id": game_id,
            "total_duplicates": len(duplicates),
            "duplicates_shown": len(limited_duplicates),
            "duplicates": limited_duplicates,
            "duplicates_by_source": duplicates_by_source,
            "message": f"Found {len(duplicates)} duplicate events",
        }
    except Exception as e:
        logger.error(f"Error retrieving duplicate events: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve duplicate events"
        )


@router.get("/event-bus/stats")
async def get_event_bus_stats():
    """Get global event bus statistics

    Returns:
        Statistics about event bus usage, deduplication effectiveness, etc.
    """
    event_bus = _get_event_bus()
    if not event_bus:
        raise HTTPException(status_code=503, detail="Event bus not available")

    try:
        total_events = 0
        total_duplicates = 0
        games_with_events = 0

        # Gather statistics from all game histories
        for game_id in list(event_bus._message_history.keys()):
            history = event_bus.get_event_history(game_id)
            if history:
                games_with_events += 1
                total_events += len(history)
                total_duplicates += sum(1 for event in history if event.duplicate)

        dedup_rate = (total_duplicates / total_events * 100) if total_events > 0 else 0

        return {
            "total_events": total_events,
            "total_duplicates": total_duplicates,
            "deduplication_rate": f"{dedup_rate:.2f}%",
            "games_with_events": games_with_events,
            "active_subscribers": len(event_bus.subscribers),
            "deduplication_enabled": True,
            "message": "Event bus deduplication is active",
        }
    except Exception as e:
        logger.error(f"Error retrieving event bus statistics: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve event bus statistics"
        )


@router.post("/games/{game_id}/retry-ai-turn")
async def retry_ai_turn(game_id: str):
    """Retry AI turn when it appears stuck.

    Resets AI subscriber state and triggers a new turn execution.
    Called by frontend when AI hasn't responded for 30+ seconds.
    """
    from services.ai_event_subscriber import get_ai_event_subscriber
    from services.ai_turn_executor import get_ai_turn_executor

    if not game_manager:
        raise HTTPException(status_code=503, detail="Game manager not available")

    game = game_manager.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Find current AI player
    current_player_index = game.state.current_player_index
    if current_player_index is None or current_player_index >= len(game.players):
        raise HTTPException(status_code=400, detail="Invalid player index")

    current_player = game.players[current_player_index]

    if not current_player.is_ai:
        raise HTTPException(status_code=400, detail="Current player is not an AI")

    logger.info(f"🔄 Retry AI turn requested for game {game_id}, player {current_player.name}")

    try:
        # Get AI subscriber and reset its state
        subscriber = get_ai_event_subscriber(game_id, current_player.id)
        if subscriber:
            # Reset last turn state to allow re-execution
            subscriber._last_turn_state = None
            logger.info(f"Reset AI subscriber state for {current_player.name}")

        # Execute AI turn directly
        executor = get_ai_turn_executor(game_manager)
        result = await executor.execute_ai_turn(game_id, current_player.id)

        if result.get("success"):
            logger.info(f"✅ AI turn retry successful: {len(result.get('actions_taken', []))} actions")
            return {
                "success": True,
                "message": f"AI turn restarted for {current_player.name}",
                "actions_taken": len(result.get("actions_taken", [])),
            }
        else:
            error_msg = result.get("error", "Unknown error")
            logger.error(f"❌ AI turn retry failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
            }

    except Exception as e:
        logger.error(f"Error retrying AI turn: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
