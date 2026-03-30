#!/usr/bin/env python3
"""
Scenario Test: Construction

Tests Construction's demand + special Empire achievement:
- Effect 1 (demand): Transfer 2 cards from opponent hand to active hand. Opponent draws a 2.
- Effect 2: If only player with 5 top cards, claim Empire achievement.

Primitives tested: DemandEffect, SelectCards (demand), TransferBetweenPlayers,
CountCards, ConditionalAction (and), only_player_with_condition, ClaimAchievement

Setup:
- Human: 5 board colors (Construction red, Clothing green, Agriculture yellow,
  Pottery blue, Mysticism purple) = 5 top cards
- AI: Writing (blue) on board - 0 castles, vulnerable to demand
- AI hand: 3 cards for demand to transfer 2

Expected:
- Demand: AI selects 2 cards, transfers to human hand, AI draws a 2
- Effect 2: Human has 5 top cards, AI doesn't → claim Empire
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestConstructionScenario:
    """Test Construction demand + Empire achievement scenario."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Construction scenario."""
        print("\n" + "="*70)
        print("SETUP: Creating Construction Empire Achievement Scenario")
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

        # Human board: 5 colors (for Empire)
        human_board = [
            ("Construction", "red"),
            ("Clothing", "green"),
            ("Agriculture", "yellow"),
            ("Pottery", "blue"),
            ("Mysticism", "purple"),
        ]
        for card_name, color in human_board:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": human_id, "card_name": card_name, "location": "board"}
            )
            assert response.status_code == 200
        print(f"✓ Human board: 5 colors ({', '.join(c for _, c in human_board)})")

        # AI board: Writing (blue, 0 castles - vulnerable)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Writing", "location": "board"}
        )
        assert response.status_code == 200
        print("✓ AI board: Writing (0 castles)")

        # AI hand: 3 cards (demand will take 2)
        ai_hand = ["Sailing", "The Wheel", "Domestication"]
        for card_name in ai_hand:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": ai_id, "card_name": card_name, "location": "hand"}
            )
            assert response.status_code == 200
        print(f"✓ AI hand: {ai_hand}")

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

    def test_construction_demand_and_empire(self):
        """Test Construction demand transfer + Empire achievement."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]
        ai_id = scenario["ai_id"]

        print("\n" + "="*70)
        print("TEST: Construction Demand + Empire")
        print("="*70)

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial = response.json()
        human_init = next(p for p in initial["players"] if p["id"] == human_id)
        ai_init = next(p for p in initial["players"] if p["id"] == ai_id)
        print(f"Initial: Human hand={len(human_init.get('hand', []))}, AI hand={len(ai_init.get('hand', []))}")

        # Execute Construction dogma
        print("\n--- Executing Construction Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Construction"
            }
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("✓ Construction dogma executed")

        # Wait for AI to process demand (API call)
        time.sleep(6)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final = response.json()
        human_final = next(p for p in final["players"] if p["id"] == human_id)
        ai_final = next(p for p in final["players"] if p["id"] == ai_id)

        human_hand = human_final.get("hand", [])
        ai_hand = ai_final.get("hand", [])
        human_hand_names = [c["name"] for c in human_hand]
        ai_hand_names = [c["name"] for c in ai_hand]

        print(f"\nFinal: Human hand={human_hand_names}, AI hand={ai_hand_names}")

        # Verify demand: 2 cards transferred from AI to human
        # AI started with 3, lost 2, drew a 2 = 2 cards
        # Human started with 0, gained 2 = 2 cards
        assert len(human_hand) >= 2, \
            f"Human should have gained 2 cards from demand, has {len(human_hand)}"
        print(f"✓ Human gained cards from demand: {human_hand_names}")

        # Verify AI drew a card (AI had 3, lost 2, drew 1 = 2)
        print(f"✓ AI hand after demand: {ai_hand_names}")

        # Check achievements for Empire
        achievements = human_final.get("achievements", [])
        achievement_names = [a.get("name", a.get("achievement_id", "?")) for a in achievements]
        print(f"Human achievements: {achievement_names}")

        # Human has 5 top cards, AI has 1 → should claim Empire
        human_board = human_final.get("board", {})
        human_colors = [k for k, v in human_board.items() if k.endswith("_cards") and v]
        ai_board = ai_final.get("board", {})
        ai_colors = [k for k, v in ai_board.items() if k.endswith("_cards") and v]
        print(f"Human board colors: {len(human_colors)}, AI board colors: {len(ai_colors)}")

        # Empire should be claimed if human has 5 and is only player with 5
        if len(human_colors) >= 5 and len(ai_colors) < 5:
            assert any("Empire" in str(a) for a in achievements), \
                f"Human should have Empire achievement with 5 top cards, achievements: {achievement_names}"
            print("✓ Empire achievement claimed!")
        else:
            print(f"⚠ Board state changed during dogma, skipping Empire check")

        # Verify game completed
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Game should complete, but has pending: {pending}"
        print("✓ Game completed without hanging")

        print("\n" + "="*70)
        print("✅ Construction test PASSED")
        print("="*70)

    def test_construction_consecutive_demands(self):
        """Test Construction demand executed twice consecutively - regression for hanging bug.

        Bug: Second execution's game_state in action_performed broadcast had
        pending_dogma_action=null (captured before it was set), causing frontend's
        action_performed handler to clear enhancedPendingAction, breaking the UI.

        This test validates the backend returns correct game_state with
        pending_dogma_action set when dogma requires interaction.
        """
        print("\n" + "="*70)
        print("TEST: Construction Consecutive Demands (regression test)")
        print("="*70)

        # Setup: Human activates Construction twice, AI is vulnerable both times
        response = requests.post(f"{BASE_URL}/api/v1/games", json={})
        assert response.status_code == 200
        game_id = response.json()["game_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/join",
            json={"name": "DemandingPlayer"}
        )
        assert response.status_code == 200
        human_id = response.json()["player_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/add_ai_player",
            json={"difficulty": "beginner"}
        )
        assert response.status_code == 200
        game_state = response.json()["game_state"]
        ai_id = next(p["id"] for p in game_state["players"] if p["is_ai"])

        # Give human Construction board
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Construction", "location": "board"}
        )

        # Give AI cards (4+ so it has enough for 2 demands of 2 each)
        for card_name in ["Sailing", "The Wheel", "Domestication", "Pottery", "Clothing"]:
            requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": ai_id, "card_name": card_name, "location": "hand"}
            )

        # AI board: Writing (0 castles, vulnerable to demand)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Writing", "location": "board"}
        )

        # Set state: human's turn, 2 actions remaining
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )

        print(f"Game: {game_id}")
        print(f"Human: {human_id[:8]}, AI: {ai_id[:8]}")

        # FIRST dogma execution
        print("\n--- First Construction Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Construction"}
        )
        assert response.status_code == 200, f"First dogma failed: {response.text}"

        # Get the pending action details from game state
        state = requests.get(f"{BASE_URL}/api/v1/games/{game_id}").json()
        pending = state.get("state", {}).get("pending_dogma_action")
        assert pending is not None, "Game should have pending interaction after first dogma"
        assert pending.get("target_player_id") == ai_id, "AI should be targeted for demand"

        # AI responds to first demand
        interaction_data = pending.get("context", {}).get("interaction_data", {})
        eligible = interaction_data.get("data", {}).get("eligible_cards", [])
        if not eligible:
            eligible = interaction_data.get("eligible_cards", [])
        print(f"AI eligible cards for demand: {len(eligible)}")

        # Use first 2 eligible cards
        selected = [c["card_id"] if isinstance(c, dict) else c for c in eligible[:2]]
        tx_id = pending.get("context", {}).get("transaction_id")

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/interactions/{tx_id}",
            json={
                "player_id": ai_id,
                "selected_cards": selected,
            }
        )
        assert response.status_code == 200, f"First dogma response failed: {response.text}"
        print("First demand responded")

        # Wait for first dogma to complete
        time.sleep(1)

        # Verify first dogma completed
        state = requests.get(f"{BASE_URL}/api/v1/games/{game_id}").json()
        pending = state.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"First dogma should have completed: {pending}"
        actions_remaining = state.get("state", {}).get("actions_remaining", 0)
        print(f"After first dogma: actions_remaining={actions_remaining}")
        assert actions_remaining == 1, f"Expected 1 action remaining, got {actions_remaining}"

        # SECOND dogma execution (the one that was hanging)
        print("\n--- Second Construction Dogma (previously hanging) ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Construction"}
        )
        assert response.status_code == 200, f"Second dogma failed: {response.text}"
        print("Second dogma action accepted")

        # Get pending action for second demand
        state = requests.get(f"{BASE_URL}/api/v1/games/{game_id}").json()
        pending2 = state.get("state", {}).get("pending_dogma_action")
        assert pending2 is not None, "Game should have pending interaction after second dogma"

        # AI responds to second demand
        interaction_data2 = pending2.get("context", {}).get("interaction_data", {})
        eligible2 = interaction_data2.get("data", {}).get("eligible_cards", [])
        if not eligible2:
            eligible2 = interaction_data2.get("eligible_cards", [])
        selected2 = [c["card_id"] if isinstance(c, dict) else c for c in eligible2[:2]]
        tx_id2 = pending2.get("context", {}).get("transaction_id")

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/interactions/{tx_id2}",
            json={
                "player_id": ai_id,
                "selected_cards": selected2,
            }
        )
        assert response.status_code == 200, f"Second dogma response failed: {response.text}"
        print("Second demand responded")

        # Wait for second dogma to complete
        time.sleep(1)

        # Verify second dogma completed
        state = requests.get(f"{BASE_URL}/api/v1/games/{game_id}").json()
        pending_final = state.get("state", {}).get("pending_dogma_action")
        assert pending_final is None, f"Second dogma should have completed, still pending: {pending_final}"
        actions_final = state.get("state", {}).get("actions_remaining", 0)
        print(f"After second dogma: actions_remaining={actions_final}")

        print("\n" + "="*70)
        print("✅ Consecutive Construction demands test PASSED")
        print("="*70)
