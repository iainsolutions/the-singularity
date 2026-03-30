#!/usr/bin/env python3
"""
Scenario Test: Services (age 9, purple)

Effects:
- Effect 0 (DEMAND): Choose a value, transfer all cards of that value from opponent's score pile to my hand.
  Primitives: DemandEffect, ChooseOption (1-11), FilterCards, TransferBetweenPlayers

Setup:
- Human: Services on board (leaf symbols)
- AI: Agriculture (fewer leaves) - demand skipped
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestServicesScenario:
    """Test Services demand + value choice."""

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
                      json={"player_id": human_id, "card_name": "Services", "location": "board"})
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

    def test_services_demand_skipped(self):
        """Test Services: demand skipped."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Services"}
        )
        assert response.status_code == 200
        time.sleep(2)

        for attempt in range(3):
            interaction, data, state = self._get_interaction(game_id)
            if not interaction:
                break
            target_player = data.get("target_player_id")
            responding_player = target_player if target_player else human_id
            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                json={"player_id": responding_player, "decline": True}
            )
            assert response.status_code == 200
            time.sleep(2)

        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()
        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        print("✅ Services test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
