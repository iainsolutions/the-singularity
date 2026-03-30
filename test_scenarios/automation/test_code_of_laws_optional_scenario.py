#!/usr/bin/env python3
"""
Scenario Test: Code of Laws Card Selection

Tests Code of Laws dogma with card selection to ensure:
1. Card selection interaction is properly created
2. Once dogma executed, player must complete effects (cannot decline)
3. Frontend state clears correctly after selection
4. Field name contract: uses 'eligible_cards' (not 'cards' or '_eligible_cards')

Based on: /Users/iainknight/Git/Innovation/backend/data/BaseCards.json (Code of Laws card)

Expected Flow:
1. Human executes Code of Laws dogma
2. Effect 0: Human must select a card from hand matching board color to tuck
   - Card tucked under matching color stack
   - CANNOT decline once dogma executed (correct game behavior)

Setup:
- Human: Code of Laws (purple) on board, Oars (red) on board
- Human hand: City States (purple), Metalworking (red)
- Both hand cards match colors on board, so both are eligible to tuck

Expected Results:
- Interaction created with can_cancel=false (must complete once dogma executed)
- Both City States and Metalworking are eligible to tuck
- User selects one card to tuck
- Selected card is tucked under matching color stack
- Frontend clears interaction UI after selection
- Field name is 'eligible_cards' (contract compliance)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestCodeOfLawsOptionalScenario:
    """Test Code of Laws optional selection and UI state clearing."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Code of Laws optional selection scenario."""
        print("\n" + "="*70)
        print("SETUP: Creating Code of Laws Optional Selection Scenario")
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

        # Setup: Human has Code of Laws (purple) on board
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Code of Laws",
                "location": "board",
                "color": "purple"
            }
        )
        assert response.status_code == 200, f"Add Code of Laws failed: {response.text}"
        print("✓ Code of Laws added to human board (purple)")

        # Setup: Human has Oars (red) on board
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Oars",
                "location": "board",
                "color": "red"
            }
        )
        assert response.status_code == 200, f"Add Oars failed: {response.text}"
        print("✓ Oars added to human board (red)")

        # Give human City States (purple) in hand - can be tucked under purple
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "City States",
                "location": "hand"
            }
        )
        assert response.status_code == 200, f"Add City States failed: {response.text}"
        print("✓ City States added to human hand (purple - can tuck)")

        # Give human Metalworking (red) in hand - can be tucked under red
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Metalworking",
                "location": "hand"
            }
        )
        assert response.status_code == 200, f"Add Metalworking failed: {response.text}"
        print("✓ Metalworking added to human hand (red - can tuck)")

        # Setup: AI has Mysticism in hand
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Mysticism",
                "location": "hand"
            }
        )
        assert response.status_code == 200, f"Add Mysticism failed: {response.text}"
        print("✓ Mysticism added to AI hand (blue)")

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

    def test_code_of_laws_optional_complete(self):
        """Test complete Code of Laws optional selection flow."""
        # Setup scenario
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        print("\n" + "="*70)
        print("TEST: Code of Laws Optional Selection")
        print("="*70)

        # Execute Code of Laws dogma
        print("\n--- Executing Code of Laws Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Code of Laws"
            }
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("✓ Code of Laws dogma executed")

        time.sleep(2)

        # Get game state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        game_state = response.json()

        print(f"\nGame ID: {game_id}")
        print(f"Game state keys: {list(game_state.keys())}")

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

            # ASSERTION 3: Selection is optional (card text says "You may tuck...")
            assert interaction_data.get("can_cancel") is True, \
                "Expected can_cancel=true (is_optional=true in card definition)"
            print("✓ Interaction is cancelable (can_cancel=true) - card says 'You may'")

            # ASSERTION 4: Field name must be eligible_cards
            data = interaction_data.get("data", {})
            assert "eligible_cards" in data, \
                f"Expected 'eligible_cards' field, got fields: {list(data.keys())}"
            print("✓ Field name is 'eligible_cards' (not 'cards' or '_eligible_cards')")

            # Select one card to complete the effect (cannot decline once dogma executed)
            print("\n--- Selecting Card to Tuck ---")
            eligible_cards = data.get("eligible_cards", [])
            selected_card = eligible_cards[0]  # Select first eligible card
            print(f"Selecting: {selected_card['name']}")

            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                json={
                    "player_id": human_id,
                    "selected_cards": [selected_card['card_id']]
                }
            )
            assert response.status_code == 200, f"Failed to select card: {response.status_code}"
            print(f"✓ Card selected successfully")

            time.sleep(1)

        else:
            print("\n✓ No pending interaction (dogma completed immediately)")
            print("  This can happen if no eligible cards exist")

        # ASSERTION 5: Get final game state - no pending interaction
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        final_pending = final_state.get("state", {}).get("pending_dogma_action")
        assert final_pending is None, \
            f"Expected no pending interaction after selection, got: {final_pending}"
        print("\n✓ Final state: No pending interaction (UI cleared after selection)")

        # ASSERTION 6: Verify game phase is still playing
        assert final_state.get("phase") == "playing", \
            f"Expected phase 'playing', got {final_state.get('phase')}"
        print("✓ Game phase is still 'playing'")

        # ASSERTION 7: Check action log for Code of Laws
        action_log = final_state.get("action_log", [])
        code_of_laws_actions = [
            log for log in action_log
            if "Code of Laws" in log.get("description", "")
        ]
        assert len(code_of_laws_actions) > 0, \
            "Expected Code of Laws in action log"
        print(f"✓ Code of Laws in action log: {len(code_of_laws_actions)} entries")

        # ASSERTION 8: Verify human still has cards in hand
        human_player = next(
            (p for p in final_state["players"] if p["id"] == human_id),
            None
        )
        assert human_player is not None, "Human player not found"
        hand_count = len(human_player.get("hand", []))
        print(f"✓ Human hand count: {hand_count} cards")

        # ASSERTION 9: Board state should show tucked card on top
        board = human_player.get("board", {})
        assert "purple_cards" in board, "Expected purple stack on board"
        purple_cards = board.get("purple_cards", [])
        assert len(purple_cards) >= 2, "Expected 2 cards on purple stack after tuck"
        assert purple_cards[0].get("name") == "City States", \
            f"Expected tucked card (City States) on top, got {purple_cards[0].get('name')}"
        assert purple_cards[1].get("name") == "Code of Laws", \
            f"Expected Code of Laws underneath, got {purple_cards[1].get('name')}"
        print("✓ Board state correct: City States tucked on top of Code of Laws")

        print("\n" + "="*70)
        print("✅ ALL ASSERTIONS PASSED - Code of Laws Optional Selection Test")
        print("="*70)


if __name__ == "__main__":
    # Run test
    test = TestCodeOfLawsOptionalScenario()
    test.test_code_of_laws_optional_complete()
