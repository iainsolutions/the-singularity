"""Tests for all 6 special achievement conditions."""

import copy
from models.card import Card, CardColor, Symbol
from models.game import Game
from models.player import Player, PlayerBoard


def make_card(name, age=1, color=CardColor.BLUE, symbols=None):
    """Helper to create a card with specific symbols."""
    syms = symbols or [Symbol.CIRCUIT, Symbol.CIRCUIT, Symbol.CIRCUIT]
    positions = syms + [None] * (4 - len(syms))
    return Card(
        name=name, age=age, color=color,
        symbols=syms, symbol_positions=positions[:4],
        dogma_effects=[], dogma_resource=syms[0],
    )


class TestEmergence:
    """SA01: Archive 6+ cards OR Harvest 6+ cards in a single turn."""

    def test_not_triggered_at_5(self, achievement_checker):
        game = Game()
        game.players = [Player(name="Alice")]
        achievement_checker.track_card_action(game.game_id, game.players[0].id, "tuck", 5)
        assert not achievement_checker.check_emergence(game, game.players[0])

    def test_triggered_at_6_tucks(self, achievement_checker):
        game = Game()
        game.players = [Player(name="Alice")]
        achievement_checker.track_card_action(game.game_id, game.players[0].id, "tuck", 6)
        assert achievement_checker.check_emergence(game, game.players[0])

    def test_triggered_at_6_scores(self, achievement_checker):
        game = Game()
        game.players = [Player(name="Alice")]
        achievement_checker.track_card_action(game.game_id, game.players[0].id, "score", 6)
        assert achievement_checker.check_emergence(game, game.players[0])

    def test_mixed_not_triggered(self, achievement_checker):
        game = Game()
        game.players = [Player(name="Alice")]
        achievement_checker.track_card_action(game.game_id, game.players[0].id, "tuck", 3)
        achievement_checker.track_card_action(game.game_id, game.players[0].id, "score", 3)
        assert not achievement_checker.check_emergence(game, game.players[0])


