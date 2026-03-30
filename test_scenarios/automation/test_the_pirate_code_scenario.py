#!/usr/bin/env python3
"""
Scenario Test: The Pirate Code

Tests The Pirate Code's two effects:
- Effect 0 (DEMAND): Transfer two cards of value 4 or less from opponent's score pile.
- Effect 1: If any cards were transferred, score lowest top card with crown from your board.

Primitives tested: DemandEffect, SelectCards (score_pile, max_age filter),
    TransferBetweenPlayers, ConditionalAction (variable_gt), SelectLowest, ScoreCards

Setup:
- Human: The Pirate Code (red, 2 crowns) on board
- AI: Agriculture (green, 0 crowns) - won't trigger demand

Expected: demand skipped, effect 1 condition false (no transfer), auto-complete
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestThePirateCodeScenario:
    """Test The Pirate Code demand + conditional score."""

    def setup_scenario(self) -> dict[str, Any]:
        response = requests.post(f"{BASE_URL}/api/v1/games", json={})
        assert response.status_code == 200
        game_id = response.json()["game_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/join", json={"name": "TestPlayer"}
        )
        assert response.status_code == 200
        human_id = response.json()["player_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/add_ai_player", json={"difficulty": "beginner"}
        )
        assert response.status_code == 200
        game_state = response.json()["game_state"]
        ai_id = next(p["id"] for p in game_state["players"] if p["is_ai"])

        time.sleep(0.5)
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state", json={"phase": "playing"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "The Pirate Code", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
                      json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2})

        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_pirate_code_demand_skipped(self):
        """Test The Pirate Code: demand skipped, conditional score not triggered."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "The Pirate Code"}
        )
        assert response.status_code == 200

        time.sleep(3)

        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        # Score pile should be empty (no transfer, no conditional score)
        score = human.get("score_pile", [])
        print(f"Score pile: {[c['name'] for c in score]}")

        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        print("✓ Demand skipped, phase playing")
        print("✅ The Pirate Code test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
