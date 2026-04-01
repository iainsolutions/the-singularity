"""Async version of the game manager using state machines."""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import datetime
from typing import Any

from action_primitives.utils import (
    INTERACTION_DATA_FIELD,
    PLAYER_ID_FIELD,
    TARGET_PLAYER_FIELDS,
)
from dogma_v2.consolidated_executor import ConsolidatedDogmaExecutor
from logging_config import EventType, activity_logger, get_logger
from models.game import ActionType, Game, GamePhase
from models.player import Player
from redis_store import redis_store
from services import game_actions, game_helpers
from services.lock_service import get_lock_service


logger = get_logger("game_manager")


def safe_to_dict(obj):
    """Safely convert an object to dict format, handling both Pydantic v2 and legacy to_dict() methods."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    elif hasattr(obj, "to_dict"):
        return obj.to_dict()
    else:
        return obj


def safe_get(obj, attr, default=None):
    """Safely get attribute from Pydantic object or dictionary."""
    if hasattr(obj, attr):  # Pydantic object
        return getattr(obj, attr, default)
    elif isinstance(obj, dict):  # Dictionary
        return obj.get(attr, default)
    else:
        return default


def resolve_interaction_player_id(interaction: Any) -> str | None:
    """Extract the responding player identifier from an interaction payload.

    The precedence order mirrors how the frontend expects routing metadata:

    1. Top-level ``player_id`` field (newest dogma payloads)
    2. Nested ``data`` object ``player_id``
    3. Nested ``data`` object ``target_player_id`` (legacy demand/sharing)
    4. Nested ``data`` object ``source_player`` (final fallback)
    """

    if not interaction:
        return None

    candidate = safe_get(interaction, PLAYER_ID_FIELD)
    if candidate:
        return candidate

    data = safe_get(interaction, INTERACTION_DATA_FIELD, {})
    if isinstance(data, dict):
        for key in TARGET_PLAYER_FIELDS:
            candidate = data.get(key)
            if candidate:
                return candidate

    return None


class AsyncGameManager:
    """Async game manager using state machines"""

    def __init__(self, event_bus=None):
        self.games: dict[str, Game] = {}
        # Removed: old dogma state machines no longer needed
        # Removed: old demand processors no longer needed with v2 system
        # Removed: self.game_locks (replaced by Redis distributed locks)
        self._cleanup_task = None
        self._cleanup_interval = 300  # 5 minutes
        # Initialize consolidated dogma v2 executor
        self.dogma_executor = ConsolidatedDogmaExecutor(activity_logger)
        self.event_bus = event_bus  # Event bus for AI player communication
        self.lock_service = get_lock_service()

    def _format_game_state_for_frontend(
        self, game_state: dict, player_id: str | None = None
    ) -> dict:
        """Format game state for frontend. Delegates to services.game_helpers."""
        return game_helpers.format_game_state_for_frontend(game_state, player_id)

    async def _cleanup_game_resources(self, game_id: str):
        """Cleanup game resources. Delegates to services.game_helpers."""
        await game_helpers.cleanup_game_resources(game_id)

    @staticmethod
    def _player_in_game(game: Game, player_id: str | None) -> bool:
        """Check player in game. Delegates to services.game_helpers."""
        return game_helpers.player_in_game(game, player_id)

    def _sanitize_game_data(self, game_data: dict) -> dict:
        """
        Fix corrupted data structures (e.g., empty dicts that should be lists).

        Legacy Support: This handles data corruption from older versions where
        empty lists were serialized as empty dicts. Kept for backward compatibility
        with existing Redis data.
        """
        if not game_data:
            return game_data

        # List of paths that should always be lists, not dicts
        list_paths = [
            ("players", "*", "hand"),
            ("players", "*", "board", "blue_cards"),
            ("players", "*", "board", "red_cards"),
            ("players", "*", "board", "green_cards"),
            ("players", "*", "board", "yellow_cards"),
            ("players", "*", "board", "purple_cards"),
            ("players", "*", "score_pile"),
            ("players", "*", "achievements"),
            ("junk_pile",),
            ("action_log",),
            (
                "state",
                "setup_selections_made",
            ),  # Fix for setup_selections_made corruption
            ("state", "players_who_have_taken_first_turn"),  # Add this too for safety
        ]

        # Card-level list fields that may be corrupted
        card_list_fields = [
            "symbols",
            "dogma_effects",
            "symbol_positions",
        ]

        def fix_card_fields(card_data: dict) -> None:
            """Fix empty dicts to empty lists in card-level list fields."""
            if not isinstance(card_data, dict):
                return
            for field in card_list_fields:
                if (
                    field in card_data
                    and isinstance(card_data[field], dict)
                    and not card_data[field]
                ):
                    card_data[field] = []

        def fix_cards_in_list(cards_list: list) -> None:
            """Fix card fields in a list of cards."""
            if not isinstance(cards_list, list):
                return
            for card in cards_list:
                fix_card_fields(card)

        # Helper to fix empty dicts to empty lists
        def fix_path(data, path_parts):
            if not path_parts:
                return

            part = path_parts[0]
            if part == "*":
                # Wildcard - apply to all elements in list/dict
                if isinstance(data, list):
                    for item in data:
                        fix_path(item, path_parts[1:])
                elif isinstance(data, dict):
                    for key in data:
                        fix_path(data[key], path_parts[1:])
            else:
                # Specific key
                if isinstance(data, dict) and part in data:
                    if len(path_parts) == 1:
                        # This is the target field
                        if isinstance(data[part], dict) and not data[part]:
                            # Empty dict -> empty list
                            data[part] = []
                    else:
                        # Continue down the path
                        fix_path(data[part], path_parts[1:])

        # Apply fixes
        for path in list_paths:
            fix_path(game_data, path)

        # Fix card-level list fields in all card locations
        if "players" in game_data:
            for player in game_data["players"]:
                if isinstance(player, dict):
                    # Fix cards in hand
                    if "hand" in player and isinstance(player["hand"], list):
                        fix_cards_in_list(player["hand"])
                    # Fix cards in score_pile
                    if "score_pile" in player and isinstance(
                        player["score_pile"], list
                    ):
                        fix_cards_in_list(player["score_pile"])
                    # Fix cards in achievements
                    if "achievements" in player and isinstance(
                        player["achievements"], list
                    ):
                        fix_cards_in_list(player["achievements"])
                    # Fix cards in board stacks
                    if "board" in player and isinstance(player["board"], dict):
                        for color in [
                            "blue_cards",
                            "red_cards",
                            "green_cards",
                            "yellow_cards",
                            "purple_cards",
                        ]:
                            if color in player["board"] and isinstance(
                                player["board"][color], list
                            ):
                                fix_cards_in_list(player["board"][color])

        # Fix cards in junk_pile
        if "junk_pile" in game_data and isinstance(game_data["junk_pile"], list):
            fix_cards_in_list(game_data["junk_pile"])

        # Fix age_decks at TOP level (old format before deck_manager refactor)
        if "age_decks" in game_data and isinstance(game_data["age_decks"], dict):
            for age, deck in list(game_data["age_decks"].items()):
                if isinstance(deck, dict) and not deck:
                    game_data["age_decks"][age] = []
                elif isinstance(deck, list):
                    fix_cards_in_list(deck)

        # Fix achievement_cards at TOP level (old format)
        if "achievement_cards" in game_data and isinstance(
            game_data["achievement_cards"], dict
        ):
            for age, cards in list(game_data["achievement_cards"].items()):
                if isinstance(cards, dict) and not cards:
                    game_data["achievement_cards"][age] = []
                elif isinstance(cards, list):
                    fix_cards_in_list(cards)

        # Fix cards in deck_manager (new format with deck_manager wrapper)
        if "deck_manager" in game_data and isinstance(game_data["deck_manager"], dict):
            dm = game_data["deck_manager"]
            # Fix cards in age_decks (dict of age -> list of cards)
            if "age_decks" in dm and isinstance(dm["age_decks"], dict):
                for age, deck in list(dm["age_decks"].items()):
                    # Fix entire deck being {} instead of []
                    if isinstance(deck, dict) and not deck:
                        dm["age_decks"][age] = []
                    elif isinstance(deck, list):
                        fix_cards_in_list(deck)
            # Fix cards in achievement_cards (dict of age -> list of cards)
            if "achievement_cards" in dm and isinstance(dm["achievement_cards"], dict):
                for age, cards in list(dm["achievement_cards"].items()):
                    # Fix entire achievement list being {} instead of []
                    if isinstance(cards, dict) and not cards:
                        dm["achievement_cards"][age] = []
                    elif isinstance(cards, list):
                        fix_cards_in_list(cards)

        # Fix special_achievements at top level (flattened from deck_manager)
        if "special_achievements" in game_data and isinstance(game_data["special_achievements"], dict):
            for name, card in list(game_data["special_achievements"].items()):
                if isinstance(card, dict):
                    fix_card_fields(card)

        # Fix special_achievements inside deck_manager
        if "deck_manager" in game_data and isinstance(game_data["deck_manager"], dict):
            dm = game_data["deck_manager"]
            if "special_achievements" in dm and isinstance(dm["special_achievements"], dict):
                for name, card in list(dm["special_achievements"].items()):
                    if isinstance(card, dict):
                        fix_card_fields(card)

        # Fix action_log entries with state_changes as dict instead of list
        if "action_log" in game_data:
            for entry in game_data["action_log"]:
                if "state_changes" in entry:
                    # Convert dict to empty list (old data had {} instead of [])
                    if isinstance(entry["state_changes"], dict):
                        if not entry["state_changes"]:  # Empty dict
                            entry["state_changes"] = []
                        else:  # Non-empty dict - convert values to list
                            entry["state_changes"] = list(
                                entry["state_changes"].values()
                            )
                else:
                    # Ensure field exists
                    entry["state_changes"] = []

        return game_data

    def _refresh_card_definitions(self, game_data: dict) -> dict:
        """
        Refresh card definitions in loaded game data from BaseCards.json.

        This ensures that when games are loaded from Redis cache, they always
        have the latest card definitions from BaseCards.json, preventing stale
        card data (like removed compliance_reward sections) from persisting.

        Args:
            game_data: Game state dictionary loaded from Redis

        Returns:
            Updated game_data with refreshed card definitions
        """
        try:
            from data.cards import load_cards_from_json

            # Load fresh card definitions from BaseCards.json (and enabled expansions)
            base_cards = load_cards_from_json()
            if not base_cards:
                logger.warning("No cards loaded from BaseCards.json for refresh")
                return game_data

            # Create lookup dictionary for fast card retrieval by name
            card_lookup = {card.name: card for card in base_cards}

            # Track refresh stats for logging
            cards_refreshed = 0

            # Refresh cards in player hands
            if "players" in game_data:
                for player_data in game_data["players"]:
                    if "hand" in player_data and isinstance(player_data["hand"], list):
                        refreshed_hand = []
                        for card_dict in player_data["hand"]:
                            card_name = card_dict.get("name")
                            if card_name:
                                fresh_card = card_lookup.get(card_name)
                                if fresh_card:
                                    refreshed_hand.append(fresh_card.to_dict())
                                    cards_refreshed += 1
                                else:
                                    # Card not found - keep old definition
                                    refreshed_hand.append(card_dict)
                            else:
                                refreshed_hand.append(card_dict)
                        player_data["hand"] = refreshed_hand

                    # Refresh cards on player boards
                    if "board" in player_data:
                        for color in [
                            "blue_cards",
                            "red_cards",
                            "green_cards",
                            "yellow_cards",
                            "purple_cards",
                        ]:
                            if color in player_data["board"] and isinstance(
                                player_data["board"][color], list
                            ):
                                refreshed_stack = []
                                for card_dict in player_data["board"][color]:
                                    card_name = card_dict.get("name")
                                    if card_name:
                                        fresh_card = card_lookup.get(card_name)
                                        if fresh_card:
                                            refreshed_stack.append(fresh_card.to_dict())
                                            cards_refreshed += 1
                                        else:
                                            refreshed_stack.append(card_dict)
                                    else:
                                        refreshed_stack.append(card_dict)
                                player_data["board"][color] = refreshed_stack

                    # Refresh cards in score pile
                    if "score_pile" in player_data and isinstance(
                        player_data["score_pile"], list
                    ):
                        refreshed_score = []
                        for card_dict in player_data["score_pile"]:
                            card_name = card_dict.get("name")
                            if card_name:
                                fresh_card = card_lookup.get(card_name)
                                if fresh_card:
                                    refreshed_score.append(fresh_card.to_dict())
                                    cards_refreshed += 1
                                else:
                                    refreshed_score.append(card_dict)
                            else:
                                refreshed_score.append(card_dict)
                        player_data["score_pile"] = refreshed_score

                    # Refresh achievements
                    if "achievements" in player_data and isinstance(
                        player_data["achievements"], list
                    ):
                        refreshed_achievements = []
                        for card_dict in player_data["achievements"]:
                            card_name = card_dict.get("name")
                            if card_name:
                                fresh_card = card_lookup.get(card_name)
                                if fresh_card:
                                    refreshed_achievements.append(fresh_card.to_dict())
                                    cards_refreshed += 1
                                else:
                                    refreshed_achievements.append(card_dict)
                            else:
                                refreshed_achievements.append(card_dict)
                        player_data["achievements"] = refreshed_achievements

            # Refresh age decks
            if "age_decks" in game_data:
                for age_key, cards_list in game_data["age_decks"].items():
                    if isinstance(cards_list, list):
                        refreshed_deck = []
                        for card_dict in cards_list:
                            card_name = card_dict.get("name")
                            if card_name:
                                fresh_card = card_lookup.get(card_name)
                                if fresh_card:
                                    refreshed_deck.append(fresh_card.to_dict())
                                    cards_refreshed += 1
                                else:
                                    refreshed_deck.append(card_dict)
                            else:
                                refreshed_deck.append(card_dict)
                        game_data["age_decks"][age_key] = refreshed_deck

            # Refresh achievement cards
            if "achievement_cards" in game_data:
                for age_key, cards_list in game_data["achievement_cards"].items():
                    if isinstance(cards_list, list):
                        refreshed_achievements = []
                        for card_dict in cards_list:
                            card_name = card_dict.get("name")
                            if card_name:
                                fresh_card = card_lookup.get(card_name)
                                if fresh_card:
                                    refreshed_achievements.append(fresh_card.to_dict())
                                    cards_refreshed += 1
                                else:
                                    refreshed_achievements.append(card_dict)
                            else:
                                refreshed_achievements.append(card_dict)
                        game_data["achievement_cards"][age_key] = refreshed_achievements

            # Refresh junk pile
            if "junk_pile" in game_data and isinstance(game_data["junk_pile"], list):
                refreshed_junk = []
                for card_dict in game_data["junk_pile"]:
                    card_name = card_dict.get("name")
                    if card_name:
                        fresh_card = card_lookup.get(card_name)
                        if fresh_card:
                            refreshed_junk.append(fresh_card.to_dict())
                            cards_refreshed += 1
                        else:
                            refreshed_junk.append(card_dict)
                    else:
                        refreshed_junk.append(card_dict)
                game_data["junk_pile"] = refreshed_junk

            logger.debug(
                f"Refreshed {cards_refreshed} card definitions from BaseCards.json"
            )

        except Exception as e:
            logger.error(f"Error refreshing card definitions: {e}", exc_info=True)
            # Don't fail the load - just log the error and return unmodified data

        return game_data

    async def initialize(self):
        """Initialize the game manager and start background tasks"""
        # Connect to Redis
        await redis_store.connect()

        # Load existing games from Redis
        game_ids = await redis_store.list_active_games()
        for game_id in game_ids:
            game_data = await redis_store.load_game(game_id)
            if game_data:
                try:
                    # Sanitize data before validation (fixes corrupted data structures)
                    game_data = self._sanitize_game_data(game_data)

                    # Refresh card definitions from BaseCards.json
                    # This ensures games always have latest card definitions
                    game_data = self._refresh_card_definitions(game_data)

                    game = Game.model_validate(game_data)
                    self.games[game_id] = game
                    logger.info(f"Loaded game {game_id} from Redis")

                    # Note: AI player reconnection handled by ai_bootstrap.py after init
                    # (keeps game manager player-agnostic)

                except Exception as e:
                    logger.error(f"Failed to load game {game_id}: {e}")

        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info(
            f"AsyncGameManager initialized with {len(self.games)} games from storage"
        )

    async def shutdown(self):
        """Shutdown the game manager and cleanup"""
        # Save all games before shutdown
        for game_id, game in self.games.items():
            await redis_store.save_game(game_id, game.to_dict())

        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        # Disconnect from Redis
        await redis_store.disconnect()
        logger.info("AsyncGameManager shutdown complete")

    async def _cleanup_loop(self):
        """Background task to cleanup abandoned games"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_abandoned_games()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_abandoned_games(self):
        """Remove games that have been inactive for too long"""
        from datetime import timedelta

        current_time = datetime.now()
        games_to_remove = []

        for game_id, game in self.games.items():
            # Check if game has been inactive for more than 1 hour
            if hasattr(game, "last_activity"):
                time_since_activity = current_time - game.last_activity
                if time_since_activity > timedelta(hours=1):
                    games_to_remove.append(game_id)
            elif game.phase == GamePhase.FINISHED:
                # Remove finished games after 5 minutes
                # Since Game model doesn't have finished_time, use last_activity
                if hasattr(game, "last_activity"):
                    time_since_finished = current_time - game.last_activity
                    if time_since_finished > timedelta(minutes=5):
                        games_to_remove.append(game_id)
                else:
                    # If no last_activity, remove immediately
                    games_to_remove.append(game_id)

        for game_id in games_to_remove:
            # Note: Redis locks don't need manual cleanup

            del self.games[game_id]
            logger.info(f"Cleaned up abandoned game: {game_id}")

    # Removed: _get_game_lock (replaced by LockService)

    async def create_game(
        self,
        creator_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new game."""
        game = Game()
        self.games[game.game_id] = game

        # Save to Redis
        await redis_store.save_game(game.game_id, game.to_dict())

        # Log game creation
        activity_logger.log_game_event(
            EventType.GAME_CREATED, game_id=game.game_id, data={"creator": creator_name}
        )

        if creator_name:
            player = Player(name=creator_name)
            game.add_player(player)

            # Log player joined
            activity_logger.log_game_event(
                EventType.PLAYER_JOINED,
                game_id=game.game_id,
                player_id=player.id,
                data={"player_name": creator_name},
            )

            return {
                "success": True,
                "game_id": game.game_id,
                "player_id": player.id,
                "game_state": self._format_game_state_for_frontend(game.to_dict()),
            }

        return {
            "success": True,
            "game_id": game.game_id,
            "game_state": self._format_game_state_for_frontend(game.to_dict()),
        }

    async def join_game(self, game_id: str, player_name: str) -> dict[str, Any]:
        """Join an existing game"""
        game = self.games.get(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        # Update last activity
        game.last_activity = datetime.now()

        # Use lock to prevent race conditions during join
        async with get_lock_service().acquire_lock(game_id):
            if game.phase != GamePhase.WAITING_FOR_PLAYERS:
                return {"success": False, "error": "Game already started"}

            if len(game.players) >= 4:
                return {"success": False, "error": "Game is full"}

            player = Player(name=player_name)
            game.add_player(player)

            # Save to Redis while holding lock
            await redis_store.save_game(game_id, game.to_dict())

            return {
                "success": True,
                "player_id": player.id,
                "game_state": self._format_game_state_for_frontend(game.to_dict()),
            }

    async def start_game(self, game_id: str) -> dict[str, Any]:
        """Start a game"""
        game = self.games.get(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        # Update last activity
        game.last_activity = datetime.now()

        # Use lock to prevent race conditions during start
        async with get_lock_service().acquire_lock(game_id):
            if len(game.players) < 2:
                return {"success": False, "error": "Cannot start game"}

            game.start_game()

            # Save to Redis while holding lock
            await redis_store.save_game(game_id, game.to_dict())

            # Log game started
            activity_logger.log_game_event(
                EventType.GAME_STARTED,
                game_id=game_id,
                data={
                    "player_count": len(game.players),
                    "players": [p.name for p in game.players],
                },
            )

            # Log first turn started for the starting player
            first_player = game.players[game.state.current_player_index]
            activity_logger.log_game_event(
                event_type=EventType.TURN_STARTED,
                game_id=game.game_id,
                player_id=first_player.id,
                data={
                    "turn_number": game.state.turn_number,
                    "actions_remaining": game.state.actions_remaining,
                },
                message=f"{first_player.name} started their turn",
            )

        # Return game state
        # Note: AI players will be notified via broadcast_game_update() in the router
        return {
            "success": True,
            "game_state": self._format_game_state_for_frontend(game.to_dict()),
        }

    async def make_setup_selection(
        self, game_id: str, player_id: str, card_identifier: str
    ) -> dict[str, Any]:
        """Handle a player's setup card selection using card ID or name (backward compat)"""
        game = self.get_game(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        # Update last activity
        game.last_activity = datetime.now()

        # Use lock for setup selections
        async with get_lock_service().acquire_lock(game_id):
            if not game.can_make_setup_selection(player_id):
                return {"success": False, "error": "Cannot make setup selection"}

            try:
                # Use ID-based method exclusively
                game.make_setup_selection_by_id(player_id, card_identifier)
            except ValueError as e:
                return {"success": False, "error": str(e)}

            # Save to Redis while holding lock
            await redis_store.save_game(game_id, game.to_dict())

            return {
                "success": True,
                "game_state": self._format_game_state_for_frontend(game.to_dict()),
            }

    def get_game(self, game_id: str) -> Game | None:
        """Get game object by ID"""
        return self.games.get(game_id)

    async def load_game_from_storage(self, game_id: str) -> Game | None:
        """Load fresh game state from Redis storage (bypasses in-memory cache)."""
        game_data = await redis_store.load_game(game_id)
        if not game_data:
            return None
        game_data = self._sanitize_game_data(game_data)
        game = Game.model_validate(game_data)
        # Update in-memory cache
        self.games[game_id] = game
        return game

    async def get_game_state(self, game_id: str) -> dict[str, Any]:
        """Get current game state"""
        game = self.games.get(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        return {
            "success": True,
            "game": self._format_game_state_for_frontend(game.to_dict()),
        }

    def list_games(self) -> list[dict[str, Any]]:
        """List all active games"""
        games_list = []
        for game_id, game in self.games.items():
            games_list.append(
                {
                    "game_id": game_id,
                    "phase": game.phase.value if game.phase else "unknown",
                    "players": [p.name for p in game.players],
                    "player_count": len(game.players),
                    "created_at": getattr(game, "created_at", None),
                }
            )
        return games_list

    async def perform_action(
        self, game_id: str, action_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Async action handler with optimistic locking for critical operations"""
        start_time = time.time()

        # Track version for optimistic locking on dogma operations
        game_version = None
        use_optimistic_locking = action_data.get("action_type") in [
            "dogma",
            "dogma_response",
        ]

        # CRITICAL: For dogma actions, reload from Redis to ensure data freshness
        # and get version for optimistic locking to prevent concurrent modifications
        # EXCEPTION: Do NOT reload when resuming a suspended transaction (dogma_response)
        # because the suspended transaction's in-memory game object has uncommitted changes
        skip_reload = False
        if action_data.get("action_type") == "dogma_response":
            # Check if we have a suspended transaction for this game
            current_game = self.games.get(game_id)
            if (
                current_game
                and current_game.state
                and current_game.state.pending_dogma_action
            ):
                skip_reload = True
                logger.info(
                    "Skipping Redis reload for dogma_response - using in-memory game with pending transaction"
                )

        if use_optimistic_locking and not skip_reload:
            game_data = await redis_store.load_game(game_id)
            if game_data:
                try:
                    # Sanitize data before validation (fixes corrupted empty dicts)
                    game_data = self._sanitize_game_data(game_data)
                    # Replace our in-memory copy with fresh data from Redis
                    self.games[game_id] = Game.model_validate(game_data)
                    # Track version for optimistic locking
                    game_version = game_data.get("version", 0)
                    logger.debug(
                        f"Reloaded game {game_id} from Redis for {action_data.get('action_type')} (version: {game_version})"
                    )
                except Exception as e:
                    logger.error(f"Failed to reload game {game_id}: {e}")

        game = self.games.get(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        # Update activity timestamp to prevent cleanup
        game.last_activity = datetime.now()

        # CRITICAL: Acquire per-game lock to prevent race conditions
        # Multiple players might try to perform actions simultaneously on the same game.
        # Without locking, this could lead to:
        # - Lost updates (one action overwrites another)
        # - Inconsistent game state
        # - Turn order violations
        # - Duplicate resource allocation
        # CRITICAL: Acquire per-game lock to prevent race conditions
        # Multiple players might try to perform actions simultaneously on the same game.
        # Without locking, this could lead to:
        # - Lost updates (one action overwrites another)
        # - Inconsistent game state
        # - Turn order violations
        # - Duplicate resource allocation
        async with get_lock_service().acquire_lock(game_id):
            # All game modifications happen within this lock

            # Extract and validate action parameters
            action_type = action_data.get("action_type")
            player_id = action_data.get("player_id")

            if not player_id:
                return {"success": False, "error": "Player ID required"}

            player = game.get_player_by_id(player_id)

            if not player:
                return {"success": False, "error": "Player not found"}

            # Phase validation - ensure we're in the correct game phase for actions
            if game.phase == GamePhase.SETUP_CARD_SELECTION:
                return {
                    "success": False,
                    "error": "Only setup selections allowed during setup phase",
                }

            # Turn validation - most actions require it to be the player's turn
            # Exception: dogma_response can happen during opponent's turn (demand effects)
            # Exception: turn_start, showcase_response, dig_response (Artifacts expansion interactions)
            if (
                action_type
                not in [
                    "dogma_response",
                    "turn_start",
                    "showcase_response",
                    "dig_response",
                ]
                and game.phase == GamePhase.PLAYING
                and game.state.current_player_index != game.players.index(player)
            ):
                return {"success": False, "error": "Not your turn"}

            # Interaction validation - block new actions if there's a pending interaction
            # Exception: dogma_response, showcase_response, dig_response resolve pending interactions
            if (
                action_type
                not in ["dogma_response", "showcase_response", "dig_response"]
                and game.state.pending_dogma_action is not None
            ):
                # SAFEGUARD: If there's no active transaction matching the pending action, clear it
                try:
                    pending_tx = (
                        game.state.pending_dogma_action.context.get("transaction_id")
                        if hasattr(game.state.pending_dogma_action, "context")
                        else None
                    )
                    active_ids = (
                        list(
                            self.dogma_executor.transaction_manager.active_transactions.keys()
                        )
                        if hasattr(self.dogma_executor, "transaction_manager")
                        else []
                    )
                    if pending_tx and pending_tx not in active_ids:
                        logger.warning(
                            f"Clearing stale pending_dogma_action with non-active transaction {pending_tx}"
                        )
                        game.state.pending_dogma_action = None
                except Exception:
                    # If any error occurs in the safeguard, proceed with original behavior
                    pass

                if game.state.pending_dogma_action is not None:
                    return {
                        "success": False,
                        "error": "Cannot perform actions while interaction is pending",
                    }

            # Action count validation - players have limited actions per turn
            # Exceptions: end_turn, dogma_response, turn_start, showcase_response, dig_response
            if (
                action_type
                not in [
                    "end_turn",
                    "dogma_response",
                    "turn_start",
                    "showcase_response",
                    "dig_response",
                ]
                and game.phase == GamePhase.PLAYING
                and game.state.actions_remaining <= 0
            ):
                return {"success": False, "error": "No actions remaining"}

            try:
                # Reset Monument tracking before actions that could score/tuck cards
                # Monument checks cards scored/tucked in a single action, not across multiple actions
                if action_type in ["dogma", "dogma_response"]:
                    try:
                        from special_achievements import special_achievement_checker

                        special_achievement_checker.reset_turn_tracking(
                            game.game_id, player.id
                        )
                    except ImportError:
                        # Special achievements module not available - continue without error
                        pass

                # Dispatch to appropriate action handler
                result = None
                if action_type == "draw":
                    result = await self._draw_card(game, player)
                elif action_type == "meld":
                    # Support both card_id (preferred, unique) and card_name (legacy, ambiguous)
                    card_identifier = action_data.get("card_id") or action_data.get(
                        "card_name"
                    )
                    if not card_identifier:
                        result = {"success": False, "error": "Card identifier required"}
                    else:
                        result = await self._meld_card(game, player, card_identifier)
                elif action_type == "dogma":
                    # Dogma uses card_name since it targets cards on the board (found by name)
                    card_name = action_data.get("card_name")
                    if not card_name:
                        result = {
                            "success": False,
                            "error": "Card name required for dogma",
                        }
                    else:
                        result = await self._execute_dogma(
                            game, player, card_name
                        )
                elif action_type == "achieve":
                    age = action_data.get("age")

                    if age is None:
                        result = {
                            "success": False,
                            "error": "Age required for achievement",
                        }
                    else:
                        result = await self._claim_achievement(game, player, age)
                elif action_type == "dogma_response":
                    result = await self._handle_dogma_response(
                        game, player, action_data
                    )
                elif action_type == "meld_response":
                    result = await self._handle_meld_interaction_response(
                        game, player, action_data
                    )
                elif action_type == "end_turn":
                    result = await self._end_turn(game, player)
                # ARTIFACTS EXPANSION: New action types
                elif action_type == "turn_start":
                    result = await self._handle_turn_start(game, player)
                elif action_type == "showcase_response":
                    try:
                        result = await self._handle_showcase_response(
                            game, player, action_data
                        )
                    except Exception as e:
                        logger.error(
                            f"Error handling showcase response for {player.name}: {e}",
                            exc_info=True,
                        )
                        result = {
                            "success": False,
                            "error": "Failed to process showcase response",
                        }
                elif action_type == "dig_response":
                    try:
                        result = await self._handle_dig_response(
                            game, player, action_data
                        )
                    except Exception as e:
                        logger.error(
                            f"Error handling dig response for {player.name}: {e}",
                            exc_info=True,
                        )
                        result = {
                            "success": False,
                            "error": "Failed to process dig response",
                        }
                elif action_type == "meld_from_museum":
                    museum_id = action_data.get("museum_id")
                    if not museum_id:
                        result = {"success": False, "error": "Museum ID required"}
                    else:
                        try:
                            result = await self._meld_from_museum(
                                game, player, museum_id
                            )
                        except ValueError as e:
                            # Handle validation errors from museum manager
                            logger.warning(
                                f"Meld from museum validation error for {player.name}: {e}"
                            )
                            result = {"success": False, "error": str(e)}
                        except Exception as e:
                            # Catch any unexpected errors
                            logger.error(
                                f"Unexpected error in meld_from_museum for {player.name}: {e}",
                                exc_info=True,
                            )
                            result = {
                                "success": False,
                                "error": "Failed to meld from museum",
                            }
                else:
                    result = {"success": False, "error": "Invalid action type"}

                # Post-action special achievement checking
                # Special achievements are awarded for specific combinations of actions/state
                if result.get("success") and action_type in [
                    "meld",
                    "dogma",
                    "dogma_response",
                ]:
                    try:
                        from special_achievements import special_achievement_checker

                        earned = special_achievement_checker.check_all_achievements(
                            game, player
                        )
                        if earned:
                            result["special_achievements_earned"] = earned

                            # Check for victory after special achievement(s) are awarded
                            # Victory conditions: 6 achievements for 2-3 players, 5 for 4 players
                            required_achievements = {2: 6, 3: 5, 4: 4}.get(
                                len(game.players), 6
                            )
                            logger.debug(
                                f"Checking victory: {player.name} has {len(player.achievements)} achievements, needs {required_achievements} for {len(game.players)} players"
                            )
                            if (
                                len(player.achievements) >= required_achievements
                                and game.phase != GamePhase.FINISHED
                            ):
                                game.winner = player
                                game.phase = GamePhase.FINISHED

                                # Cleanup AI Event Subscribers to prevent resource leaks
                                await self._cleanup_game_resources(game.game_id)

                                activity_logger.log_game_event(
                                    game_id=game.game_id,
                                    event_type=EventType.GAME_ENDED,
                                    data={
                                        "winner": player.name,
                                        "victory_type": "achievements",
                                        "achievement_count": len(player.achievements),
                                        "final_phase": "FINISHED",
                                    },
                                )
                                logger.info(
                                    f"GAME OVER: Game {game.game_id} won by {player.name} with {len(player.achievements)} achievements (needed {required_achievements} for {len(game.players)} players)"
                                )
                                result["game_over"] = True
                                result["winner"] = player.name

                        # Reset Monument tracking after each action (not just at end of turn)
                        # Monument checks cards scored/tucked in a single action, not across a turn
                        special_achievement_checker.reset_turn_tracking(
                            game.game_id, player.id
                        )
                    except ImportError:
                        # Special achievements module not available - continue without error
                        pass

                # Performance monitoring and activity logging
                duration_ms = (time.time() - start_time) * 1000
                if action_type:  # Only log if we have a valid action type
                    activity_logger.log_player_action(
                        game_id=game_id,
                        player_id=player_id,
                        action_type=str(action_type),  # Ensure it's a string
                        action_data=action_data,
                        result={"success": result.get("success", False)},
                        duration_ms=duration_ms,
                    )

                # CRITICAL: Persist game state to Redis after successful actions
                # Use optimistic locking for dogma operations to prevent race conditions
                if result.get("success"):
                    # DEBUG: Log action_log state before saving
                    if action_type == "dogma" and game.action_log:
                        last_entry = game.action_log[-1]
                        logger.info(
                            f"PRE-SAVE CHECK: Last action log entry has {len(last_entry.state_changes)} state_changes"
                        )
                        logger.info(
                            f"PRE-SAVE CHECK: Entry description: {last_entry.description}"
                        )

                    if use_optimistic_locking and game_version is not None:
                        # Try to save with version check for dogma operations
                        # DEBUG: Check state_changes right before serialization
                        if action_type == "dogma" and game.action_log:
                            game_dict = game.to_dict()
                            if game_dict.get("action_log"):
                                last_log = game_dict["action_log"][-1]
                                logger.info(
                                    f"PRE-SERIALIZE: Last log entry in dict has {len(last_log.get('state_changes', []))} state_changes"
                                )

                        max_retries = 3
                        for retry in range(max_retries):
                            (
                                success,
                                message,
                            ) = await redis_store.save_game_with_version_check(
                                game_id, game.to_dict(), game_version
                            )
                            if success:
                                logger.debug(
                                    f"Saved game {game_id} with optimistic lock: {message}"
                                )
                                break
                            elif retry < max_retries - 1:
                                # Version conflict - reload and retry
                                logger.warning(
                                    f"Version conflict on save, retrying ({retry + 1}/{max_retries}): {message}"
                                )
                                game_data = await redis_store.load_game(game_id)
                                if game_data:
                                    game_version = game_data.get("version", 0)
                                    # Re-apply our changes to the fresh data
                                    # This is safe because we're still holding the lock
                                await asyncio.sleep(
                                    0.1 * (retry + 1)
                                )  # Exponential backoff
                            else:
                                logger.error(
                                    f"Failed to save game {game_id} after {max_retries} retries: {message}"
                                )
                                result["warning"] = (
                                    "Game saved but version conflict detected"
                                )
                    else:
                        # Regular save for non-dogma actions
                        await redis_store.save_game(game_id, game.to_dict())

            except Exception as e:
                # Comprehensive error handling with logging
                logger.error(f"Action failed for game {game_id}: {e}")
                activity_logger.log_error(
                    f"Action failed: {action_type}",
                    error=e,
                    game_id=game_id,
                    player_id=player_id,
                )
                result = {"success": False, "error": str(e)}

        return result

    async def _execute_dogma(
        self,
        game: Game,
        player: Player,
        card_name: str,
    ) -> dict[str, Any]:
        """Execute dogma using dogma v2 executor."""
        logger.error(
            f"_execute_dogma ENTRY: Starting dogma for {card_name} by {player.name}"
        )
        logger.info(f"_execute_dogma: Starting dogma for {card_name} by {player.name}")

        # Check if card is on player's board and get the card object
        # Support both card_id and name for robust card identification
        card = None
        for board_card in player.board.get_top_cards():
            # Check card_id first (preferred stable identifier), then fall back to name
            if (
                hasattr(board_card, "card_id")
                and board_card.card_id
                and board_card.card_id == card_name
            ) or board_card.name == card_name:
                card = board_card
                break

        # ARTIFACTS EXPANSION: Also check if card is on display for showcase dogma
        if not card and hasattr(player, "display") and player.display:
            if (
                hasattr(player.display, "card_id")
                and player.display.card_id
                and player.display.card_id == card_name
            ) or player.display.name == card_name:
                card = player.display

        if not card:
            return {"success": False, "error": "Card not on your board"}

        if not card.has_dogma():
            return {
                "success": False,
                "error": "Card has no dogma effects",
            }

        # Add to action log

        try:
            # Pre-log the activation so the UI always reflects the click
            game.add_log_entry(
                player_name=player.name,
                action_type=ActionType.DOGMA,
                description=f"activated {card_name}",
            )

            # Log action event for real-time UI updates
            activity_logger.log_game_event(
                event_type=EventType.ACTION_DOGMA,
                game_id=game.game_id,
                player_id=player.id,
                data={"card_name": card_name},
            )

            # Fire activity event for UI activity panel with dogma texts
            try:
                dogma_texts = []
                try:
                    if hasattr(card, "dogma_effects") and card.dogma_effects:
                        for eff in card.dogma_effects:
                            txt = getattr(eff, "text", None) or getattr(
                                eff, "description", None
                            )
                            if txt:
                                dogma_texts.append(str(txt))
                except Exception:
                    pass

                activity_logger.log_game_event(
                    event_type=EventType.DOGMA_STARTED,
                    game_id=game.game_id,
                    player_id=player.id,
                    data={
                        "card_name": card_name,
                        "dogma_texts": dogma_texts,
                        "effect_count": len(getattr(card, "dogma_effects", []) or []),
                    },
                    message=f"Dogma started: {card_name}",
                )
            except Exception:
                pass

            # Execute dogma
            result = self.dogma_executor.execute_dogma(
                game, player, card
            )

            # AsyncGameManager Hook: Log sharing decisions and activity
            try:
                self._log_sharing_activity(result, card_name, player)
            except Exception as log_error:
                logger.warning(f"Failed to log sharing activity: {log_error}")

            # Update the most recent log entry with transaction/context info when available
            # CRITICAL: Modify result.context.game.action_log since that's what gets returned to client
            try:
                # Use result.context.game instead of game - that's what gets returned in response
                action_log = (
                    result.context.game.action_log
                    if result.context and result.context.game
                    else game.action_log
                )
                if action_log:
                    last = action_log[-1]
                    last.transaction_id = (
                        result.transaction.id if result.transaction else None
                    )
                    last.context_snapshot = {
                        "card_name": card_name,
                        "success": result.success,
                        "interaction_required": result.interaction_required,
                        "phase_count": (
                            len(result.transaction.phases_executed)
                            if result.transaction
                            and hasattr(result.transaction, "phases_executed")
                            else 0
                        ),
                    }
                    # CRITICAL FIX: Use state_tracker.get_changes_as_dict() for detailed state changes
                    # This includes player names and all execution details
                    try:
                        if result.context and hasattr(result.context, "state_tracker"):
                            # Get detailed state changes from state tracker with player names
                            last.state_changes = (
                                result.context.state_tracker.get_changes_as_dict()
                            )
                            logger.debug(
                                f"STATE CHANGES: Assigned {len(last.state_changes)} state changes from tracker"
                            )
                        else:
                            last.state_changes = []
                            logger.debug(
                                "STATE CHANGES: No state tracker available, using empty list"
                            )
                    except Exception as extract_error:
                        logger.error(
                            f"STATE CHANGES: Error extracting state changes: {extract_error}",
                            exc_info=True,
                        )
                        # Preserve existing state_changes if they exist
                        if (
                            not hasattr(last, "state_changes")
                            or last.state_changes is None
                        ):
                            last.state_changes = []
            except Exception as e:
                logger.error(
                    f"STATE CHANGES: Error extracting state changes: {e}",
                    exc_info=True,
                )

            if result.success:
                if result.interaction_required:
                    # Check if this is an auto_resume suspension (for UI refresh)
                    auto_resume = result.context.get_variable("auto_resume", False)

                    # Dogma needs player interaction (or auto-resume)
                    # Store transaction for later resume
                    from models.game import PendingDogmaAction

                    # Create response object
                    response = {
                        "success": True,
                        "action": "dogma_requires_response",
                        "game_state": self._format_game_state_for_frontend(
                            result.context.game.to_dict()
                        ),
                    }

                    # Check for unified interaction first (new pattern)
                    if result.interaction_request:
                        interaction_payload = safe_to_dict(result.interaction_request)
                        target_player_id = resolve_interaction_player_id(
                            interaction_payload
                        )
                        if not target_player_id:
                            logger.error(
                                "Dogma interaction payload missing player_id",
                                extra={
                                    "card_name": card_name,
                                    "transaction_id": result.transaction.id,
                                    "interaction_payload": interaction_payload,
                                },
                            )
                            return {
                                "success": False,
                                "error": "Dogma interaction is missing target player information",
                                "game_state": self._format_game_state_for_frontend(
                                    result.context.game.to_dict()
                                ),
                            }
                        if not self._player_in_game(game, target_player_id):
                            logger.error(
                                "Dogma interaction target is not part of this game",
                                extra={
                                    "card_name": card_name,
                                    "transaction_id": result.transaction.id,
                                    "target_player_id": target_player_id,
                                    "game_players": [p.id for p in game.players],
                                },
                            )
                            return {
                                "success": False,
                                "error": "Dogma interaction referenced a player outside this game",
                                "game_state": self._format_game_state_for_frontend(
                                    result.context.game.to_dict()
                                ),
                            }
                        # CRITICAL: Set pending_dogma_action on result.context.game.state
                        # NOT on game.state directly, because _sync_game_state_safely()
                        # will overwrite game.state with result.context.game.state.
                        # Setting it on the context game ensures it survives the sync.
                        pending_action = PendingDogmaAction(
                            card_name=card_name,
                            effect_index=0,
                            original_player_id=player.id,
                            target_player_id=target_player_id,
                            action_type="dogma_v2_interaction",
                            context={
                                "transaction_id": result.transaction.id,
                                "interaction_data": interaction_payload,
                            },
                        )
                        result.context.game.state.pending_dogma_action = pending_action

                        # CRITICAL FIX: Regenerate game_state AFTER setting pending_dogma_action.
                        # The initial response["game_state"] was captured before pending_dogma_action
                        # was set, so it had null. The frontend's action_performed handler clears
                        # enhancedPendingAction if game_state has no pending_dogma_action, causing
                        # the second (and subsequent) dogma interactions to be silently cleared.
                        response["game_state"] = self._format_game_state_for_frontend(
                            result.context.game.to_dict()
                        )

                        # Add unified interaction to response
                        # HYBRID SOLUTION: Merge StandardInteractionBuilder payload with routing metadata
                        # This ensures both WebSocket validation (needs dogma_interaction format)
                        # and HTTP targeting (needs player_id) work correctly
                        response["interaction_request"] = interaction_payload
                        response["interaction_type"] = result.interaction_type
                        response["transaction_id"] = result.transaction.id

                        logger.info(
                            f"Dogma requires {result.interaction_type} interaction. Target player: {result.interaction_request.player_id}"
                        )

                        # Activity log: interaction required with interaction payload
                        with contextlib.suppress(Exception):
                            activity_logger.log_game_event(
                                event_type=EventType.DOGMA_INTERACTION_REQUIRED,
                                game_id=game.game_id,
                                player_id=target_player_id,
                                data={
                                    "card_name": card_name,
                                    "interaction_type": result.interaction_type,
                                    "interaction": safe_get(
                                        interaction_payload, "data", interaction_payload
                                    ),
                                },
                                message=f"Interaction required for {card_name}",
                            )

                        # Publish player_interaction event to Event Bus for AI players
                        # PERFORMANCE FIX: Send minimal data - AI fetches game from game_manager
                        if self.event_bus:
                            logger.info(
                                f"DEBUG: Publishing player_interaction via event_bus instance {id(self.event_bus)}, "
                                f"game_manager instance {id(self)}"
                            )
                            await self.event_bus.publish(
                                game_id=game.game_id,
                                event_type="player_interaction",
                                data={
                                    "player_id": target_player_id,
                                    "interaction": interaction_payload,
                                    # Don't send full game_state to prevent "Invalid string length"
                                },
                                source="async_game_manager.dogma_v2",
                            )

                    # CRITICAL FIX: Sync game state changes before suspension
                    # When dogma suspends for interaction, we MUST sync the working copy
                    # back to the persistent game object. Otherwise, changes made before
                    # suspension (like melding cards in Domestication) will be lost when
                    # the game is reloaded from Redis before the player responds.
                    self._sync_game_state_safely(game, result.context.game)
                    logger.debug(
                        "Synced game state before dogma suspension (initial execution)"
                    )

                    # CRITICAL FIX: Broadcast updated game state to frontend
                    # When dogma suspends for interaction, the frontend needs the updated
                    # game state (e.g., drawn cards) BEFORE showing the interaction UI.
                    # Otherwise, users can't see the cards they just drew.
                    try:
                        from services.broadcast_service import get_broadcast_service

                        broadcast_service = get_broadcast_service()
                        await broadcast_service.broadcast_game_update(
                            game_id=game.game_id,
                            message_type="game_state_updated",
                            data={
                                "game_state": self._format_game_state_for_frontend(
                                    game.to_dict()
                                )
                            },
                        )
                        logger.debug(
                            "Broadcast game_state_updated before dogma suspension"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to broadcast game state before suspension: {e}",
                            exc_info=True,
                        )

                    return response
                else:
                    # Dogma completed successfully - apply state changes to the modified game object
                    result.context.game.state.pending_dogma_action = None

                    # Decrement actions
                    if result.context.game.state.actions_remaining > 0:
                        result.context.game.state.actions_remaining -= 1

                    # Auto-advance turn if needed
                    self._advance_turn_if_needed(result.context.game)

                    # Sync changes back to original game for Redis persistence
                    # Use defensive copying to prevent immutable object contamination
                    self._sync_game_state_safely(game, result.context.game)

                    # Activity log: dogma completed with results
                    with contextlib.suppress(Exception):
                        activity_logger.log_game_event(
                            event_type=EventType.DOGMA_COMPLETED,
                            game_id=game.game_id,
                            player_id=player.id,
                            data={
                                "card_name": (
                                    result.context.card.name
                                    if result.context and result.context.card
                                    else card_name
                                ),
                                "results": result.results or [],
                            },
                            message=f"Dogma completed: {card_name}",
                        )

                    return {
                        "success": True,
                        "action": "dogma",
                        "card_name": result.context.card.name,
                        "results": result.results,
                        "game_state": self._format_game_state_for_frontend(
                            result.context.game.to_dict()
                        ),
                    }
            else:
                # Dogma execution failed
                # Activity log: dogma failed
                with contextlib.suppress(Exception):
                    activity_logger.log_game_event(
                        event_type=EventType.DOGMA_FAILED,
                        game_id=game.game_id,
                        player_id=player.id,
                        data={"card_name": card_name, "error": result.error},
                        message=f"Dogma failed: {card_name}",
                    )
                return {"success": False, "error": result.error}

        except Exception as e:
            logger.error(f"Dogma v2 execution failed: {e}", exc_info=True)
            return {"success": False, "error": f"Dogma execution failed: {e!s}"}

    def _log_sharing_activity(self, result, card_name: str, activating_player: Player):
        """AsyncGameManager hook to log sharing decisions and activity."""
        try:
            # Check if sharing occurred by examining the context
            if hasattr(result, "context") and hasattr(result.context, "sharing"):
                sharing_context = result.context.sharing

                if (
                    hasattr(sharing_context, "sharing_players")
                    and sharing_context.sharing_players
                ):
                    # sharing_context.sharing_players is a list of player IDs (strings), not objects
                    # We need to get the actual player names from the game
                    game = result.context.game
                    sharing_player_names = []
                    for player_id in sharing_context.sharing_players:
                        player = game.get_player_by_id(player_id)
                        if player:
                            sharing_player_names.append(player.name)

                    logger.info(f"ASYNC_GAME_MANAGER: Sharing detected for {card_name}")
                    logger.info(
                        f"ASYNC_GAME_MANAGER: Sharing players: {sharing_player_names}"
                    )
                    logger.info(
                        f"ASYNC_GAME_MANAGER: Activating player: {activating_player.name}"
                    )

                    # Check if sharing actually executed (anyone_shared variable)
                    anyone_shared = result.context.get_variable("anyone_shared", False)
                    if anyone_shared:
                        logger.info("ASYNC_GAME_MANAGER: Sharing effects were executed")

                        # Log activity event for sharing completion
                        with contextlib.suppress(Exception):
                            # EventType and activity_logger already imported at module level
                            activity_logger.log_game_event(
                                event_type=EventType.DOGMA_SHARING_COMPLETED,
                                game_id=result.context.game.game_id,
                                player_id=activating_player.id,
                                data={
                                    "card_name": card_name,
                                    "sharing_players": sharing_player_names,
                                    "total_sharing_players": len(sharing_player_names),
                                    "execution_method": "per_effect_inline",
                                },
                                message=f"Per-effect sharing completed for {card_name}",
                            )
                    else:
                        logger.info(
                            "ASYNC_GAME_MANAGER: Sharing players identified but no sharing effects executed"
                        )
                else:
                    logger.debug(
                        f"ASYNC_GAME_MANAGER: No sharing players for {card_name}"
                    )
            else:
                logger.debug(
                    f"ASYNC_GAME_MANAGER: No sharing context available for {card_name}"
                )

        except Exception as e:
            logger.warning(f"Error in _log_sharing_activity: {e}")

    def _should_allow_sharing(self, card_name: str, sharing_players: list) -> bool:
        """AsyncGameManager hook to control whether sharing should be allowed.

        Future extension point for:
        - Configuration-based sharing control
        - UI prompts for sharing confirmation
        - Game mode specific sharing rules
        """
        # For now, always allow sharing (maintain current behavior)
        # This method provides a hook for future enhancements
        if sharing_players:
            logger.info(
                f"ASYNC_GAME_MANAGER: Allowing sharing for {card_name} with {len(sharing_players)} players"
            )
            return True
        return False

    async def _handle_dogma_response(
        self, game: Game, player: Player, response_data: dict
    ) -> dict[str, Any]:
        """Handle dogma interaction response using v2 system"""

        # All dogma interactions use v2 system
        pending_action = game.state.pending_dogma_action
        if not pending_action:
            return {"success": False, "error": "No pending dogma interaction"}

        return await self._handle_dogma_v2_response(
            game, player, response_data, pending_action
        )

    async def _handle_dogma_v2_response(
        self, game: Game, player: Player, response_data: dict, pending_action
    ) -> dict[str, Any]:
        """Handle dogma v2 interaction response"""

        # Validate response data format
        if not isinstance(response_data, dict):
            return {
                "success": False,
                "error": f"Invalid response_data type: expected dict, got {type(response_data)}",
            }

        # Validate required fields based on response type
        required_fields = set()
        if response_data.get("selected_cards"):
            required_fields.add("selected_cards")
        if response_data.get("selected_achievements"):
            required_fields.add("selected_achievements")
        if response_data.get("selected_achievement"):
            required_fields.add("selected_achievement")
        if response_data.get("chosen_option") is not None:
            required_fields.add("chosen_option")
        if response_data.get("transaction_id"):
            required_fields.add("transaction_id")

        # Additional validation for card selection responses - only validate if not None
        if "selected_cards" in response_data:
            selected_cards = response_data["selected_cards"]
            if selected_cards is not None and not isinstance(selected_cards, list):
                return {
                    "success": False,
                    "error": f"selected_cards must be a list, got {type(selected_cards)}",
                }

        # Additional validation for achievement selection responses - only validate if not None
        if "selected_achievements" in response_data:
            selected_achievements = response_data["selected_achievements"]
            if selected_achievements is not None and not isinstance(
                selected_achievements, list
            ):
                return {
                    "success": False,
                    "error": f"selected_achievements must be a list, got {type(selected_achievements)}",
                }

        # Additional validation for single achievement selection (AI format)
        if "selected_achievement" in response_data:
            selected_achievement = response_data["selected_achievement"]
            if selected_achievement is not None and not isinstance(
                selected_achievement, str
            ):
                return {
                    "success": False,
                    "error": f"selected_achievement must be a string, got {type(selected_achievement)}",
                }

        # Validate transaction ID format if provided
        if "transaction_id" in response_data:
            transaction_id_response = response_data["transaction_id"]
            if (
                not isinstance(transaction_id_response, str)
                or not transaction_id_response.strip()
            ):
                return {
                    "success": False,
                    "error": "transaction_id must be a non-empty string",
                }

        try:
            transaction_id = pending_action.context.get("transaction_id")
            if not transaction_id:
                return {
                    "success": False,
                    "error": "No transaction ID in pending action",
                }

            logger.info(f"Resuming dogma v2 transaction {transaction_id} with response")

            # Resume dogma execution with the response
            # CRITICAL: Pass the freshly loaded game to update player references in suspended context
            result = self.dogma_executor.resume_from_interaction(
                transaction_id, response_data, updated_game=game
            )

            if result.success:
                if result.interaction_required:
                    # Another interaction is needed
                    logger.info(
                        f"DEBUG: Interaction required. interaction_type={result.interaction_type}, interaction_request={result.interaction_request}"
                    )
                    if game.state.pending_dogma_action and hasattr(
                        game.state.pending_dogma_action, "context"
                    ):
                        game.state.pending_dogma_action.context["transaction_id"] = (
                            result.transaction.id
                        )

                    # Ensure game_state reflects the new pending interaction (prevents UI from clearing)
                    try:
                        from models.game import PendingDogmaAction

                        if result.interaction_request:
                            # CRITICAL FIX: Use activating_player from context, not the responding player
                            # At this point, 'player' is the player who just responded to an interaction,
                            # but original_player_id should always be the player who activated the dogma
                            activating_player_id = (
                                result.context.activating_player.id
                                if result.context and result.context.activating_player
                                else player.id  # Fallback (shouldn't happen)
                            )
                            # CRITICAL: Set pending_dogma_action on result.context.game.state
                            # NOT on game.state directly, because _sync_game_state_safely()
                            # will overwrite game.state with result.context.game.state.
                            result.context.game.state.pending_dogma_action = PendingDogmaAction(
                                card_name=(
                                    result.context.card.name
                                    if result.context and result.context.card
                                    else "Unknown"
                                ),
                                effect_index=0,
                                original_player_id=activating_player_id,
                                target_player_id=result.interaction_request.player_id,
                                action_type="dogma_v2_interaction",
                                context={
                                    "transaction_id": result.transaction.id,
                                    "interaction_data": safe_to_dict(
                                        result.interaction_request
                                    ),
                                },
                            )
                    except Exception as e:
                        logger.warning(
                            f"Failed to set pending_dogma_action on resume: {e}"
                        )

                    # Determine target player ID from the interaction
                    target_player_id = resolve_interaction_player_id(
                        result.interaction_request
                    )
                    if not target_player_id:
                        logger.error(
                            "Dogma resume payload missing player_id",
                            extra={
                                "transaction_id": result.transaction.id,
                                "interaction_request": result.interaction_request,
                                "player_id": player.id,
                            },
                        )
                        return {
                            "success": False,
                            "error": "Dogma interaction is missing target player information",
                            "game_state": self._format_game_state_for_frontend(
                                result.context.game.to_dict()
                            ),
                        }
                    if not self._player_in_game(game, target_player_id):
                        logger.error(
                            "Dogma resume target is not part of this game",
                            extra={
                                "transaction_id": result.transaction.id,
                                "target_player_id": target_player_id,
                                "game_players": [p.id for p in game.players],
                            },
                        )
                        return {
                            "success": False,
                            "error": "Dogma interaction referenced a player outside this game",
                            "game_state": self._format_game_state_for_frontend(
                                result.context.game.to_dict()
                            ),
                        }

                    response = {
                        "success": True,
                        "action": "dogma_requires_response",
                        "interaction": {
                            "type": "dogma_v2_interaction",
                            "transaction_id": result.transaction.id,
                            "message": "Dogma execution requires additional interaction",
                            "target_player_id": target_player_id,
                        },
                        "game_state": self._format_game_state_for_frontend(
                            result.context.game.to_dict()
                        ),
                    }

                    # Activity log: subsequent interaction required
                    try:
                        payload = (
                            safe_to_dict(result.interaction_request)
                            if hasattr(result.interaction_request, "to_dict")
                            else (result.interaction_request or {})
                        )
                        activity_logger.log_game_event(
                            event_type=EventType.DOGMA_INTERACTION_REQUIRED,
                            game_id=game.game_id,
                            player_id=target_player_id,
                            data={
                                "card_name": (
                                    result.context.card.name
                                    if result.context and result.context.card
                                    else None
                                ),
                                "interaction_type": result.interaction_type,
                                "interaction": safe_get(payload, "data", payload),
                            },
                            message="Interaction required (resume)",
                        )
                    except Exception:
                        pass

                    # CRITICAL FIX: Sync game state changes before suspension
                    # When dogma suspends for interaction, we MUST sync the working copy
                    # back to the persistent game object. Otherwise, changes made before
                    # suspension (like DrawCards) will be lost when we resume from the
                    # un-synced persistent state.
                    self._sync_game_state_safely(game, result.context.game)
                    logger.debug("Synced game state before dogma suspension")

                    # CRITICAL FIX: Broadcast updated game state to frontend (resume path)
                    # When dogma suspends for interaction during resume, the frontend needs
                    # the updated game state BEFORE showing the interaction UI.
                    try:
                        from services.broadcast_service import get_broadcast_service

                        broadcast_service = get_broadcast_service()
                        await broadcast_service.broadcast_game_update(
                            game_id=game.game_id,
                            message_type="game_state_updated",
                            data={
                                "game_state": self._format_game_state_for_frontend(
                                    game.to_dict()
                                )
                            },
                        )
                        logger.debug(
                            "Broadcast game_state_updated before dogma suspension (resume)"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to broadcast game state before suspension (resume): {e}",
                            exc_info=True,
                        )

                    # Include unified interaction data
                    if result.interaction_request:
                        # HYBRID SOLUTION: Merge StandardInteractionBuilder payload with routing metadata
                        # This ensures both WebSocket validation (needs dogma_interaction format)
                        # and HTTP targeting (needs player_id) work correctly
                        response["interaction_request"] = safe_to_dict(
                            result.interaction_request
                        )
                        response["interaction_type"] = result.interaction_type
                        response["transaction_id"] = result.transaction.id
                        logger.info(
                            f"Dogma response requires {result.interaction_type} interaction. Target player: {result.interaction_request.player_id}"
                        )

                        # Publish player_interaction event to Event Bus for AI players (resume path)
                        # PERFORMANCE FIX: Send minimal data - AI fetches game from game_manager
                        if self.event_bus:
                            await self.event_bus.publish(
                                game_id=game.game_id,
                                event_type="player_interaction",
                                data={
                                    "player_id": result.interaction_request.player_id,
                                    "interaction": safe_to_dict(
                                        result.interaction_request
                                    ),
                                    # Don't send full game_state to prevent "Invalid string length"
                                },
                                source="async_game_manager.dogma_v2_resume",
                            )

                    return response
                else:
                    # Dogma execution completed - apply state changes to the modified game object
                    result.context.game.state.pending_dogma_action = None

                    # Decrement actions
                    if result.context.game.state.actions_remaining > 0:
                        result.context.game.state.actions_remaining -= 1

                    # Auto-advance turn if needed
                    self._advance_turn_if_needed(result.context.game)

                    # Sync changes back to original game for Redis persistence
                    # Use defensive copying to prevent immutable object contamination
                    self._sync_game_state_safely(game, result.context.game)

                    # CRITICAL: Update state_changes in action_log after dogma completes
                    # This is the RESUME path - dogma completed after player responded to interaction
                    try:
                        # Use result.context.game (the working copy that was just synced)
                        action_log = (
                            result.context.game.action_log
                            if result.context and result.context.game
                            else game.action_log
                        )
                        if action_log:
                            last = action_log[-1]
                            if result.context and hasattr(
                                result.context, "state_tracker"
                            ):
                                # Get detailed state changes from state tracker with player names
                                last.state_changes = (
                                    result.context.state_tracker.get_changes_as_dict()
                                )
                                logger.debug(
                                    f"STATE CHANGES (RESUME): Assigned {len(last.state_changes)} state changes from tracker"
                                )
                            else:
                                logger.debug(
                                    "STATE CHANGES (RESUME): No state tracker available"
                                )
                    except Exception as e:
                        logger.error(
                            f"STATE CHANGES (RESUME): Error extracting state changes: {e}",
                            exc_info=True,
                        )

                    # Activity log: dogma completed (after response)
                    try:
                        activity_logger.log_game_event(
                            event_type=EventType.DOGMA_COMPLETED,
                            game_id=game.game_id,
                            player_id=player.id,
                            data={
                                "card_name": (
                                    result.context.card.name
                                    if result.context and result.context.card
                                    else None
                                ),
                                "results": result.results or [],
                            },
                            message="Dogma completed (after response)",
                        )
                        # Emit a follow-up event that explicitly indicates who now has control
                        # so the UI can focus the activating player after sharing flows.
                        try:
                            current_player = result.context.game.current_player
                            activity_logger.log_game_event(
                                event_type=EventType.PLAYER_ACTION,
                                game_id=game.game_id,
                                player_id=current_player.id if current_player else None,
                                data={
                                    "action": "turn_resume",
                                    "after_dogma": True,
                                    "card_name": (
                                        result.context.card.name
                                        if result.context and result.context.card
                                        else None
                                    ),
                                    "actions_remaining": getattr(
                                        result.context.game.state,
                                        "actions_remaining",
                                        None,
                                    ),
                                },
                                message="Turn ready after dogma",
                            )
                        except Exception:
                            pass
                    except Exception:
                        pass

                    # DEBUG: Log game state before serialization
                    logger.info("DEBUG: About to serialize game state for response")
                    logger.info(
                        f"DEBUG: Player 0 hand: {[c.name for c in game.players[0].hand] if game.players else 'No players'}"
                    )
                    logger.info(
                        f"DEBUG: Player 0 red_cards: {[c.name for c in game.players[0].board.red_cards] if game.players and hasattr(game.players[0], 'board') else 'No board'}"
                    )

                    return {
                        "success": True,
                        "action": "dogma",
                        "card_name": result.context.card.name,
                        "results": result.results,
                        "game_state": self._format_game_state_for_frontend(
                            game.to_dict()  # Use synced main game object, not context.game
                        ),
                    }
            else:
                # Dogma execution failed
                game.state.pending_dogma_action = None
                return {"success": False, "error": result.error}

        except Exception as e:
            logger.error(f"Error handling dogma v2 response: {e}", exc_info=True)
            game.state.pending_dogma_action = None
            return {
                "success": False,
                "error": f"Failed to handle dogma response: {e!s}",
            }

    def _sync_game_state_safely(self, target_game: Game, source_game: Game):
        """Sync game state from DogmaContext. Delegates to services.game_helpers."""
        game_helpers.sync_game_state_safely(target_game, source_game)

    def _advance_turn_if_needed(self, game: Game):
        """Auto-advance turn. Delegates to services.game_helpers."""
        game_helpers.advance_turn_if_needed(game)

    async def _draw_card(self, game: Game, player: Player) -> dict[str, Any]:
        """Draw card. Delegates to services.game_actions."""
        return await game_actions.draw_card(game, player)

    async def _meld_card(
        self, game: Game, player: Player, card_identifier: str
    ) -> dict[str, Any]:
        """Simple meld implementation using card ID or name (backward compat)"""
        # Try to find by ID first (preferred)
        card = player.remove_from_hand_by_id(card_identifier)

        # If not found by ID, try by name for backward compatibility
        if not card:
            card = player.remove_from_hand_by_name(card_identifier)

        if card:
            player.meld_card(card)

            # Add to action log
            game.add_log_entry(
                player_name=player.name,
                action_type=ActionType.MELD,
                description=f"deployed {card.name}",
            )

            # Log action event for real-time UI updates
            activity_logger.log_game_event(
                event_type=EventType.ACTION_MELD,
                game_id=game.game_id,
                player_id=player.id,
                data={"card_name": card.name, "color": card.color},
                message=f"{player.name} deployed {card.name}",
            )

            result = {
                "success": True,
                "action": "meld",
                "card_melded": card.to_dict(),
            }

            if game.state.actions_remaining > 0:
                game.state.actions_remaining -= 1

            # Auto-advance turn if no actions remaining
            self._advance_turn_if_needed(game)

            result["game_state"] = self._format_game_state_for_frontend(game.to_dict())
            return result

        return {"success": False, "error": "Card not found in hand"}

    async def _claim_achievement(
        self, game: Game, player: Player, age: int
    ) -> dict[str, Any]:
        """Claim achievement. Delegates to services.game_actions."""
        return await game_actions.claim_achievement(game, player, age)

    async def _end_turn(self, game: Game, player: Player) -> dict[str, Any]:
        """End turn. Delegates to services.game_actions."""
        return await game_actions.end_turn(game, player)

    async def start_action_transaction(
        self, game_id: str, player_id: str, action_type: str
    ) -> dict:
        """
        Start a new transaction for an action with undo support.

        Creates a snapshot of the game state before the action is performed.

        Args:
            game_id: ID of the game
            player_id: ID of the player performing the action
            action_type: Type of action (draw, meld, dogma, achieve)

        Returns:
            dict with transaction_id
        """
        if game_id not in self.games:
            raise ValueError(f"Game {game_id} not found")

        game = self.games[game_id]
        async with self.lock_service.acquire_lock(game_id):
            transaction_id = game.start_transaction(player_id, action_type)
            await redis_store.save_game(game_id, game.to_dict())

            logger.info(
                f"Started transaction {transaction_id} for {action_type} by player {player_id} in game {game_id}"
            )

            return {"transaction_id": transaction_id, "success": True}

    async def commit_action(self, game_id: str) -> dict:
        """
        Commit the pending transaction in a game.

        Finalizes all changes made during the transaction.

        Args:
            game_id: ID of the game

        Returns:
            dict with success status
        """
        if game_id not in self.games:
            raise ValueError(f"Game {game_id} not found")

        game = self.games[game_id]
        async with self.lock_service.acquire_lock(game_id):
            if not game.pending_transaction:
                return {"success": False, "message": "No pending transaction to commit"}

            transaction_id = game.pending_transaction["id"]
            game.commit_transaction()
            await redis_store.save_game(game_id, game.to_dict())

            logger.info(f"Committed transaction {transaction_id} in game {game_id}")

            return {"success": True, "message": "Transaction committed"}

    async def undo_action(self, game_id: str, player_id: str) -> dict:
        """
        Undo the pending transaction and restore previous game state.

        Only the player who started the transaction can undo it.

        Args:
            game_id: ID of the game
            player_id: ID of the player requesting undo

        Returns:
            dict with success status and updated game state
        """
        if game_id not in self.games:
            raise ValueError(f"Game {game_id} not found")

        game = self.games[game_id]
        async with self.lock_service.acquire_lock(game_id):
            if not game.pending_transaction:
                return {"success": False, "message": "No pending transaction to undo"}

            # Verify the player requesting undo is the one who started the transaction
            if game.pending_transaction["player_id"] != player_id:
                return {
                    "success": False,
                    "message": "Only the player who started the action can undo it",
                }

            transaction_id = game.pending_transaction["id"]
            action_type = game.pending_transaction["action_type"]

            try:
                game.rollback_transaction()
                await redis_store.save_game(game_id, game.to_dict())

                logger.info(
                    f"Rolled back transaction {transaction_id} ({action_type}) for player {player_id} in game {game_id}"
                )

                # Return updated game state
                return {
                    "success": True,
                    "message": f"Action undone: {action_type}",
                    "game_state": self._sanitize_game_data(game.to_dict()),
                }
            except Exception as e:
                logger.error(
                    f"Failed to rollback transaction {transaction_id}: {e}",
                    exc_info=True,
                )
                return {"success": False, "message": f"Failed to undo action: {e!s}"}

    async def get_player_hand(self, game_id: str, player_id: str) -> dict[str, Any]:
        """Get a player's hand"""
        game = self.games.get(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        player = game.get_player_by_id(player_id)
        if not player:
            return {"success": False, "error": "Player not found"}

        return {
            "success": True,
            "cards": [card.to_dict() for card in player.hand],
            "game_state": self._format_game_state_for_frontend(game.to_dict()),
        }

    async def get_available_actions(
        self, game_id: str, player_id: str
    ) -> dict[str, Any]:
        """Get available actions for a player"""
        # CRITICAL: Always reload from Redis to get latest game state
        # AI actions performed via HTTP update Redis, not in-memory cache
        # This prevents stale cache bugs where available actions show outdated state
        game_data = await redis_store.load_game(game_id)
        if game_data:
            try:
                # Sanitize data before validation (fixes corrupted empty dicts)
                game_data = self._sanitize_game_data(game_data)
                # Replace our in-memory copy with fresh data from Redis
                self.games[game_id] = Game.model_validate(game_data)
                logger.debug(
                    f"Reloaded game {game_id} from Redis for get_available_actions"
                )
            except Exception as e:
                logger.error(f"Failed to reload game {game_id}: {e}")

        game = self.games.get(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        player = game.get_player_by_id(player_id)
        if not player:
            return {"success": False, "error": "Player not found"}

        # Check if it's player's turn
        if game.phase != GamePhase.PLAYING:
            return {
                "success": True,
                "actions": [],
                "game_state": self._format_game_state_for_frontend(game.to_dict()),
            }

        if game.state.current_player_index != game.players.index(player):
            return {
                "success": True,
                "actions": [],
                "game_state": self._format_game_state_for_frontend(game.to_dict()),
            }

        # Check for pending dogma interaction (v2 system)
        if (
            game.state.pending_dogma_action
            and game.state.pending_dogma_action.action_type == "dogma_v2_interaction"
        ):
            return {
                "success": True,
                "actions": ["dogma_response"],
                "game_state": self._format_game_state_for_frontend(game.to_dict()),
            }

        # Normal turn actions
        actions = []
        if game.state.actions_remaining > 0:
            # Calculate draw age (highest age on player's board, or 1 if empty)
            top_cards = player.board.get_top_cards()
            draw_age = max([card.age for card in top_cards], default=0)
            if draw_age == 0:
                draw_age = 1
            actions.append(f"draw:{draw_age}")

            # Add meld actions with card names to prevent AI hallucination
            for card in player.hand:
                actions.append(f"meld:{card.name}")

            # Add dogma actions with card names to prevent AI hallucination
            top_cards = player.board.get_top_cards()
            for card in top_cards:
                actions.append(f"dogma:{card.name}")

            # Check for achievable achievements
            score = sum(card.age for card in player.score_pile)
            logger.debug(
                f"Achievement check for {player.name}: score={score}, "
                f"achievement_cards={list(game.deck_manager.achievement_cards.keys())}, "
                f"player_achievements={len(player.achievements)}"
            )
            for age, achievements in game.deck_manager.achievement_cards.items():
                if achievements:  # If there are achievements available for this age
                    achievement = achievements[0]
                    # Calculate required score with multiple achievement cost
                    same_age_achievements = len(
                        [ach for ach in player.achievements if ach.age == age]
                    )
                    required_score = age * 5 * (same_age_achievements + 1)
                    logger.debug(
                        f"  Age {age}: required_score={required_score}, "
                        f"score={score}, same_age_count={same_age_achievements}"
                    )
                    if score >= required_score:
                        top_card_value = max(
                            [card.age for card in player.board.get_top_cards()] + [0]
                        )
                        logger.debug(
                            f"    Score check passed! top_card_value={top_card_value}, "
                            f"achievement.age={achievement.age}"
                        )
                        if top_card_value >= achievement.age:
                            logger.info(
                                f"    ACHIEVE action available for {player.name}! "
                                f"(score={score}, age={age})"
                            )
                            actions.append(f"achieve:{age}")
                            break
                        else:
                            logger.debug(
                                f"    Top card too low: {top_card_value} < {achievement.age}"
                            )
                    else:
                        logger.debug(
                            f"    Insufficient score: {score} < {required_score}"
                        )

        if game.state.actions_remaining < 2:
            actions.append("end_turn")

        return {
            "success": True,
            "actions": actions,
            "game_state": self._format_game_state_for_frontend(game.to_dict()),
        }

    async def leave_game(self, game_id: str, player_id: str) -> dict[str, Any]:
        """Handle a player leaving the game"""
        game = self.games.get(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        # Use lock to prevent race conditions during leave
        lock = self.lock_service.acquire_lock(game_id)
        async with lock:
            # Find the player
            player = game.get_player_by_id(player_id)
            if not player:
                return {"success": False, "error": "Player not in game"}

            # Handle based on game phase
            if game.phase == GamePhase.WAITING_FOR_PLAYERS:
                # Remove player from lobby
                game.players.remove(player)
                if len(game.players) == 0:
                    # Delete empty game and its lock
                    if game_id in self.game_locks:
                        del self.game_locks[game_id]
                    del self.games[game_id]
                    return {"success": True, "game_deleted": True}
            elif game.phase in [GamePhase.SETUP_CARD_SELECTION, GamePhase.PLAYING]:
                # In active game - end the game with remaining players as winners
                game.players.remove(player)
                if len(game.players) == 1:
                    # Last remaining player wins
                    game.winner = game.players[0]
                    game.phase = GamePhase.FINISHED

                    # Cleanup AI Event Subscribers to prevent resource leaks
                    await self._cleanup_game_resources(game.game_id)

                    activity_logger.log_game_event(
                        game_id=game.game_id,
                        event_type=EventType.GAME_ENDED,
                        data={
                            "winner": game.winner.name,
                            "victory_type": "last_player_standing",
                            "reason": f"Player {player.name} left the game",
                            "final_phase": "FINISHED",
                        },
                    )
                    logger.info(
                        f"GAME OVER: Game {game.game_id} won by {game.winner.name} - last player standing after {player.name} left"
                    )
                elif len(game.players) == 0:
                    # No players left - delete game and its lock
                    if game_id in self.game_locks:
                        del self.game_locks[game_id]
                    del self.games[game_id]
                    return {"success": True, "game_deleted": True}

            # Save to Redis while holding lock
            await redis_store.save_game(game_id, game.to_dict())

            return {
                "success": True,
                "game_state": self._format_game_state_for_frontend(game.to_dict()),
            }

    async def get_system_stats(self) -> dict[str, Any]:
        """
        Get comprehensive system statistics.

        Provides system stats through the service layer to maintain proper
        architectural separation. Router layer should call this instead of
        directly accessing redis_store.

        Returns:
            Dictionary containing system statistics including storage status
        """
        # Get storage stats through the service layer
        storage_stats = await redis_store.get_stats()

        return {
            "games_in_memory": len(self.games),
            "storage": storage_stats,
            "active_game_locks": len(self.game_locks),
            "cleanup_task_running": self._cleanup_task is not None
            and not self._cleanup_task.done(),
        }

    def get_cards_database(self) -> dict[str, Any]:
        """
        Get all card data through the service layer.

        Provides card database access through proper architectural separation.
        Router layer should call this instead of directly accessing data files.

        Returns:
            Dictionary containing all cards data with proper enum conversions
        """
        from data.cards import load_cards_from_json

        # load_cards_from_json returns a single list of all cards
        cards = load_cards_from_json()
        cards_data = []

        for card in cards:
            card_dict = card.model_dump()
            card_dict = self._convert_card_enums_to_strings(card_dict)
            cards_data.append(card_dict)

        return {"cards": cards_data, "total": len(cards_data)}

    def _convert_card_enums_to_strings(self, card_dict: dict) -> dict:
        """Convert card enum values to strings for JSON serialization"""
        # Convert color enum
        if card_dict.get("color"):
            card_dict["color"] = (
                str(card_dict["color"].value)
                if hasattr(card_dict["color"], "value")
                else str(card_dict["color"])
            )

        # Convert dogma_resource enum
        if card_dict.get("dogma_resource"):
            card_dict["dogma_resource"] = (
                str(card_dict["dogma_resource"].value)
                if hasattr(card_dict["dogma_resource"], "value")
                else str(card_dict["dogma_resource"])
            )

        # Convert symbols list
        if card_dict.get("symbols"):
            card_dict["symbols"] = [
                str(s.value) if hasattr(s, "value") else str(s)
                for s in card_dict["symbols"]
            ]

        # Convert symbol_positions list
        if card_dict.get("symbol_positions"):
            card_dict["symbol_positions"] = [
                str(s.value) if hasattr(s, "value") else str(s) if s else None
                for s in card_dict["symbol_positions"]
            ]

        return card_dict

    async def get_dogma_debug_info(
        self, game_id: str, transaction_id: str | None = None
    ) -> dict:
        """Get detailed debug information for dogma execution"""
        async with self.lock_service.acquire_lock(game_id):
            return self.dogma_executor.get_debug_info(
                transaction_id=transaction_id, game_id=game_id
            )
