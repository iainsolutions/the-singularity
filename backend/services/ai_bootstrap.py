"""
AI Bootstrap Service

Handles reconnecting AI players after server restart.
Keeps AsyncGameManager player-agnostic by moving AI initialization here.
"""
import asyncio

from logging_config import get_logger

logger = get_logger(__name__)


async def bootstrap_ai_players_for_game(game_id: str, game, event_bus, game_manager):
    """
    Reconnect AI players for a game after server restart.

    Called by external orchestration, not by game manager.
    """
    from services.ai_event_subscriber import create_ai_event_subscriber
    from services.ai_service import ai_service

    ai_count = 0
    for player in game.players:
        if player.is_ai:
            try:
                # Get difficulty from player's ai_difficulty field
                difficulty = getattr(player, "ai_difficulty", "easy")

                # Recreate AI agent
                ai_service.create_agent(player_id=player.id, difficulty=difficulty)
                logger.info(
                    f"Recreated AI agent for {player.name} "
                    f"(difficulty={difficulty}) in game {game_id}"
                )

                # Reconnect AI Event Subscriber (if event bus is available)
                if event_bus:
                    await create_ai_event_subscriber(
                        game_id, player.id, event_bus, game_manager
                    )
                    logger.info(f"Reconnected AI Event Subscriber for {player.name}")
                else:
                    logger.warning(
                        f"Event bus not available, AI player {player.name} will not receive events"
                    )

                ai_count += 1

            except Exception as ai_err:
                logger.error(
                    f"Failed to recreate AI agent/subscriber for {player.name}: {ai_err}",
                    exc_info=True,
                )

    if ai_count > 0:
        logger.info(f"Bootstrapped {ai_count} AI player(s) for game {game_id}")

        # CRITICAL FIX: Notify AI players if it's their turn after Redis reload
        # When games are loaded from Redis, no game_state_updated event is published,
        # so AI players don't know to take their turn. Publish the event here.
        if event_bus and game.phase.value == "playing":
            current_player = game.players[game.state.current_player_index]
            if current_player.is_ai:
                logger.info(
                    f"Publishing game_restored event for AI player {current_player.name} "
                    f"(it's their turn with {game.state.actions_remaining} actions)"
                )
                await event_bus.publish(
                    game_id=game_id,
                    event_type="game_restored",
                    data={
                        "player_id": current_player.id,
                        "actions_remaining": game.state.actions_remaining
                    },
                    source="ai_bootstrap"
                )


async def bootstrap_all_ai_players(game_manager, event_bus):
    """
    Bootstrap AI players for all games after server restart.

    Called once during server startup, after games are loaded from Redis.
    """
    logger.info("Bootstrapping AI players for all games...")

    ai_games = []
    for game_id, game in game_manager.games.items():
        has_ai = any(player.is_ai for player in game.players)
        if has_ai:
            ai_games.append((game_id, game))

    if not ai_games:
        logger.info("No games with AI players found")
        return

    logger.info(f"Found {len(ai_games)} game(s) with AI players")

    # Bootstrap all AI players concurrently
    tasks = [
        bootstrap_ai_players_for_game(game_id, game, event_bus, game_manager)
        for game_id, game in ai_games
    ]

    await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("AI player bootstrap complete")
