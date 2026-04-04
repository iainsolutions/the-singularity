"""
AI Player API Endpoints

Endpoints for managing AI players in games.
"""

from async_game_manager import AsyncGameManager, redis_store
from fastapi import APIRouter, HTTPException
from logging_config import get_logger
from models.player import Player
from pydantic import BaseModel
from services.ai_cost_monitor import cost_monitor
from services.ai_event_subscriber import create_ai_event_subscriber
from services.ai_providers.factory import _PROVIDER_REGISTRY
from services.ai_service import ai_service


logger = get_logger(__name__)

# Provider display names (proper capitalization)
_PROVIDER_DISPLAY_NAMES = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "gemini": "Gemini",
}

# Model ID to display name mapping (no dates, user-friendly)
_MODEL_DISPLAY_NAMES = {
    # Anthropic Claude models
    "claude-3-5-haiku-20241022": "Haiku 3.5",
    "claude-3-7-sonnet-20250219": "Sonnet 3.7",
    "claude-sonnet-4-20250514": "Sonnet 4",
    "claude-sonnet-4-5-20250929": "Sonnet 4.5",
    "claude-opus-4-20250514": "Opus 4",
    "claude-opus-4-1-20250805": "Opus 4.1",
    # OpenAI models
    "gpt-4o-mini": "GPT-4o Mini",
    "gpt-4o": "GPT-4o",
    "gpt-4-turbo": "GPT-4 Turbo",
    "o1-mini": "o1 Mini",
    "o1": "o1",
    # Gemini models
    "gemini-2.5-flash-lite": "Gemini Flash Lite",
    "gemini-2.5-flash": "Gemini Flash",
    "gemini-2.5-pro": "Gemini Pro",
}


def _get_ai_display_name(difficulty: str, provider: str | None = None) -> str:
    """Generate a user-friendly AI player name based on personality codename."""
    from services.ai_personalities import get_codename

    # Use the thematic codename from the personality system
    return get_codename(difficulty)

# Provider-specific cost estimates (per game)
_PROVIDER_COST_ESTIMATES = {
    "anthropic": {
        "easy": "$0.01-0.05",
        "medium": "$0.30-0.80",
        "hard": "$2.50-4.50",
    },
    "openai": {
        "easy": "$0.15-0.40",
        "medium": "$0.80-1.20",
        "hard": "$1.20-1.80",
    },
    "gemini": {
        "easy": "$0.04-0.08",
        "medium": "$0.15-0.30",
        "hard": "$0.50-1.00",
    },
}

router = APIRouter(prefix="/api/v1", tags=["ai"])

# Game manager will be injected from main.py
game_manager: AsyncGameManager | None = None
event_bus = None  # Will be set by main.py


def set_game_manager(gm: AsyncGameManager, eb=None):
    """Set game manager dependency injected from main.py"""
    global game_manager, event_bus
    game_manager = gm
    event_bus = eb


class AddAIPlayerRequest(BaseModel):
    difficulty: str
    name: str | None = None
    provider: str | None = None  # Optional: "anthropic" or "openai"


class AddAIPlayerResponse(BaseModel):
    success: bool
    player_id: str | None = None
    player_name: str | None = None
    is_ai: bool = True
    difficulty: str | None = None
    game_state: dict | None = None
    error: str | None = None


class ProviderInfo(BaseModel):
    """Information about an AI provider."""

    name: str
    display_name: str
    available: bool
    is_default: bool


class PersonalityInfo(BaseModel):
    """AI personality profile for a difficulty level."""

    codename: str
    era: int
    tagline: str
    backstory: str
    play_style: str


class DifficultyInfo(BaseModel):
    """Information about a difficulty level with provider-specific details."""

    id: str
    name: str
    description: str
    models: dict[str, str]
    costs: dict[str, str]
    personality: PersonalityInfo | None = None
    # Legacy fields for backward compatibility
    model: str | None = None
    estimated_cost_per_game: str | None = None
    openai_model: str | None = None


class CostLimits(BaseModel):
    """Cost monitoring limits and usage."""

    daily_limit: float
    daily_used: float
    daily_remaining: float
    per_game_limit: float


