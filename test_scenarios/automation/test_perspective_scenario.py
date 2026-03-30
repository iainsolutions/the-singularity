#!/usr/bin/env python3
"""
Scenario Test: Perspective

Tests Perspective's CountColorsWithSymbol + RepeatAction with nested SelectCards:
- Effect: Return a card from hand. Then score a card from hand for every
  color on your board with lightbulb.

Primitives tested: SelectCards (optional + repeated in RepeatAction),
ReturnCards, CountColorsWithSymbol, RepeatAction (nested interactive),
ScoreCards

Setup:
- Human: Perspective (yellow, 2 lightbulbs) + Writing (blue, 2 lightbulbs)
  + Paper (green, 2 lightbulbs) on board → 3 colors with lightbulb
- AI: Agriculture (yellow, 0 lightbulbs) on board - won't share
- Human hand: 5 cards (1 to return + 3 to score in repeat loop + 1 remaining)

Expected:
- Human selects 1 card to return
- CountColorsWithSymbol("lightbulb") = 3 (yellow, blue, green all have lightbulb)
- RepeatAction 3x: each time select 1 card from hand, score it
- After: 1 returned + 3 scored = 4 cards removed from hand, 1 remaining
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestPerspectiveScenario:
    """Test Perspective CountColorsWithSymbol + RepeatAction."""

    def setup_scenario(self) -> dict[str, Any]:
        print("\n" + "="*70)
        print("SETUP: Creating Perspective RepeatAction Scenario")
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

        # Human board: 3 colors with lightbulb
        # Perspective (yellow, 2 lightbulbs), Writing (blue, 2 lightbulbs),
        # Paper (green, 2 lightbulbs)
        for card in ["Perspective", "Writing", "Paper"]:
            requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": human_id, "card_name": card, "location": "board"}
            )
        print("✓ Human board: Perspective (yellow), Writing (blue), Paper (green) - 3 lightbulb colors")

        # AI board: Agriculture (0 lightbulbs)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"}
        )

        # Human hand: 5 cards (1 return + 3 score + 1 left over)
        hand_cards = ["Archery", "Oars", "Sailing", "Masonry", "Clothing"]
        for card in hand_cards:
            requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": human_id, "card_name": card, "location": "hand"}
            )
        print(f"✓ Human hand: {hand_cards}")

        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )
        print("✓ Setup complete")

        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_perspective_repeat_score(self):
        """Test Perspective: return 1, then score 3 (one per lightbulb color)."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        print("\n--- Executing Perspective Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Perspective"}
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"

        time.sleep(2)

        # Interaction 1: Select card to return
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        state = response.json()
        pending = state.get("state", {}).get("pending_dogma_action")
        assert pending is not None, "Should have pending interaction for return"

        context = pending.get("context", {})
        interaction = context.get("interaction_data", {})
        data = interaction.get("data", {})
        eligible = data.get("eligible_cards", [])
        print(f"Return selection - eligible: {[c['name'] for c in eligible]}")

        # Select first card to return
        card_to_return = eligible[0]
        print(f"Returning: {card_to_return['name']}")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
            json={"player_id": human_id, "selected_cards": [card_to_return["card_id"]]}
        )
        assert response.status_code == 200

        # Now RepeatAction should fire 3 times (3 lightbulb colors)
        # Each iteration: SelectCards(hand, 1) → ScoreCards
        scored_cards = []
        for i in range(3):
            time.sleep(2)

            response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
            state = response.json()
            pending = state.get("state", {}).get("pending_dogma_action")

            if pending is None:
                print(f"  Iteration {i+1}: No pending interaction (may have auto-completed)")
                break

            context = pending.get("context", {})
            interaction = context.get("interaction_data", {})
            data = interaction.get("data", {})
            eligible = data.get("eligible_cards", [])

            if not eligible:
                print(f"  Iteration {i+1}: No eligible cards remaining")
                break

            card_to_score = eligible[0]
            scored_cards.append(card_to_score["name"])
            print(f"  Iteration {i+1}: Scoring {card_to_score['name']}")

            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                json={"player_id": human_id, "selected_cards": [card_to_score["card_id"]]}
            )
            assert response.status_code == 200

        time.sleep(2)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        hand = human.get("hand", [])
        score = human.get("score_pile", [])
        hand_names = [c["name"] for c in hand]
        score_names = [c["name"] for c in score]

        print(f"\nFinal hand: {hand_names}")
        print(f"Score pile: {score_names}")

        # After fix: RepeatAction clears selection variables between iterations,
        # so each iteration creates a fresh interaction for the player.
        # Expected: 1 returned + 3 scored = 4 cards removed from hand, 1 remaining
        assert len(score) >= 3, \
            f"Should have scored 3 cards (one per lightbulb color), got {len(score)}"
        assert len(hand) <= 1, \
            f"Should have at most 1 card remaining in hand (started 5, returned 1, scored 3), got {len(hand)}: {hand_names}"
        # Score pile should have 3 DIFFERENT cards (not the same card 3x)
        assert len(set(score_names)) >= min(3, len(score_names)), \
            f"Score pile should have different cards, got {score_names}"
        print(f"✓ All 3 RepeatAction iterations scored different cards")

        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Game should complete"
        print("✅ Perspective test PASSED")
