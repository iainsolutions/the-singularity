"""Tests for AI turn executor: interaction failure cleanup."""

import asyncio
import copy
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.ai_turn_executor import AITurnExecutor


def make_pending_dogma(target_player_id, transaction_id="tx-123"):
    """Create a mock pending dogma action."""
    pending = MagicMock()
    pending.target_player_id = target_player_id
    pending.action_type = "dogma_v2_interaction"
    pending.context = {
        "transaction_id": transaction_id,
        "interaction_data": {
            "type": "select_color",
            "data": {"message": "Select a color", "eligible_cards": []},
        },
    }
    pending.to_serializable_dict.return_value = {
        "context": pending.context,
        "target_player_id": target_player_id,
    }
    return pending


def make_mock_game(player_id="ai-1", player_name="PROMETHEUS", is_ai=True,
                   actions_remaining=1, pending_dogma=None):
    """Create a mock game with an AI player."""
    from models.game import GamePhase

    player = MagicMock()
    player.id = player_id
    player.name = player_name
    player.is_ai = is_ai
    player.hand = []
    player.achievements = []
    player.score = 0
    player.board = MagicMock()
    player.board.count_symbol = MagicMock(return_value=0)
    player.board.model_dump = MagicMock(return_value={})

    game = MagicMock()
    game.game_id = "test-game"
    game.phase = GamePhase.PLAYING
    game.players = [player]
    game.state = MagicMock()
    game.state.current_player_index = 0
    game.state.actions_remaining = actions_remaining
    game.state.turn_number = 1
    game.state.actions_taken = 0
    game.state.pending_dogma_action = pending_dogma
    game.state.sharing_context = None
    game.action_log = []
    game.achievement_cards = {}
    game.deck_manager = MagicMock()
    game.deck_manager.age_decks = {}
    game.get_player_by_id = MagicMock(return_value=player)
    game.to_dict = MagicMock(return_value={})

    return game, player


class TestInteractionFailureCleanup:
    """Regression: AI executor retries transient failures before clearing pending_dogma_action."""

    @pytest.mark.asyncio
    async def test_failed_interaction_retries_then_clears(self):
        """When _handle_interaction returns None 3 times, pending_dogma_action should be cleared."""
        pending = make_pending_dogma("ai-1")
        game, player = make_mock_game(pending_dogma=pending)

        gm = MagicMock()
        gm.get_game.return_value = game
        gm.load_game_from_storage = AsyncMock(return_value=game)
        gm.games = {}

        executor = AITurnExecutor(gm)

        agent = AsyncMock()
        agent.difficulty = "hard"

        handle_call_count = 0
        clear_called = False

        async def count_handles(*args, **kwargs):
            nonlocal handle_call_count
            handle_call_count += 1
            return None

        async def track_clear(game_id):
            nonlocal clear_called
            clear_called = True
            game.state.pending_dogma_action = None

        with patch.object(executor, '_handle_interaction', side_effect=count_handles):
            with patch.object(executor, '_clear_pending_dogma', side_effect=track_clear):
                with patch('services.ai_turn_executor.ai_service') as mock_ai_svc:
                    mock_ai_svc.get_agent.return_value = agent
                    with patch('asyncio.sleep', new_callable=AsyncMock):
                        result = await executor.execute_ai_turn("test-game", "ai-1")

        assert handle_call_count == 3, f"Expected 3 retries, got {handle_call_count}"
        assert clear_called, "pending_dogma_action was not cleared after 3 failed retries"

    @pytest.mark.asyncio
    async def test_transient_failure_preserves_pending_dogma(self):
        """A single transient failure should NOT clear pending_dogma_action — it retries."""
        pending = make_pending_dogma("ai-1")
        game, player = make_mock_game(pending_dogma=pending)

        gm = MagicMock()
        gm.get_game.return_value = game
        gm.load_game_from_storage = AsyncMock(return_value=game)
        gm.get_available_actions = AsyncMock(return_value={"success": True, "actions": []})
        gm.games = {}

        executor = AITurnExecutor(gm)

        agent = AsyncMock()
        agent.difficulty = "hard"

        call_count = 0

        async def fail_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # first attempt fails
            # Second attempt succeeds — also clear pending so loop can exit
            game.state.pending_dogma_action = None
            return {"action": {"action_type": "dogma_response"}, "success": True, "api_cost": 0, "latency_ms": 0}

        clear_called = False

        async def track_clear(game_id):
            nonlocal clear_called
            clear_called = True

        with patch.object(executor, '_handle_interaction', side_effect=fail_then_succeed):
            with patch.object(executor, '_clear_pending_dogma', side_effect=track_clear):
                with patch('services.ai_turn_executor.ai_service') as mock_ai_svc:
                    mock_ai_svc.get_agent.return_value = agent
                    with patch('asyncio.sleep', new_callable=AsyncMock):
                        result = await executor.execute_ai_turn("test-game", "ai-1")

        assert call_count == 2, f"Expected retry after first failure, got {call_count} calls"
        assert not clear_called, "pending_dogma_action should NOT be cleared on transient failure"

    @pytest.mark.asyncio
    async def test_stale_interaction_clears_pending_dogma(self):
        """When interaction is stuck (stale skip > 5), pending_dogma_action should be cleared."""
        pending = make_pending_dogma("ai-1")
        game, player = make_mock_game(pending_dogma=pending)

        gm = MagicMock()
        gm.get_game.return_value = game
        gm.load_game_from_storage = AsyncMock(return_value=game)
        gm.games = {}

        executor = AITurnExecutor(gm)

        agent = AsyncMock()
        agent.difficulty = "hard"

        # _handle_interaction succeeds first time but pending_dogma stays set
        handle_count = 0

        async def handle_once(*args, **kwargs):
            nonlocal handle_count
            handle_count += 1
            if handle_count == 1:
                return {"action": {"action_type": "dogma_response"}, "success": True, "api_cost": 0, "latency_ms": 0}
            return None

        clear_called = False

        async def track_clear(game_id):
            nonlocal clear_called
            clear_called = True
            game.state.pending_dogma_action = None

        with patch.object(executor, '_handle_interaction', side_effect=handle_once):
            with patch.object(executor, '_clear_pending_dogma', side_effect=track_clear):
                with patch('services.ai_turn_executor.ai_service') as mock_ai_svc:
                    mock_ai_svc.get_agent.return_value = agent
                    with patch('asyncio.sleep', new_callable=AsyncMock):
                        result = await executor.execute_ai_turn("test-game", "ai-1")

        assert clear_called, "pending_dogma_action was not cleared after stale interaction timeout"

    @pytest.mark.asyncio
    async def test_clear_pending_dogma_saves_to_redis(self):
        """_clear_pending_dogma should null out the field and save to Redis."""
        pending = make_pending_dogma("ai-1")
        game, player = make_mock_game(pending_dogma=pending)

        mock_redis = AsyncMock()

        gm = AsyncMock()
        gm.load_game_from_storage = AsyncMock(return_value=game)
        gm.games = {}

        executor = AITurnExecutor(gm)

        with patch.dict('sys.modules', {'redis_store': MagicMock(redis_store=mock_redis)}):
            with patch('redis_store.redis_store', mock_redis):
                await executor._clear_pending_dogma("test-game")

        assert game.state.pending_dogma_action is None
        mock_redis.save_game.assert_called_once()
