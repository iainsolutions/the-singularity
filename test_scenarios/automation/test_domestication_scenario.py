#!/usr/bin/env python3
"""
Scenario Test: Domestication

Tests Domestication's SelectLowest + MeldCard:
- Effect: Meld the lowest card in your hand. Draw a 1.

Primitives tested: SelectLowest (auto-selects), MeldCard, DrawCards

Setup:
- Human: Domestication (yellow, 2 castles) on board
- AI: Agriculture (yellow, 0 castles) on board - won't share
- Human hand: mix of ages (age 1 + age 2 cards)

Expected:
- SelectLowest auto-selects the age 1 card
- Card melded to board (new color stack or on existing)
- Human draws a 1
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestDomesticationScenario:
    """Test Domestication SelectLowest + meld."""

    def setup_scenario(self) -> dict[str, Any]:
        print("\n" + "="*70)
        print("SETUP: Creating Domestication Scenario")
        print("="*70)

        response = requests.post(f"{BASE_URL}/api/v1/games", json={})
        assert response.status_code == 200
        game_id = response.json()["game_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/join",
            json={"name": "TestPlayer"}
        )
        assert response.status_code == 200
        human_id = response.json()["player_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/add_ai_player",
            json={"difficulty": "beginner"}
        )
        assert response.status_code == 200
        game_state = response.json()["game_state"]
        ai_id = next(p["id"] for p in game_state["players"] if p["is_ai"])

        time.sleep(0.5)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing"}
        )

        # Human board: Domestication (yellow)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Domestication", "location": "board"}
        )

        # AI board: Agriculture (yellow, 0 castles)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"}
        )

        # Human hand: 1 age-2 card + 1 age-1 card (lowest should be age 1)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Canal Building", "location": "hand"}
        )
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Archery", "location": "hand"}
        )
        print("✓ Hand: Canal Building (age 2), Archery (age 1)")

        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )
        print("✓ Setup complete")

        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_domestication_meld_lowest(self):
        """Test Domestication: meld lowest card, draw a 1."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Get initial board state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial = response.json()
        human_init = next(p for p in initial["players"] if p["id"] == human_id)
        init_board = human_init.get("board", {})
        init_colors = [k for k, v in init_board.items() if k.endswith("_cards") and v]
        print(f"Initial board colors: {init_colors}")

        print("\n--- Executing Domestication Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Domestication"}
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"

        time.sleep(2)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        hand = human.get("hand", [])
        board = human.get("board", {})
        hand_names = [c["name"] for c in hand]

        # Find all board cards
        board_cards = []
        for cards in board.values():
            if isinstance(cards, list):
                board_cards.extend([c["name"] for c in cards])

        print(f"Final hand: {hand_names}")
        print(f"Final board: {board_cards}")

        # Archery (age 1, lowest) should have been melded to red stack
        assert "Archery" in board_cards, \
            f"Archery (lowest card) should be melded to board, board: {board_cards}"
        print("✓ Archery (lowest) melded to board")

        # Canal Building should still be in hand
        assert "Canal Building" in hand_names, \
            f"Canal Building (age 2) should remain in hand, hand: {hand_names}"
        print("✓ Canal Building remains in hand")

        # Should have drawn a 1 (hand: Canal Building + drawn card)
        assert len(hand) >= 2, f"Should have at least 2 cards (kept + drawn), got {len(hand)}"
        print(f"✓ Drew a card, hand now has {len(hand)} cards")

        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Game should complete"
        print("✅ Domestication test PASSED")
