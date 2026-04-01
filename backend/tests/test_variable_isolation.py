"""Tests for variable isolation between sharing players during dogma execution.

These tests verify the fix for the LISP/Search Trees bug where effect variables
(to_return, to_meld, drawn_cards, etc.) leaked from one player to the next
during shared dogma execution.
"""

from dogma_v2.core.constants import SYSTEM_CONTEXT_VARS
from dogma_v2.core.context import DogmaContext
from models.card import Card, CardColor, Symbol
from models.game import Game
from models.player import Player


class TestSystemContextVars:
    def test_is_frozenset(self):
        assert isinstance(SYSTEM_CONTEXT_VARS, frozenset)

    def test_contains_essential_vars(self):
        assert "game_id" in SYSTEM_CONTEXT_VARS
        assert "effects" in SYSTEM_CONTEXT_VARS
        assert "activating_player_id" in SYSTEM_CONTEXT_VARS
        assert "demanding_player" in SYSTEM_CONTEXT_VARS

    def test_does_not_contain_effect_vars(self):
        """Effect variables must NOT be in system vars — they get cleared between players."""
        effect_vars = [
            "selected_cards", "selected_card", "to_return", "to_meld",
            "to_give", "drawn_cards", "returned_count", "last_drawn",
            "chosen_option", "condition_result", "highest_card",
        ]
        for var in effect_vars:
            assert var not in SYSTEM_CONTEXT_VARS, f"{var} should NOT be a system var"


class TestVariableClearing:
    def test_clearing_preserves_system_vars(self):
        """Simulate the whitelist clearing logic."""
        variables = {
            "game_id": "test-123",
            "effects": [],
            "to_return": ["some_card"],
            "selected_card": "card_obj",
            "last_drawn": "drawn_obj",
        }

        # Simulate clearing (same logic as consolidated_phases)
        cleared = {}
        for k, v in variables.items():
            if k in SYSTEM_CONTEXT_VARS:
                cleared[k] = v

        assert "game_id" in cleared
        assert "effects" in cleared
        assert "to_return" not in cleared
        assert "selected_card" not in cleared
        assert "last_drawn" not in cleared

    def test_arbitrary_store_result_names_cleared(self):
        """Any custom store_result name should be cleared — not just known ones."""
        variables = {
            "game_id": "test",
            "my_custom_variable": "should_be_cleared",
            "drawn_cards": ["card1", "card2"],
            "fancy_selection_result": "also_cleared",
        }

        remaining = {k: v for k, v in variables.items() if k in SYSTEM_CONTEXT_VARS}
        assert "my_custom_variable" not in remaining
        assert "drawn_cards" not in remaining
        assert "fancy_selection_result" not in remaining
        assert "game_id" in remaining


class TestDogmaContextImmutability:
    def test_with_variable_creates_new_context(self):
        """DogmaContext.with_variable should return new context, not mutate."""
        game = Game()
        game.players = [Player(name="Alice")]
        card = Card(name="Test", age=1, color=CardColor.BLUE,
                    symbols=[Symbol.CIRCUIT], dogma_effects=[], dogma_resource=Symbol.CIRCUIT)

        ctx = DogmaContext.create_initial(game, game.players[0], card)
        ctx2 = ctx.with_variable("test_var", "value")

        assert not ctx.has_variable("test_var")
        assert ctx2.has_variable("test_var")
        assert ctx2.get_variable("test_var") == "value"

    def test_without_variable_creates_new_context(self):
        game = Game()
        game.players = [Player(name="Alice")]
        card = Card(name="Test", age=1, color=CardColor.BLUE,
                    symbols=[Symbol.CIRCUIT], dogma_effects=[], dogma_resource=Symbol.CIRCUIT)

        ctx = DogmaContext.create_initial(game, game.players[0], card)
        ctx = ctx.with_variable("to_remove", "value")
        assert ctx.has_variable("to_remove")

        ctx2 = ctx.without_variable("to_remove")
        assert ctx.has_variable("to_remove")  # Original unchanged
        assert not ctx2.has_variable("to_remove")  # New context cleared
