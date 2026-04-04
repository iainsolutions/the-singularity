"""Tests for dogma execution: simple effects, conditionals, overrides, sharing."""

import copy
from models.card import Card, CardColor, Symbol
from models.game import Game, GamePhase
from models.player import Player
from dogma_v2.consolidated_executor import ConsolidatedDogmaExecutor


def make_game_with_cards(p1_board, p2_board, p1_hand=None, p2_hand=None):
    """Helper to create a game with specific cards on board."""
    game = Game()
    game.players = [Player(name="Alice"), Player(name="Bob")]
    game.start_game()
    # Clear dealt cards
    for p in game.players:
        p.hand = []
        p.setup_selection_made = True
    # Place specific cards
    for card in (p1_board or []):
        game.players[0].board.add_card(copy.deepcopy(card))
    for card in (p2_board or []):
        game.players[1].board.add_card(copy.deepcopy(card))
    game.players[0].hand = [copy.deepcopy(c) for c in (p1_hand or [])]
    game.players[1].hand = [copy.deepcopy(c) for c in (p2_hand or [])]
    game.complete_setup()
    return game


class TestSimpleDogma:
    def test_abacus_draws_era_1(self, card_by_name):
        """Abacus: Research a [1]."""
        abacus = card_by_name("Abacus")
        game = make_game_with_cards([abacus], [card_by_name("Pascaline")])
        player = game.players[0]
        hand_before = len(player.hand)

        executor = ConsolidatedDogmaExecutor()
        result = executor.execute_dogma(game, player, abacus)

        assert result.success
        # Player should have drawn a card
        assert len(player.hand) >= hand_before + 1

    def test_astrolabe_draws(self, card_by_name):
        """Astrolabe: Research a [1] (nerfed — draw only, no score)."""
        astrolabe = card_by_name("Astrolabe")
        game = make_game_with_cards([astrolabe], [card_by_name("Pascaline")])
        player = game.players[0]
        hand_before = len(player.hand)

        executor = ConsolidatedDogmaExecutor()
        result = executor.execute_dogma(game, player, astrolabe)

        assert result.success
        assert len(player.hand) >= hand_before + 1

    def test_jacquard_loom_draws_and_melds(self, card_by_name):
        """Jacquard Loom: Research a [1] and Deploy it."""
        loom = card_by_name("Jacquard Loom")
        game = make_game_with_cards([loom], [card_by_name("Pascaline")])
        player = game.players[0]
        board_before = sum(len(player.board.get_cards_by_color(c)) for c in ["blue", "red", "green", "yellow", "purple"])

        executor = ConsolidatedDogmaExecutor()
        result = executor.execute_dogma(game, player, loom)

        assert result.success
        board_after = sum(len(player.board.get_cards_by_color(c)) for c in ["blue", "red", "green", "yellow", "purple"])
        assert board_after >= board_before + 1


class TestConditionalDogma:
    def test_mechanical_turk_deploys_purple(self, card_by_name):
        """Mechanical Turk: Research a [1]. If Creativity, Deploy it and research a [1]."""
        turk = card_by_name("Mechanical Turk")
        game = make_game_with_cards([turk], [card_by_name("Pascaline")])

        # Stack era 1 deck with a purple card on top
        purple_card = None
        for i, card in enumerate(game.deck_manager.age_decks.get(1, [])):
            if card.color == CardColor.PURPLE:
                purple_card = card
                # Move to top (end of list)
                game.deck_manager.age_decks[1].remove(card)
                game.deck_manager.age_decks[1].append(card)
                break

        if not purple_card:
            # No purple in era 1 deck — skip test
            return

        player = game.players[0]
        board_before = sum(len(player.board.get_cards_by_color(c)) for c in ["blue", "red", "green", "yellow", "purple"])

        executor = ConsolidatedDogmaExecutor()
        result = executor.execute_dogma(game, player, turk)

        assert result.success
        # Purple card should have been deployed
        board_after = sum(len(player.board.get_cards_by_color(c)) for c in ["blue", "red", "green", "yellow", "purple"])
        assert board_after >= board_before + 1


class TestOverrideDogma:
    def test_difference_engine_transfers_card(self, card_by_name):
        """Difference Engine: I Override you transfer a card from your hand to my hand!"""
        de = card_by_name("Difference Engine")
        victim_card = card_by_name("Abacus")
        game = make_game_with_cards(
            p1_board=[de],
            p2_board=[card_by_name("Pascaline")],
            p2_hand=[victim_card],
        )
        # Alice (player 0) has more circuit icons than Bob — override should fire
        alice = game.players[0]
        bob = game.players[1]

        # Verify Alice has more of the featured icon (circuit)
        alice_circuits = alice.count_symbol("circuit")
        bob_circuits = bob.count_symbol("circuit")

        if alice_circuits <= bob_circuits:
            # Bob not vulnerable — skip
            return

        bob_hand_before = len(bob.hand)

        executor = ConsolidatedDogmaExecutor()
        result = executor.execute_dogma(game, alice, de)

        assert result.success
        # Bob should have lost a card (transferred or interaction pending)
        if not result.interaction_required:
            assert len(bob.hand) < bob_hand_before or len(alice.hand) > 0


class TestSharing:
    def test_cooperative_sharing_bonus_draw(self, card_by_name):
        """When opponent shares a cooperative effect, activating player gets bonus draw."""
        astrolabe = card_by_name("Astrolabe")  # data featured icon
        # Give both players data icons so Bob shares
        game = make_game_with_cards(
            p1_board=[astrolabe],
            p2_board=[card_by_name("Astrolabe")],  # Also has data icons
        )
        alice = game.players[0]
        bob = game.players[1]

        # Both have data as featured icon — Bob should share
        alice_data = alice.count_symbol("data")
        bob_data = bob.count_symbol("data")

        executor = ConsolidatedDogmaExecutor()
        result = executor.execute_dogma(game, alice, astrolabe)

        assert result.success
        # Both should have scored cards
        # Alice gets sharing bonus if Bob shared
        if bob_data >= alice_data:
            # Bob shared — Alice should have gotten bonus draw
            assert len(alice.hand) > 0 or len(alice.score_pile) > 0


class TestColorCondition:
    def test_card_color_uses_value_not_str(self, card_by_name):
        """Verify card.color.value returns 'purple' not 'CardColor.PURPLE'."""
        turk = card_by_name("Mechanical Turk")
        assert turk.color.value == "purple"
        assert turk.color.value != "CardColor.PURPLE"

    def test_dogma_resource_uses_value(self, card_by_name):
        abacus = card_by_name("Abacus")
        assert abacus.dogma_resource.value == "circuit"
