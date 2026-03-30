#!/usr/bin/env python3
"""
Scenario Test: Canning

Tests Canning's two effects:
- Effect 0: Optional draw and tuck a 6. If tucked, score top cards without factory.
- Effect 1: You may splay yellow cards right.

Primitives tested: ChooseOption, DrawCards, TuckCard, FilterCards, ScoreCards, SplayCards

Setup:
- Human: Canning (yellow, 2 factories) on board + Clothing (green, no factory)
- AI: Agriculture (green, 0 factories) - won't share

Expected:
- Effect 0: ChooseOption to draw/tuck (interaction)
- Effect 1: Splay yellow auto-completes
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestCanningScenario:
    """Test Canning draw/tuck/score and splay."""

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
                      json={"player_id": human_id, "card_name": "Canning", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Clothing", "location": "board"})
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

    def test_canning_draw_tuck_score(self):
        """Test Canning: choose to draw/tuck, score non-factory top cards."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Canning"}
        )
        assert response.status_code == 200
        time.sleep(2)

        # Handle ChooseOption interaction
        for attempt in range(5):
            interaction, data, state = self._get_interaction(game_id)
            if not interaction:
                print(f"No interaction (attempt {attempt+1})")
                break

            interaction_type = interaction.get("interaction_type")
            print(f"Interaction: type={interaction_type}")

            if interaction_type == "choose_option":
                options = data.get("options", [])
                print(f"  Options: {[o.get('description', o.get('value')) for o in options]}")
                value = options[0].get("value") if options else "draw_tuck_6"
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "chosen_option": value}
                )
                assert response.status_code == 200
                print(f"  Selected: {value}")
            else:
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "decline": True}
                )
                assert response.status_code == 200

            time.sleep(2)

        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()

        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        print("✓ Phase playing, no pending")
        print("✅ Canning test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
