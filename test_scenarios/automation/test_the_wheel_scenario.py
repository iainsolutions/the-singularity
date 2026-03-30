#!/usr/bin/env python3
"""
Scenario Test: The Wheel

Tests The Wheel's single effect:
- Draw two 1s.

Primitives tested: DrawCards (count=2, age=1)

Setup:
- Human: The Wheel (green, 3 castles) on board
- AI: Agriculture (green, 0 castles) - won't share

Expected:
- No sharing, no interactions
- Hand gains 2 age-1 cards
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestTheWheelScenario:
    """Test The Wheel draw effect."""

    def setup_scenario(self) -> dict[str, Any]:
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

        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "The Wheel", "location": "board"}
        )
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"}
        )
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )

        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_the_wheel_draw_two(self):
        """Test The Wheel: draw two age-1 cards."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Get initial hand count
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        initial = response.json()
        human_initial = next(p for p in initial["players"] if p["id"] == human_id)
        initial_hand_count = len(human_initial.get("hand", []))

        # Execute dogma
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "The Wheel"}
        )
        assert response.status_code == 200

        time.sleep(3)

        # Check final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        hand = human.get("hand", [])
        print(f"Hand: {[c['name'] for c in hand]} (count: {len(hand)})")

        assert len(hand) == initial_hand_count + 2, \
            f"Should draw 2 cards, was {initial_hand_count} now {len(hand)}"
        print("✓ Drew 2 cards")

        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        print("✅ The Wheel test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
