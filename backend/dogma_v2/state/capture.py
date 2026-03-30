"""
State capture system for Dogma v2.

This module provides comprehensive state capture and comparison
functionality for tracking game state changes during dogma execution.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from models.card import Card
from models.player import Player

logger = logging.getLogger(__name__)


@dataclass
class GameStateSnapshot:
    """Snapshot of game state for change detection"""

    # Available achievements
    available_achievement_count: int
    available_achievement_ages: list[int]

    # Junk pile
    junk_pile_count: int

    @classmethod
    def capture(cls, game) -> "GameStateSnapshot":
        """Capture current game state"""
        return cls(
            available_achievement_count=len(game.deck_manager.achievement_cards),
            available_achievement_ages=sorted(game.deck_manager.achievement_cards.keys()),
            junk_pile_count=len(game.junk_pile),
        )


@dataclass
class PlayerStateSnapshot:
    """Snapshot of a player's state at a point in time"""

    player_id: str
    player_name: str

    # Card counts
    hand_count: int
    score_pile_count: int
    achievement_count: int

    # Board state
    board_cards: dict[str, list[dict[str, Any]]]  # color -> list of card dicts
    board_splays: dict[str, str]  # color -> splay direction

    # Symbol counts (calculated)
    symbol_counts: dict[str, int]

    # Detailed card information (for change detection)
    hand_cards: list[dict[str, Any]] = field(default_factory=list)
    score_cards: list[dict[str, Any]] = field(default_factory=list)
    achievements: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def capture(cls, player: Player) -> "PlayerStateSnapshot":
        """Capture current player state"""

        # Capture board state
        board_cards = {}
        board_splays = {}

        for color in ["blue", "red", "yellow", "green", "purple"]:
            color_stack = getattr(player.board, f"{color}_cards", [])
            board_cards[color] = [cls._card_to_dict(card) for card in color_stack]
            board_splays[color] = getattr(player.board, f"{color}_splay", "none")

        # Calculate symbol counts
        symbol_counts = {}
        from models.card import Symbol

        for symbol in Symbol:
            symbol_counts[symbol.value] = player.count_symbol(symbol)

        return cls(
            player_id=player.id,
            player_name=player.name,
            hand_count=len(player.hand),
            score_pile_count=len(player.score_pile),
            achievement_count=len(player.achievements),
            board_cards=board_cards,
            board_splays=board_splays,
            symbol_counts=symbol_counts,
            hand_cards=[cls._card_to_dict(card) for card in player.hand],
            score_cards=[cls._card_to_dict(card) for card in player.score_pile],
            achievements=[cls._card_to_dict(card) for card in player.achievements],
        )

    @staticmethod
    def _card_to_dict(card: Card) -> dict[str, Any]:
        """Convert card to comparable dictionary"""
        return {
            "card_id": getattr(card, "card_id", None),
            "name": card.name,
            "age": card.age,
            "color": card.color,
        }


@dataclass
class GameStateSnapshot:  # noqa: F811
    """Snapshot of complete game state"""

    game_id: str
    current_age: int
    actions_taken: int
    current_player_id: str

    # Age deck sizes
    age_deck_sizes: dict[int, int]

    # Achievement deck size
    achievements_available: int

    # Player states
    player_states: dict[str, PlayerStateSnapshot]

    @classmethod
    def capture(cls, game) -> "GameStateSnapshot":
        """Capture current game state"""

        # Capture age deck sizes
        age_deck_sizes = {}
        for age in range(1, 11):
            deck = getattr(game, f"age_{age}_cards", [])
            age_deck_sizes[age] = len(deck)

        # Capture player states
        player_states = {}
        for player in game.players:
            player_states[player.id] = PlayerStateSnapshot.capture(player)

        return cls(
            game_id=game.game_id,
            current_age=game.state.current_age,
            actions_taken=game.state.actions_taken,
            current_player_id=game.current_player.id if game.current_player else "",
            age_deck_sizes=age_deck_sizes,
            achievements_available=len(game.deck_manager.achievement_cards),
            player_states=player_states,
        )


