"""
Game action handlers extracted from AsyncGameManager.

These handle the core player actions: draw, meld, achieve, end_turn.
Each function takes a Game and Player, performs the action, and returns a result dict.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from logging_config import EventType, activity_logger, get_logger
from models.game import ActionType, GamePhase
from services.game_helpers import (
    advance_turn_if_needed,
    cleanup_game_resources,
    format_game_state_for_frontend,
)

if TYPE_CHECKING:
    from models.game import Game
    from models.player import Player

logger = get_logger(__name__)


async def _check_and_apply_victory(game: Game, player: Player):
    """Check if player won via achievements and end game if so."""
    required = {2: 6, 3: 5, 4: 4}.get(len(game.players), 6)
    logger.info(f"Achievement claimed - {player.name} has {len(player.achievements)}/{required}")
    if len(player.achievements) >= required:
        game.winner = player
        game.phase = GamePhase.FINISHED
        await cleanup_game_resources(game.game_id)
        activity_logger.log_game_event(
            game_id=game.game_id,
            event_type=EventType.GAME_ENDED,
            data={
                "winner": player.name,
                "victory_type": "achievements",
                "achievement_count": len(player.achievements),
                "required_count": required,
                "player_count": len(game.players),
            },
        )


async def draw_card(game: Game, player: Player) -> dict[str, Any]:
    """Draw a card from the age deck matching the player's highest top card age."""
    age = player.board.get_highest_age() or 1
    card = game.draw_card(age)

    if card:
        player.add_to_hand(card)
        game.add_log_entry(
            player_name=player.name,
            action_type=ActionType.DRAW,
            description=f"researched an era {card.age} card",
        )

        activity_logger.log_game_event(
            event_type=EventType.ACTION_DRAW,
            game_id=game.game_id,
            player_id=player.id,
            data={"card_name": card.name, "age": age},
            message=f"{player.name} researched an era {card.age} card",
        )

        if game.state.actions_remaining > 0:
            game.state.actions_remaining -= 1

        advance_turn_if_needed(game)

        return {
            "success": True,
            "action": "draw",
            "card_drawn": card.to_dict(),
            "game_state": format_game_state_for_frontend(game.to_dict()),
        }

    # No card drawn — check if game ended due to age exhaustion
    if game.phase == GamePhase.FINISHED:
        activity_logger.log_game_event(
            game_id=game.game_id,
            event_type=EventType.GAME_ENDED,
            data={
                "winner": game.winner.name if game.winner else "None",
                "victory_type": "age_exhaustion",
                "final_phase": "FINISHED",
                "reason": "All age decks exhausted",
            },
        )
        logger.info(
            f"GAME OVER: Game {game.game_id} ended due to age exhaustion - "
            f"Winner: {game.winner.name if game.winner else 'TBD by score'}"
        )
        return {
            "success": True,
            "action": "draw",
            "game_ended": True,
            "reason": "age_exhaustion",
            "game_state": format_game_state_for_frontend(game.to_dict()),
        }

    return {"success": False, "error": "No cards available"}


async def end_turn(game: Game, player: Player) -> dict[str, Any]:
    """End the current player's turn and advance to the next player."""
    if game.players[game.state.current_player_index].id != player.id:
        return {"success": False, "error": "Not your turn"}

    activity_logger.log_game_event(
        event_type=EventType.TURN_ENDED,
        game_id=game.game_id,
        player_id=player.id,
        data={"turn_number": game.state.turn_number},
        message=f"{player.name} ended their turn",
    )

    # Mark first turn completion
    if (
        game.state.current_player_index
        not in game.state.players_who_have_taken_first_turn
    ):
        game.state.players_who_have_taken_first_turn.append(
            game.state.current_player_index
        )

    # Advance to next player
    game.state.current_player_index = (game.state.current_player_index + 1) % len(
        game.players
    )
    game.state.turn_number += 1

    # Determine actions for next player
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

    next_player = game.players[game.state.current_player_index]
    activity_logger.log_game_event(
        event_type=EventType.TURN_STARTED,
        game_id=game.game_id,
        player_id=next_player.id,
        data={
            "turn_number": game.state.turn_number,
            "actions_remaining": game.state.actions_remaining,
        },
        message=f"{next_player.name} started their turn",
    )

    return {
        "success": True,
        "game_state": format_game_state_for_frontend(game.to_dict()),
    }


async def claim_achievement(game: Game, player: Player, age: int) -> dict[str, Any]:
    """Claim an age achievement if requirements are met."""
    achievement = None
    if game.deck_manager.achievement_cards.get(age):
        achievement = game.deck_manager.achievement_cards[age][0]

    if not achievement:
        return {"success": False, "error": "Achievement not available"}

    score = sum(card.age for card in player.score_pile)
    same_age_achievements = len(
        [ach for ach in player.achievements if ach.age == age]
    )
    required_score = age * 5 * (same_age_achievements + 1)

    if score < required_score:
        return {"success": False, "error": f"Need {required_score} points, have {score}"}

    top_cards_value = max([card.age for card in player.board.get_top_cards()] + [0])
    if top_cards_value < age:
        return {"success": False, "error": f"Need top card of age {age} or higher"}

    game.deck_manager.achievement_cards[age].remove(achievement)
    player.achievements.append(achievement)

    game.add_log_entry(
        player_name=player.name,
        action_type=ActionType.ACHIEVE,
        description=f"breakthrough: era {age}",
    )

    activity_logger.log_game_event(
        event_type=EventType.ACTION_ACHIEVE,
        game_id=game.game_id,
        player_id=player.id,
        data={
            "achievement_name": achievement.name,
            "age": age,
            "score": score,
            "required_score": required_score,
        },
        message=f"{player.name} breakthrough: era {age}",
    )

    if game.state.actions_remaining > 0:
        game.state.actions_remaining -= 1

    advance_turn_if_needed(game)

    await _check_and_apply_victory(game, player)

    return {
        "success": True,
        "action": "achieve",
        "game_state": format_game_state_for_frontend(game.to_dict()),
    }


