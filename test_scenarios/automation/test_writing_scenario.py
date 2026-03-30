#!/usr/bin/env python3
"""
Scenario Test: Writing

Tests Writing's basic draw effect - the simplest possible card:
- Effect 0: Draw a 2.

Primitives tested: DrawCards (basic, no variables)

Setup:
- Human: Writing (blue, 2 lightbulbs) on board
- AI: Agriculture (green, 0 lightbulbs) on board - won't share
- Human hand: known count

Expected:
- No sharing (AI has 0 lightbulbs < human's 2)
- Human draws 1 age 2 card to hand
- No interactions (auto-completes)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestWritingScenario:
    """Test Writing basic draw effect."""

    def setup_scenario(self) -> dict[str, Any]:
        print("\n" + "="*70)
        print("SETUP: Creating Writing basic draw scenario")
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

        # Human board: Writing (blue, 2 lightbulbs)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Writing", "location": "board"}
        )

        # AI board: Agriculture (green, 0 lightbulbs)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"}
        )

        print("✓ Setup complete")

        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )

        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_writing_basic_draw(self):
        """Test Writing: draw a 2 with no interactions."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Get initial hand count
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()
        human = next(p for p in initial_state["players"] if p["id"] == human_id)
        initial_hand_count = len(human.get("hand", []))
        print(f"Initial hand count: {initial_hand_count}")

        print("\n--- Executing Writing Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Writing"}
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"

        # Wait for auto-completion
        time.sleep(3)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        hand = human.get("hand", [])
        final_hand_count = len(hand)
        hand_names = [c["name"] for c in hand]

        print(f"Final hand: {hand_names}")
        print(f"Final hand count: {final_hand_count}")

        # Should have drawn exactly 1 card
        assert final_hand_count == initial_hand_count + 1, \
            f"Expected hand to increase by 1 (from {initial_hand_count} to {initial_hand_count + 1}), got {final_hand_count}"
        print(f"✓ Hand increased by 1 card (drew age 2)")

        # No pending interaction
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, "Should have no pending interaction"
        print("✓ No pending interaction")

        # Phase should still be playing
        phase = final.get("phase")
        assert phase == "playing", f"Expected phase 'playing', got {phase}"
        print("✓ Phase still 'playing'")

        # Check action log contains Writing
        action_log = final.get("action_log", [])
        writing_actions = [a for a in action_log if "Writing" in a.get("description", "")]
        assert len(writing_actions) > 0, "Action log should contain Writing dogma"
        print("✓ Action log contains Writing dogma")

        print("✅ Writing test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