class APIHealth(BaseModel):
    """API health status."""

    status: str


class AIStatusResponse(BaseModel):
    """Response model for AI service status endpoint."""

    enabled: bool
    default_provider: str | None = None
    configured_providers: list[str] = []
    available_providers: list[ProviderInfo] = []
    available_difficulties: list[DifficultyInfo] = []
    cost_limits: CostLimits | None = None
    api_health: APIHealth | None = None
    error: str | None = None


@router.post("/games/{game_id}/add_ai_player")
async def add_ai_player(
    game_id: str, request: AddAIPlayerRequest
) -> AddAIPlayerResponse:
    """Add an AI player to an existing game (before it starts)"""

    try:
        # Check if AI service is enabled
        if not ai_service.enabled:
            return AddAIPlayerResponse(
                success=False,
                error="AI service not enabled. Set ANTHROPIC_API_KEY and AI_ENABLED=true",
            )

        # Event bus is required for AI players - fail fast BEFORE any mutations
        if not event_bus:
            logger.error("Event bus not available - AI players require event bus!")
            return AddAIPlayerResponse(
                success=False,
                error="Event bus not configured. AI players cannot function without it.",
            )

        # Get game
        game = game_manager.get_game(game_id)
        if not game:
            return AddAIPlayerResponse(
                success=False, error=f"Game not found: {game_id}"
            )

        # Check if game has started (can only add AI players in waiting phase)
        if game.phase != "waiting_for_players":
            return AddAIPlayerResponse(success=False, error="Game has already started")

        # Check if game is full
        if len(game.players) >= 4:  # Max players
            return AddAIPlayerResponse(success=False, error="Game is full")

        # Use game lock to prevent race conditions (following join_game pattern)
        lock = game_manager.lock_service.acquire_lock(game_id)

        async with lock:
            # Re-check game state while holding lock
            if game.phase != "waiting_for_players":
                return AddAIPlayerResponse(
                    success=False, error="Game has already started"
                )

            if len(game.players) >= 4:
                return AddAIPlayerResponse(success=False, error="Game is full")

            # Create AI player
            player_name = request.name or _get_ai_display_name(request.difficulty, request.provider)
            player = Player(
                name=player_name, is_ai=True, ai_difficulty=request.difficulty
            )

            # Create AI agent BEFORE adding to game (fail-fast if this fails)
            try:
                # Validate provider if specified
                if request.provider:
                    available_providers = ai_service.get_available_providers()
                    if request.provider not in available_providers:
                        return AddAIPlayerResponse(
                            success=False,
                            error=f"Provider '{request.provider}' not configured. "
                            f"Available: {', '.join(available_providers)}",
                        )

                # Pass provider config if specified
                agent_config = {}
                if request.provider:
                    agent_config["provider"] = request.provider

                ai_service.create_agent(
                    player_id=player.id,
                    difficulty=request.difficulty,
                    config=agent_config if agent_config else None,
                )
            except Exception as e:
                logger.error(f"Failed to create AI agent: {e}")
                return AddAIPlayerResponse(
                    success=False, error=f"Failed to create AI agent: {e!s}"
                )

            # Add player to game using proper method (not direct list manipulation)
            game.add_player(player)

            # Persist to Redis while holding lock (following join_game pattern)
            await redis_store.save_game(game_id, game.to_dict())

        # Start AI Event Subscriber OUTSIDE lock to avoid deadlock
        # (subscriber may need to interact with game_manager)
        #
        # NOTE: Small race window exists where player appears in game state
        # but subscriber isn't running yet. This is acceptable because:
        # 1. Race window is very small (milliseconds)
        # 2. Game is still in "waiting_for_players" phase (no game logic executing)
        # 3. If subscriber creation fails, we properly rollback the player addition
        # 4. Holding lock during subscriber creation could cause deadlock
        try:
            await create_ai_event_subscriber(
                game_id, player.id, event_bus, game_manager
            )
            logger.info(f"AI Event Subscriber started for player {player.name}")
        except Exception as e:
            logger.error(f"Failed to start AI Event Subscriber: {e}", exc_info=True)
            # Subscriber failed - need to rollback the player addition
            # Re-acquire lock for cleanup
            async with lock:
                game.players.remove(player)
                await redis_store.save_game(game_id, game.to_dict())

            # Also remove the AI agent
            ai_service.remove_agent(player.id)

            return AddAIPlayerResponse(
                success=False,
                error=f"Failed to start AI event subscriber: {e!s}",
            )

        logger.info(
            f"AI player added to game {game_id}: {player.name} (difficulty={request.difficulty})"
        )

        return AddAIPlayerResponse(
            success=True,
            player_id=player.id,
            player_name=player.name,
            difficulty=request.difficulty,
            game_state=game.to_dict(),
        )

    except ValueError as e:
        logger.error(f"Invalid request: {e}")
        return AddAIPlayerResponse(success=False, error=str(e))

    except Exception as e:
        logger.error(f"Error adding AI player: {e}", exc_info=True)
        return AddAIPlayerResponse(success=False, error=f"Server error: {e!s}")


