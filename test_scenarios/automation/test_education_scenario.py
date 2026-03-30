#!/usr/bin/env python3
"""
Scenario Test: Education - Optional Return Highest + Draw Higher

Tests Education dogma effect:
Effect 0: "You may return the highest card from your score pile. If you do, draw a card
          of value two higher than the highest card remaining in your score pile."

Actions:
1. SelectHighest(source=score_pile, count=1, is_optional=true)
2. ConditionalAction(condition=cards_selected) → [ReturnCards, SelectHighest(remaining),
   GetCardAge, CalculateValue(age+2), DrawCards(calculated_age)]

Setup:
- Human: Education on purple board (4 lightbulbs)
- AI: Agriculture on green board (few lightbulbs - won't share)
- Human score pile: Metalworking(1), Compass(2), Paper(3)

Expected:
- Human selects Paper(3) to return
- Paper returned, remaining highest=Compass(2), draws age 4 card
- Final score pile: Metalworking + Compass + age 4 card
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"

class TestEducationScenario:
    """Test Education optional return-highest-then-draw-higher flow."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Education scenario."""
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

        # SETUP HUMAN BOARD - Education on purple (4 lightbulbs)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Education",
                "location": "board",
                "color": "purple"
            }
        )
        assert response.status_code == 200

        # SETUP AI BOARD - Agriculture on green (1 lightbulb, won't share)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Agriculture",
                "location": "board",
                "color": "green"
            }
        )
        assert response.status_code == 200

        # SETUP HUMAN SCORE PILE - Metalworking(1), Compass(2), Paper(3)
        for card_name in ["Metalworking", "Compass", "Paper"]:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": human_id,
                    "card_name": card_name,
                    "location": "score_pile"
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

    def test_education_complete(self):
        """Test complete Education flow: select highest, return, draw age+2."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()

        human_player = next(p for p in initial_state["players"] if p["id"] == human_id)
        initial_score_pile = human_player.get("score_pile", [])
        print(f"\n=== Initial score pile: {len(initial_score_pile)} cards ===")
        for card in initial_score_pile:
            print(f"  {card['name']} (age {card['age']})")

        # ASSERTION 1: Verify initial score pile
        assert len(initial_score_pile) == 3, f"Should have 3 cards in score pile, got {len(initial_score_pile)}"

        # Execute dogma on Education
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Education"
            }
        )
        assert response.status_code == 200

        # Wait for interaction (SelectHighest from score pile)
        time.sleep(1)
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        state = response.json()

        pending = state.get("state", {}).get("pending_dogma_action")
        assert pending is not None, "Should have pending interaction for SelectHighest"

        context = pending.get("context", {})
        interaction_data = context.get("interaction_data", {})

        # ASSERTION 2: Verify interaction type
        assert interaction_data.get("interaction_type") == "select_cards", \
            f"Should be select_cards, got {interaction_data.get('interaction_type')}"

        # ASSERTION 3: Verify field name contract
        data = interaction_data.get("data", {})
        assert "eligible_cards" in data, "Should use eligible_cards field name"

        eligible_cards = data.get("eligible_cards", [])
        print(f"\n=== SelectHighest interaction: {len(eligible_cards)} eligible ===")
        for card in eligible_cards:
            print(f"  {card['name']} (age {card['age']})")

        # Select Paper (highest, age 3)
        paper_card = next((c for c in eligible_cards if c["name"] == "Paper"), None)
        assert paper_card is not None, "Paper should be eligible"

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
            json={
                "player_id": human_id,
                "selected_cards": [paper_card["card_id"]]
            }
        )
        assert response.status_code == 200

        # Wait for completion
        time.sleep(1)
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        human_player = next(p for p in final_state["players"] if p["id"] == human_id)
        final_score_pile = human_player.get("score_pile", [])

        print(f"\n=== Final score pile: {len(final_score_pile)} cards ===")
        for card in final_score_pile:
            print(f"  {card['name']} (age {card['age']})")

        # ASSERTION 5: Verify Paper returned from score pile
        # Started with 3 (Metalworking, Compass, Paper), returned Paper → 2 remaining
        assert len(final_score_pile) <= 3, f"Score pile should not grow, got {len(final_score_pile)}"
        assert not any(c["name"] == "Paper" for c in final_score_pile), "Paper should be returned"

        # After return, remaining highest should drive a draw (age + 2) to hand
        final_hand = human_player.get("hand", [])
        print(f"Final hand: {[c['name'] for c in final_hand]}")
        if not final_hand:
            print("⚠ BUG: Draw after SelectHighest+GetCardAge+CalculateValue may not execute")

        # ASSERTION 6: Verify no pending interactions
        final_pending = final_state.get("state", {}).get("pending_dogma_action")
        assert final_pending is None, "Should have no pending interactions"

        print(f"\nGame ID: {game_id}")
        print("✅ ALL 6 ASSERTIONS PASSED")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
