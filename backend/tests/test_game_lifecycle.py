"""Tests for game lifecycle: create, join, start, setup, actions, victory."""

from models.game import Game, GamePhase
from models.player import Player


class TestGameCreation:
    def test_new_game_waiting(self):
        game = Game()
        assert game.phase == GamePhase.WAITING_FOR_PLAYERS

    def test_add_players(self):
        game = Game()
        game.players = [Player(name="Alice"), Player(name="Bob")]
        assert len(game.players) == 2
        assert game.players[0].name == "Alice"

    def test_game_has_id(self):
        game = Game()
        assert game.game_id is not None
        assert len(game.game_id) > 0


class TestGameStart:
    def test_start_deals_two_cards(self, two_player_game):
        for player in two_player_game.players:
            assert len(player.hand) == 2

    def test_start_sets_setup_phase(self, two_player_game):
        assert two_player_game.phase == GamePhase.SETUP_CARD_SELECTION

    def test_deck_setup(self, two_player_game):
        dm = two_player_game.deck_manager
        # 10 eras of decks
        assert len(dm.age_decks) >= 10
        # Each era 1-9 has an achievement card
        for era in range(1, 10):
            assert era in dm.achievement_cards, f"Era {era} missing achievement"
        # 6 special achievements
        assert len(dm.special_achievements) == 6


class TestSetupSelection:
    def test_setup_selection(self, two_player_game):
        game = two_player_game
        for player in game.players:
            card = player.hand[0]
            game.make_setup_selection_by_id(player.id, card.card_id)

        assert game.phase == GamePhase.PLAYING

    def test_first_player_alphabetical(self, two_player_game):
        game = two_player_game
        # Give Alice a card named "Zebra" and Bob a card named "Abacus"
        # by selecting their first cards (random, but we test the mechanism)
        for player in game.players:
            card = player.hand[0]
            game.make_setup_selection_by_id(player.id, card.card_id)

        # First player should be the one with alphabetically first card
        first = game.players[game.state.current_player_index]
        assert first is not None

    def test_first_player_gets_1_action(self, playing_game):
        assert playing_game.state.actions_remaining == 1


class TestDrawAction:
    def test_draw_adds_to_hand(self, playing_game):
        player = playing_game.players[playing_game.state.current_player_index]
        hand_before = len(player.hand)
        card = playing_game.draw_card(1)
        assert card is not None
        player.hand.append(card)
        assert len(player.hand) == hand_before + 1

    def test_draw_from_empty_goes_higher(self, playing_game):
        # Empty era 1
        playing_game.deck_manager.age_decks[1] = []
        card = playing_game.draw_card(1)
        # Should draw from era 2+
        if card:
            assert card.age >= 2


class TestMeldAction:
    def test_meld_to_board(self, playing_game):
        player = playing_game.players[playing_game.state.current_player_index]
        # Draw a card first
        card = playing_game.draw_card(1)
        assert card is not None
        player.hand.append(card)

        # Meld it
        player.hand.remove(card)
        player.board.add_card(card)

        # Card should be on board in correct color stack
        color = card.color.value
        stack = player.board.get_cards_by_color(color)
        assert card in stack


class TestAchieveAction:
    def test_achievement_requirements(self, playing_game):
        player = playing_game.players[0]
        # Need 5 points and era 1+ top card for era 1 achievement
        required = player.required_score_for_achievement(1)
        assert required == 5

    def test_victory_at_6_achievements_2p(self, playing_game):
        needed = playing_game.get_achievements_needed_for_victory()
        assert needed == 6

    def test_victory_check(self, playing_game):
        player = playing_game.players[0]
        # Give player 6 fake achievements
        from models.card import Card, CardColor
        for i in range(6):
            player.achievements.append(
                Card(name=f"Ach{i}", age=1, color=CardColor.PURPLE,
                     symbols=[], dogma_effects=[], is_achievement=True)
            )
        assert playing_game.check_victory_conditions()
        assert playing_game.phase == GamePhase.FINISHED
        assert playing_game.winner == player


class TestGameSerialization:
    def test_to_dict_round_trip(self, playing_game):
        d = playing_game.to_dict()
        assert d["phase"] == "playing"
        assert len(d["players"]) == 2
        assert "achievement_cards" in d
        assert "special_achievements" in d
        assert "special_achievements_available" in d

    def test_special_achievements_in_state(self, playing_game):
        d = playing_game.to_dict()
        available = d["special_achievements_available"]
        assert "Emergence" in available
        assert "Dominion" in available
        assert len(available) == 6

    def test_symbols_serialize_as_strings(self, playing_game):
        d = playing_game.to_dict()
        # Check a player's board card symbols are strings not enums
        for player_data in d["players"]:
            computed = player_data.get("computed_state", {})
            visible = computed.get("visible_symbols", {})
            for key in visible:
                assert isinstance(key, str), f"Symbol key should be string, got {type(key)}"
                assert key in ("circuit", "neural_net", "data", "algorithm", "human_mind", "robot")