@router.get("/ai/status", response_model=AIStatusResponse)
async def get_ai_status() -> AIStatusResponse:
    """Check AI service availability and configuration"""

    try:
        if not ai_service.enabled:
            return AIStatusResponse(
                enabled=False,
                error="AI service not enabled",
            )

        # Get providers that have API keys configured
        configured_providers = ai_service.get_available_providers()
        default_provider = ai_service.default_provider

        # Build provider list showing which are available
        available_providers = [
            {
                "name": provider_name,
                "display_name": _PROVIDER_DISPLAY_NAMES.get(
                    provider_name, provider_name.capitalize()
                ),
                "available": provider_name in configured_providers,
                "is_default": provider_name == default_provider,
            }
            for provider_name in sorted(_PROVIDER_REGISTRY.keys())
        ]

        # Get difficulties with provider-specific models and costs
        # Create copies to avoid mutation of original data
        difficulties = [dict(d) for d in ai_service.get_available_difficulties()]

        # Add provider-specific information for each difficulty
        for diff in difficulties:
            diff_id = diff["id"]

            # Initialize provider-specific fields
            diff["models"] = {}
            diff["costs"] = {}

            # Add Anthropic model and cost (always available via base implementation)
            if "anthropic" in configured_providers:
                diff["models"]["anthropic"] = diff.get(
                    "model", "claude-3-5-haiku-20241022"
                )
                diff["costs"]["anthropic"] = _PROVIDER_COST_ESTIMATES.get(
                    "anthropic", {}
                ).get(diff_id, "$0.10-0.20")

            # Add OpenAI model and cost if configured
            if "openai" in configured_providers:
                try:
                    from services.ai_providers.openai_provider import OpenAIProvider

                    openai_models = OpenAIProvider.get_difficulty_models()
                    diff["models"]["openai"] = openai_models.get(diff_id, "gpt-4-turbo")
                    diff["costs"]["openai"] = _PROVIDER_COST_ESTIMATES.get(
                        "openai", {}
                    ).get(diff_id, "$0.80-1.20")
                    # Keep legacy field for backward compatibility
                    diff["openai_model"] = diff["models"]["openai"]
                except ImportError:
                    logger.warning("OpenAI provider not available for model mappings")

            # Add Gemini model and cost if configured
            if "gemini" in configured_providers:
                try:
                    from services.ai_providers.gemini_provider import GeminiAIProvider

                    gemini_models = GeminiAIProvider.get_difficulty_models()
                    diff["models"]["gemini"] = gemini_models.get(
                        diff_id, "gemini-2.5-flash"
                    )
                    diff["costs"]["gemini"] = _PROVIDER_COST_ESTIMATES.get(
                        "gemini", {}
                    ).get(diff_id, "$0.12-0.24")
                except ImportError:
                    logger.warning("Gemini provider not available for model mappings")

            # Keep legacy field for backward compatibility
            # Use Anthropic cost as default for old clients
            if "estimated_cost_per_game" not in diff:
                diff["estimated_cost_per_game"] = diff["costs"].get(
                    "anthropic", "$0.10-0.20"
                )

        return AIStatusResponse(
            enabled=True,
            default_provider=default_provider,
            configured_providers=configured_providers,
            available_providers=[ProviderInfo(**p) for p in available_providers],
            available_difficulties=[DifficultyInfo(**d) for d in difficulties],
            cost_limits=CostLimits(
                daily_limit=cost_monitor.daily_limit,
                daily_used=cost_monitor.daily_costs,
                daily_remaining=cost_monitor.daily_limit - cost_monitor.daily_costs,
                per_game_limit=cost_monitor.per_game_limit,
            ),
            api_health=APIHealth(status="healthy"),
        )

    except Exception as e:
        logger.error(f"Error getting AI status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/ai/cost_stats")
