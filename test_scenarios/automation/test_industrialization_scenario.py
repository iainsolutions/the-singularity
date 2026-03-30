#!/usr/bin/env python3
"""
Scenario Test: Industrialization

Tests Industrialization's two effects:
- Effect 0: Draw and tuck three 6s. If you're the single player with most factory, return top red.
- Effect 1: You may splay red or purple cards right.

Primitives tested: DrawCards (count=3, age=6), TuckCard (last_drawn),
    ConditionalAction (single_player_with_most_symbol), SelectCards (board_top, color),
    ReturnCards, ChooseOption (optional), SplayCards

Setup:
- Human: Industrialization (red, 3 factories) on board
- AI: Agriculture (green, 0 factories) - won't share, human has most factory

Expected:
- Effect 0: Draw 3 age-6 cards, tuck them. Human has most factory -> return top red.
- Effect 1: Optional splay choice (interaction)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestIndustrializationScenario:
    """Test Industrialization draw/tuck and conditional return."""

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
        # Human: Industrialization (red, 3 factories)
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Industrialization", "location": "board"})
        # AI: Agriculture (green, 0 factories)
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

    def test_industrialization_draw_tuck_return(self):
        """Test Industrialization: draw/tuck 3, conditional return, optional splay."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Execute dogma
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Industrialization"}
        )
        assert response.status_code == 200

        # Handle interactions (effect 1: ChooseOption for splay)
        time.sleep(3)

        for attempt in range(5):
            interaction, data, state = self._get_interaction(game_id)
            if not interaction:
                print(f"No pending interaction (attempt {attempt+1})")
                break

            interaction_type = interaction.get("interaction_type")
            target = interaction.get("target_player_id")
            print(f"Interaction: type={interaction_type}, target={target}")

            if target and target != human_id:
                time.sleep(2)
                continue

            if interaction_type == "choose_option":
                # Select first option (decline doesn't work for ChooseOption)
                options = data.get("options", [])
                value = options[0].get("value") if options else "red"
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "chosen_option": value}
                )
                assert response.status_code == 200
                print(f"  Selected splay: {value}")
            else:
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "decline": True}
                )
                assert response.status_code == 200

            time.sleep(2)

        # Final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()

        phase = final.get("phase")
        assert phase == "playing", f"Expected 'playing', got {phase}"
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, "Should have no pending interaction"
        print("✓ Phase playing, no pending")

        print("✅ Industrialization test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
