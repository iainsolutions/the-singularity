#!/usr/bin/env python3
"""
Scenario Test: Mapmaking

Tests Mapmaking dogma with demand transfer + conditional draw/score.

Card Definition:
- Age 2, green
- Symbols: lightbulb, crown, crown, castle
- Dogma resource: crown

Effect 0 (demand): "I demand you transfer a 1 from your score pile to my score pile!"
Effect 1: "If any card was transferred due to the demand, draw and score a 1."

Setup:
- Human: Mapmaking on green board (2 crowns)
- AI: Agriculture on yellow board (0 crowns) → vulnerable to demand
- AI score pile: Archery (age 1) → eligible for transfer

Expected Flow:
1. Effect 0: AI has 0 crowns < human's 2 crowns → AI is vulnerable
   - AI transfers Archery (age 1) from score pile to human score pile
   - demand_transferred_count = 1
2. Effect 1: Condition met (demand_transferred_count > 0)
   - Human draws age 1 card
   - Human scores drawn card
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestMapmakingScenario:
    """Test Mapmaking demand with conditional draw/score."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Mapmaking scenario."""
        print("\n" + "="*70)
        print("SETUP: Creating Mapmaking Scenario")
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

        # Initialize age decks
        time.sleep(0.5)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing"}
        )
        assert response.status_code == 200, f"Initialize decks failed: {response.text}"
        print("✓ Age decks initialized")

        # Enable tracing
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/tracing/start",
                json={"enabled": True}
            )
            print("✓ Tracing enabled")
        except Exception:
            print("⚠ Tracing not available")

        # Set up board: Human gets Mapmaking on green stack (2 crowns)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Mapmaking",
                "location": "board",
                "color": "green"
            }
        )
        assert response.status_code == 200, f"Add Mapmaking failed: {response.text}"
        print("✓ Mapmaking added to human board (green) - 2 crowns")

        # Set up board: AI gets Agriculture on yellow stack (0 crowns → vulnerable)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Agriculture",
                "location": "board",
                "color": "yellow"
            }
        )
        assert response.status_code == 200, f"Add Agriculture failed: {response.text}"
        print("✓ Agriculture added to AI board (yellow) - 0 crowns")

        # Give AI Archery in score pile (age 1 card eligible for transfer)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Archery",
                "location": "score_pile"
            }
        )
        assert response.status_code == 200, f"Add Archery failed: {response.text}"
        print("✓ Archery added to AI score pile (age 1)")

        # Set game to playing state
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={
                "phase": "playing",
                "current_player_index": 0,
                "actions_remaining": 2
            }
        )
        assert response.status_code == 200, f"Set state failed: {response.text}"
        print("✓ Game state set to playing")

        print("="*70)
        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def get_game_state(self, game_id: str) -> dict[str, Any]:
        """Get current game state."""
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        return response.json()

    def get_player(self, state: dict[str, Any], player_id: str) -> dict[str, Any]:
        """Get player from game state."""
        for player in state["players"]:
            if player["id"] == player_id:
                return player
        raise ValueError(f"Player {player_id} not found")

    def get_ai_interactions(self, game_id: str) -> list:
        """Get AI interaction history for this game."""
        response = requests.get(
            f"{BASE_URL}/api/v1/ai/interactions?limit=50&game_id={game_id}"
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("interactions", [])
        return []

    def test_mapmaking_complete(self):
        """
        Complete test of Mapmaking demand + conditional draw/score.
        Validates transfer, condition evaluation, and draw/score.
        """
        # Setup scenario
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]
        ai_id = scenario["ai_id"]

        print("\n" + "="*70)
        print("TEST: Mapmaking Demand + Conditional Draw/Score")
        print("Game ID:", game_id)
        print("="*70)

        # Get initial state
        initial_state = self.get_game_state(game_id)
        initial_human = self.get_player(initial_state, human_id)
        initial_ai = self.get_player(initial_state, ai_id)

        initial_human_score = len(initial_human.get('score_pile', []))
        initial_ai_score = len(initial_ai.get('score_pile', []))

        print("\nInitial State:")
        print(f"  Human score pile: {initial_human_score} cards")
        print(f"  AI score pile: {initial_ai_score} cards (includes Archery)")

        # Activate Mapmaking dogma
        print("\nActivating Mapmaking dogma...")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Mapmaking"}
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("✓ Mapmaking dogma activated")

        # Wait for AI to respond to demand
        print("\nWaiting for AI demand response...")
        time.sleep(8)  # Anthropic API call needs time

        # Wait for completion
        max_wait = 15
        waited = 0
        while waited < max_wait:
            time.sleep(1.0)
            waited += 1.0

            state = self.get_game_state(game_id)
            pending = state.get('state', {}).get('pending_dogma_action')

            if not pending:
                print(f"✓ Dogma completed after {waited:.1f}s")
                break

            print(f"  Waiting for completion... ({waited:.1f}s, pending: {bool(pending)})")

        # Get final state
        final_state = self.get_game_state(game_id)
        final_human = self.get_player(final_state, human_id)
        final_ai = self.get_player(final_state, ai_id)

        final_human_score = len(final_human.get('score_pile', []))
        final_ai_score = len(final_ai.get('score_pile', []))

        print("\nFinal State:")
        print(f"  Human score pile: {final_human_score} cards")
        print(f"  AI score pile: {final_ai_score} cards")

        print("\n" + "="*70)
        print("ASSERTIONS")
        print("="*70)

        # === ASSERTION 1: Archery transferred from AI to human ===
        # AI score pile: 1 → 0 (lost Archery)
        # Human score pile: 0 → 2 (gained Archery + drew and scored 1)
        print(f"\n2. Card transferred from AI to human")
        print(f"   AI score pile: {initial_ai_score} → {final_ai_score}")
        assert final_ai_score == initial_ai_score - 1, \
            f"Expected AI score {initial_ai_score - 1}, got {final_ai_score}"
        print("   ✓ PASS")

        # === ASSERTION 3: Human gained 2 cards (transfer + draw/score) ===
        # +1 from demand transfer (Archery)
        # +1 from conditional draw/score (age 1 card)
        expected_human_score = initial_human_score + 2
        print(f"\n3. Human gained 2 cards in score pile")
        print(f"   Human score pile: {initial_human_score} → {final_human_score}")
        assert final_human_score == expected_human_score, \
            f"Expected human score {expected_human_score}, got {final_human_score}"
        print("   ✓ PASS")

        # === ASSERTION 4: Verify Archery in human score pile ===
        archery_in_human_score = any(
            card.get('name') == 'Archery'
            for card in final_human.get('score_pile', [])
        )
        print(f"\n4. Archery in human score pile")
        print(f"   Found: {archery_in_human_score}")
        assert archery_in_human_score, "Expected Archery in human score pile"
        print("   ✓ PASS")

        # === ASSERTION 5: Verify age 1 card scored ===
        age_1_cards = [
            card for card in final_human.get('score_pile', [])
            if card.get('age') == 1
        ]
        print(f"\n5. Age 1 card(s) in human score pile")
        print(f"   Count: {len(age_1_cards)}")
        assert len(age_1_cards) == 2, \
            f"Expected 2 age 1 cards (Archery + drawn), got {len(age_1_cards)}"
        print("   ✓ PASS")

        # === ASSERTION 6: Dogma completed (no pending) ===
        print(f"\n6. Dogma completed (no pending interaction)")
        pending = final_state.get('state', {}).get('pending_dogma_action')
        print(f"   Pending: {pending}")
        assert not pending, f"Expected no pending interaction, got {pending}"
        print("   ✓ PASS")

        print("\n" + "="*70)
        print("ALL ASSERTIONS PASSED! ✓")
        print("="*70)
        print(f"\nTrace: curl {BASE_URL}/api/v1/games/{game_id}/tracing/list | python3 -m json.tool")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
