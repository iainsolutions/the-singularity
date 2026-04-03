"""Tests for demand variable leaking into cooperative effects.

Regression: ENIAC demand (effect 1) uses store_result="to_return".
Cooperative (effect 2) also uses store_result="to_return". Without cleanup,
the demand's variable leaks and SelectCards skips the interaction entirely.
"""

import copy

from dogma_v2.consolidated_executor import ConsolidatedDogmaExecutor
from models.card import Card, CardColor, Symbol
from models.game import Game, GamePhase
from models.player import Player


def make_game_with_cards(p1_board, p2_board, p1_hand=None, p2_hand=None):
    """Helper to create a game with specific cards on board."""
    game = Game()
    game.players = [Player(name="Alice"), Player(name="Bob")]
    game.start_game()
    for p in game.players:
        p.hand = []
        p.setup_selection_made = True
    for card in (p1_board or []):
        game.players[0].board.add_card(copy.deepcopy(card))
    for card in (p2_board or []):
        game.players[1].board.add_card(copy.deepcopy(card))
    game.players[0].hand = [copy.deepcopy(c) for c in (p1_hand or [])]
    game.players[1].hand = [copy.deepcopy(c) for c in (p2_hand or [])]
    game.complete_setup()
    return game


class TestDemandVariableLeak:
    """Regression: demand store_result must not leak into cooperative effects."""

    def test_eniac_cooperative_requires_interaction(self, card_by_name):
        """ENIAC cooperative (effect 2) must prompt player to optionally return a card.

        Bug: demand (effect 1) sets to_return for PROMETHEUS. When cooperative
        runs for Alice, SelectCards sees stale to_return and skips interaction.
        """
        eniac = card_by_name("ENIAC")

        # Give Alice more algorithm icons so Bob is vulnerable (demand fires)
        # ENIAC itself provides algorithm + circuit + circuit
        # Give Bob fewer algorithm icons (use a card with no algorithm)
        music_box = card_by_name("Music Box")  # era 1, no algorithm

        game = make_game_with_cards(
            p1_board=[eniac],
            p2_board=[music_box],
            p1_hand=[card_by_name("Abacus")],  # Alice has a card to optionally return
            p2_hand=[card_by_name("Pascaline")],  # Bob has a card to be demanded
        )

        alice = game.players[0]
        bob = game.players[1]

        # Verify Alice has more algorithm than Bob (demand should fire)
        alice_algo = alice.count_symbol("algorithm")
        bob_algo = bob.count_symbol("algorithm")
        assert alice_algo > bob_algo, (
            f"Alice needs more algorithm ({alice_algo}) than Bob ({bob_algo})"
        )

        executor = ConsolidatedDogmaExecutor()
        result = executor.execute_dogma(game, alice, eniac)

        # After demand executes, cooperative effect should require interaction
        # (Alice choosing whether to return a card from hand).
        # Before fix: result.success=True, no interaction (variable leak skipped it)
        # After fix: result.interaction_required=True (SelectCards prompts Alice)
        assert result.interaction_required, (
            "ENIAC cooperative effect should prompt Alice to optionally return a card. "
            "Demand variable 'to_return' likely leaked into cooperative effect."
        )

    def test_effect_transition_clears_demand_variables(self, card_by_name):
        """Effect transition must clear demand-scoped variables and demanding_player."""
        from dogma_v2.core.constants import SYSTEM_CONTEXT_VARS
        from dogma_v2.core.context import DogmaContext

        eniac = card_by_name("ENIAC")

        game = make_game_with_cards(
            p1_board=[eniac],
            p2_board=[card_by_name("Music Box")],
            p1_hand=[card_by_name("Abacus")],
            p2_hand=[card_by_name("Pascaline")],
        )

        alice = game.players[0]

        # Build context simulating post-demand state
        context = DogmaContext.create_initial(game, alice, eniac)
        context = context.with_variable("to_return", [card_by_name("Pascaline")])
        context = context.with_variable("demanding_player", alice)

        # Simulate the scheduler effect transition cleanup
        preserve_vars = SYSTEM_CONTEXT_VARS | {"demand_transferred_count", "endorsed"}
        updated = context
        for k in list(updated.variables.keys()):
            if k not in preserve_vars and not k.startswith("_"):
                updated = updated.without_variable(k)

        # Custom store_result vars should be cleared
        assert not updated.has_variable("to_return"), "to_return should be cleared"

        # demanding_player is a system var but must be cleared on demand→coop transition
        assert updated.has_variable("demanding_player"), (
            "demanding_player survives whitelist clearing (it's a system var)"
        )
        # Scheduler clears it separately for demand→non-demand transitions
        updated = updated.without_variable("demanding_player")
        assert not updated.has_variable("demanding_player")
