#!/usr/bin/env python3
"""
Scenario Test: Atomic Theory

Tests Atomic Theory's two effects:
- Effect 0: You may splay your blue cards right.
- Effect 1: Draw and meld a 7.

Primitives tested: SplayCards (optional), DrawCards, MeldCard

Setup:
- Human: Atomic Theory (blue, 3 lightbulbs) on board
- AI: Agriculture (green, 0 lightbulbs) - won't share

Expected: auto-complete, no interactions, age 7 melded to board
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestAtomicTheoryScenario:
    """Test Atomic Theory splay + draw/meld."""

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
                      json={"player_id": human_id, "card_name": "Atomic Theory", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
                      json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2})
        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_atomic_theory_splay_and_meld(self):
        """Test Atomic Theory: splay blue, draw and meld 7."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Atomic Theory"}
        )
        assert response.status_code == 200
        time.sleep(3)

        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        board = human.get("board", {})
        total_cards = sum(len(board.get(c, [])) for c in ["red_cards", "blue_cards", "green_cards", "yellow_cards", "purple_cards"])
        print(f"Board has {total_cards} cards (Atomic Theory + melded 7)")
        assert total_cards >= 2, f"Should have melded a 7, total={total_cards}"

        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        print("✅ Atomic Theory test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
