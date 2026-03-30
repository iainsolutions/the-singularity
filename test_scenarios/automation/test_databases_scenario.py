#!/usr/bin/env python3
"""
Scenario Test: Databases (age 10, green)

Effects:
- Effect 0 (DEMAND): Return cards from score pile equal to highest achievement value.

Setup: Human has Databases on board, AI has fewer clocks - demand skipped.
"""

import os, sys, pytest, requests, time
from typing import Any
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
BASE_URL = "http://localhost:8000"


class TestDatabasesScenario:
    def setup_scenario(self) -> dict[str, Any]:
        r = requests.post(f"{BASE_URL}/api/v1/games", json={})
        game_id = r.json()["game_id"]
        r = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/join", json={"name": "TestPlayer"})
        human_id = r.json()["player_id"]
        r = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/add_ai_player", json={"difficulty": "beginner"})
        ai_id = next(p["id"] for p in r.json()["game_state"]["players"] if p["is_ai"])
        time.sleep(0.5)
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state", json={"phase": "playing"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Databases", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
                      json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2})
        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_databases_demand_skipped(self):
        scenario = self.setup_scenario()
        game_id, human_id = scenario["game_id"], scenario["human_id"]
        r = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/action",
                          json={"player_id": human_id, "action_type": "dogma", "card_name": "Databases"})
        assert r.status_code == 200
        time.sleep(2)

        final = requests.get(f"{BASE_URL}/api/v1/games/{game_id}").json()
        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        print("✅ Databases test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
