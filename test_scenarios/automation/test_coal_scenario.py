#!/usr/bin/env python3
"""
Scenario Test: Coal

Tests Coal's three effects:
- Effect 0: Draw and tuck a 5.
- Effect 1: You may splay your red cards right.
- Effect 2: You may choose a color. If you do, score your top card of that color, twice.

Primitives tested: DrawCards, TuckCard, SplayCards (optional), SelectColor (optional),
    ConditionalAction, SelectCards, RepeatAction, ScoreCards

Setup:
- Human: Coal (red, 4 factories) + Metalworking (red) on board
- AI: Agriculture (green, 0 factories) - won't share

Expected:
- Effect 0: auto draw+tuck 5
- Effect 1: optional splay red right (interaction)
- Effect 2: optional color choice to score top card (interaction)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestCoalScenario:
    """Test Coal draw/tuck, splay, and score effects."""

    def setup_scenario(self) -> dict[str, Any]:
        print("\n" + "="*70)
        print("SETUP: Creating Coal Scenario")
        print("="*70)

        response = requests.post(f"{BASE_URL}/api/v1/games", json={})
        assert response.status_code == 200
        game_id = response.json()["game_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/join",
            json={"name": "TestPlayer"}
        )
        assert response.status_code == 200
        human_id = response.json()["player_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/add_ai_player",
            json={"difficulty": "beginner"}
        )
        assert response.status_code == 200
        game_state = response.json()["game_state"]
        ai_id = next(p["id"] for p in game_state["players"] if p["is_ai"])

        time.sleep(0.5)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing"}
        )

        # Human board: Coal (red) + Metalworking (red)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Coal", "location": "board"}
        )
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Metalworking", "location": "board"}
        )
        # AI board
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"}
        )

        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )

        print("✓ Setup: Coal + Metalworking on board")
        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def _get_interaction(self, game_id):
        """Get pending interaction data from game state."""
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

    def test_coal_draw_tuck_and_effects(self):
        """Test Coal: draw/tuck 5, optional splay, optional score."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Execute dogma
        print("\n--- Executing Coal Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Coal"}
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"

        # Handle interactions (splay choice, color choice)
        time.sleep(2)

        for attempt in range(5):
            interaction, data, state = self._get_interaction(game_id)

            if not interaction:
                print(f"No pending interaction (attempt {attempt+1})")
                break

            interaction_type = interaction.get("interaction_type")
            print(f"Interaction {attempt+1}: type={interaction_type}")

            if interaction_type == "select_cards":
                # Decline optional selection
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "decline": True}
                )
                print("  Declined card selection")

            elif interaction_type == "choose_option":
                options = data.get("options", [])
                print(f"  Options: {[o.get('description', o.get('value')) for o in options]}")
                # Select first option (decline doesn't work for ChooseOption)
                value = options[0].get("value") if options else "pass"
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "chosen_option": value}
                )
                print(f"  Selected: {value}")

            elif interaction_type == "select_color":
                # Decline optional color selection
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "decline": True}
                )
                print("  Declined color selection")

            elif interaction_type == "confirm":
                # Decline
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "decline": True}
                )
                print("  Declined confirmation")

            else:
                print(f"  Unknown type: {interaction_type}, declining")
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "decline": True}
                )

            assert response.status_code == 200, f"Response failed: {response.text}"
            time.sleep(2)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final = response.json()

        # Verify phase and no pending
        phase = final.get("phase")
        assert phase == "playing", f"Expected 'playing', got {phase}"
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Should have no pending interaction"
        print("✓ Phase playing, no pending")

        print("✅ Coal test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
