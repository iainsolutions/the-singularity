#!/usr/bin/env python3
"""
Scenario Test: Statistics

Tests Statistics dogma effects:
1. Effect 0 (DEMAND): "I demand you transfer all the cards of the value of my choice
   in your score pile to your hand!"
2. Effect 1: "You may splay your yellow cards right."

Primitives tested: DemandEffect, ChooseOption, FilterCards, TransferCards, SplayCards

Setup:
- Human: Statistics (yellow, 2 leaf symbols) on board
- AI: Clothing (green, 1 leaf symbol) - AI gets demanded (fewer leaves)
- AI score pile: Paper (age 3), Metalworking (age 1)

NOTE: ChooseOption in demand context executes against the demanded player (AI).
AI auto-responds via Anthropic API. Test verifies dogma completes, not specific choice.
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestStatisticsScenario:
    """Test Statistics demand + splay effects."""

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

        # Human board: Statistics (yellow, 2 leaf)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Statistics", "location": "board", "color": "yellow"}
        )

        # AI board: Clothing (green, 1 leaf) - fewer leaves → demanded
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Clothing", "location": "board", "color": "green"}
        )

        # AI score pile: Paper (age 3) and Metalworking (age 1)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Paper", "location": "score_pile"}
        )
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Metalworking", "location": "score_pile"}
        )

        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )

        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_statistics_demand_complete(self):
        """Test Statistics demand completes without hanging."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]
        ai_id = scenario["ai_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        initial = response.json()
        ai_initial = next(p for p in initial["players"] if p["id"] == ai_id)
        initial_ai_score = len(ai_initial["score_pile"])
        initial_ai_hand = len(ai_initial.get("hand", []))

        print(f"Initial AI score pile: {initial_ai_score} cards")
        print(f"Initial AI hand: {initial_ai_hand} cards")

        # Execute Statistics dogma
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Statistics"}
        )
        assert response.status_code == 200

        # Wait for AI API response (ChooseOption goes to AI in demand context)
        time.sleep(8)

        # Poll for completion
        for attempt in range(20):
            time.sleep(0.5)
            response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
            state = response.json()
            if not state.get("state", {}).get("pending_dogma_action"):
                print(f"Dogma completed after {8 + (attempt + 1) * 0.5}s")
                break
        else:
            print("Warning: Dogma still pending after 18s")

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()
        ai_final = next(p for p in final["players"] if p["id"] == ai_id)
        final_ai_score = len(ai_final["score_pile"])
        final_ai_hand = len(ai_final.get("hand", []))

        print(f"Final AI score pile: {final_ai_score} cards")
        print(f"Final AI hand: {final_ai_hand} cards")

        # The AI chooses an age via ChooseOption. If it picks age 1 or 3,
        # matching cards transfer from score pile to hand.
        # We can't predict what the AI picks, so verify:
        # 1. Total cards conserved (score + hand unchanged)
        total_before = initial_ai_score + initial_ai_hand
        total_after = final_ai_score + final_ai_hand
        assert total_after == total_before, (
            f"AI card count should be conserved (transfer, not destruction). "
            f"Before: {total_before}, After: {total_after}"
        )
        print(f"✓ Card conservation: {total_before} = {total_after}")

        # 2. No pending interaction
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, "Should have no pending interaction"
        print("✓ No pending interaction")

        # 3. Phase still playing
        assert final["phase"] == "playing"
        print("✓ Phase is playing")

        # 4. Action log
        action_log = final.get("action_log", [])
        stats_actions = [a for a in action_log if "Statistics" in str(a)]
        assert len(stats_actions) > 0
        print("✓ Statistics in action log")

        print("✅ Statistics demand test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
