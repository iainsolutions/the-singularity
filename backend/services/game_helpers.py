"""
Shared helper functions extracted from AsyncGameManager.

Operate on Game/Player objects; some mutate their arguments in place.
Imported by AsyncGameManager (which delegates to them) and by extracted modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from logging_config import get_logger

if TYPE_CHECKING:
    from models.game import Game
    from models.player import Player

logger = get_logger(__name__)


def format_game_state_for_frontend(
    game_state: dict, player_id: str | None = None
) -> dict:
    """Format game state for frontend display by converting raw state_changes to descriptions.

    NOTE: Mutates game_state dict in place (modifies action_log entries, adds special_achievements).
    """
    for entry in game_state.get("action_log", []):
        if entry.get("state_changes"):
            from dogma_v2.state_tracker import StateChangeTracker

            try:
                tracker = StateChangeTracker.from_dict_list(entry["state_changes"])
                formatted = []
                for change in tracker.changes:
                    description = tracker._format_change(
                        change, viewing_player_id=player_id
                    )
                    if description:
                        formatted.append(
                            {
                                "description": description,
                                "change_type": change.change_type,
                                "visibility": change.visibility.value,
                                "context": change.context,
                            }
                        )
                entry["state_changes"] = formatted
            except Exception as e:
                logger.warning(f"Failed to format state_changes: {e}")

    if (
        "special_achievements_available" in game_state
        and "special_achievements_junk" in game_state
    ):
        game_state["special_achievements"] = {
            "available": game_state.get("special_achievements_available", []),
            "junk": game_state.get("special_achievements_junk", []),
            "claimed": {},
        }
        for player in game_state.get("players", []):
            if player.get("special_achievement"):
                game_state["special_achievements"]["claimed"][player["id"]] = (
                    player["special_achievement"]
                )

    return game_state


def sync_game_state_safely(target_game: Game, source_game: Game):
    """Sync game state from DogmaContext game to main game object.

    IMPORTANT: Uses direct assignment, NOT deep copy. Deep copy creates new
    player objects which loses tucked card changes and other mutations made
    during dogma execution. The immutable object concern was a red herring —
    we need the actual modified objects from DogmaContext, not copies.
    """
    try:
        if hasattr(source_game, "state"):
            target_game.state = source_game.state
        if hasattr(source_game, "players"):
            target_game.players = source_game.players
        if hasattr(source_game.deck_manager, "age_decks"):
            target_game.deck_manager.age_decks = source_game.deck_manager.age_decks
        if hasattr(source_game.deck_manager, "achievement_cards"):
            target_game.deck_manager.achievement_cards = (
                source_game.deck_manager.achievement_cards
            )
        if hasattr(source_game.deck_manager, "junk_pile"):
            target_game.deck_manager.junk_pile = source_game.deck_manager.junk_pile
        if hasattr(source_game, "action_log"):
            target_game.action_log = source_game.action_log
        logger.debug("Synced game state from DogmaContext to main game object")
    except Exception as e:
        logger.error(f"Error during game state sync: {e}", exc_info=True)
        raise


def advance_turn_if_needed(game: Game):
    """Auto-advance turn if no actions remaining."""
    if game.state.actions_remaining == 0:
        if (
            game.state.current_player_index
            not in game.state.players_who_have_taken_first_turn
        ):
            game.state.players_who_have_taken_first_turn.append(
                game.state.current_player_index
            )

        old_player_index = game.state.current_player_index
        game.state.current_player_index = (
            game.state.current_player_index + 1
        ) % len(game.players)
        game.state.turn_number += 1

        logger.info(
            f"Turn change: {game.players[old_player_index].name} -> "
            f"{game.players[game.state.current_player_index].name} "
            f"(Game: {game.game_id})"
        )

        if (
            game.state.current_player_index
            not in game.state.players_who_have_taken_first_turn
        ):
            if game.state.current_player_index == game.state.first_player_index:
                game.state.actions_remaining = 1
            else:
                game.state.actions_remaining = 2
        else:
            game.state.actions_remaining = 2


def player_in_game(game: Game, player_id: str | None) -> bool:
    """Return True when the given player belongs to the game."""
    if not player_id:
        return False
    try:
        return game.get_player_by_id(player_id) is not None
    except AttributeError:
        return any(getattr(p, "id", None) == player_id for p in game.players)


async def cleanup_game_resources(game_id: str):
    """Stop AI subscribers and clean up game resources."""
    try:
        from services.ai_event_subscriber import cleanup_game_subscribers
        await cleanup_game_subscribers(game_id)
        logger.debug(f"Cleaned up resources for finished game {game_id}")
    except Exception as e:
        logger.error(f"Error cleaning up game resources for {game_id}: {e}", exc_info=True)
