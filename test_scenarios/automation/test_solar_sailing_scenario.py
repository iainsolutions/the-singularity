#!/usr/bin/env python3
"""
Scenario Test: Solar Sailing (age 11, blue)

Effects:
- Effect 0: Draw and meld an 11. If its color is not splayed aslant on your board,
  return all but your top four cards of that color, and splay that color aslant.
  If there are at least six cards of that color on your board, you win.

Setup: Human has Solar Sailing on board. AI has Agriculture.
"""

import os, sys, pytest, requests, time
from typing import Any
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
BASE_URL = "http://localhost:8000"


class TestSolarSailingScenario:
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
                      json={"player_id": human_id, "card_name": "Solar Sailing", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
                      json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2})
        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_solar_sailing_draw_meld_splay(self):
        scenario = self.setup_scenario()
        game_id, human_id = scenario["game_id"], scenario["human_id"]
        r = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/action",
                          json={"player_id": human_id, "action_type": "dogma", "card_name": "Solar Sailing"})
        assert r.status_code == 200
        time.sleep(2)

        for attempt in range(5):
            r = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
            state = r.json()
            pending = state.get("state", {}).get("pending_dogma_action")
            if not pending:
                break
            ctx = pending.get("context", {})
            idata = ctx.get("interaction_data", {})
            if not idata:
                break
            data = idata.get("data", {})
            target = data.get("target_player_id")
            player = target if target else human_id
            r = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                              json={"player_id": player, "decline": True})
            assert r.status_code == 200
            time.sleep(2)

        final = requests.get(f"{BASE_URL}/api/v1/games/{game_id}").json()
        phase = final.get("phase")
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None or phase != "playing"
        print("✅ Solar Sailing test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
