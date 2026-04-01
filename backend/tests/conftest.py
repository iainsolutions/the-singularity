"""
Test fixtures for The Singularity game tests.
"""

import copy
import sys
from pathlib import Path

import pytest

# Ensure backend is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.cards import load_cards_from_json, load_achievement_cards_from_json
from models.card import Card, CardColor, Symbol
from models.deck_manager import DeckManager
from models.game import Game, GamePhase
from models.player import Player, PlayerBoard
from special_achievements import SpecialAchievementChecker


@pytest.fixture
def all_cards():
    """All 105 Singularity cards."""
    return load_cards_from_json()


@pytest.fixture
def achievements():
    """Standard and special achievements."""
    standard, special = load_achievement_cards_from_json()
    return {"standard": standard, "special": special}


@pytest.fixture
def two_player_game():
    """A started 2-player game ready for setup selection."""
    game = Game()
    game.players = [Player(name="Alice"), Player(name="Bob")]
    game.start_game()
    return game


@pytest.fixture
def playing_game():
    """A 2-player game past setup, in PLAYING phase."""
    game = Game()
    game.players = [Player(name="Alice"), Player(name="Bob")]
    game.start_game()
    # Auto-select first card for each player
    for player in game.players:
        if player.hand:
            card = player.hand[0]
            player.hand.remove(card)
            player.board.add_card(card)
            player.setup_selection_made = True
    game.complete_setup()
    return game


@pytest.fixture
def card_by_name(all_cards):
    """Lookup function for cards by name."""
    cards = {c.name: c for c in all_cards}
    def _get(name):
        return copy.deepcopy(cards[name])
    return _get


@pytest.fixture
def achievement_checker():
    return SpecialAchievementChecker()
