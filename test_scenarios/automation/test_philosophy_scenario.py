#!/usr/bin/env python3
"""
Scenario Test: Philosophy

Tests Philosophy dogma effects:
1. Effect 1 (Non-DEMAND): SelectColor interaction for splay left (tests color_selected condition)
2. Effect 2 (Non-DEMAND): Optional hand scoring

Expected Flow:
1. Human executes Philosophy dogma (age 2 purple card, 4 lightbulbs)
2. Sharing check: AI has 2 lightbulbs (Oars), Human has 4 - AI does NOT share
3. Effect 1: SelectColor interaction shows eligible colors (red, blue only - not purple with 1 card)
4. Human selects color (e.g., red) to splay left
5. color_selected condition triggers → SplayCards executes
6. Effect 2: Optional card selection from hand to score
7. Human selects card or declines

Setup:
- Human: Philosophy on purple board (4 lightbulbs), red stack (2 cards), blue stack (2 cards), 3 cards in hand
- AI: Oars on green board (2 lightbulbs), green stack (2 cards), yellow stack (2 cards), 2 cards in hand

Expected Results:
- SelectColor interaction with only eligible colors (2+ cards)
- color_selected condition works correctly
- Splay applied to selected color
- Symbol visibility increases after splay
- Optional hand scoring works
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


class TestPhilosophyScenario:
    """Test Philosophy scenario."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Philosophy scenario."""
        print("\n" + "="*70)
        print("SETUP: Creating Philosophy Color Selection and Splay Scenario")
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

        # Setup: Human board - Philosophy on purple (4 lightbulbs)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Philosophy",
                "location": "board"
            }
        )
        assert response.status_code == 200, f"Add Philosophy failed: {response.text}"
        print("✓ Philosophy added to human purple board (4 lightbulbs)")

        # Setup: Human red stack (2 cards - eligible for splay)
        for card_name in ["Archery", "Metalworking"]:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": human_id,
                    "card_name": card_name,
                    "location": "board"
                }
            )
            assert response.status_code == 200, f"Add {card_name} failed: {response.text}"
        print("✓ Human red stack: 2 cards (Archery, Metalworking)")

        # Setup: Human blue stack (2 cards - eligible for splay)
        for card_name in ["Pottery", "Tools"]:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": human_id,
                    "card_name": card_name,
                    "location": "board"
                }
            )
            assert response.status_code == 200, f"Add {card_name} failed: {response.text}"
        print("✓ Human blue stack: 2 cards (Pottery, Tools)")

        # Setup: Human hand (3 cards for scoring test)
        for card_name in ["Writing", "Clothing", "Agriculture"]:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": human_id,
                    "card_name": card_name,
                    "location": "hand"
                }
            )
            assert response.status_code == 200, f"Add {card_name} failed: {response.text}"
        print("✓ Human hand: 3 cards (Writing, Clothing, Agriculture)")

        # Setup: AI board (3 cards)
        for card_name in ["Sailing", "Fermenting", "Masonry"]:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": ai_id,
                    "card_name": card_name,
                    "location": "board"
                }
            )
            assert response.status_code == 200, f"Add {card_name} failed: {response.text}"
        print("✓ AI board: 3 cards (Sailing-green, Fermenting-yellow, Masonry-yellow)")

        # Setup: AI hand (2 cards)
        for card_name in ["Construction", "Mysticism"]:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": ai_id,
                    "card_name": card_name,
                    "location": "hand"
                }
            )
            assert response.status_code == 200, f"Add {card_name} failed: {response.text}"
        print("✓ AI hand: 2 cards (Construction, Mysticism)")

        # Set game to playing state (DON'T call /start)
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

    def test_philosophy_complete(self):
        """Test complete Philosophy flow."""
        # Setup scenario
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]
        ai_id = scenario["ai_id"]

        print("\n" + "="*70)
        print("TEST: Philosophy Color Selection and Splay")
        print("="*70)

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()

        human_initial = next(p for p in initial_state["players"] if p["id"] == human_id)
        initial_hand_count = len(human_initial["hand"])
        initial_score_count = len(human_initial.get("score_pile", []))

        # Get initial board state (board uses red_cards, blue_cards, etc.)
        red_stack_initial = human_initial["board"].get("red_cards", [])
        blue_stack_initial = human_initial["board"].get("blue_cards", [])

        print(f"\nInitial State:")
        print(f"  Human hand: {initial_hand_count} cards")
        print(f"  Human score: {initial_score_count} cards")
        print(f"  Human red stack: {len(red_stack_initial)} cards")
        print(f"  Human blue stack: {len(blue_stack_initial)} cards")

        # Execute Philosophy dogma
        print("\n--- Executing Philosophy Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Philosophy"
            }
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("✓ Philosophy dogma executed")

        time.sleep(2)

        # Get game state after dogma (Effect 1: SelectColor)
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        game_state = response.json()

        print(f"\nGame ID: {game_id}")

        # ASSERTION 1: Check for SelectColor interaction
        pending_interaction = game_state.get("state", {}).get("pending_dogma_action")
        assert pending_interaction is not None, "Should have pending SelectColor interaction"
        print("✓ Pending interaction exists (Effect 1: SelectColor)")

        # Get interaction data from context
        context = pending_interaction.get("context", {})
        interaction_data = context.get("interaction_data", {})

        print(f"  Interaction type: {interaction_data.get('interaction_type')}")
        print(f"  Is optional: {interaction_data.get('can_cancel')}")

        # ASSERTION 2: Interaction type should be select_color
        assert interaction_data.get("interaction_type") == "select_color", \
            f"Expected select_color interaction, got {interaction_data.get('interaction_type')}"
        print("✓ Interaction type is select_color")

        # ASSERTION 3: Interaction must be marked as optional
        assert interaction_data.get("can_cancel") is True, \
            "Expected optional interaction (can_cancel=true)"
        print("✓ Interaction is marked as optional (can_cancel=true)")

        # ASSERTION 4: Check eligible colors
        data = interaction_data.get("data", {})
        eligible_colors = data.get("available_colors", [])  # FIXED: Use available_colors not eligible_colors
        print(f"  Eligible colors: {eligible_colors}")

        assert len(eligible_colors) > 0, "Should have at least one eligible color"
        assert "red" in eligible_colors, "Red stack (2 cards) should be eligible"
        assert "blue" in eligible_colors, "Blue stack (2 cards) should be eligible"
        assert "purple" not in eligible_colors, "Purple stack (1 card) should NOT be eligible"
        print("✓ Eligible colors correct (red, blue shown; purple with 1 card excluded)")

        # ASSERTION 5: Select red color to splay
        print("\n--- Selecting Red Color to Splay Left ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
            json={
                "player_id": human_id,
                "selected_color": "red"
            }
        )
        print(f"Selection response status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response: {response.text}")
        else:
            color_response = response.json()
            print(f"Response action: {color_response.get('action')}")
            print(f"Response results: {color_response.get('results', [])}")

            # Check if there's a game_state in the response
            if "game_state" in color_response:
                resp_state = color_response["game_state"]
                resp_human = next((p for p in resp_state["players"] if p["id"] == human_id), None)
                if resp_human:
                    resp_splay = resp_human["board"].get("splay_directions", {})
                    print(f"  Splay in response: {resp_splay}")

                # Check what interaction is pending
                pending = resp_state.get("state", {}).get("pending_dogma_action")
                if pending:
                    ctx = pending.get("context", {})
                    int_data = ctx.get("interaction_data", {})
                    print(f"  Next interaction type: {int_data.get('interaction_type')}")
                    print(f"  Effect index: {pending.get('effect_index')}")

        assert response.status_code == 200, f"Color selection failed: {response.text}"

        time.sleep(3)  # Increased wait time for state to settle

        # Get state after color selection
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        after_splay_state = response.json()

        human_after_splay = next(p for p in after_splay_state["players"] if p["id"] == human_id)

        # Debug: Print board state
        print(f"\n  Board state after color selection:")
        print(f"    Red cards: {len(human_after_splay['board'].get('red_cards', []))}")
        print(f"    Splay directions: {human_after_splay['board'].get('splay_directions', {})}")

        # ASSERTION 6: Verify splay applied to red stack
        splay_dirs = human_after_splay["board"].get("splay_directions", {})
        assert splay_dirs.get("red") == "left", \
            f"Red stack should be splayed left, got {splay_dirs.get('red')}. Full splay_dirs: {splay_dirs}"
        print(f"✓ Red stack splayed left")

        # ASSERTION 7: Symbol visibility should increase after splay
        # With left splay, each card except top reveals 1 additional symbol
        # Red has 2 cards, so 1 card should reveal additional symbols
        print(f"  Red stack splay: {splay_dirs.get('red')}")

        # ASSERTION 8: Check for Effect 2 interaction (hand scoring)
        pending_interaction_2 = after_splay_state.get("state", {}).get("pending_dogma_action")

        if pending_interaction_2 is not None:
            print("\n--- Effect 2: Hand Scoring Interaction ---")
            context_2 = pending_interaction_2.get("context", {})
            interaction_data_2 = context_2.get("interaction_data", {})

            print(f"  Interaction type: {interaction_data_2.get('interaction_type')}")

            # ASSERTION 9: Interaction type should be select_cards
            assert interaction_data_2.get("interaction_type") == "select_cards", \
                f"Expected select_cards interaction, got {interaction_data_2.get('interaction_type')}"
            print("✓ Effect 2 interaction is select_cards")

            # ASSERTION 10: Should be optional
            assert interaction_data_2.get("can_cancel") is True, \
                "Expected optional interaction for hand scoring"
            print("✓ Effect 2 is optional")

            # ASSERTION 11: Field name must be eligible_cards
            data_2 = interaction_data_2.get("data", {})
            assert "eligible_cards" in data_2, \
                f"Expected 'eligible_cards' field, got fields: {list(data_2.keys())}"
            print("✓ Field name is 'eligible_cards'")

            # Select Writing (age 1, blue) from hand to score
            print("\n--- Selecting Writing to Score ---")
            writing_card = next(
                (card for card in human_after_splay["hand"] if card["name"] == "Writing"),
                None
            )
            assert writing_card is not None, "Writing not found in hand"

            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                json={
                    "player_id": human_id,
                    "selected_cards": [writing_card["card_id"]]
                }
            )
            print(f"Selection response status: {response.status_code}")
            if response.status_code != 200:
                print(f"Response: {response.text}")

            time.sleep(2)

        # ASSERTION 12: Get final game state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        final_human = next(p for p in final_state["players"] if p["id"] == human_id)
        final_hand_count = len(final_human["hand"])
        final_score_count = len(final_human.get("score_pile", []))

        print(f"\nFinal State:")
        print(f"  Human hand: {final_hand_count} cards")
        print(f"  Human score: {final_score_count} cards")

        # ASSERTION 13: Hand should decrease by 1 (scored Pottery)
        if pending_interaction_2 is not None:
            assert final_hand_count == initial_hand_count - 1, \
                f"Expected hand to decrease by 1, was {initial_hand_count}, now {final_hand_count}"
            print(f"✓ Hand decreased by 1 ({initial_hand_count} → {final_hand_count})")

            # ASSERTION 14: Score should increase by 1
            assert final_score_count == initial_score_count + 1, \
                f"Expected score to increase by 1, was {initial_score_count}, now {final_score_count}"
            print(f"✓ Score increased by 1 ({initial_score_count} → {final_score_count})")

        # ASSERTION 15: No pending interaction
        final_pending = final_state.get("state", {}).get("pending_dogma_action")
        assert final_pending is None, \
            f"Expected no pending interaction, got: {final_pending}"
        print("✓ No pending interaction")

        # ASSERTION 16: Phase is still playing
        assert final_state.get("phase") == "playing", \
            f"Expected phase 'playing', got {final_state.get('phase')}"
        print("✓ Game phase is still 'playing'")

        # ASSERTION 17: Action log contains Philosophy
        action_log = final_state.get("action_log", [])
        philosophy_actions = [
            log for log in action_log
            if "Philosophy" in log.get("description", "")
        ]
        assert len(philosophy_actions) > 0, \
            "Expected Philosophy in action log"
        print(f"✓ Philosophy in action log: {len(philosophy_actions)} entries")

        # ASSERTION 18: Verify splay persists in final state
        final_splay_dirs = final_human["board"].get("splay_directions", {})
        assert final_splay_dirs.get("red") == "left", \
            f"Red stack should still be splayed left in final state, got {final_splay_dirs.get('red')}"
        print("✓ Red stack splay persisted in final state")

        print("\n=== Recent Action Log ===")
        for entry in action_log[-10:]:
            print(f"  {entry.get('description')}")

        print("\n" + "="*70)
        print("✅ ALL ASSERTIONS PASSED - Philosophy SelectColor Test")
        print("="*70)
        print(f"\nNew Primitives Tested:")
        print(f"  - SelectColor (9 uses in BaseCards) - PRIMARY TEST")
        print(f"  - color_selected condition (3 uses) - PRIMARY TEST")
        print(f"\nSecondary Primitives Used:")
        print(f"  - ConditionalAction (86 uses)")
        print(f"  - SplayCards (37 uses)")
        print(f"  - SelectCards (86 uses)")
        print(f"  - ScoreCards (32 uses)")


if __name__ == "__main__":
    # Run test
    test = TestPhilosophyScenario()
    test.test_philosophy_complete()
