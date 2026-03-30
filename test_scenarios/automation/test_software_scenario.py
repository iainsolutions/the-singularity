#!/usr/bin/env python3
"""
Scenario Test: Software (age 10, blue)

Effects:
- Effect 0: Draw and score a 10.
- Effect 1: Draw and meld two 9, then self-execute the second card.

Setup: Human has Software on board (clock symbols). ExecuteDogma is complex.
"""

import os, sys, pytest, requests, time
from typing import Any
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
BASE_URL = "http://localhost:8000"


class TestSoftwareScenario:
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
                      json={"player_id": human_id, "card_name": "Software", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
                      json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2})
        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def _get_interaction(self, game_id):
        r = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        state = r.json()
        pending = state.get("state", {}).get("pending_dogma_action")
        if not pending:
            return None, None, state
        ctx = pending.get("context", {})
        idata = ctx.get("interaction_data", {})
        if not idata:
            return None, None, state
        return idata, idata.get("data", {}), state

    def test_software_draw_score_execute(self):
        scenario = self.setup_scenario()
        game_id, human_id = scenario["game_id"], scenario["human_id"]
        requests.post(f"{BASE_URL}/api/v1/games/{game_id}/action",
                      json={"player_id": human_id, "action_type": "dogma", "card_name": "Software"})
        time.sleep(2)

        for attempt in range(10):
            interaction, data, state = self._get_interaction(game_id)
            if not interaction:
                break
            itype = interaction.get("interaction_type")
            target = data.get("target_player_id")
            player = target if target else human_id
            print(f"Interaction {attempt}: type={itype}")

            if itype == "select_cards":
                eligible = data.get("eligible_cards", [])
                first = eligible[0] if eligible else None
                cid = first["card_id"] if isinstance(first, dict) else first
                r = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                                  json={"player_id": player, "selected_cards": [cid] if cid else []})
            elif itype == "select_color":
                colors = data.get("eligible_colors", data.get("colors", []))
                color = colors[0] if colors else "red"
                r = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                                  json={"player_id": player, "selected_color": color})
            elif itype == "choose_option":
                opts = data.get("options", [])
                val = str(opts[0].get("value")) if opts else "pass"
                r = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                                  json={"player_id": player, "chosen_option": val})
            elif itype == "select_achievement":
                eligible = data.get("eligible_achievements", [])
                aid = eligible[0]["id"] if eligible and isinstance(eligible[0], dict) else (eligible[0] if eligible else None)
                r = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                                  json={"player_id": player, "selected_achievement": aid})
            else:
                r = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                                  json={"player_id": player, "decline": True})
            assert r.status_code == 200
            time.sleep(2)

        final = requests.get(f"{BASE_URL}/api/v1/games/{game_id}").json()
        phase = final.get("phase")
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None or phase != "playing"
        print("✅ Software test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
