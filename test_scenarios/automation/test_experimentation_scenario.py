#!/usr/bin/env python3
"""
Scenario Test: Experimentation

Tests Experimentation's single effect:
- Draw and meld a 5.

Primitives tested: DrawCards (age 5), MeldCard (last_drawn)

Setup:
- Human: Experimentation (blue, 3 lightbulbs) on board
- AI: Agriculture (green, 0 lightbulbs) - won't share

Expected: auto-complete, no interactions, new age 5 card on board
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestExperimentationScenario:
    """Test Experimentation draw and meld."""

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
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Experimentation", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
                      json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2})

        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_experimentation_draw_and_meld(self):
        """Test Experimentation: draw age 5, meld it."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Experimentation"}
        )
        assert response.status_code == 200

        time.sleep(3)

        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        board = human.get("board", {})
        # Count total board cards across all colors
        total_board_cards = 0
        for color_key in ["red_cards", "blue_cards", "green_cards", "yellow_cards", "purple_cards"]:
            cards = board.get(color_key, [])
            if cards:
                print(f"  {color_key}: {[c.get('name') for c in cards]}")
                total_board_cards += len(cards)

        # Should have at least 2 cards on board (Experimentation + melded age 5)
        assert total_board_cards >= 2, f"Should have melded a card, total board = {total_board_cards}"
        print(f"✓ Board has {total_board_cards} cards (Experimentation + melded age 5)")

        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        print("✅ Experimentation test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