class StateCapture:
    """
    Main state capture utility for tracking game state changes.

    This class provides static methods for capturing, comparing, and
    analyzing game state changes during dogma execution.
    """

    @staticmethod
    def capture_player_state(player: Player) -> PlayerStateSnapshot:
        """Capture a player's current state"""
        return PlayerStateSnapshot.capture(player)

    @staticmethod
    def capture_game_state(game) -> GameStateSnapshot:
        """Capture complete game state"""
        return GameStateSnapshot.capture(game)

    @staticmethod
    def game_states_differ(before: GameStateSnapshot, after: GameStateSnapshot) -> bool:
        """Check if two game states differ meaningfully"""

        # Check achievement changes
        if (
            before.available_achievement_count != after.available_achievement_count
            or before.available_achievement_ages != after.available_achievement_ages
        ):
            return True

        # Check junk pile changes
        return before.junk_pile_count != after.junk_pile_count

    @staticmethod
    def capture_all_players(game) -> dict[str, PlayerStateSnapshot]:
        """Capture all player states"""
        player_states = {}
        for player in game.players:
            player_states[player.id] = StateCapture.capture_player_state(player)
        return player_states

    @staticmethod
    def states_differ(before: PlayerStateSnapshot, after: PlayerStateSnapshot) -> bool:
        """Check if two player states differ meaningfully"""

        # Check basic counts
        if (
            before.hand_count != after.hand_count
            or before.score_pile_count != after.score_pile_count
            or before.achievement_count != after.achievement_count
        ):
            return True

        # Check board state
        if before.board_cards != after.board_cards:
            return True

        if before.board_splays != after.board_splays:
            return True

        # Check symbol counts (important for sharing detection)
        return before.symbol_counts != after.symbol_counts

    @staticmethod
    def game_states_differ(before: GameStateSnapshot, after: GameStateSnapshot) -> bool:
        """Check if two game states differ meaningfully"""

        # Check game-level changes
        if (
            before.current_age != after.current_age
            or before.actions_taken != after.actions_taken
            or before.current_player_id != after.current_player_id
        ):
            return True

        # Check age deck sizes
        if before.age_deck_sizes != after.age_deck_sizes:
            return True

        # Check achievements
        if before.achievements_available != after.achievements_available:
            return True

        # Check each player state
        for player_id in before.player_states:
            if player_id not in after.player_states:
                return True

            if StateCapture.states_differ(
                before.player_states[player_id], after.player_states[player_id]
            ):
                return True

        return False

    @staticmethod
    def get_state_changes(
        before: PlayerStateSnapshot, after: PlayerStateSnapshot
    ) -> dict[str, Any]:
        """Get detailed description of state changes"""
        changes = {}

        # Hand changes
        if before.hand_count != after.hand_count:
            changes["hand_count"] = {
                "before": before.hand_count,
                "after": after.hand_count,
                "change": after.hand_count - before.hand_count,
            }

        # Score pile changes
        if before.score_pile_count != after.score_pile_count:
            changes["score_pile_count"] = {
                "before": before.score_pile_count,
                "after": after.score_pile_count,
                "change": after.score_pile_count - before.score_pile_count,
            }

        # Achievement changes
        if before.achievement_count != after.achievement_count:
            changes["achievement_count"] = {
                "before": before.achievement_count,
                "after": after.achievement_count,
                "change": after.achievement_count - before.achievement_count,
            }

        # Board changes
        board_changes = {}
        for color in before.board_cards:
            before_cards = before.board_cards[color]
            after_cards = after.board_cards[color]

            if before_cards != after_cards:
                board_changes[color] = {
                    "before_count": len(before_cards),
                    "after_count": len(after_cards),
                    "change": len(after_cards) - len(before_cards),
                }

        if board_changes:
            changes["board_cards"] = board_changes

        # Splay changes
        splay_changes = {}
        for color in before.board_splays:
            if before.board_splays[color] != after.board_splays[color]:
                splay_changes[color] = {
                    "before": before.board_splays[color],
                    "after": after.board_splays[color],
                }

        if splay_changes:
            changes["board_splays"] = splay_changes

        # Symbol count changes
        symbol_changes = {}
        for symbol in before.symbol_counts:
            before_count = before.symbol_counts[symbol]
            after_count = after.symbol_counts[symbol]

            if before_count != after_count:
                symbol_changes[symbol] = {
                    "before": before_count,
                    "after": after_count,
                    "change": after_count - before_count,
                }

        if symbol_changes:
            changes["symbol_counts"] = symbol_changes

        return changes

    @staticmethod
    def get_game_changes(
        before: GameStateSnapshot, after: GameStateSnapshot
    ) -> dict[str, Any]:
        """Get detailed description of game state changes"""
        changes = {}

        # Game-level changes
        if before.current_age != after.current_age:
            changes["current_age"] = {
                "before": before.current_age,
                "after": after.current_age,
            }

        if before.actions_taken != after.actions_taken:
            changes["actions_taken"] = {
                "before": before.actions_taken,
                "after": after.actions_taken,
                "change": after.actions_taken - before.actions_taken,
            }

        if before.current_player_id != after.current_player_id:
            changes["current_player"] = {
                "before": before.current_player_id,
                "after": after.current_player_id,
            }

        # Age deck changes
        deck_changes = {}
        for age in before.age_deck_sizes:
            before_size = before.age_deck_sizes[age]
            after_size = after.age_deck_sizes.get(age, 0)

            if before_size != after_size:
                deck_changes[f"age_{age}"] = {
                    "before": before_size,
                    "after": after_size,
                    "change": after_size - before_size,
                }

        if deck_changes:
            changes["age_decks"] = deck_changes

        # Achievement changes
        if before.achievements_available != after.achievements_available:
            changes["achievements_available"] = {
                "before": before.achievements_available,
                "after": after.achievements_available,
                "change": after.achievements_available - before.achievements_available,
            }

        # Player changes
        player_changes = {}
        for player_id in before.player_states:
            if player_id in after.player_states:
                player_change = StateCapture.get_state_changes(
                    before.player_states[player_id], after.player_states[player_id]
                )
                if player_change:
                    player_name = before.player_states[player_id].player_name
                    player_changes[player_name] = player_change

        if player_changes:
            changes["players"] = player_changes

        return changes

    @staticmethod
    def has_meaningful_change(changes: dict[str, Any]) -> bool:
        """Check if changes represent meaningful game state modification"""

        # Any change to counts is meaningful
        meaningful_keys = [
            "hand_count",
            "score_pile_count",
            "achievement_count",
            "board_cards",
            "board_splays",
            "symbol_counts",
            "current_age",
            "current_player",
            "achievements_available",
        ]

        for key in meaningful_keys:
            if key in changes:
                return True

        # Check player changes
        if "players" in changes:
            for player_changes in changes["players"].values():
                if StateCapture.has_meaningful_change(player_changes):
                    return True

        return False
