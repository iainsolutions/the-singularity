#!/usr/bin/env python3
"""
Scenario Test: Medicine (age 3, yellow)

Effects:
- Effect 0 (DEMAND): Exchange the highest card in your score pile with the lowest card in my score pile.
  Primitives: SelectHighest, SelectLowest, ExchangeCards
- Effect 1: Junk an available achievement of value 3 or 4.
  Primitives: SelectAchievement, TransferCards (to junk_pile)

Setup:
- Human: Medicine on board (leaf symbols)
- AI: Agriculture on board (fewer leaves) - demand skipped
- Effect 1 is non-demand sharing, so both AI and human may get select_achievement interaction
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestMedicineScenario:
    """Test Medicine demand + achievement junking."""

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
                      json={"player_id": human_id, "card_name": "Medicine", "location": "board"})
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

    def test_medicine_demand_and_junk_achievement(self):
        """Test Medicine: demand skipped, junk achievements (sharing)."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]
        ai_id = scenario["ai_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Medicine"}
        )
        assert response.status_code == 200
        time.sleep(2)

        for attempt in range(8):
            interaction, data, state = self._get_interaction(game_id)
            if not interaction:
                break

            interaction_type = interaction.get("interaction_type")
            # target_player_id is in data, not interaction_data
            target_player = data.get("target_player_id")
            responding_player = target_player if target_player else human_id
            print(f"Interaction {attempt}: type={interaction_type}, target={target_player}, responding_as={responding_player}")

            if interaction_type == "select_achievement":
                eligible = data.get("eligible_achievements", [])
                ach_id = eligible[0]["id"] if eligible and isinstance(eligible[0], dict) else (eligible[0] if eligible else None)
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": responding_player, "selected_achievement": ach_id}
                )
                print(f"  Selected achievement: {ach_id}")
            elif interaction_type == "select_cards":
                eligible = data.get("eligible_cards", [])
                card_id = eligible[0] if eligible else None
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": responding_player, "selected_cards": [card_id] if card_id else []}
                )
            elif interaction_type == "choose_option":
                options = data.get("options", [])
                value = str(options[0].get("value")) if options else "pass"
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": responding_player, "chosen_option": value}
                )
            else:
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
        print("✓ Phase playing, no pending")
        print("✅ Medicine test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
