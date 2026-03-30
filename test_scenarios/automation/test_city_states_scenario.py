#!/usr/bin/env python3
"""
Scenario Test: City States Demand Bug

Tests City States demand effect - transfer doesn't complete after user selection.

Card Text:
"I DEMAND you transfer a top card with a castle from your board to my board
if you have at least four castle symbols on your board!"

Expected Flow:
1. Count target player's castle symbols
2. If >= 4 castles, target selects a top card with castle
3. That card transfers to demanding player's board

Setup:
- Human (P1): City States on board (crowns)
- Human (P2): 4+ castle symbols from multiple cards
- Execute City States dogma
- P2 selects Mysticism
- Verify Mysticism transfers to P1

This test reproduces the bug where user selects card but transfer doesn't happen.
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestCityStatesScenario:
    """Test City States demand transfer completion after user selection."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with City States scenario."""
        # CREATE GAME
        response = requests.post(f"{BASE_URL}/api/v1/games", json={})
        assert response.status_code == 200
        game_id = response.json()["game_id"]

        # JOIN HUMAN PLAYER 1 (demanding)
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/join",
            json={"name": "DemandingPlayer"}
        )
        assert response.status_code == 200
        p1_id = response.json()["player_id"]

        # JOIN HUMAN PLAYER 2 (target)
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/join",
            json={"name": "TargetPlayer"}
        )
        assert response.status_code == 200
        p2_id = response.json()["player_id"]

        # INITIALIZE GAME TO PLAYING STATE
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

        # SETUP P1 BOARD: City States (purple, crowns)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": p1_id,
                "card_name": "City States",
                "location": "board",
                "color": "purple"
            }
        )
        assert response.status_code == 200

        # SETUP P2 BOARD: 4+ castles with multiple top cards that have castle
        # Mysticism (purple, 3 castles)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": p2_id,
                "card_name": "Mysticism",
                "location": "board",
                "color": "purple"
            }
        )
        assert response.status_code == 200

        # Masonry (yellow, 3 castles)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": p2_id,
                "card_name": "Masonry",
                "location": "board",
                "color": "yellow"
            }
        )
        assert response.status_code == 200

        # SET GAME TO PLAYING STATE with P1 as current player
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={
                "phase": "playing",
                "current_player_index": 0,  # P1 is current
                "actions_remaining": 2
            }
        )
        assert response.status_code == 200

        return {
            "game_id": game_id,
            "p1_id": p1_id,
            "p2_id": p2_id
        }

    def test_city_states_demand_transfer(self):
        """Test City States demand completes transfer after user selection."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        p1_id = scenario["p1_id"]
        p2_id = scenario["p2_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()

        p1 = next(p for p in initial_state["players"] if p["id"] == p1_id)
        p2 = next(p for p in initial_state["players"] if p["id"] == p2_id)

        print(f"\n=== INITIAL STATE ===")
        print(f"P1 board: {[c['name'] for color in ['purple_cards', 'yellow_cards', 'blue_cards', 'red_cards', 'green_cards'] for c in p1['board'].get(color, [])]}")
        print(f"P2 board: {[c['name'] for color in ['purple_cards', 'yellow_cards', 'blue_cards', 'red_cards', 'green_cards'] for c in p2['board'].get(color, [])]}")

        # Verify P2 has Mysticism and Masonry
        p2_cards = [c['name'] for color in ['purple_cards', 'yellow_cards', 'blue_cards', 'red_cards', 'green_cards']
                    for c in p2['board'].get(color, [])]
        assert "Mysticism" in p2_cards, "P2 should have Mysticism"
        assert "Masonry" in p2_cards, "P2 should have Masonry"

        # Execute City States dogma by P1
        print(f"\n=== EXECUTING CITY STATES DOGMA ===")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": p1_id,
                "action_type": "dogma",
                "card_name": "City States"
            }
        )
        assert response.status_code == 200
        result = response.json()

        print(f"Dogma result: {result}")

        # Get game state to see pending interaction
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        game_state = response.json()
        pending = game_state.get("pending_interaction") or game_state.get("state", {}).get("pending_dogma_action")

        print(f"\n=== GAME STATE PENDING ===")
        print(f"Pending: {pending}")

        # Check if interaction is required (P2 should select card)
        if pending:
            print(f"\n=== PENDING INTERACTION ===")
            print(f"Type: {pending.get('action_type')}")
            print(f"Target: {pending.get('target_player_id')}")
            print(f"Context: {pending.get('context', {})}")

            # P2 should be the one needing to respond
            assert pending.get("target_player_id") == p2_id, f"P2 should need to respond to demand. Got target: {pending.get('target_player_id')}"

            # Get eligible cards
            context = pending.get("context", {})
            eligible_cards = context.get("eligible_cards", context.get("cards", []))
            print(f"Eligible cards: {eligible_cards}")

            # P2 responds by selecting Mysticism
            # Get the interaction_id (transaction_id) from context
            transaction_id = context.get("transaction_id")
            interaction_data = context.get("interaction_data", {})
            data = interaction_data.get("data", {})

            # Use the /interactions/{interaction_id} endpoint
            print(f"\n=== P2 RESPONDING - SELECTING MYSTICISM ===")
            print(f"Transaction ID: {transaction_id}")
            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/interactions/{transaction_id}",
                json={
                    "player_id": p2_id,
                    "selected_cards": ["Mysticism"]
                }
            )

            if response.status_code != 200:
                print(f"Response failed: {response.text}")
            assert response.status_code == 200, f"Response failed: {response.text}"
            resume_result = response.json()
            print(f"Resume result: {resume_result}")

            # Check for further pending interactions
            if resume_result.get("pending"):
                print(f"\n=== STILL PENDING ===")
                print(f"Pending: {resume_result['pending']}")

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        p1_final = next(p for p in final_state["players"] if p["id"] == p1_id)
        p2_final = next(p for p in final_state["players"] if p["id"] == p2_id)

        print(f"\n=== FINAL STATE ===")
        p1_final_cards = [c['name'] for color in ['purple_cards', 'yellow_cards', 'blue_cards', 'red_cards', 'green_cards']
                         for c in p1_final['board'].get(color, [])]
        p2_final_cards = [c['name'] for color in ['purple_cards', 'yellow_cards', 'blue_cards', 'red_cards', 'green_cards']
                         for c in p2_final['board'].get(color, [])]
        print(f"P1 board: {p1_final_cards}")
        print(f"P2 board: {p2_final_cards}")

        # VERIFY TRANSFER: Mysticism should now be on P1's board
        assert "Mysticism" in p1_final_cards, f"FAILURE: Mysticism should have transferred to P1. P1 has: {p1_final_cards}"
        assert "Mysticism" not in p2_final_cards, f"FAILURE: Mysticism should NOT still be on P2's board. P2 has: {p2_final_cards}"

        print(f"\n=== SUCCESS: Mysticism transferred to P1! ===")


if __name__ == "__main__":
    test = TestCityStatesScenario()
    test.test_city_states_demand_transfer()
