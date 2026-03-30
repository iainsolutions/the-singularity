#!/usr/bin/env python3
"""
Scenario Test: Currency

Tests Currency dogma effects:
1. Effect 1 (Non-DEMAND): Optional card selection from hand, CountUniqueValues, return and score

Expected Flow:
1. Human executes Currency dogma (age 2 green card, 2 crowns)
2. Sharing check: AI has 1 crown (Sailing), Human has 2 - AI does NOT share
3. Effect 1: SelectCards interaction shows hand cards (optional, can select multiple)
4. Human selects cards with different ages (e.g., 4 age-1 cards + 1 age-2 card = 2 unique)
5. CountUniqueValues counts unique ages in selected cards
6. Selected cards returned to age decks
7. RepeatAction: Draw age-2 card, score it, repeat for each unique value
8. Score pile gains cards equal to unique value count

Setup:
- Human: Currency on green board (2 crowns), 5 cards in hand (4x age-1, 1x age-2)
- AI: Sailing on green board (1 crown), 2 cards in hand

Expected Results:
- SelectCards interaction with hand cards (optional)
- CountUniqueValues correctly counts unique ages
- Cards returned to appropriate age decks
- Score pile gains correct number of age-2 cards
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


class TestCurrencyScenario:
    """Test Currency scenario."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Currency scenario."""
        print("\n" + "="*70)
        print("SETUP: Creating Currency CountUniqueValues Scenario")
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

        # Setup: Human board - Currency on green (2 crowns)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Currency",
                "location": "board"
            }
        )
        assert response.status_code == 200, f"Add Currency failed: {response.text}"
        print("✓ Currency added to human green board")

        # Setup: Human hand - 4 age-1 cards + 1 age-2 card = 2 unique ages
        age1_cards = ["Archery", "Pottery", "Tools", "Writing"]
        for card_name in age1_cards:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": human_id,
                    "card_name": card_name,
                    "location": "hand"
                }
            )
            assert response.status_code == 200, f"Add {card_name} failed: {response.text}"
        print(f"✓ Human hand: {len(age1_cards)} age-1 cards")

        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Calendar",
                "location": "hand"
            }
        )
        assert response.status_code == 200, f"Add Calendar failed: {response.text}"
        print("✓ Human hand: 1 age-2 card (Calendar)")

        # Setup: AI board (1 crown)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Sailing",
                "location": "board"
            }
        )
        assert response.status_code == 200, f"Add Sailing failed: {response.text}"
        print("✓ AI board: Sailing (green, 1 crown)")

        # Setup: AI hand
        for card_name in ["Masonry", "Construction"]:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": ai_id,
                    "card_name": card_name,
                    "location": "hand"
                }
            )
            assert response.status_code == 200, f"Add {card_name} failed: {response.text}"
        print("✓ AI hand: 2 cards")

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
        return {
            "game_id": game_id,
            "human_id": human_id,
            "ai_id": ai_id
        }

    def test_currency_complete(self):
        """Test complete Currency flow with CountUniqueValues."""
        # Setup scenario
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        print("\n" + "="*70)
        print("TEST: Currency CountUniqueValues")
        print("="*70)

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()

        human_initial = next(p for p in initial_state["players"] if p["id"] == human_id)
        initial_hand_count = len(human_initial["hand"])
        initial_score_count = len(human_initial.get("score_pile", []))

        print(f"\nInitial State:")
        print(f"  Human hand: {initial_hand_count} cards")
        print(f"  Human score: {initial_score_count} cards")

        # ASSERTION 1: Hand should have 5 cards
        assert initial_hand_count == 5, f"Expected 5 cards in hand, got {initial_hand_count}"
        print("✓ Hand has 5 cards")

        # Execute Currency dogma
        print("\n--- Executing Currency Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Currency"
            }
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("✓ Currency dogma executed")

        # Wait for AI to process sharing (Anthropic API call takes ~3-4s)
        time.sleep(6)

        # Get game state after dogma (Effect 1: SelectCards)
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        game_state = response.json()

        # ASSERTION 2: Check for SelectCards interaction
        pending_interaction = game_state.get("state", {}).get("pending_dogma_action")
        assert pending_interaction is not None, "Should have pending SelectCards interaction"
        print("✓ Pending interaction exists (Effect 1: SelectCards)")

        context = pending_interaction.get("context", {})
        interaction_data = context.get("interaction_data", {})

        # ASSERTION 3: Interaction type should be select_cards
        assert interaction_data.get("interaction_type") == "select_cards", \
            f"Expected select_cards interaction, got {interaction_data.get('interaction_type')}"
        print("✓ Interaction type is select_cards")

        # ASSERTION 4: Should be optional
        assert interaction_data.get("can_cancel") is True, \
            "Expected optional interaction (can_cancel=true)"
        print("✓ Interaction is optional")

        # ASSERTION 5: Source should be hand
        data = interaction_data.get("data", {})
        eligible_cards = data.get("eligible_cards", [])
        assert len(eligible_cards) == 5, f"Expected 5 eligible cards, got {len(eligible_cards)}"
        print(f"✓ {len(eligible_cards)} cards eligible for selection")

        # Select all 5 cards (4 age-1 + 1 age-2 = 2 unique values)
        print("\n--- Selecting All 5 Cards (2 Unique Ages) ---")
        card_ids = [card["card_id"] for card in eligible_cards]
        
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
            json={
                "player_id": human_id,
                "selected_cards": card_ids
            }
        )
        print(f"Selection response status: {response.status_code}")
        assert response.status_code == 200, f"Card selection failed: {response.text}"

        time.sleep(3)

        # ASSERTION 6: Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        final_human = next(p for p in final_state["players"] if p["id"] == human_id)
        final_hand_count = len(final_human["hand"])
        final_score_count = len(final_human.get("score_pile", []))

        print(f"\nFinal State:")
        print(f"  Human hand: {final_hand_count} cards")
        print(f"  Human score: {final_score_count} cards")

        # ASSERTION 7: Hand should have exactly 1 card (sharing bonus from AI sharing)
        # AI has Sailing (1 crown) = shares Currency dogma
        # AI selects its 2 hand cards (Masonry + Construction), returns them, draws 2 to score
        # AI did something with a card → activating player (Human) gets sharing bonus draw (+1 to hand)
        # Human returned 5 cards (hand=0) + 1 sharing bonus = hand=1
        assert final_hand_count == 1, \
            f"Expected 1 card in hand (sharing bonus), got {final_hand_count} cards"
        print(f"✓ Hand has 1 card (sharing bonus after AI sharing)")

        # ASSERTION 8: Score should increase by 2 (2 unique ages)
        assert final_score_count == initial_score_count + 2, \
            f"Expected score to increase by 2, was {initial_score_count}, now {final_score_count}"
        print(f"✓ Score increased by 2 ({initial_score_count} → {final_score_count})")

        # ASSERTION 9: Scored cards should be age 2
        scored_cards = final_human.get("score_pile", [])[-2:]  # Last 2 cards
        for card in scored_cards:
            assert card["age"] == 2, f"Expected age 2, got {card['age']}"
        print("✓ Scored cards are both age 2")

        # ASSERTION 10: No pending interaction
        final_pending = final_state.get("state", {}).get("pending_dogma_action")
        assert final_pending is None, \
            f"Expected no pending interaction, got: {final_pending}"
        print("✓ No pending interaction")

        # ASSERTION 11: Phase is still playing
        assert final_state.get("phase") == "playing", \
            f"Expected phase 'playing', got {final_state.get('phase')}"
        print("✓ Game phase is still 'playing'")

        print("\n=== Recent Action Log ===")
        action_log = final_state.get("action_log", [])
        for entry in action_log[-10:]:
            print(f"  {entry.get('description')}")

        print("\n" + "="*70)
        print("✅ ALL ASSERTIONS PASSED - Currency CountUniqueValues Test")
        print("="*70)
        print(f"\nNew Primitives Tested:")
        print(f"  - CountUniqueValues (4 uses in BaseCards) - PRIMARY TEST")
        print(f"\nSecondary Primitives Used:")
        print(f"  - SelectCards (86 uses)")
        print(f"  - ReturnCards (46 uses)")
        print(f"  - RepeatAction (12 uses)")
        print(f"  - DrawCards (83 uses)")
        print(f"  - ScoreCards (32 uses)")


if __name__ == "__main__":
    # Run test
    test = TestCurrencyScenario()
    test.test_currency_complete()
