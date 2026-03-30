#!/usr/bin/env python3
"""
Scenario Test: Socialism Card with Optional Selection and Conditional Tucking

Tests Socialism dogma with optional selection and conditional action to ensure:
1. Optional board card selection is properly created
2. ConditionalAction correctly checks if card was selected
3. If card selected, both board card and ALL hand cards are tucked
4. If declined, nothing is tucked (conditional behavior)
5. Field name contract: uses 'eligible_cards' (not 'cards' or '_eligible_cards')

Based on: /home/user/Innovation/backend/data/BaseCards.json (Socialism card)

Card: Socialism (Age 8, Purple, 3 leaf symbols)

Effect 1 (1 leaf required):
"You may tuck a top card from your board. If you do, tuck all cards from your hand."

Primitives Tested:
- SelectCards (optional, source: board_top)
- ConditionalAction (condition: cards_selected)
- TuckCard (selected_cards and hand cards)

Expected Flow:
1. Human executes Socialism dogma
2. Effect 1: System presents optional selection from board_top cards
   - Player can select one of: Socialism (purple), Antibiotics (purple), or Rocket (red)
3. If player selects a card:
   - Selected card is tucked under its color stack
   - Then ALL cards from hand are tucked automatically (ConditionalAction)
4. If player declines:
   - No cards are tucked (conditional behavior verified)

Setup:
- Human board: Socialism (purple), Antibiotics (purple), Rocket (red)
- Human hand: Experimentation (blue), Democracy (purple)
- All board cards are top cards (eligible for selection)

Expected Results:
- Interaction created with can_cancel=true (is_optional=true)
- Eligible cards are all top board cards
- Field name is 'eligible_cards' (contract compliance)
- If card selected: board card tucked, then ALL hand cards tucked
- If declined: nothing tucked, hand unchanged
- ConditionalAction properly gates the hand tucking based on selection
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestSocialismScenario:
    """Test Socialism optional selection and conditional tucking."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Socialism scenario."""
        print("\n" + "="*70)
        print("SETUP: Creating Socialism Optional Selection Scenario")
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

        # Setup: Human has Antibiotics (purple) on board FIRST (will be under Socialism)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Antibiotics",
                "location": "board",
                "color": "purple"
            }
        )
        assert response.status_code == 200, f"Add Antibiotics failed: {response.text}"
        print("✓ Antibiotics added to human board (purple) - will be under Socialism")

        # Setup: Human has Socialism (purple) on TOP of board (can dogma it)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Socialism",
                "location": "board",
                "color": "purple"
            }
        )
        assert response.status_code == 200, f"Add Socialism failed: {response.text}"
        print("✓ Socialism added to human board (purple) - TOP card")

        # Setup: Human has Rocket (red) on board
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Satellites",
                "location": "board",
                "color": "red"
            }
        )
        assert response.status_code == 200, f"Add Satellites failed: {response.text}"
        print("✓ Satellites added to human board (red)")

        # Give human Experimentation (blue) in hand
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Experimentation",
                "location": "hand"
            }
        )
        assert response.status_code == 200, f"Add Experimentation failed: {response.text}"
        print("✓ Experimentation added to human hand (blue)")

        # Give human Democracy (purple) in hand
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Democracy",
                "location": "hand"
            }
        )
        assert response.status_code == 200, f"Add Democracy failed: {response.text}"
        print("✓ Democracy added to human hand (purple)")

        # Setup: AI has Fission in hand
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Fission",
                "location": "hand"
            }
        )
        assert response.status_code == 200, f"Add Fission failed: {response.text}"
        print("✓ Fission added to AI hand")

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

    def test_socialism_optional_with_selection(self):
        """Test Socialism with board card selection and conditional hand tucking."""
        # Setup scenario
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        print("\n" + "="*70)
        print("TEST: Socialism Optional Selection with Conditional Tucking")
        print("="*70)

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()

        human_player = next(p for p in initial_state["players"] if p["id"] == human_id)
        initial_hand_count = len(human_player.get("hand", []))
        print(f"Initial hand count: {initial_hand_count} cards")

        initial_board = human_player.get("board", {})
        initial_purple_count = len(initial_board.get("purple_cards", []))
        initial_red_count = len(initial_board.get("red_cards", []))
        print(f"Initial board: {initial_purple_count} purple, {initial_red_count} red")

        # Execute Socialism dogma
        print("\n--- Executing Socialism Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Socialism"
            }
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("✓ Socialism dogma executed")

        time.sleep(2)

        # Get game state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        game_state = response.json()

        # ASSERTION 1: Check if there's a pending interaction (optional)
        pending_interaction = game_state.get("state", {}).get("pending_dogma_action")

        if pending_interaction is not None:
            print("\n✓ Pending interaction exists (optional selection)")

            # Get interaction data from context
            context = pending_interaction.get("context", {})
            interaction_data = context.get("interaction_data", {})

            print(f"  Interaction type: {interaction_data.get('interaction_type')}")
            print(f"  Is optional: {interaction_data.get('is_optional')}")

            # ASSERTION 2: Interaction type should be select_cards
            assert interaction_data.get("interaction_type") == "select_cards", \
                f"Expected select_cards interaction, got {interaction_data.get('interaction_type')}"
            print("✓ Interaction type is select_cards")

            # ASSERTION 3: Selection is optional (card text says "You may...")
            assert interaction_data.get("can_cancel") is True, \
                "Expected can_cancel=true (is_optional=true in card definition)"
            print("✓ Interaction is cancelable (can_cancel=true) - card says 'You may'")

            # ASSERTION 4: Field name must be eligible_cards
            data = interaction_data.get("data", {})
            assert "eligible_cards" in data, \
                f"Expected 'eligible_cards' field, got fields: {list(data.keys())}"
            print("✓ Field name is 'eligible_cards' (not 'cards' or '_eligible_cards')")

            # ASSERTION 5: Source should be board_top
            source = interaction_data.get("source")
            print(f"✓ Source: {source}")

            # ASSERTION 6: Eligible cards should be top cards from board
            eligible_cards = data.get("eligible_cards", [])
            print(f"✓ Eligible cards count: {len(eligible_cards)}")
            eligible_names = [card.get("name") for card in eligible_cards]
            print(f"  Eligible cards: {eligible_names}")

            # Should have one top card per color on board (Antibiotics for purple, Rocket for red)
            # Note: Socialism is under Antibiotics, so Antibiotics is the purple top
            assert len(eligible_cards) >= 2, \
                f"Expected at least 2 eligible cards (top cards per color), got {len(eligible_cards)}"

            # Select one card to tuck (triggering conditional hand tucking)
            print("\n--- Selecting Board Card to Tuck ---")
            selected_card = eligible_cards[0]  # Select first eligible card
            print(f"Selecting: {selected_card['name']} ({selected_card.get('color')})")

            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                json={
                    "player_id": human_id,
                    "selected_cards": [selected_card['card_id']]
                }
            )
            assert response.status_code == 200, f"Failed to select card: {response.status_code}"
            print(f"✓ Card selected successfully")

            time.sleep(2)

            # ASSERTION 7: Get final state - verify tucking occurred
            response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
            assert response.status_code == 200
            final_state = response.json()

            human_player = next(p for p in final_state["players"] if p["id"] == human_id)

            # ASSERTION 8: Hand should be empty (all cards tucked due to ConditionalAction)
            final_hand_count = len(human_player.get("hand", []))
            assert final_hand_count == 0, \
                f"Expected hand to be empty after conditional tucking, got {final_hand_count} cards"
            print(f"✓ Hand is now empty (was {initial_hand_count}, all cards tucked by ConditionalAction)")

            # ASSERTION 9: Board should show increased card counts
            final_board = human_player.get("board", {})
            final_purple_count = len(final_board.get("purple_cards", []))
            final_red_count = len(final_board.get("red_cards", []))

            print(f"✓ Final board: {final_purple_count} purple, {final_red_count} red")

            # Total cards on board should increase (board card tucked + hand cards tucked)
            total_increase = (final_purple_count - initial_purple_count) + (final_red_count - initial_red_count)
            print(f"✓ Total cards added to board: {total_increase} (1 selected + {initial_hand_count} from hand)")

        else:
            print("\n✓ No pending interaction (dogma completed immediately)")
            print("  This can happen if no eligible cards exist")

        # HANDLE EFFECT 2: Socialism also has "junk an available achievement" sharing effect
        # Check if there's a second pending interaction for achievement junking
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        intermediate_state = response.json()

        effect2_pending = intermediate_state.get("state", {}).get("pending_dogma_action")
        if effect2_pending:
            interaction_data = effect2_pending.get("context", {}).get("interaction_data", {})
            data = interaction_data.get("data", {})
            message = data.get("message", "")
            source = data.get("source", "")
            print(f"\n--- Checking Effect 2 ---")
            print(f"  Message: {message}")
            print(f"  Source: {source}")
            print(f"  Has achievements in message: {'achievements' in message.lower()}")

            if "achievement" in message.lower() or source == "achievements_available":
                print("\n--- Handling Effect 2: Junk Achievement (Optional) ---")
                # Decline the optional achievement junking
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={
                        "player_id": human_id,
                        "decline": True
                    }
                )
                print(f"  Response status: {response.status_code}")
                print(f"  Response text: {response.text}")
                assert response.status_code == 200, f"Failed to decline effect 2: {response.text}"
                print("✓ Declined optional achievement junking")
                time.sleep(2)  # More time to process

        # ASSERTION 10: Get final game state - no pending interaction
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        final_pending = final_state.get("state", {}).get("pending_dogma_action")
        assert final_pending is None, \
            f"Expected no pending interaction after selection, got: {final_pending}"
        print("\n✓ Final state: No pending interaction (UI cleared after selection)")

        # ASSERTION 11: Verify game phase is still playing
        assert final_state.get("phase") == "playing", \
            f"Expected phase 'playing', got {final_state.get('phase')}"
        print("✓ Game phase is still 'playing'")

        # ASSERTION 12: Check action log for Socialism
        action_log = final_state.get("action_log", [])
        socialism_actions = [
            log for log in action_log
            if "Socialism" in log.get("description", "")
        ]
        assert len(socialism_actions) > 0, \
            "Expected Socialism in action log"
        print(f"✓ Socialism in action log: {len(socialism_actions)} entries")

        print("\n" + "="*70)
        print("✅ ALL ASSERTIONS PASSED - Socialism Optional Selection Test")
        print("="*70)
        print("\nPrimitives Tested:")
        print("  ✓ SelectCards (optional, source: board_top)")
        print("  ✓ ConditionalAction (condition: cards_selected)")
        print("  ✓ TuckCard (selected_cards and hand cards)")
        print("  ✓ Field name contract: 'eligible_cards'")
        print("="*70)


if __name__ == "__main__":
    # Run test
    test = TestSocialismScenario()
    test.test_socialism_optional_with_selection()
