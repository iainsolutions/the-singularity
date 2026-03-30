#!/usr/bin/env python3
"""
Scenario Test: Gunpowder Card - Demand with Castle Symbol Filter

Tests Gunpowder dogma with has_symbol filter to ensure:
1. SelectCards filters by has_symbol: castle correctly
2. Only cards with castle symbols are eligible for demand
3. TransferBetweenPlayers moves card from opponent board to active score pile
4. ConditionalAction checks demand_transferred_count correctly
5. DrawCards and ScoreCards execute when condition is true

Based on: /home/user/Innovation/backend/data/BaseCards.json (Gunpowder card)

Card: Gunpowder (Age 4, Red, Factory resource)
Effect 0 (Demand): "I demand you transfer a top card with castle from your board to my score pile!"
Effect 1: "If any card was transferred due to the demand, draw and score a 2."

Expected Flow:
1. Human executes Gunpowder dogma
2. Effect 0: AI must select top card with castle symbol from board
3. SelectCards filters by has_symbol: castle
4. Eligible: Mysticism (has 3 castle), Metalworking (has 3 castle)
5. NOT eligible: Agriculture (no castle, leaf only)
6. Selected card transferred to Human's score pile
7. Effect 1: Conditional checks demand_transferred_count > 0
8. If true: Draw and score Age 2 card
9. Human score pile has transferred card + scored card

Setup:
- Human: Gunpowder (red) on board
- AI: Mysticism (purple), Metalworking (red), Agriculture (yellow) on board
- Only Mysticism and Metalworking have castle symbols

Expected Results:
- AI selects card with castle symbol (Mysticism or Metalworking)
- Selected card transferred to Human score pile
- Human draws and scores Age 2 card
- Human score pile has 2+ cards
- AI board has 2 cards (originally 3, one transferred)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestGunpowderScenario:
    """Test Gunpowder demand with castle symbol filter and conditional scoring."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Gunpowder demand scenario."""
        print("\n" + "="*70)
        print("SETUP: Creating Gunpowder Demand Scenario")
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

        # Setup: Human has Gunpowder (red) on board
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Gunpowder",
                "location": "board",
                "color": "red"
            }
        )
        assert response.status_code == 200, f"Add Gunpowder failed: {response.text}"
        print("✓ Gunpowder added to human board (red)")

        # Setup: AI has Mysticism (purple) on board - has 3 castle symbols
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Mysticism",
                "location": "board",
                "color": "purple"
            }
        )
        assert response.status_code == 200, f"Add Mysticism failed: {response.text}"
        print("✓ Mysticism added to AI board (purple - HAS 3 castle symbols)")

        # Setup: AI has Metalworking (red) on board - has 3 castle symbols
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Metalworking",
                "location": "board",
                "color": "red"
            }
        )
        assert response.status_code == 200, f"Add Metalworking failed: {response.text}"
        print("✓ Metalworking added to AI board (red - HAS 3 castle symbols)")

        # Setup: AI has Agriculture (yellow) on board - NO castle symbol
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Agriculture",
                "location": "board",
                "color": "yellow"
            }
        )
        assert response.status_code == 200, f"Add Agriculture failed: {response.text}"
        print("✓ Agriculture added to AI board (yellow - NO castle symbol)")

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

    def test_gunpowder_demand_complete(self):
        """Test complete Gunpowder demand with castle symbol filter."""
        # Setup scenario
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]
        ai_id = scenario["ai_id"]

        print("\n" + "="*70)
        print("TEST: Gunpowder Demand with Castle Symbol Filter")
        print("="*70)

        # Get initial game state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()

        # Count initial cards
        human_player_initial = next(p for p in initial_state["players"] if p["id"] == human_id)
        ai_player_initial = next(p for p in initial_state["players"] if p["id"] == ai_id)

        initial_human_score = len(human_player_initial.get("score_pile", []))
        initial_ai_board_count = sum(
            len(cards) for cards in ai_player_initial.get("board", {}).values()
            if isinstance(cards, list)
        )

        print(f"\nInitial state:")
        print(f"  Human score pile: {initial_human_score} cards")
        print(f"  AI board: {initial_ai_board_count} cards")

        # Execute Gunpowder dogma
        print("\n--- Executing Gunpowder Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Gunpowder"
            }
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("✓ Gunpowder dogma executed")

        # Wait for AI to process demand (Anthropic API call can take 4-5s)
        time.sleep(6)

        # Get game state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        game_state = response.json()

        print(f"\nGame ID: {game_id}")

        # ASSERTION 1: No pending interaction (AI handles demand automatically)
        pending_interaction = game_state.get("state", {}).get("pending_dogma_action")
        assert pending_interaction is None, \
            f"Expected no pending interaction (AI handles demand), got: {pending_interaction}"
        print("✓ No pending interaction (AI processed demand automatically)")

        # ASSERTION 2: Get final player states
        human_player = next(p for p in game_state["players"] if p["id"] == human_id)
        ai_player = next(p for p in game_state["players"] if p["id"] == ai_id)

        # ASSERTION 3: Human score pile increased
        final_human_score = len(human_player.get("score_pile", []))
        print(f"\nHuman score pile:")
        print(f"  Initial: {initial_human_score}")
        print(f"  Final: {final_human_score}")
        print(f"  Increase: {final_human_score - initial_human_score}")

        # Should have at least 2 cards: transferred card + scored Age 2 card
        assert final_human_score >= initial_human_score + 2, \
            f"Expected at least 2 new cards in score pile (transferred + scored), got {final_human_score - initial_human_score}"
        print("✓ Human score pile increased by at least 2 cards")

        # ASSERTION 4: AI board decreased by 1 (transferred card)
        final_ai_board_count = sum(
            len(cards) for cards in ai_player.get("board", {}).values()
            if isinstance(cards, list)
        )
        print(f"\nAI board:")
        print(f"  Initial: {initial_ai_board_count}")
        print(f"  Final: {final_ai_board_count}")
        print(f"  Decrease: {initial_ai_board_count - final_ai_board_count}")

        assert final_ai_board_count == initial_ai_board_count - 1, \
            f"Expected AI board to decrease by 1, got decrease of {initial_ai_board_count - final_ai_board_count}"
        print("✓ AI board decreased by 1 card (transferred)")

        # ASSERTION 5: Check score pile contents
        score_pile = human_player.get("score_pile", [])
        print(f"\nHuman score pile cards ({len(score_pile)} total):")
        for card in score_pile:
            symbols = card.get("symbols", [])
            has_castle = "castle" in symbols
            print(f"  - {card.get('name')} (Age {card.get('age')}) - Castle: {has_castle}")

        # At least one card should have castle symbol (transferred from AI)
        castle_cards = [c for c in score_pile if "castle" in c.get("symbols", [])]
        assert len(castle_cards) >= 1, \
            "Expected at least one card with castle symbol in score pile"
        print(f"✓ Found {len(castle_cards)} card(s) with castle symbol in score pile")

        # At least one card should be Age 2 (scored from draw)
        age_2_cards = [c for c in score_pile if c.get("age") == 2]
        assert len(age_2_cards) >= 1, \
            "Expected at least one Age 2 card in score pile (from conditional draw/score)"
        print(f"✓ Found {len(age_2_cards)} Age 2 card(s) in score pile (from conditional)")

        # ASSERTION 6: Verify game phase is still playing
        assert game_state.get("phase") == "playing", \
            f"Expected phase 'playing', got {game_state.get('phase')}"
        print("\n✓ Game phase is still 'playing'")

        # ASSERTION 7: Check action log for Gunpowder
        action_log = game_state.get("action_log", [])
        gunpowder_actions = [
            log for log in action_log
            if "Gunpowder" in log.get("description", "")
        ]
        assert len(gunpowder_actions) > 0, \
            "Expected Gunpowder in action log"
        print(f"✓ Gunpowder in action log: {len(gunpowder_actions)} entries")

        # ASSERTION 8: Check for demand-related actions
        demand_actions = [
            log for log in action_log
            if "demand" in log.get("description", "").lower() or
               "transfer" in log.get("description", "").lower()
        ]
        print(f"✓ Found {len(demand_actions)} demand/transfer actions in log")

        # Print some action log entries
        print("\nRecent action log entries:")
        for log in action_log[-5:]:
            print(f"  - {log.get('description')}")

        print("\n" + "="*70)
        print("✅ ALL ASSERTIONS PASSED - Gunpowder Demand Test")
        print("="*70)
        print("\nPrimitives Tested:")
        print("  ✓ DemandEffect with required_symbol: factory")
        print("  ✓ SelectCards with filter: has_symbol: castle")
        print("  ✓ TransferBetweenPlayers (opponent board → active score_pile)")
        print("  ✓ ConditionalAction (variable_gt: demand_transferred_count > 0)")
        print("  ✓ DrawCards (Age 2)")
        print("  ✓ ScoreCards (last_drawn)")
        print("="*70)


if __name__ == "__main__":
    # Run test
    test = TestGunpowderScenario()
    test.test_gunpowder_demand_complete()
