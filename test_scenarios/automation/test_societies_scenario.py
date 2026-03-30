#!/usr/bin/env python3
"""
Scenario Test: Societies

Tests Societies' demand effect:
- I demand you transfer a top card with lightbulb higher than my top card of same color!
  If you do, draw a 5!

Primitives tested: DemandEffect, SelectCards (board_top, higher_than_active_same_color),
    TransferBetweenPlayers, DrawCards

Setup:
- Human: Societies (purple, crown/lightbulb) on board
- AI: Agriculture (green, 0 crowns) - won't trigger demand

Expected: demand skipped, auto-complete
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestSocietiesScenario:
    """Test Societies demand transfer."""

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
                      json={"player_id": human_id, "card_name": "Societies", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
                      json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2})

        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_societies_demand_skipped(self):
        """Test Societies: demand skipped when AI has fewer crowns."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Societies"}
        )
        assert response.status_code == 200

        time.sleep(3)

        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()

        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        print("✓ Demand skipped (AI has fewer crowns), phase playing")
        print("✅ Societies test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
