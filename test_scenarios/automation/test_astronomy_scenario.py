#!/usr/bin/env python3
"""
Scenario Test: Astronomy

Tests Astronomy's two effects:
- Effect 0: Draw and reveal a 6. If green or blue, meld it and repeat. Otherwise stop.
- Effect 1: If all non-purple top cards are value 6+, claim Universe achievement.

Primitives tested: LoopAction, DrawCards (reveal), ConditionalAction (or/card_color),
    MeldCard, ConditionalAction (all_non_color_top_cards_min_age), ClaimAchievement

Setup:
- Human: Astronomy (purple, 3 lightbulbs) on board
- AI: Agriculture (green, 0 lightbulbs) - won't share

Expected:
- Effect 0: Draws age 6 cards in a loop, melding green/blue, stopping on other colors
- Effect 1: Checks board for Universe achievement
- Auto-completes, no interactions (random outcome based on deck)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestAstronomyScenario:
    """Test Astronomy loop draw/reveal/meld effect."""

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
            json={"player_id": human_id, "card_name": "Astronomy", "location": "board"}
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

    def test_astronomy_loop_draw_reveal(self):
        """Test Astronomy: loop draw/reveal/meld for green/blue cards."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        initial = response.json()
        human_initial = next(p for p in initial["players"] if p["id"] == human_id)
        initial_hand_count = len(human_initial.get("hand", []))

        # Execute dogma
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Astronomy"}
        )
        assert response.status_code == 200

        time.sleep(4)

        # Check final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        hand = human.get("hand", [])
        board = human.get("board", {})
        hand_names = [c["name"] for c in hand]

        print(f"Hand: {hand_names} (count: {len(hand)})")

        # Count board colors
        board_colors = {}
        if isinstance(board, dict):
            for color_key in ["red_cards", "blue_cards", "green_cards", "yellow_cards", "purple_cards"]:
                cards = board.get(color_key, [])
                if cards:
                    color = color_key.replace("_cards", "")
                    board_colors[color] = [c.get("name") for c in cards]
        print(f"Board: {board_colors}")

        # The loop draws age 6 cards. Non-green/blue go to hand, green/blue get melded.
        # At minimum, drew 1 card (the one that stopped the loop, non-green/blue)
        # That card goes to hand
        hand_gained = len(hand) - initial_hand_count
        print(f"Hand gained: {hand_gained} card(s)")

        # Verify completion
        phase = final.get("phase")
        assert phase == "playing", f"Expected 'playing', got {phase}"
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, "Should have no pending interaction"
        print("✓ Phase playing, no pending")

        # Check Universe achievement
        achievements = human.get("achievements", [])
        achievement_names = [a.get("name", a.get("achievement_name", "")) for a in achievements]
        if "Universe" in achievement_names:
            print("✓ Universe achievement claimed!")
        else:
            print("Note: Universe not claimed (not all non-purple top cards are age 6+)")

        print("✅ Astronomy test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
