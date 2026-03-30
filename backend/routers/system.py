"""System and admin API endpoints for Innovation game server.

Handles health checks, stats, and system monitoring.
"""

import time

from fastapi import APIRouter, HTTPException

from logging_config import get_logger

logger = get_logger(__name__)

# Router instance
router = APIRouter(prefix="/api/v1")

# Import game manager - will be set by main.py
game_manager = None
connection_manager = None  # Will be set by main.py


def set_game_manager(gm):
    """Set game manager dependency injected from main.py."""
    global game_manager
    game_manager = gm


def set_connection_manager(cm):
    """Set connection manager dependency injected from main.py."""
    global connection_manager
    connection_manager = cm


@router.get("/")
async def root():
    return {"message": "Innovation Game API"}


@router.get("/health")
async def health_check():
    """Health check endpoint with security status."""
    from security_config import security_config

    # Re-validate security for health check (fresh validation, not cached)
    security_config.validate_all()
    security_status = security_config.get_security_status()

    return {
        "status": "healthy" if security_status["is_secure"] else "degraded",
        "message": "Innovation Game API",
        "security": {
            "environment": security_status["environment"],
            "is_secure": security_status["is_secure"],
            "issues_count": security_status["critical_issues"],
            "warnings_count": security_status["warnings"],
        },
        "timestamp": time.time(),
    }


@router.get("/system/stats")
async def get_system_stats():
    """Get system statistics through proper service layer."""
    if not game_manager:
        return {
            "error": "Game manager not initialized",
            "timestamp": time.time(),
        }

    # Use service layer instead of direct redis_store access
    stats = await game_manager.get_system_stats()
    stats["timestamp"] = time.time()

    return stats


@router.get("/system/broadcast-stats")
async def get_broadcast_stats():
    """Get broadcast service statistics for observability."""
    from services.broadcast_service import get_broadcast_service

    try:
        broadcast_service = get_broadcast_service()
        stats = broadcast_service.get_stats()
        stats["timestamp"] = time.time()
        return stats
    except RuntimeError:
        # BroadcastService not initialized yet
        return {
            "error": "BroadcastService not initialized",
            "total_broadcasts": 0,
            "websocket": {"successes": 0, "failures": 0, "success_rate": 0.0},
            "event_bus": {"successes": 0, "failures": 0, "success_rate": 0.0},
            "timestamp": time.time(),
        }


@router.get("/system/ws-log")
async def get_ws_log(
    game_id: str | None = None, player_id: str | None = None, limit: int = 50
):
    """Retrieve recent outbound WebSocket messages for a player.

    Requires INNOVATION_DEBUG=true.

    - If player_id is provided, returns the last N messages for that player.
    - If only game_id is provided, returns a list of player_ids with logs in that game.
    """
    import os

    if os.getenv("INNOVATION_DEBUG", "false").lower() != "true":
        raise HTTPException(
            status_code=403,
            detail="Admin endpoints disabled. Set INNOVATION_DEBUG=true.",
        )

    if not connection_manager:
        raise HTTPException(
            status_code=500, detail="Connection manager not initialized"
        )

    # Player-specific logs
    if player_id:
        logs = connection_manager.get_ws_logs(player_id, limit=limit)
        return {"player_id": player_id, "count": len(logs), "messages": logs}

    # Game overview of players with logs
    if game_id:
        players = []
        try:
            if game_id in connection_manager.game_connections:
                players = list(connection_manager.game_connections.get(game_id, set()))
        except Exception:
            players = []
        return {"game_id": game_id, "players_with_logs": players}

    # Neither provided
    raise HTTPException(status_code=400, detail="Provide player_id or game_id")
