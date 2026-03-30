#!/usr/bin/env python3
"""
Scenario Test: Agriculture

Tests Agriculture's return-draw-score effect with AI player.

Card Text:
"You may return a card from your hand. If you do, draw and score a card of value one higher than the card you returned."

Expected Flow:
1. AI selects card from hand (e.g., age 1 card)
2. Card is returned to deck
3. Draw card from age 2 (one higher)
4. Score that card (goes to score pile, NOT hand)

Setup:
- AI player: Agriculture (yellow) on board
- AI hand: Several age 1 cards
- Natural age decks

Expected Results:
- AI score pile gains the drawn card
- AI hand loses the returned card
- Score pile count increases by 1
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"

class TestAgricultureScenario:
    """Test Agriculture return-draw-score effect."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Agriculture scenario."""
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
        # AI board: Agriculture (yellow)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Agriculture",
                "location": "board",
                "color": "yellow"
            }
        )
        assert response.status_code == 200

        # AI hand: Give several age 1 cards
        for card_name in ["Masonry", "Pottery", "Writing"]:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": ai_id,
                    "card_name": card_name,
                    "location": "hand"
                }
            )
            assert response.status_code == 200

        # Human board: Some card with castles
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Archery",
                "location": "board",
                "color": "red"
            }
        )
        assert response.status_code == 200

        # SET GAME TO PLAYING STATE WITH AI TURN
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={
                "phase": "playing",
                "current_player_index": 1,  # AI player
                "actions_remaining": 2
            }
        )
        assert response.status_code == 200

        return {
            "game_id": game_id,
            "human_id": human_id,
            "ai_id": ai_id
        }

    def test_agriculture_return_draw_score(self):
        """Test Agriculture returns card, draws higher age, and scores it."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        ai_id = scenario["ai_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()
        ai_player = next(p for p in initial_state["players"] if p["id"] == ai_id)

        # Record initial state
        initial_hand_count = len(ai_player["hand"])
        initial_score_count = len(ai_player["score_pile"])
        initial_hand_cards = [c["name"] for c in ai_player["hand"]]

        print(f"\n=== INITIAL STATE ===")
        print(f"AI hand ({initial_hand_count}): {initial_hand_cards}")
        print(f"AI score pile: {initial_score_count} cards")

        # Execute Agriculture dogma (AI will respond automatically via Event Bus)
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": ai_id,
                "action_type": "dogma",
                "card_name": "Agriculture"
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

        # CRITICAL: Extra wait for state persistence
        time.sleep(1.0)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        # Get AI player final state
        ai_player = next(p for p in final_state["players"] if p["id"] == ai_id)

        final_hand_count = len(ai_player["hand"])
        final_score_count = len(ai_player["score_pile"])
        final_hand_cards = [c["name"] for c in ai_player["hand"]]
        final_score_cards = [c["name"] for c in ai_player["score_pile"]]

        print(f"\n=== FINAL STATE ===")
        print(f"AI hand ({final_hand_count}): {final_hand_cards}")
        print(f"AI score pile ({final_score_count}): {final_score_cards}")

        # ASSERTIONS
        print(f"\n=== VALIDATION ===")
        print(f"Game ID: {game_id}")

        # 1. Score pile should have increased by 1 (card was scored)
        assert final_score_count == initial_score_count + 1, (
            f"Score pile should increase by 1. "
            f"Initial: {initial_score_count}, Final: {final_score_count}"
        )
        print(f"✓ Score pile increased: {initial_score_count} → {final_score_count}")

        # 2. Hand size should be SAME (returned 1, drew 0 to hand, scored 1)
        # Actually: returned 1, drew 1 to SCORE (not hand)
        # So hand should decrease by 1
        assert final_hand_count == initial_hand_count - 1, (
            f"Hand should decrease by 1 (card returned, not drawn to hand). "
            f"Initial: {initial_hand_count}, Final: {final_hand_count}"
        )
        print(f"✓ Hand size decreased: {initial_hand_count} → {final_hand_count}")

        # 3. Score pile should contain an age 2 card (one higher than returned age 1)
        scored_ages = [c["age"] for c in ai_player["score_pile"]]
        assert 2 in scored_ages, (
            f"Score pile should contain age 2 card. "
            f"Scored card ages: {scored_ages}"
        )
        print(f"✓ Age 2 card scored: {final_score_cards}")

        # 4. No errors in game state
        context = final_state.get("context", {})
        assert not context.get("error"), f"Unexpected error: {context.get('error')}"

        # 5. Game phase should still be 'playing'
        assert final_state["phase"] == "playing", (
            f"Expected phase 'playing', got '{final_state['phase']}'"
        )

        print("\n✅ TEST PASSED")
        print(f"  - Agriculture effect executed correctly")
        print(f"  - Returned card from hand")
        print(f"  - Drew and scored age 2 card")
        print(f"  - Final score pile: {final_score_cards}")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