async def get_cost_stats():
    """Get real-time cost monitoring statistics"""

    try:
        return cost_monitor.get_stats()

    except Exception as e:
        logger.error(f"Error getting cost stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/ai/stats")
async def get_ai_stats():
    """Get AI player statistics and performance metrics"""

    try:
        stats = ai_service.get_all_stats()
        cost_stats = cost_monitor.get_stats()

        return {
            "service": stats,
            "costs": cost_stats,
        }

    except Exception as e:
        logger.error(f"Error getting AI stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/games/{game_id}/execute_ai_turn")
async def execute_ai_turn_manually(game_id: str):
    """
    Manually trigger AI turn execution (debug endpoint).

    Publishes synthetic event to Event Bus, letting AI Event Subscriber handle it.
    This respects the event-bus architecture and deduplication logic.
    """

    try:
        game = game_manager.get_game(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")

        # Get current player
        current_player = game.players[game.state.current_player_index]

        logger.info(
            f"Manual AI turn trigger - Current player: {current_player.name}, "
            f"is_ai={current_player.is_ai}, "
            f"phase={game.phase}, "
            f"actions_remaining={game.state.actions_remaining}"
        )

        if not event_bus:
            raise HTTPException(status_code=503, detail="Event bus not available")

        # Publish synthetic event to trigger AI Event Subscriber
        # This maintains single orchestration pathway and respects deduplication
        # PERFORMANCE FIX: Send minimal metadata - AI fetches game from game_manager
        game_dict = game.to_dict()
        await event_bus.publish(
            game_id=game_id,
            event_type="game_state_updated",
            data={
                "current_player_id": game_dict.get("current_player_id"),
                "phase": game_dict.get("phase"),
                "turn_number": game_dict.get("turn_number"),
                "actions_remaining": game_dict.get("state", {}).get(
                    "actions_remaining"
                ),
            },
            source="ai_games_router.manual_trigger",
        )

        return {
            "success": True,
            "message": "Synthetic event published to trigger AI turn",
            "current_player": current_player.name,
            "is_ai": current_player.is_ai,
            "event_published": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in manual AI turn trigger: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/games/{game_id}/players/{player_id}")
async def remove_ai_player(game_id: str, player_id: str):
    """Remove an AI player from a game (before it starts)"""

    try:
        # Get game
        game = game_manager.get_game(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")

        # Check if game has started (can only remove AI players in waiting phase)
        if game.phase != "waiting_for_players":
            raise HTTPException(status_code=400, detail="Game has already started")

        # Find and remove player
        player = next((p for p in game.players if p.id == player_id), None)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")

        if not player.is_ai:
            raise HTTPException(status_code=400, detail="Player is not an AI")

        # Stop AI Event Subscriber first (before removing from game)
        from services.ai_event_subscriber import stop_ai_event_subscriber

        try:
            await stop_ai_event_subscriber(game_id, player_id)
        except Exception as e:
            logger.warning(f"Failed to stop AI Event Subscriber: {e}")

        # Use game lock to prevent race conditions
        lock = game_manager.lock_service.acquire_lock(game_id)

        async with lock:
            # Re-check game state while holding lock
            if game.phase != "waiting_for_players":
                raise HTTPException(status_code=400, detail="Game has already started")

            # Remove player from game
            game.players.remove(player)

            # Persist to Redis while holding lock
            await redis_store.save_game(game_id, game.to_dict())

        # Remove AI agent (after releasing lock)
        ai_service.remove_agent(player_id)

        logger.info(f"AI player removed from game {game_id}: {player.name}")

        return {
            "success": True,
            "message": "AI player removed",
            "game_state": game.to_dict(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing AI player: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
