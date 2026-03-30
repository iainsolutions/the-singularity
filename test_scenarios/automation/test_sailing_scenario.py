#!/usr/bin/env python3
"""
Scenario Test: Sailing

Tests Sailing's draw and meld effect:
- Effect 0: Draw and meld a 1.

Primitives tested: DrawCards, MeldCard (selection=last_drawn)

Setup:
- Human: Sailing (green, 2 crowns) on board
- AI: Agriculture (yellow, 0 crowns) on board - won't share
- Human hand: empty

Expected:
- No sharing (AI has 0 crowns < human's 2)
- Human draws age 1 card to hand, then melds it (moves to board)
- No interactions (auto-completes)
- Hand count unchanged (drew 1, melded 1)
- Board should have a new card (the drawn age 1 card was melded)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestSailingScenario:
    """Test Sailing draw and meld effect."""

    def setup_scenario(self) -> dict[str, Any]:
        print("\n" + "="*70)
        print("SETUP: Creating Sailing Scenario")
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

        # Human board: Sailing (green, 2 crowns)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Sailing", "location": "board", "color": "green"}
        )

        # AI board: Agriculture (yellow, 0 crowns)
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

    def test_sailing_draw_and_meld(self):
        """Test Sailing: draw age 1 and meld it."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial = response.json()
        human_initial = next(p for p in initial["players"] if p["id"] == human_id)
        initial_hand_count = len(human_initial.get("hand", []))
        initial_board = human_initial.get("board", {})
        initial_board_cards = initial_board
        initial_green_count = len(initial_board.get("green_cards", []))

        print(f"Initial hand count: {initial_hand_count}")
        print(f"Initial green board count: {initial_green_count}")

        print("\n--- Executing Sailing Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Sailing"}
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
        board = human.get("board", {})
        green_cards = board.get("green_cards", [])
        hand_names = [c["name"] for c in hand]
        green_names = [c["name"] for c in green_cards]

        print(f"Final hand: {hand_names}")
        print(f"Final green board: {green_names}")

        # Assertions
        # 1. Hand count unchanged (drew 1, melded 1)
        assert len(hand) == initial_hand_count, f"Hand count should be unchanged, was {initial_hand_count}, now {len(hand)}"
        print(f"✓ Hand count unchanged: {len(hand)}")

        # 2. Board should have a new card melded (could be any color, not necessarily green)
        total_board_cards = sum(len(board.get(f"{c}_cards", [])) for c in ["red", "blue", "green", "yellow", "purple"])
        initial_total_board = sum(len(initial_board.get(f"{c}_cards", [])) for c in ["red", "blue", "green", "yellow", "purple"])
        assert total_board_cards == initial_total_board + 1, \
            f"Board should have 1 more card (melded), was {initial_total_board}, now {total_board_cards}"
        print(f"✓ Board has 1 new melded card ({total_board_cards} total)")

        # 4. No pending interaction
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Should have no pending interaction"
        print("✓ No pending interaction")

        # 5. Phase still playing
        phase = final.get("phase")
        assert phase == "playing", f"Phase should be 'playing', got '{phase}'"
        print(f"✓ Phase is 'playing'")

        # 6. Action log contains Sailing
        action_log = final.get("action_log", [])
        sailing_actions = [a for a in action_log if "Sailing" in str(a)]
        assert len(sailing_actions) > 0, f"Action log should mention Sailing"
        print(f"✓ Action log contains Sailing execution")

        print("✅ Sailing test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
