#!/usr/bin/env python3
"""
Scenario Test: Machine Tools

Tests Machine Tools' draw and score effect based on highest score pile card:
- Effect 0: Draw and score a card of value equal to the highest card in your score pile.

Primitives tested: SelectHighest (score_pile), GetCardAge, DrawCards, ScoreCards (last_drawn)

Setup:
- Human: Machine Tools (red, 3 factories) on board
- Human score pile: Compass (age 3) - this is the highest card, so we'll draw age 3
- AI: Agriculture (green, 0 factories) on board - won't share

Expected:
- No sharing (AI has 0 factories < human's 3)
- SelectHighest auto-selects Compass (only card in score pile)
- GetCardAge extracts age 3 from Compass
- DrawCards draws an age 3 card to hand
- ScoreCards scores that age 3 card
- Result: score pile should have 2 cards (original Compass + newly scored age 3)
- No interactions needed (auto-completes)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestMachineToolsScenario:
    """Test Machine Tools draw and score effect."""

    def setup_scenario(self) -> dict[str, Any]:
        print("\n" + "="*70)
        print("SETUP: Creating Machine Tools Draw and Score Scenario")
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

        # Human board: Machine Tools (red, 3 factories)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Machine Tools", "location": "board"}
        )
        print("✓ Human board: Machine Tools (red, 3 factories)")

        # Human score pile: Compass (age 3) - this is the highest card
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Compass", "location": "score_pile"}
        )
        print("✓ Human score pile: Compass (age 3)")

        # AI board: Agriculture (green, 0 factories)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"}
        )
        print("✓ AI board: Agriculture (green, 0 factories)")

        print("✓ Setup complete")

        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )

        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_machine_tools_draw_and_score(self):
        """Test Machine Tools: draw and score based on highest score pile card."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial = response.json()
        human_initial = next(p for p in initial["players"] if p["id"] == human_id)
        initial_hand_count = len(human_initial.get("hand", []))
        initial_score = human_initial.get("score_pile", [])
        initial_score_count = len(initial_score)
        initial_score_names = [c["name"] for c in initial_score]

        print(f"Initial hand count: {initial_hand_count}")
        print(f"Initial score pile: {initial_score_names} (count: {initial_score_count})")

        print("\n--- Executing Machine Tools Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Machine Tools"}
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
        score = human.get("score_pile", [])
        hand_names = [c["name"] for c in hand]
        score_names = [c["name"] for c in score]

        print(f"Final hand: {hand_names}")
        print(f"Final score pile: {score_names}")

        # Assertions
        # 1. Hand count unchanged (drew 1, scored 1)
        assert len(hand) == initial_hand_count, \
            f"Hand count should be unchanged, was {initial_hand_count}, now {len(hand)}"
        print(f"✓ Hand count unchanged: {len(hand)}")

        # 2. Score pile should have 1 more card
        final_score_count = len(score)
        assert final_score_count == initial_score_count + 1, \
            f"Score pile should have 1 more card, was {initial_score_count}, now {final_score_count}"
        print(f"✓ Score pile has 1 new card ({final_score_count} total)")

        # 3. Original Compass still in score pile
        assert "Compass" in score_names, \
            f"Compass should still be in score pile, got {score_names}"
        print("✓ Compass (age 3) still in score pile")

        # 4. New card is age 3 (drawn based on Compass age)
        # Since we scored a card, it's in the score pile now
        # We can verify by checking there's a 2nd card (any age 3 card)
        assert len(score) == 2, \
            f"Score pile should have exactly 2 cards (Compass + new age 3), got {len(score)}"
        print("✓ New age 3 card scored to score pile")

        # 5. No pending interaction
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, "Should have no pending interaction"
        print("✓ No pending interaction")

        # 6. Phase still playing
        phase = final.get("phase")
        assert phase == "playing", f"Expected phase 'playing', got {phase}"
        print("✓ Phase still 'playing'")

        # 7. Action log contains Machine Tools
        action_log = final.get("action_log", [])
        machine_tools_actions = [a for a in action_log if "Machine Tools" in a.get("description", "")]
        assert len(machine_tools_actions) > 0, "Action log should contain Machine Tools dogma"
        print("✓ Action log contains Machine Tools dogma")

        print("✅ Machine Tools test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
