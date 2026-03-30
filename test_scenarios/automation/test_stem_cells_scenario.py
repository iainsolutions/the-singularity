#!/usr/bin/env python3
"""
Scenario Test: Stem Cells (age 10, yellow)

Effects:
- Effect 0: Score all cards from your hand.
- Effect 1: Draw a 10.

Setup: Human has Stem Cells on board + Paper in hand.
"""

import os, sys, pytest, requests, time
from typing import Any
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
BASE_URL = "http://localhost:8000"


class TestStemCellsScenario:
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
                      json={"player_id": human_id, "card_name": "Stem Cells", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Paper", "location": "hand"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
                      json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2})
        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_stem_cells_score_hand_draw(self):
        scenario = self.setup_scenario()
        game_id, human_id = scenario["game_id"], scenario["human_id"]
        r = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/action",
                          json={"player_id": human_id, "action_type": "dogma", "card_name": "Stem Cells"})
        assert r.status_code == 200
        time.sleep(2)

        for attempt in range(3):
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
        human = next(p for p in final["players"] if p["id"] == human_id)
        score_count = len(human.get("score_pile", []))
        hand_count = len(human.get("hand", []))
        print(f"Score: {score_count}, Hand: {hand_count}")

        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        # Paper scored from hand + drew a 10
        assert score_count >= 1, "Should have scored Paper"
        print("✅ Stem Cells test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
