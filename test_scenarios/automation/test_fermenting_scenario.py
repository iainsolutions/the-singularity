#!/usr/bin/env python3
"""
Scenario Test: Fermenting

Tests Fermenting's CountColorsWithSymbol, RepeatAction, and FilterCards primitives.

Expected Flow:
1. Execute Fermenting dogma
2. Effect 1: Count colors with leaf symbol (should be 2: yellow and blue)
3. RepeatAction: Draw 2 age-2 cards (one for each color)
4. Effect 2: Optional select green card to tuck (no green available)
5. Since no green tucked: FilterCards gets all age 2 deck cards, junk them all
6. Check if Fermenting is still on top, if yes junk it too

Setup:
- Human: Agriculture (bottom yellow), Pottery (blue), Fermenting (top yellow) on board, Archery in hand
- AI: Mysticism (blue) on board

Expected Results:
- CountColorsWithSymbol correctly counts 2 colors (yellow + blue)
- RepeatAction executes 2 times
- Hand increased by 2 (from 1 to 3: Archery + 2 drawn cards)
- Age 2 deck emptied (FilterCards + TransferCards to junk)
- Fermenting removed from board (still on top when checked)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"

class TestFermentingScenario:
    """Test Fermenting scenario."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Fermenting scenario."""
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
        # Human board: Agriculture (bottom yellow), Pottery (blue), Fermenting (top yellow)
        # Order matters - Fermenting must be on top to be clickable
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Agriculture",
                "location": "board",
                "color": "yellow"
            }
        )
        assert response.status_code == 200

        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Pottery",
                "location": "board",
                "color": "blue"
            }
        )
        assert response.status_code == 200

        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Fermenting",
                "location": "board",
                "color": "yellow"
            }
        )
        assert response.status_code == 200

        # Human hand: Archery (no green card available)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Archery",
                "location": "hand"
            }
        )
        assert response.status_code == 200

        # AI board: Mysticism
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Mysticism",
                "location": "board",
                "color": "blue"
            }
        )
        assert response.status_code == 200

        # SET GAME TO PLAYING STATE (DON'T call /start)
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

    def test_fermenting_complete(self):
        """Test complete Fermenting flow."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()
        human_player = next(p for p in initial_state["players"] if p["id"] == human_id)
        initial_hand_count = len(human_player["hand"])

        # Execute Fermenting dogma
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Fermenting"
            }
        )
        assert response.status_code == 200

        # Poll for interaction to appear (Effect 2 - optional green card selection)
        # OR wait for dogma to complete (if AI declines automatically)
        interaction_data = None
        for attempt in range(30):  # 30 attempts = 15 seconds max
            time.sleep(0.5)
            response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
            state = response.json()
            # Check interaction data inside pending_dogma_action.context
            pending_dogma = state.get("state", {}).get("pending_dogma_action")
            interaction_data = (
                pending_dogma.get("context", {}).get("interaction_data", {})
                if pending_dogma
                else {}
            )

            # Found interaction - break and respond
            if interaction_data and interaction_data.get("interaction_type") == "select_cards":
                print(f"✓ Interaction found after {(attempt + 1) * 0.5}s")
                break

            # Dogma completed without interaction - break
            if not pending_dogma:
                print(f"✓ Dogma completed after {(attempt + 1) * 0.5}s (no interaction needed)")
                break

            if attempt % 6 == 0:  # Log every 3 seconds
                print(f"  Waiting... (attempt {attempt+1}, pending={bool(pending_dogma)})")
        else:
            print(f"⚠ Warning: Timeout after 15s")
            print(f"  Final: pending={bool(pending_dogma)}, has_interaction={bool(interaction_data)}")

        # If there's a select_cards interaction, cancel it (no green card to tuck)
        if interaction_data and interaction_data.get("interaction_type") == "select_cards":
            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                json={
                    "player_id": human_id,
                    "selected_cards": []  # Cancel - no cards selected
                }
            )
            assert response.status_code == 200

            # CRITICAL: Wait for dogma execution to complete (async processing)
            # Poll until pending_dogma_action clears (max 10 seconds)
            for attempt in range(20):  # 20 attempts = 10 seconds max
                time.sleep(0.5)
                response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
                state = response.json()
                # Check if dogma completed (no pending action)
                pending = state.get("state", {}).get("pending_dogma_action")
                if not pending:
                    print(f"✓ Dogma completed after {(attempt + 1) * 0.5} seconds")
                    break
            else:
                print("⚠ Warning: Dogma still pending after 10s")

        # CRITICAL: Extra wait to ensure full state persistence
        time.sleep(0.5)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        # Get human player
        human_player = next(p for p in final_state["players"] if p["id"] == human_id)
        final_hand_count = len(human_player["hand"])

        # ASSERTIONS
        # 1. CountColorsWithSymbol counted 2 colors (yellow: Fermenting+Agriculture, blue: Pottery)
        #    We verify this by checking that 2 cards were drawn (RepeatAction executed 2x)
        assert final_hand_count == initial_hand_count + 2, (
            f"Expected hand to increase by 2 (RepeatAction 2x), "
            f"but went from {initial_hand_count} to {final_hand_count}"
        )

        # 2. Check for optional green card interaction (Effect 2)
        # Interaction data is stored in pending_dogma_action.context, NOT at game.context level
        pending_dogma = final_state.get("state", {}).get("pending_dogma_action")
        interaction_data = (
            pending_dogma.get("context", {}).get("interaction_data", {})
            if pending_dogma
            else {}
        )

        # Should have optional select_cards interaction for green cards
        if interaction_data:
            assert interaction_data.get("interaction_type") == "select_cards", (
                "Expected select_cards interaction for green card tuck"
            )
            # Check if interaction data exists inside pending_dogma_action.context
            interaction_payload = interaction_data.get("data", interaction_data)
            assert interaction_payload.get("is_optional") is True, (
                "Expected optional interaction (is_optional=true)"
            )
            # Check field name is 'eligible_cards' (field name contract)
            assert "eligible_cards" in interaction_payload or "eligible_card_ids" in interaction_payload, (
                "Expected 'eligible_cards' or 'eligible_card_ids' field in interaction_data"
            )

        # 3. No errors in pending dogma context
        if pending_dogma and pending_dogma.get("context"):
            dogma_context = pending_dogma.get("context", {})
            assert not dogma_context.get("error"), f"Unexpected error in dogma context: {dogma_context.get('error')}"

        # 4. Phase should still be 'playing'
        assert final_state["phase"] == "playing", (
            f"Expected phase 'playing', got '{final_state['phase']}'"
        )

        # 5. Fermenting should be in action log
        action_log = final_state.get("action_log", [])
        fermenting_actions = [
            log for log in action_log
            if "Fermenting" in log.get("description", "") or "Fermenting" in log.get("message", "")
        ]
        assert len(fermenting_actions) > 0, "Expected Fermenting in action log"

        # 6. Effect 2: Age 2 deck should be empty (FilterCards + TransferCards to junk)
        # Test always declines to test the false branch (junking deck)
        age_decks = final_state.get("age_decks", {})
        age_2_deck = age_decks.get("2", [])
        assert len(age_2_deck) == 0, (
            f"Expected age 2 deck to be empty (junked), but has {len(age_2_deck)} cards"
        )

        # 7. Effect 2: Fermenting should be removed from board (was top card, got junked)
        yellow_cards = human_player["board"].get("yellow_cards", [])
        fermenting_on_board = any(c["name"] == "Fermenting" for c in yellow_cards)
        assert not fermenting_on_board, (
            "Expected Fermenting to be junked from board (was top card)"
        )

        # 8. Agriculture should still be on board (was under Fermenting)
        agriculture_on_board = any(c["name"] == "Agriculture" for c in yellow_cards)
        assert agriculture_on_board, (
            "Expected Agriculture to remain on board (was under Fermenting)"
        )

        print(f"Game ID: {game_id}")
        print("✅ ALL ASSERTIONS PASSED")
        print(f"  - RepeatAction executed 2 times (hand +2)")
        print(f"  - CountColorsWithSymbol counted 2 colors with leaf (yellow + blue)")
        print(f"  - FilterCards found and junked all age 2 deck cards")
        print(f"  - Fermenting junked from board (was top card)")
        print(f"  - Agriculture still on board (was underneath)")
        print(f"  - New primitives tested: CountColorsWithSymbol, RepeatAction, FilterCards")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
