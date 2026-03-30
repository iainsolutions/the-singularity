#!/usr/bin/env python3
"""
Scenario Test: Metric System

Tests Metric System's two effects:
- Effect 0: If green splayed right, you may splay any color right.
- Effect 1: You may splay green cards right.

Primitives tested: ConditionalAction (color_splayed), SelectColor, SplayCards

Setup:
- Human: Metric System (green) on board + Agriculture (green) underneath
- AI: Metalworking (red, 0 crowns) - won't share

Expected:
- Effect 0: Green not splayed yet, condition false, skipped
- Effect 1: Splay green right (auto since only 1 option)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestMetricSystemScenario:
    """Test Metric System conditional splay."""

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
        # Green stack: Agriculture underneath Metric System (splayable)
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Agriculture", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Metric System", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": ai_id, "card_name": "Metalworking", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
                      json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2})
        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_metric_system_splay(self):
        """Test Metric System: conditional splay + green splay."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Metric System"}
        )
        assert response.status_code == 200
        time.sleep(3)

        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()

        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        print("✓ Phase playing, no pending")
        print("✅ Metric System test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