class TestDominion:
    """SA02: 3+ of every icon type visible on board."""

    def test_not_triggered_missing_icon(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        # 3 of 5 icon types but missing robot and human_mind
        player.board.add_card(make_card("c1", symbols=[Symbol.CIRCUIT, Symbol.CIRCUIT, Symbol.CIRCUIT]))
        player.board.add_card(make_card("c2", color=CardColor.GREEN, symbols=[Symbol.DATA, Symbol.DATA, Symbol.DATA]))
        player.board.add_card(make_card("c3", color=CardColor.PURPLE, symbols=[Symbol.NEURAL_NET, Symbol.NEURAL_NET, Symbol.NEURAL_NET]))
        player.board.add_card(make_card("c4", color=CardColor.YELLOW, symbols=[Symbol.ALGORITHM, Symbol.ALGORITHM, Symbol.ALGORITHM]))
        assert not achievement_checker.check_dominion(game, player)

    def test_triggered_all_icons(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        # Need 3+ visible of each of 6 icon types — use 6 separate color stacks isn't possible (only 5 colors)
        # Use 5 colors, each top card has a unique mix, ensuring 3+ of each
        # blue: circuit circuit circuit (3 circuit)
        player.board.add_card(make_card("c1", color=CardColor.BLUE, symbols=[Symbol.CIRCUIT, Symbol.CIRCUIT, Symbol.CIRCUIT]))
        # red: data data data (3 data)
        player.board.add_card(make_card("c2", color=CardColor.RED, symbols=[Symbol.DATA, Symbol.DATA, Symbol.DATA]))
        # green: algorithm neural_net neural_net (1 algo, 2 nn)
        player.board.add_card(make_card("c3", color=CardColor.GREEN, symbols=[Symbol.ALGORITHM, Symbol.NEURAL_NET, Symbol.NEURAL_NET]))
        # purple: algorithm human_mind human_mind (1 algo, 2 hm)
        player.board.add_card(make_card("c4", color=CardColor.PURPLE, symbols=[Symbol.ALGORITHM, Symbol.HUMAN_MIND, Symbol.HUMAN_MIND]))
        # yellow: robot robot neural_net (2 robot, 1 nn) — not enough yet
        player.board.add_card(make_card("c5", color=CardColor.YELLOW, symbols=[Symbol.ROBOT, Symbol.ROBOT, Symbol.NEURAL_NET]))
        # Totals: circuit=3, data=3, algorithm=2, neural_net=3, human_mind=2, robot=2 — not enough algo/hm/robot
        # Need splay to reveal more. Instead, rebuild with better distribution:
        player.board = PlayerBoard()
        # Each card has 3 symbols, 5 top cards = 15 visible symbols, need 3 of each of 6 = 18 minimum
        # Impossible with only 5 single-card stacks (15 symbols). Need splayed stacks.
        # Use splayed stacks with 2 cards each
        for color in CardColor:
            # Bottom card: position [0]=algo, [1]=circuit, [2]=data, [3]=None
            # Splay up reveals [1,2,3] → circuit, data, None
            player.board.add_card(make_card("bot", color=color, symbols=[Symbol.ALGORITHM, Symbol.CIRCUIT, Symbol.DATA]))
            # Top card shows all: neural_net, human_mind, robot
            player.board.add_card(make_card("top", age=2, color=color, symbols=[Symbol.NEURAL_NET, Symbol.HUMAN_MIND, Symbol.ROBOT]))
            player.board.splay_directions[color.value] = "up"
        # Per stack visible: top(nn,hm,robot) + bottom splay up(circuit,data) = 5
        # 5 stacks: circuit=5, data=5, neural_net=5, human_mind=5, robot=5, algorithm=0
        # Still missing algorithm! Need splay right for position [0].
        # Use splay right instead — reveals positions [0,1] → algo, circuit
        player.board = PlayerBoard()
        for color in CardColor:
            player.board.add_card(make_card("bot", color=color,
                                           symbols=[Symbol.ALGORITHM, Symbol.CIRCUIT, Symbol.DATA]))
            player.board.add_card(make_card("top", age=2, color=color,
                                           symbols=[Symbol.NEURAL_NET, Symbol.HUMAN_MIND, Symbol.ROBOT]))
            player.board.splay_directions[color.value] = "right"
        # Splay right reveals positions [0,1] → algorithm, circuit
        # Per stack: top(nn,hm,robot) + bottom right(algo,circuit) = 5
        # 5 stacks: algorithm=5, circuit=5, neural_net=5, human_mind=5, robot=5, data=0
        # Still missing data! The only way is to have ALL 6 in visible positions.
        # Use 3-card stacks with different splays, or just accept we need lots of cards.
        # Simplest: use top cards that cover all 6, needing 2 top cards per icon minimum
        player.board = PlayerBoard()
        # 5 top cards with mixed icons ensuring 3+ of each
        player.board.add_card(make_card("c1", color=CardColor.BLUE,
                                        symbols=[Symbol.CIRCUIT, Symbol.CIRCUIT, Symbol.CIRCUIT]))
        player.board.add_card(make_card("c2", color=CardColor.RED,
                                        symbols=[Symbol.DATA, Symbol.DATA, Symbol.DATA]))
        player.board.add_card(make_card("c3", color=CardColor.GREEN,
                                        symbols=[Symbol.ALGORITHM, Symbol.ALGORITHM, Symbol.ALGORITHM]))
        player.board.add_card(make_card("c4", color=CardColor.PURPLE,
                                        symbols=[Symbol.NEURAL_NET, Symbol.NEURAL_NET, Symbol.NEURAL_NET]))
        player.board.add_card(make_card("c5", color=CardColor.YELLOW,
                                        symbols=[Symbol.HUMAN_MIND, Symbol.HUMAN_MIND, Symbol.HUMAN_MIND]))
        # Missing robot — need a 6th stack but only 5 colors. Add robot via splay.
        # Add bottom card to yellow with robots, splay right to reveal
        player.board.yellow_cards.insert(0, make_card("c5b", color=CardColor.YELLOW,
                                                       symbols=[Symbol.ROBOT, Symbol.ROBOT, Symbol.ROBOT]))
        player.board.splay_directions["yellow"] = "right"
        # Yellow right splay: bottom reveals [0,1] = robot, robot. Top shows hm,hm,hm.
        # Totals: circuit=3, data=3, algo=3, nn=3, hm=3, robot=2 — still only 2 robot
        # Add bottom to purple too
        player.board.purple_cards.insert(0, make_card("c4b", color=CardColor.PURPLE,
                                                       symbols=[Symbol.ROBOT, Symbol.ROBOT, Symbol.ROBOT]))
        player.board.splay_directions["purple"] = "right"
        # Purple right splay: bottom reveals [0,1] = robot, robot. Total robot = 4
        assert achievement_checker.check_dominion(game, player)


class TestConsciousness:
    """SA03: 12+ visible Human Mind icons."""

    def test_not_triggered_at_11(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        # 4 cards with 3 human_mind each = 12... but only top cards visible without splay
        # Single card per color = only top card symbols visible = max 3 per stack
        # Need 4 stacks with 3 human_mind each
        for i, color in enumerate([CardColor.BLUE, CardColor.RED, CardColor.GREEN]):
            player.board.add_card(make_card(f"c{i}", color=color,
                                           symbols=[Symbol.HUMAN_MIND, Symbol.HUMAN_MIND, Symbol.HUMAN_MIND]))
        # 9 human_mind visible (3 stacks * 3)
        assert not achievement_checker.check_consciousness(game, player)

    def test_triggered_at_12(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        for i, color in enumerate([CardColor.BLUE, CardColor.RED, CardColor.GREEN, CardColor.YELLOW]):
            player.board.add_card(make_card(f"c{i}", color=color,
                                           symbols=[Symbol.HUMAN_MIND, Symbol.HUMAN_MIND, Symbol.HUMAN_MIND]))
        # 12 human_mind visible (4 stacks * 3 each)
        assert achievement_checker.check_consciousness(game, player)


class TestApotheosis:
    """SA04: All 5 colors, each splayed right/up/aslant."""

    def test_not_triggered_missing_color(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        # 4 colors splayed right, missing yellow
        for color in [CardColor.BLUE, CardColor.RED, CardColor.GREEN, CardColor.PURPLE]:
            player.board.add_card(make_card("a", color=color))
            player.board.add_card(make_card("b", age=2, color=color))
            player.board.splay_directions[color.value] = "right"
        assert not achievement_checker.check_apotheosis(game, player)

    def test_not_triggered_left_splay(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        for color in CardColor:
            player.board.add_card(make_card("a", color=color))
            player.board.add_card(make_card("b", age=2, color=color))
            player.board.splay_directions[color.value] = "left"
        assert not achievement_checker.check_apotheosis(game, player)

    def test_triggered_all_right(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        for color in CardColor:
            player.board.add_card(make_card("a", color=color))
            player.board.add_card(make_card("b", age=2, color=color))
            player.board.splay_directions[color.value] = "right"
        assert achievement_checker.check_apotheosis(game, player)

    def test_triggered_mixed_right_up(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        directions = ["right", "up", "aslant", "right", "up"]
        for color, direction in zip(CardColor, directions):
            player.board.add_card(make_card("a", color=color))
            player.board.add_card(make_card("b", age=2, color=color))
            player.board.splay_directions[color.value] = direction
        assert achievement_checker.check_apotheosis(game, player)


class TestTranscendence:
    """SA05: All 5 colors, each top card era 8+."""

    def test_not_triggered_missing_color(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        for color in [CardColor.BLUE, CardColor.RED, CardColor.GREEN, CardColor.PURPLE]:
            player.board.add_card(make_card("c", age=8, color=color))
        assert not achievement_checker.check_transcendence(game, player)

    def test_not_triggered_low_era(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        for color in CardColor:
            player.board.add_card(make_card("c", age=7, color=color))
        assert not achievement_checker.check_transcendence(game, player)

    def test_triggered_all_era_8(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        for color in CardColor:
            player.board.add_card(make_card("c", age=8, color=color))
        assert achievement_checker.check_transcendence(game, player)

    def test_triggered_mixed_8_9_10(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        ages = [8, 9, 10, 8, 10]
        for color, age in zip(CardColor, ages):
            player.board.add_card(make_card("c", age=age, color=color))
        assert achievement_checker.check_transcendence(game, player)


class TestAbundance:
    """SA06: 5+ cards in Harvest pile from different eras."""

    def test_not_triggered_at_4_eras(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        for age in [1, 2, 3, 4]:
            player.score_pile.append(make_card("c", age=age))
        assert not achievement_checker.check_abundance(game, player)

    def test_not_triggered_same_era(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        for _ in range(10):
            player.score_pile.append(make_card("c", age=3))
        assert not achievement_checker.check_abundance(game, player)

    def test_triggered_5_different_eras(self, achievement_checker):
        game = Game()
        player = Player(name="Alice")
        game.players = [player]
        for age in [1, 2, 3, 4, 5]:
            player.score_pile.append(make_card("c", age=age))
        assert achievement_checker.check_abundance(game, player)
