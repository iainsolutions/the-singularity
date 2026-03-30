#!/usr/bin/env python3
"""
Scenario Test: Classification Card - GetCardColor Primitive

Tests Classification dogma with GetCardColor primitive to ensure:
1. SelectCards interaction creates proper card selection
2. GetCardColor extracts card color and stores in variable
3. TransferBetweenPlayers uses stored color variable for filtering
4. FilterCards uses stored color variable for filtering hand
5. MeldCard melds all cards of the revealed color
6. Variable storage and reuse works correctly across primitives

Based on: /home/user/Innovation/backend/data/BaseCards.json (Classification card)

Expected Flow:
1. Human executes Classification dogma
2. SelectCards: Human selects a card from hand to reveal (Tools - blue)
3. GetCardColor: Extract color from Tools and store as "revealed_color" = "blue"
4. TransferBetweenPlayers: Transfer all blue cards from AI hand to human hand
   - Pottery (blue) transferred from AI to human
5. FilterCards: Filter human hand for blue cards
   - Tools (blue) and Pottery (blue) selected
6. MeldCard: Meld all filtered blue cards
   - Tools and Pottery melded to human board

Setup:
- Human: Classification (green) on board, Tools (blue) and Archery (red) in hand
- AI: Sailing (green) on board, Pottery (blue), Metalworking (red), City States (purple) in hand

Expected Results:
- Human reveals Tools (blue)
- GetCardColor extracts "blue" and stores in revealed_color variable
- Pottery (blue) transferred from AI hand to human hand
- Both Tools and Pottery melded to human board (blue stack)
- Archery (red) remains in human hand
- AI has Metalworking and City States remaining in hand
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


class TestClassificationScenario:
    """Test Classification card with GetCardColor primitive."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Classification scenario."""
        print("\n" + "="*70)
        print("SETUP: Creating Classification Scenario (GetCardColor Test)")
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

        # Setup: Human has Classification (green) on board
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Classification",
                "location": "board",
                "color": "green"
            }
        )
        assert response.status_code == 200, f"Add Classification failed: {response.text}"
        print("✓ Classification added to human board (green)")

        # Setup: Human has Tools (blue) in hand
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Tools",
                "location": "hand"
            }
        )
        assert response.status_code == 200, f"Add Tools failed: {response.text}"
        print("✓ Tools added to human hand (blue)")

        # Setup: Human has Archery (red) in hand
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Archery",
                "location": "hand"
            }
        )
        assert response.status_code == 200, f"Add Archery failed: {response.text}"
        print("✓ Archery added to human hand (red)")

        # Setup: AI has Sailing (green) on board
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Sailing",
                "location": "board",
                "color": "green"
            }
        )
        assert response.status_code == 200, f"Add Sailing failed: {response.text}"
        print("✓ Sailing added to AI board (green)")

        # Setup: AI has Pottery (blue) in hand - will be transferred
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Pottery",
                "location": "hand"
            }
        )
        assert response.status_code == 200, f"Add Pottery failed: {response.text}"
        print("✓ Pottery added to AI hand (blue - will be transferred)")

        # Setup: AI has Metalworking (red) in hand
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Metalworking",
                "location": "hand"
            }
        )
        assert response.status_code == 200, f"Add Metalworking failed: {response.text}"
        print("✓ Metalworking added to AI hand (red)")

        # Setup: AI has City States (purple) in hand
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "City States",
                "location": "hand"
            }
        )
        assert response.status_code == 200, f"Add City States failed: {response.text}"
        print("✓ City States added to AI hand (purple)")

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

    def test_classification_complete(self):
        """Test complete Classification flow with GetCardColor primitive."""
        # Setup scenario
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]
        ai_id = scenario["ai_id"]

        print("\n" + "="*70)
        print("TEST: Classification GetCardColor Flow")
        print("="*70)

        # Execute Classification dogma
        print("\n--- Executing Classification Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Classification"
            }
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("✓ Classification dogma executed")

        time.sleep(2)

        # Get game state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        game_state = response.json()

        print(f"\nGame ID: {game_id}")

        # ASSERTION 1: Check for pending interaction (card selection)
        pending_interaction = game_state.get("state", {}).get("pending_dogma_action")
        assert pending_interaction is not None, "Expected pending interaction for card selection"
        print("\n✓ Pending interaction exists (card selection)")

        # Get interaction data
        context = pending_interaction.get("context", {})
        interaction_data = context.get("interaction_data", {})

        print(f"  Interaction type: {interaction_data.get('interaction_type')}")
        print(f"  Description: {interaction_data.get('description')}")

        # ASSERTION 2: Interaction type should be select_cards
        assert interaction_data.get("interaction_type") == "select_cards", \
            f"Expected select_cards interaction, got {interaction_data.get('interaction_type')}"
        print("✓ Interaction type is select_cards")

        # ASSERTION 3: Field name must be eligible_cards
        data = interaction_data.get("data", {})
        assert "eligible_cards" in data, \
            f"Expected 'eligible_cards' field, got fields: {list(data.keys())}"
        print("✓ Field name is 'eligible_cards' (contract compliance)")

        # Select Tools (blue) to reveal
        print("\n--- Selecting Tools (blue) to Reveal ---")
        eligible_cards = data.get("eligible_cards", [])
        tools_card = next((c for c in eligible_cards if c["name"] == "Tools"), None)
        assert tools_card is not None, "Tools card not found in eligible cards"
        print(f"Selecting: {tools_card['name']} ({tools_card['color']})")

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
            json={
                "player_id": human_id,
                "selected_cards": [tools_card['card_id']]
            }
        )
        assert response.status_code == 200, f"Failed to select card: {response.status_code}"
        print(f"✓ Tools (blue) selected successfully")

        time.sleep(2)

        # ASSERTION 4: Get final game state - no pending interaction
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        final_pending = final_state.get("state", {}).get("pending_dogma_action")
        assert final_pending is None, \
            f"Expected no pending interaction after dogma completion, got: {final_pending}"
        print("\n✓ Final state: No pending interaction (dogma completed)")

        # ASSERTION 5: Verify game phase is still playing
        assert final_state.get("phase") == "playing", \
            f"Expected phase 'playing', got {final_state.get('phase')}"
        print("✓ Game phase is still 'playing'")

        # Get player states
        human_player = next(
            (p for p in final_state["players"] if p["id"] == human_id),
            None
        )
        ai_player = next(
            (p for p in final_state["players"] if p["id"] == ai_id),
            None
        )
        assert human_player is not None, "Human player not found"
        assert ai_player is not None, "AI player not found"

        # ASSERTION 6: Human hand should only contain Archery (red)
        human_hand = human_player.get("hand", [])
        hand_names = [card["name"] for card in human_hand]
        print(f"\n✓ Human hand after dogma: {hand_names}")
        assert "Archery" in hand_names, "Archery should remain in hand"
        assert "Tools" not in hand_names, "Tools should be melded"
        assert "Pottery" not in hand_names, "Pottery should be melded"
        print("✓ Human hand correct: Only Archery (red) remains")

        # ASSERTION 7: AI hand should not contain Pottery (transferred)
        ai_hand = ai_player.get("hand", [])
        ai_hand_names = [card["name"] for card in ai_hand]
        print(f"\n✓ AI hand after dogma: {ai_hand_names}")
        assert "Pottery" not in ai_hand_names, "Pottery should be transferred"
        assert "Metalworking" in ai_hand_names, "Metalworking should remain"
        assert "City States" in ai_hand_names, "City States should remain"
        print("✓ AI hand correct: Pottery transferred, others remain")

        # ASSERTION 8: Human board should have blue stack with Tools and Pottery
        board = human_player.get("board", {})
        assert "blue_cards" in board, "Expected blue stack on board"
        blue_cards = board.get("blue_cards", [])
        blue_names = [card["name"] for card in blue_cards]
        print(f"\n✓ Human blue stack: {blue_names}")
        assert "Tools" in blue_names, "Tools should be melded"
        assert "Pottery" in blue_names, "Pottery should be melded"
        print("✓ Board state correct: Tools and Pottery melded to blue stack")

        # ASSERTION 9: Check action log for Classification
        action_log = final_state.get("action_log", [])
        classification_actions = [
            log for log in action_log
            if "Classification" in log.get("description", "")
        ]
        assert len(classification_actions) > 0, \
            "Expected Classification in action log"
        print(f"\n✓ Classification in action log: {len(classification_actions)} entries")

        print("\n" + "="*70)
        print("✅ ALL ASSERTIONS PASSED - Classification GetCardColor Test")
        print("="*70)
        print("\nPrimitives Tested:")
        print("  ✓ SelectCards - card selection from hand")
        print("  ✓ GetCardColor - color extraction and variable storage")
        print("  ✓ TransferBetweenPlayers - with color filter using stored variable")
        print("  ✓ FilterCards - hand filtering using stored color variable")
        print("  ✓ MeldCard - melding filtered cards")
        print("  ✓ Variable storage/reuse - revealed_color used across multiple primitives")
        print("="*70)


if __name__ == "__main__":
    # Run test
    test = TestClassificationScenario()
    test.test_classification_complete()
