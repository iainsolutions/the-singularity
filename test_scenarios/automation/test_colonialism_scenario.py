#!/usr/bin/env python3
"""
Scenario Test: Colonialism

Tests Colonialism's LoopAction with has_symbol crown check breaking the loop.

Card Text:
"Draw and tuck a 3. If it is green, junk all cards in the 5 deck.
If it has crown, repeat this effect."

Expected Flow:
1. Loop: Draw age 3 card → Tuck it
2. If green: Junk all age 5 deck cards
3. If has crown: Continue loop
4. If NO crown: BREAK loop (stop repeating)

Setup:
- Human: Colonialism (red) on board
- Natural age 3 deck (default shuffle)
- Max 10 iterations in loop

Expected Results:
- Loop should draw cards from age 3 until it hits one without crown
- Then loop should BREAK
- We check debug logs showing has_symbol returning TRUE/FALSE
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"

class TestColonialismScenario:
    """Test Colonialism loop break on card without crown."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Colonialism scenario."""
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

        # SETUP CARDS
        # Human board: Colonialism (red)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Colonialism",
                "location": "board",
                "color": "red"
            }
        )
        assert response.status_code == 200

        # AI board: Something with factory symbols
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Machinery",
                "location": "board",
                "color": "yellow"
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

    def test_colonialism_loop_with_natural_deck(self):
        """Test Colonialism loop behavior with natural age 3 deck."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()
        human_player = next(p for p in initial_state["players"] if p["id"] == human_id)

        # Count initial red cards (should have Colonialism)
        initial_red_count = len(human_player["board"].get("red_cards", []))
        assert initial_red_count == 1, "Should start with 1 red card (Colonialism)"

        # Execute Colonialism dogma
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Colonialism"
            }
        )
        assert response.status_code == 200

        # Poll for dogma to complete (no interactions expected)
        for attempt in range(30):  # 30 attempts = 15 seconds max
            time.sleep(0.5)
            response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
            state = response.json()
            pending_dogma = state.get("state", {}).get("pending_dogma_action")

            # Dogma completed - break
            if not pending_dogma:
                print(f"✓ Dogma completed after {(attempt + 1) * 0.5}s")
                break

            if attempt % 6 == 0:  # Log every 3 seconds
                print(f"  Waiting for dogma completion... (attempt {attempt+1})")
        else:
            print(f"⚠ Warning: Timeout after 15s")
            print(f"  Final: pending={bool(pending_dogma)}")

        # CRITICAL: Extra wait to ensure full state persistence
        time.sleep(0.5)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        # Get human player
        human_player = next(p for p in final_state["players"] if p["id"] == human_id)

        # Get all tucked cards (all color stacks)
        board = human_player["board"]
        all_tucked_cards = []
        for color in ["red", "blue", "green", "yellow", "purple"]:
            cards = board.get(f"{color}_cards", [])
            all_tucked_cards.extend([c["name"] for c in cards])

        # ASSERTIONS
        print(f"\nGame ID: {game_id}")
        print(f"Tucked cards: {all_tucked_cards}")
        print(f"Total cards on board: {len(all_tucked_cards)}")

        # The loop should have stopped at SOME point < 10 iterations
        # If the bug exists, it will do all 10 iterations
        total_cards_on_board = len(all_tucked_cards)

        # We expect Colonialism + some tucked cards (not all 10)
        # If loop breaks correctly, should be less than 10 total cards
        assert total_cards_on_board < 11, (
            f"Loop appears to have executed max iterations (10). "
            f"Expected it to break earlier when hitting card without crown. "
            f"Got {total_cards_on_board} cards: {all_tucked_cards}"
        )

        # Colonialism should still be on board (wasn't junked)
        assert "Colonialism" in all_tucked_cards, (
            "Colonialism should still be on board"
        )

        # No errors in context
        context = final_state.get("context", {})
        assert not context.get("error"), f"Unexpected error: {context.get('error')}"

        # Phase should still be 'playing'
        assert final_state["phase"] == "playing", (
            f"Expected phase 'playing', got '{final_state['phase']}'"
        )

        print("✅ TEST PASSED")
        print(f"  - Loop executed and stopped (not full 10 iterations)")
        print(f"  - Total cards on board: {total_cards_on_board}")
        print(f"  - Check backend logs for 🔍 has_symbol debug output")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
