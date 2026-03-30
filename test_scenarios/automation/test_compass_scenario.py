#!/usr/bin/env python3
"""
Scenario Test: Compass

Tests Compass demand with dual-direction board-to-board transfers:
- Effect (demand): Transfer non-green top card with leaf from opponent board
  to active board. Then transfer top card without leaf from active board
  to opponent board.

Primitives tested: DemandEffect, SelectCards (board_top with not_color + has_symbol),
SelectCards (board_top with not_has_symbol, player="active"),
TransferBetweenPlayers (2x, opposite directions, board-to-board)

Setup:
- Human: Compass (green, 2 crowns) + Metalworking (red, no leaf) on board
- AI: Agriculture (yellow, has leaf, not green) + Writing (blue, no leaf) on board
- Human has 2 crowns, AI has 0 → AI is vulnerable to demand

Expected:
- First transfer: Agriculture (non-green, has leaf) from AI board → human board
- Second transfer: Metalworking (no leaf) from human board → AI board
- After: Human has Compass + Agriculture, AI has Writing + Metalworking
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestCompassScenario:
    """Test Compass dual-direction board transfer demand."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Compass scenario."""
        print("\n" + "="*70)
        print("SETUP: Creating Compass Dual-Transfer Demand Scenario")
        print("="*70)

        # Create game
        response = requests.post(f"{BASE_URL}/api/v1/games", json={})
        assert response.status_code == 200
        game_id = response.json()["game_id"]
        print(f"✓ Game created: {game_id}")

        # Join human player
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/join",
            json={"name": "TestPlayer"}
        )
        assert response.status_code == 200
        human_id = response.json()["player_id"]
        print(f"✓ Human joined: {human_id}")

        # Add AI player
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/add_ai_player",
            json={"difficulty": "beginner"}
        )
        assert response.status_code == 200
        game_state = response.json()["game_state"]
        ai_id = next(p["id"] for p in game_state["players"] if p["is_ai"])
        print(f"✓ AI added: {ai_id}")

        # Initialize
        time.sleep(0.5)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing"}
        )
        assert response.status_code == 200

        # Human board: Compass (green, 2 crowns) + Metalworking (red, no leaf)
        for card_name in ["Compass", "Metalworking"]:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": human_id, "card_name": card_name, "location": "board"}
            )
            assert response.status_code == 200
        print("✓ Human board: Compass (green), Metalworking (red)")

        # AI board: Agriculture (yellow, has leaf) + Writing (blue, no leaf)
        for card_name in ["Agriculture", "Writing"]:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": ai_id, "card_name": card_name, "location": "board"}
            )
            assert response.status_code == 200
        print("✓ AI board: Agriculture (yellow, leaf), Writing (blue, no leaf)")

        # Set game state
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={
                "phase": "playing",
                "current_player_index": 0,
                "actions_remaining": 2
            }
        )
        assert response.status_code == 200
        print("✓ Game state set")

        print("="*70)
        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_compass_dual_transfer(self):
        """Test Compass demand with dual-direction board transfers."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]
        ai_id = scenario["ai_id"]

        print("\n" + "="*70)
        print("TEST: Compass Dual-Direction Board Transfers")
        print("="*70)

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial = response.json()

        human_init = next(p for p in initial["players"] if p["id"] == human_id)
        ai_init = next(p for p in initial["players"] if p["id"] == ai_id)

        def get_board_cards(player):
            board = player.get("board", {})
            cards = {}
            for color in ["red", "green", "blue", "yellow", "purple"]:
                stack = board.get(f"{color}_cards", [])
                if stack:
                    cards[color] = [c["name"] for c in stack]
            return cards

        human_board_init = get_board_cards(human_init)
        ai_board_init = get_board_cards(ai_init)
        print(f"Initial Human board: {human_board_init}")
        print(f"Initial AI board: {ai_board_init}")

        # Execute Compass dogma
        print("\n--- Executing Compass Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Compass"
            }
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("✓ Compass dogma executed")

        # Wait for AI demand processing
        time.sleep(6)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final = response.json()

        human_final = next(p for p in final["players"] if p["id"] == human_id)
        ai_final = next(p for p in final["players"] if p["id"] == ai_id)

        human_board_final = get_board_cards(human_final)
        ai_board_final = get_board_cards(ai_final)

        print(f"\nFinal Human board: {human_board_final}")
        print(f"Final AI board: {ai_board_final}")

        # Verify Transfer 1: Agriculture moved from AI → Human
        # Agriculture is yellow with leaf, non-green - eligible for first transfer
        human_has_agriculture = any(
            "Agriculture" in cards
            for cards in human_board_final.values()
        )
        ai_lost_agriculture = not any(
            "Agriculture" in cards
            for cards in ai_board_final.values()
        )
        print(f"Human has Agriculture: {human_has_agriculture}")
        print(f"AI lost Agriculture: {ai_lost_agriculture}")

        assert human_has_agriculture, \
            f"Agriculture should transfer to human board, human board: {human_board_final}"
        assert ai_lost_agriculture, \
            f"Agriculture should leave AI board, AI board: {ai_board_final}"
        print("✓ Transfer 1: Agriculture (leaf, non-green) → human board")

        # Verify Transfer 2: Metalworking moved from Human → AI
        # Metalworking is red with no leaf - eligible for second transfer
        ai_has_metalworking = any(
            "Metalworking" in cards
            for cards in ai_board_final.values()
        )
        human_lost_metalworking = not any(
            "Metalworking" in cards
            for cards in human_board_final.values()
        )
        print(f"AI has Metalworking: {ai_has_metalworking}")
        print(f"Human lost Metalworking: {human_lost_metalworking}")

        assert ai_has_metalworking, \
            f"Metalworking should transfer to AI board, AI board: {ai_board_final}"
        assert human_lost_metalworking, \
            f"Metalworking should leave human board, human board: {human_board_final}"
        print("✓ Transfer 2: Metalworking (no leaf) → AI board")

        # Verify Compass stayed on human board (green, not eligible for transfer)
        assert "green" in human_board_final and "Compass" in human_board_final["green"], \
            f"Compass should stay on human board, board: {human_board_final}"
        print("✓ Compass stayed on human board")

        # Verify Writing stayed on AI board (blue, no leaf - not eligible for first transfer)
        assert "blue" in ai_board_final and "Writing" in ai_board_final["blue"], \
            f"Writing should stay on AI board, board: {ai_board_final}"
        print("✓ Writing stayed on AI board")

        # Verify game completed
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Game should complete, but has pending: {pending}"
        print("✓ Game completed without hanging")

        print("\n" + "="*70)
        print("✅ Compass dual-transfer test PASSED")
        print("="*70)
