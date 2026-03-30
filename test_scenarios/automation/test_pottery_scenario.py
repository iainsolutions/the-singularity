#!/usr/bin/env python3
"""
Scenario Test: Pottery

Tests Pottery's dynamic age draw using store_count:
- Effect 1: Return up to 3 hand cards. If any returned, draw and score a card
  of value equal to the number returned.
- Effect 2: Draw a 1.

Primitives tested: SelectCards (optional, variable count), ReturnCards (store_count),
DrawCards (dynamic age from variable), ScoreCards

Setup:
- Human: Pottery (blue, 3 leaves) on board
- AI: Metalworking (red, 0 leaves) on board - won't share
- Human hand: 3 age-1 cards

Expected:
- Effect 1: Human selects 2 cards to return, draws and scores an age 2
- Effect 2: Human draws a 1
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestPotteryScenario:
    """Test Pottery store_count dynamic age draw."""

    def setup_scenario(self) -> dict[str, Any]:
        print("\n" + "="*70)
        print("SETUP: Creating Pottery store_count Scenario")
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

        # Human board: Pottery (blue, 3 leaves)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Pottery", "location": "board"}
        )

        # AI board: Metalworking (red, 0 leaves)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Metalworking", "location": "board"}
        )

        # Human hand: 3 age-1 cards
        for card in ["Archery", "Oars", "Sailing"]:
            requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": human_id, "card_name": card, "location": "hand"}
            )
        print("✓ Setup complete")

        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )

        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_pottery_return_and_score(self):
        """Test Pottery: return 2 cards, draw and score age 2."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        print("\n--- Executing Pottery Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Pottery"}
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"

        time.sleep(2)

        # Check for card selection interaction
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

        assert len(eligible) == 3, f"Should have 3 eligible hand cards, got {len(eligible)}"

        # Select 2 cards to return (not all 3)
        card_ids = [c["card_id"] for c in eligible[:2]]
        card_names = [c["name"] for c in eligible[:2]]
        print(f"Selecting 2 cards to return: {card_names}")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
            json={"player_id": human_id, "selected_cards": card_ids}
        )
        assert response.status_code == 200, f"Selection failed: {response.text}"

        time.sleep(2)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        hand = human.get("hand", [])
        score = human.get("score_pile", [])
        hand_names = [c["name"] for c in hand]
        score_names = [c["name"] for c in score]

        print(f"Final hand: {hand_names}")
        print(f"Score pile: {score_names}")

        # Returned 2 cards, so should draw and score an age 2
        # Also Effect 2 draws a 1 to hand
        # Hand: started 3, returned 2 = 1, then drew a 1 from Effect 2 = 2
        assert len(hand) >= 2, f"Expected at least 2 cards in hand, got {len(hand)}: {hand_names}"
        print(f"✓ Hand has {len(hand)} cards")

        # Score pile should have 1 card (the age 2 drawn and scored)
        assert len(score) >= 1, f"Expected at least 1 scored card, got {len(score)}"
        # The scored card should be age 2 (returned 2 cards)
        scored_ages = [c["age"] for c in score]
        assert 2 in scored_ages, f"Should have scored an age 2 card, got ages: {scored_ages}"
        print(f"✓ Score pile has age 2 card (returned_count=2 → drew age 2)")

        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Game should complete"
        print("✅ Pottery test PASSED")
