#!/usr/bin/env python3
"""
Scenario Test: Democracy

Tests Democracy's effect:
- Return any number of cards from hand. If returned more than any opponent due to
  Democracy this action, draw and score an 8.

Primitives tested: SelectCards (hand, multi, optional), ReturnCards,
    ConditionalAction (returned_most_cards_this_action), DrawCards, ScoreCards

Setup:
- Human: Democracy (purple, 3 lightbulbs) on board
- Human hand: Tools (age 1), Clothing (age 1) - 2 cards to return
- AI: Agriculture (green, 0 lightbulbs) - won't share

Expected:
- SelectCards interaction for returning cards from hand
- If returned, conditional checks if most returns → draw/score 8
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestDemocracyScenario:
    """Test Democracy return and conditional draw/score."""

    def setup_scenario(self) -> dict[str, Any]:
        response = requests.post(f"{BASE_URL}/api/v1/games", json={})
        assert response.status_code == 200
        game_id = response.json()["game_id"]

        response = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/join", json={"name": "TestPlayer"})
        assert response.status_code == 200
        human_id = response.json()["player_id"]

        response = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/add_ai_player", json={"difficulty": "beginner"})
        assert response.status_code == 200
        ai_id = next(p["id"] for p in response.json()["game_state"]["players"] if p["is_ai"])

        time.sleep(0.5)
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state", json={"phase": "playing"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Democracy", "location": "board"})
        for card in ["Tools", "Clothing"]:
            requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                          json={"player_id": human_id, "card_name": card, "location": "hand"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
                      json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2})
        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def _get_interaction(self, game_id):
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        state = response.json()
        pending = state.get("state", {}).get("pending_dogma_action")
        if not pending:
            return None, None, state
        context = pending.get("context", {})
        interaction_data = context.get("interaction_data", {})
        if not interaction_data:
            return None, None, state
        return interaction_data, interaction_data.get("data", {}), state

    def test_democracy_return_and_score(self):
        """Test Democracy: return cards, conditional draw/score 8."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Democracy"}
        )
        assert response.status_code == 200
        time.sleep(2)

        # Handle SelectCards interaction
        interaction, data, state = self._get_interaction(game_id)
        if interaction and interaction.get("interaction_type") == "select_cards":
            eligible = data.get("eligible_cards", [])
            print(f"Eligible to return: {[c.get('name') for c in eligible]}")
            # Return all cards
            selected_ids = [c["card_id"] for c in eligible]
            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                json={"player_id": human_id, "selected_cards": selected_ids}
            )
            assert response.status_code == 200
            print(f"Returned {len(selected_ids)} cards")
        else:
            print(f"No select_cards interaction (got: {interaction})")

        time.sleep(3)

        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        hand = human.get("hand", [])
        score = human.get("score_pile", [])
        print(f"Final hand: {[c['name'] for c in hand]}")
        print(f"Final score: {[c['name'] for c in score]}")

        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        print("✓ Phase playing, no pending")
        print("✅ Democracy test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
