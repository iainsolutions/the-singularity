#!/usr/bin/env python3
"""
Scenario Test: Mathematics

Tests Mathematics' GetCardAge + CalculateValue for dynamic draw age:
- Effect: Return a card from hand. Draw and meld a card of value one higher.

Primitives tested: SelectCards (optional), GetCardAge, ReturnCards, CalculateValue,
DrawCards (dynamic age), MeldCard

Setup:
- Human: Mathematics (blue, 3 lightbulbs) on board
- AI: Agriculture (yellow, 0 lightbulbs) on board - won't share
- Human hand: 1 age-2 card

Expected:
- Human selects age 2 card to return
- GetCardAge → 2, CalculateValue → 2+1=3
- Draw and meld an age 3 card
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestMathematicsScenario:
    """Test Mathematics GetCardAge + CalculateValue."""

    def setup_scenario(self) -> dict[str, Any]:
        print("\n" + "="*70)
        print("SETUP: Creating Mathematics Scenario")
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

        # Human board: Mathematics (blue, 3 lightbulbs)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Mathematics", "location": "board"}
        )

        # AI board: Agriculture (0 lightbulbs)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"}
        )

        # Human hand: 1 age-2 card (Fermenting)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Fermenting", "location": "hand"}
        )
        print("✓ Hand: Fermenting (age 2)")

        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )
        print("✓ Setup complete")

        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_mathematics_return_draw_higher(self):
        """Test Mathematics: return age 2, draw and meld age 3."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        print("\n--- Executing Mathematics Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Mathematics"}
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"

        time.sleep(2)

        # Check for card selection
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        state = response.json()
        pending = state.get("state", {}).get("pending_dogma_action")
        assert pending is not None, "Should have pending interaction"

        context = pending.get("context", {})
        interaction = context.get("interaction_data", {})
        data = interaction.get("data", {})
        eligible = data.get("eligible_cards", [])
        print(f"Eligible cards: {[c['name'] for c in eligible]}")

        assert len(eligible) >= 1, f"Should have at least 1 eligible card"

        # Select Fermenting (age 2) to return
        fermenting = next((c for c in eligible if c["name"] == "Fermenting"), eligible[0])
        print(f"Selecting: {fermenting['name']} (age {fermenting['age']})")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
            json={"player_id": human_id, "selected_cards": [fermenting["card_id"]]}
        )
        assert response.status_code == 200, f"Selection failed: {response.text}"

        time.sleep(2)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        board = human.get("board", {})
        board_cards = []
        for color_key, cards in board.items():
            if color_key.endswith("_cards") and cards:
                for c in cards:
                    board_cards.append(c)

        board_names = [c["name"] for c in board_cards]
        board_ages = {c["name"]: c["age"] for c in board_cards}
        print(f"Final board: {board_names}")
        print(f"Board ages: {board_ages}")

        # Should have melded an age 3 card (returned age 2, so 2+1=3)
        age3_cards = [c for c in board_cards if c["age"] == 3]
        assert len(age3_cards) > 0, \
            f"Should have melded an age 3 card (returned age 2 → drew age 3), board: {board_ages}"
        print(f"✓ Melded age 3 card: {age3_cards[0]['name']}")

        # Fermenting should NOT be in hand (returned) or board (unless it was re-drawn)
        hand = human.get("hand", [])
        hand_names = [c["name"] for c in hand]
        print(f"Final hand: {hand_names}")

        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Game should complete"
        print("✅ Mathematics test PASSED")
