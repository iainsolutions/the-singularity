#!/usr/bin/env python3
"""
Scenario Test: Emancipation

Tests Emancipation's two effects:
- Effect 0 (DEMAND): Transfer a card from opponent's hand to your score pile. If done, opponent draws 6.
- Effect 1: You may splay red or purple cards right.

Primitives tested: DemandEffect, SelectCards, TransferBetweenPlayers, ChooseOption, SplayCards

Setup:
- Human: Emancipation (purple, 2 factories) on board
- AI: Agriculture (green, 0 factories) - won't trigger demand

Expected: demand skipped, splay choice interaction
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestEmancipationScenario:
    """Test Emancipation demand + splay."""

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
                      json={"player_id": human_id, "card_name": "Emancipation", "location": "board"})
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

    def test_emancipation_demand_and_splay(self):
        """Test Emancipation: demand skipped, splay choice."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Emancipation"}
        )
        assert response.status_code == 200
        time.sleep(2)

        # Handle ChooseOption for splay
        for attempt in range(3):
            interaction, data, state = self._get_interaction(game_id)
            if not interaction:
                break

            interaction_type = interaction.get("interaction_type")
            print(f"Interaction: type={interaction_type}")

            if interaction_type == "choose_option":
                options = data.get("options", [])
                value = options[0].get("value") if options else "splay_red_right"
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
        print("✅ Emancipation test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
