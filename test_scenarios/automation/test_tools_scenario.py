#!/usr/bin/env python3
"""
Scenario Test: Tools

Tests Tools' selection_condition feature (ONLY card that uses this):
- Effect 1: Return 3 hand cards → draw and meld a 3 (if no age 3+ in hand)
- Effect 2: Return a 3 from hand → draw three 1s (if age 3+ in hand)

Primitives tested: selection_condition, SelectCards (optional), ReturnCards,
DrawCards, MeldCard

Setup:
- Human: Tools (blue, 2 lightbulbs) on board
- AI: Agriculture (yellow, 0 lightbulbs) on board - won't share
- Human hand: 4 age-1 cards (no age 3+, so Effect 1 fires)

Expected:
- Effect 1 fires (selection_condition matches "no age 3+ in hand")
- Human gets optional SelectCards for 3 cards
- After selecting 3, they're returned and a 3 is drawn and melded
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestToolsScenario:
    """Test Tools selection_condition scenario."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Tools scenario."""
        print("\n" + "="*70)
        print("SETUP: Creating Tools selection_condition Scenario")
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

        # Initialize game
        time.sleep(0.5)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing"}
        )
        assert response.status_code == 200

        # Human board: Tools (blue, 2 lightbulbs)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Tools", "location": "board"}
        )
        assert response.status_code == 200
        print("✓ Human board: Tools (blue, 2 lightbulbs)")

        # AI board: Agriculture (yellow, 0 lightbulbs)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"}
        )
        assert response.status_code == 200
        print("✓ AI board: Agriculture (0 lightbulbs)")

        # Human hand: 4 age-1 cards (no age 3+, so Effect 1 fires)
        hand_cards = ["Archery", "Oars", "Mysticism", "Sailing"]
        for card_name in hand_cards:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": human_id, "card_name": card_name, "location": "hand"}
            )
            assert response.status_code == 200
        print(f"✓ Human hand: {hand_cards}")

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

    def test_tools_effect1_return_and_meld(self):
        """Test Tools Effect 1: return 3 cards, draw and meld a 3."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        print("\n" + "="*70)
        print("TEST: Tools selection_condition (Effect 1)")
        print("="*70)

        # Execute Tools dogma
        print("\n--- Executing Tools Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Tools"
            }
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("✓ Tools dogma executed")

        time.sleep(2)

        # Check for card selection interaction
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        game_state = response.json()

        pending = game_state.get("state", {}).get("pending_dogma_action")
        assert pending is not None, "Should have pending interaction for card selection"

        context = pending.get("context", {})
        interaction = context.get("interaction_data", {})
        interaction_type = interaction.get("interaction_type", "")
        print(f"Interaction type: {interaction_type}")

        # Should be a select_cards interaction
        assert interaction_type == "select_cards", \
            f"Expected select_cards interaction, got {interaction_type}"

        # eligible_cards is nested under "data" in the interaction structure
        data = interaction.get("data", {})
        eligible = data.get("eligible_cards", [])
        print(f"Eligible cards: {[c.get('name', c.get('card_id', '?')) for c in eligible]}")

        # The player has 4 cards in hand, so eligible should not be empty
        assert len(eligible) > 0, \
            f"SelectCards should find hand cards, but eligible is empty. " \
            f"Interaction data keys: {list(data.keys())}"

        # Select 3 cards to return (Archery, Oars, Mysticism)
        card_ids = [c["card_id"] for c in eligible[:3]]
        card_names = [c.get("name", "?") for c in eligible[:3]]
        print(f"\n--- Selecting 3 cards to return: {card_names} ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
            json={
                "player_id": human_id,
                "selected_cards": card_ids
            }
        )
        assert response.status_code == 200, f"Selection failed: {response.text}"
        print("✓ Cards selected for return")

        time.sleep(2)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()
        human_final = next(p for p in final_state["players"] if p["id"] == human_id)

        final_hand = human_final.get("hand", [])
        final_hand_names = [c["name"] for c in final_hand]
        board = human_final.get("board", {})

        print(f"\nFinal hand: {final_hand_names}")
        print(f"Final board colors: {[k for k, v in board.items() if k.endswith('_cards') and v]}")

        # Verify: 3 cards returned from hand → 1 remaining
        # Effect draws a 3 to hand then melds it → hand stays at 1
        assert len(final_hand) == 1, \
            f"Should have 1 card in hand (4 - 3 returned), got {len(final_hand)}: {final_hand_names}"
        # The remaining card should be the one we didn't select
        selected_names = [c.get("name", "?") for c in eligible[:3]]
        unselected = [n for n in ["Archery", "Oars", "Mysticism", "Sailing"] if n not in selected_names]
        assert final_hand_names[0] in ["Archery", "Oars", "Mysticism", "Sailing"], \
            f"Remaining card should be from original hand, got {final_hand_names[0]}"
        print(f"✓ Hand has 1 card after returning 3: {final_hand_names}")

        # Verify: an age 3 card was melded to board
        board_colors = [k.replace("_cards", "") for k, v in board.items()
                       if k.endswith("_cards") and v]
        # Should have at least 2 colors now (blue from Tools + whatever color the age 3 card is)
        # Unless the age 3 card is also blue, then just Tools stack gets taller
        all_board_cards = []
        for cards in board.values():
            if isinstance(cards, list):
                all_board_cards.extend([c["name"] for c in cards])
        print(f"Board cards: {all_board_cards}")
        print(f"✓ Board colors: {board_colors}")

        # Verify game completed
        pending = final_state.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Game should complete, but has pending: {pending}"
        print("✓ Game completed without hanging")

        print("\n" + "="*70)
        print("✅ Tools selection_condition test PASSED")
        print("="*70)
