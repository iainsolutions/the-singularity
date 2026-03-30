#!/usr/bin/env python3
"""
Scenario Test: Metalworking

Tests Metalworking's LoopAction with continue_condition:
- Draw and reveal a 1. If it has castle, score it and repeat.
- Loop stops when a non-castle card is drawn.

Primitives tested: LoopAction (continue_condition, max_iterations), DrawCards (reveal),
ConditionalAction, ScoreCards

Setup:
- Human: Metalworking (red, 3 castles) on board
- AI: Agriculture (yellow, 0 castles) on board - won't share (0 < 3 castles)
- Age 1 deck has remaining cards (mix of castle/non-castle)

Expected:
- Loop draws age 1 cards, scores those with castle
- Loop stops when a non-castle card is drawn
- Score pile contains only castle cards
- Non-castle card ends up in hand (drawn but not scored)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestMetalworkingScenario:
    """Test Metalworking LoopAction scenario."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Metalworking scenario."""
        print("\n" + "="*70)
        print("SETUP: Creating Metalworking LoopAction Scenario")
        print("="*70)

        # Create game
        response = requests.post(f"{BASE_URL}/api/v1/games", json={})
        assert response.status_code == 200, f"Create game failed: {response.text}"
        game_id = response.json()["game_id"]
        print(f"✓ Game created: {game_id}")

        # Join human player
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/join",
            json={"name": "TestPlayer"}
        )
        assert response.status_code == 200, f"Join failed: {response.text}"
        human_id = response.json()["player_id"]
        print(f"✓ Human player joined: {human_id}")

        # Add AI player
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/add_ai_player",
            json={"difficulty": "beginner"}
        )
        assert response.status_code == 200, f"Add AI failed: {response.text}"
        game_state = response.json()["game_state"]
        ai_id = next(p["id"] for p in game_state["players"] if p["is_ai"])
        print(f"✓ AI player added: {ai_id}")

        # Initialize game
        time.sleep(0.5)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing"}
        )
        assert response.status_code == 200, f"Initialize failed: {response.text}"

        # Human board: Metalworking (red, 3 castles)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Metalworking", "location": "board"}
        )
        assert response.status_code == 200, f"Add Metalworking failed: {response.text}"
        print("✓ Human board: Metalworking (red, 3 castles)")

        # AI board: Agriculture (yellow, 0 castles)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"}
        )
        assert response.status_code == 200, f"Add Agriculture failed: {response.text}"
        print("✓ AI board: Agriculture (yellow, 0 castles)")

        # Set game state
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={
                "phase": "playing",
                "current_player_index": 0,
                "actions_remaining": 2
            }
        )
        assert response.status_code == 200, f"Set state failed: {response.text}"
        print("✓ Game state set")

        print("="*70)
        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_metalworking_loop_action(self):
        """Test Metalworking draw-reveal-score loop."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        print("\n" + "="*70)
        print("TEST: Metalworking LoopAction")
        print("="*70)

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()
        human_initial = next(p for p in initial_state["players"] if p["id"] == human_id)
        initial_score = len(human_initial.get("score_pile", []))
        initial_hand = len(human_initial.get("hand", []))
        print(f"Initial: score={initial_score}, hand={initial_hand}")

        # Execute Metalworking dogma
        print("\n--- Executing Metalworking Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Metalworking"
            }
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("✓ Metalworking dogma executed")

        time.sleep(2)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()
        human_final = next(p for p in final_state["players"] if p["id"] == human_id)

        final_score_pile = human_final.get("score_pile", [])
        final_hand = human_final.get("hand", [])
        final_score_count = len(final_score_pile)
        final_hand_count = len(final_hand)

        print(f"\nFinal: score={final_score_count}, hand={final_hand_count}")
        print(f"Score pile cards: {[c['name'] for c in final_score_pile]}")
        print(f"Hand cards: {[c['name'] for c in final_hand]}")

        # Verify loop ran (at least one card drawn)
        assert final_score_count > 0 or final_hand_count > initial_hand, \
            "Loop should have drawn at least one card"
        print("✓ Loop drew cards")

        # Verify scored cards all have castle symbol
        castle_cards = {"Archery", "City States", "Domestication", "Masonry",
                       "Metalworking", "Mysticism", "Oars", "The Wheel", "Tools"}
        for card in final_score_pile:
            if card["age"] == 1:  # Only check age 1 cards
                assert card["name"] in castle_cards, \
                    f"Scored card {card['name']} should have castle symbol"
        print("✓ All scored age-1 cards have castle symbol")

        # Verify game is not stuck (pending action should be next turn or None)
        pending = final_state.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Game should not be stuck in dogma, but has pending: {pending}"
        print("✓ Game completed dogma without hanging")

        print("\n" + "="*70)
        print("✅ Metalworking LoopAction test PASSED")
        print("="*70)
