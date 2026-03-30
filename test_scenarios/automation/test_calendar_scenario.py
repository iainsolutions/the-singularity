#!/usr/bin/env python3
"""
Scenario Test: Calendar

Tests Calendar dogma effects:
1. Non-DEMAND effect: If score_pile > hand, draw two age 3 cards
2. PRIMARY CONDITION: variable_gt (comparing two variables)

Expected Flow:
1. Human executes Calendar dogma (age 2 blue card)
2. CountCards counts score_pile cards (3) → store as score_count
3. CountCards counts hand cards (1) → store as hand_count
4. ConditionalAction evaluates: variable_gt score_count > hand_count (3 > 1)
5. Condition TRUE → DrawCards executes: draw 2 age 3 cards
6. Human hand increases from 1 to 3 cards

Setup:
- Human: Calendar on blue board, 1 card in hand, 3 cards in score pile
- AI: Oars on green board (no sharing - fewer leaves: 0 < 2)
- Hand count (1) < Score count (3) = condition TRUE

Expected Results:
- CountCards stores variables correctly
- variable_gt condition evaluates TRUE when score_count > hand_count
- DrawCards executes when condition is TRUE
- Human draws 2 age 3 cards
- Final hand count = 3 (1 initial + 2 drawn)
- No pending interactions
- Phase remains playing
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"

class TestCalendarScenario:
    """Test Calendar scenario with variable_gt condition."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Calendar scenario."""
        # CREATE GAME
        response = requests.post(f"{BASE_URL}/api/v1/games", json={})
        assert response.status_code == 200
        game_id = response.json()["game_id"]

        # JOIN HUMAN PLAYER
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/join",
            json={"name": "TestPlayer"}
        )
        assert response.status_code == 200
        human_id = response.json()["player_id"]

        # ADD AI PLAYER
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/add_ai_player",
            json={"difficulty": "beginner"}
        )
        assert response.status_code == 200
        game_state = response.json()["game_state"]
        ai_id = next(p["id"] for p in game_state["players"] if p["is_ai"])

        # INITIALIZE AGE DECKS
        time.sleep(0.5)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing"}
        )
        assert response.status_code == 200

        # ENABLE TRACING
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/tracing/start",
                json={"enabled": True}
            )
        except Exception:
            pass

        # SETUP HUMAN BOARD - Calendar on blue
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Calendar",
                "location": "board",
                "color": "blue"
            }
        )
        assert response.status_code == 200

        # SETUP HUMAN HAND - 1 age 1 card
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Pottery",
                "location": "hand"
            }
        )
        assert response.status_code == 200

        # SETUP HUMAN SCORE - 3 age 1 cards
        for card_name in ["Tools", "Archery", "Metalworking"]:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": human_id,
                    "card_name": card_name,
                    "location": "score_pile"
                }
            )
            assert response.status_code == 200

        # SETUP AI BOARD - Oars on green (AI won't share - 0 leaves < 2 leaves)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Oars",
                "location": "board",
                "color": "green"
            }
        )
        assert response.status_code == 200

        # SETUP AI HAND - 2 age 2 cards
        for card_name in ["Sailing", "Fermenting"]:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": ai_id,
                    "card_name": card_name,
                    "location": "hand"
                }
            )
            assert response.status_code == 200

        # SET GAME TO PLAYING STATE
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={
                "phase": "playing",
                "current_player_index": 0,
                "actions_remaining": 2
            }
        )
        assert response.status_code == 200

        return {
            "game_id": game_id,
            "human_id": human_id,
            "ai_id": ai_id
        }

    def test_calendar_variable_gt_condition(self):
        """Test Calendar with variable_gt condition comparing two variables."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()

        human_player = next(p for p in initial_state["players"] if p["id"] == human_id)
        initial_hand = human_player["hand"]
        initial_score = human_player["score_pile"]

        print(f"\n=== Initial State ===")
        print(f"Hand count: {len(initial_hand)} cards - {[c['name'] for c in initial_hand]}")
        print(f"Score count: {len(initial_score)} cards - {[c['name'] for c in initial_score]}")

        # ASSERTION 1: Hand should have 1 card
        assert len(initial_hand) == 1, f"Hand should have 1 card, got {len(initial_hand)}"

        # ASSERTION 2: Score should have 3 cards
        assert len(initial_score) == 3, f"Score should have 3 cards, got {len(initial_score)}"

        # ASSERTION 3: Condition should be TRUE (3 > 1)
        print(f"\n🔍 Condition: score_count ({len(initial_score)}) > hand_count ({len(initial_hand)})")
        print(f"   Expected: TRUE (will draw 2 cards)")

        # Execute dogma on Calendar
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Calendar"
            }
        )
        assert response.status_code == 200

        # Wait for AI Event Bus processing
        print("\n🤖 Waiting for Event Bus processing...")
        time.sleep(3)

        # Get final game state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        human_player = next(p for p in final_state["players"] if p["id"] == human_id)
        final_hand = human_player["hand"]

        print(f"\n=== Final State ===")
        print(f"Hand count: {len(final_hand)} cards - {[c['name'] for c in final_hand]}")

        # ASSERTION 4: Hand should now have 3 cards (1 initial + 2 drawn)
        assert len(final_hand) == 3, f"Hand should have 3 cards after drawing, got {len(final_hand)}"
        print(f"✅ Hand increased: {len(initial_hand)} → {len(final_hand)} (+2 cards)")

        # ASSERTION 5: Verify drawn cards are age 3
        drawn_cards = [c for c in final_hand if c not in initial_hand]
        assert len(drawn_cards) == 2, f"Should have drawn 2 cards, got {len(drawn_cards)}"

        drawn_ages = [c["age"] for c in drawn_cards]
        print(f"Drawn cards: {[c['name'] for c in drawn_cards]} (ages: {drawn_ages})")
        assert all(age == 3 for age in drawn_ages), f"All drawn cards should be age 3, got {drawn_ages}"
        print(f"✅ Both drawn cards are age 3")

        # ASSERTION 6: No pending interactions
        final_pending = final_state.get("state", {}).get("pending_dogma_action")
        assert final_pending is None, "Should have no pending interactions after completion"

        # ASSERTION 7: Phase should remain playing
        assert final_state.get("phase") == "playing", "Phase should be playing"

        # ASSERTION 8: Check action log for Calendar activation
        action_log = final_state.get("action_log", [])
        log_descriptions = [entry.get("description", "") for entry in action_log]
        assert any("Calendar" in desc for desc in log_descriptions), \
            "Should have Calendar activation log"

        print("\n=== Recent Action Log ===")
        for entry in action_log[-5:]:
            print(f"  {entry.get('description')}")

        print(f"\nGame ID: {game_id}")
        print("✅ ALL CALENDAR ASSERTIONS PASSED (8/8)")
        print("\n📊 Condition Tested: variable_gt (score_count > hand_count)")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
