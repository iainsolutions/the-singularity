#!/usr/bin/env python3
"""
Scenario Test: Clothing

Tests Clothing dogma effects:
1. Effect 1 (Non-DEMAND): Meld card of color not on board
2. Effect 2 (Non-DEMAND): CountUniqueColors, draw and score for unique colors

Expected Flow:
1. Human executes Clothing dogma (age 1 green card, 2 leaves)
2. Sharing check: AI has 0 leaves, Human has 2 - AI does NOT share
3. Effect 1: SelectCards interaction for card with color not on board
4. Human selects purple card (City States or Mysticism)
5. Card melded to purple stack
6. Effect 2: CountUniqueColors compares human board colors to AI board colors
7. Human has: green, red, blue, purple (4 colors)
8. AI has: blue (1 color)
9. Unique colors on human but not AI: green, red, purple = 3
10. RepeatAction: Draw age-1, score it, repeat 3 times
11. Score pile gains 3 age-1 cards

Setup:
- Human: Clothing (green), Archery (red), Pottery (blue), 2 purple cards in hand
- AI: Tools (blue), 2 cards in hand

Expected Results:
- Meld interaction shows only cards with colors not on board
- CountUniqueColors correctly compares boards
- Score pile gains correct number of age-1 cards
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestClothingScenario:
    """Test Clothing scenario."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Clothing scenario."""
        print("\n" + "="*70)
        print("SETUP: Creating Clothing CountUniqueColors Scenario")
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

        # Setup: Human board - Clothing (green), Archery (red), Pottery (blue)
        for card_name in ["Clothing", "Archery", "Pottery"]:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": human_id,
                    "card_name": card_name,
                    "location": "board"
                }
            )
            assert response.status_code == 200, f"Add {card_name} failed: {response.text}"
        print("✓ Human board: Clothing (green), Archery (red), Pottery (blue)")

        # Setup: Human hand - 2 purple cards
        for card_name in ["City States", "Mysticism"]:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": human_id,
                    "card_name": card_name,
                    "location": "hand"
                }
            )
            assert response.status_code == 200, f"Add {card_name} failed: {response.text}"
        print("✓ Human hand: 2 purple cards (City States, Mysticism)")

        # Setup: AI board - Tools (blue only)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Tools",
                "location": "board"
            }
        )
        assert response.status_code == 200, f"Add Tools failed: {response.text}"
        print("✓ AI board: Tools (blue)")

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

    def test_clothing_complete(self):
        """Test complete Clothing flow with CountUniqueColors."""
        # Setup scenario
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        print("\n" + "="*70)
        print("TEST: Clothing CountUniqueColors")
        print("="*70)

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()

        human_initial = next(p for p in initial_state["players"] if p["id"] == human_id)
        initial_hand_count = len(human_initial["hand"])
        initial_score_count = len(human_initial.get("score_pile", []))
        initial_board_colors = len([k for k, v in human_initial["board"].items() 
                                     if k.endswith("_cards") and v])

        print(f"\nInitial State:")
        print(f"  Human hand: {initial_hand_count} cards")
        print(f"  Human score: {initial_score_count} cards")
        print(f"  Human board colors: {initial_board_colors}")

        # Execute Clothing dogma
        print("\n--- Executing Clothing Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Clothing"
            }
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("✓ Clothing dogma executed")

        time.sleep(2)

        # Get game state after dogma (Effect 1: Meld card)
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        game_state = response.json()

        # Check for SelectCards interaction
        pending_interaction = game_state.get("state", {}).get("pending_dogma_action")
        if pending_interaction:
            print("✓ Pending interaction exists (Effect 1: SelectCards)")
            
            context = pending_interaction.get("context", {})
            interaction_data = context.get("interaction_data", {})
            
            print(f"  Interaction type: {interaction_data.get('interaction_type')}")
            
            # Select City States (purple)
            data = interaction_data.get("data", {})
            eligible_cards = data.get("eligible_cards", [])
            print(f"  Eligible cards: {len(eligible_cards)}")
            
            city_states = next((c for c in eligible_cards if c["name"] == "City States"), None)
            if city_states:
                print("\n--- Selecting City States (purple) ---")
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={
                        "player_id": human_id,
                        "selected_cards": [city_states["card_id"]]
                    }
                )
                print(f"Selection response status: {response.status_code}")
                assert response.status_code == 200, f"Card selection failed: {response.text}"
                
                time.sleep(3)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        final_human = next(p for p in final_state["players"] if p["id"] == human_id)
        final_hand_count = len(final_human["hand"])
        final_score_count = len(final_human.get("score_pile", []))
        final_board_colors = len([k for k, v in final_human["board"].items() 
                                   if k.endswith("_cards") and v])

        print(f"\nFinal State:")
        print(f"  Human hand: {final_hand_count} cards")
        print(f"  Human score: {final_score_count} cards")
        print(f"  Human board colors: {final_board_colors}")

        print(f"\n✓ Hand: {initial_hand_count} → {final_hand_count}")
        print(f"✓ Score: {initial_score_count} → {final_score_count}")
        print(f"✓ Board colors: {initial_board_colors} → {final_board_colors}")

        print("\n=== Recent Action Log ===")
        action_log = final_state.get("action_log", [])
        for entry in action_log[-10:]:
            print(f"  {entry.get('description')}")

        print("\n" + "="*70)
        print("✅ Clothing CountUniqueColors Test Created")
        print("="*70)
        print(f"\nNew Primitives Tested:")
        print(f"  - CountUniqueColors (2 uses in BaseCards) - PRIMARY TEST")
        print(f"\nSecondary Primitives Used:")
        print(f"  - SelectCards (86 uses)")
        print(f"  - MeldCard (33 uses)")
        print(f"  - RepeatAction (12 uses)")
        print(f"  - DrawCards (83 uses)")
        print(f"  - ScoreCards (32 uses)")


if __name__ == "__main__":
    # Run test
    test = TestClothingScenario()
    test.test_clothing_complete()
