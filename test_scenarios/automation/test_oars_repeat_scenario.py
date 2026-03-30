#!/usr/bin/env python3
"""
Scenario Test: Oars Repeat Demand

Tests Oars dogma with repeat_on_compliance=true to ensure the demand
loops until the opponent has no more crown cards in their hand.

Based on: /Users/iainknight/Git/Innovation/backend/data/BaseCards.json (Oars card)

Expected Flow:
1. Effect 0 (Demand with repeat): AI is vulnerable (0 < 2 castles)
   - Iteration 1: AI transfers crown card to human score pile, AI draws 1 (replaces card)
   - Demand checks: AI still has crown cards → REPEAT
   - Iteration 2: AI transfers crown card to human score pile, AI draws 1 (replaces card)
   - Demand checks: AI still has crown cards → REPEAT
   - Iteration 3: AI transfers crown card to human score pile, AI draws 1 (replaces card)
   - Demand checks: AI still has crown cards → REPEAT
   - Iteration 4: AI transfers crown card to human score pile, AI draws 1 (replaces card)
   - Demand checks: AI has NO crown cards → STOP
2. Effect 1: Draw and Meld a card from hand

Setup:
- Human: Oars (red) on board → 2 castles
- AI: 4 crown cards in hand (City States, Code of Laws, Sailing, Currency)
      + 3 non-crown cards (Archery, Mysticism, Road Building)
- Age 1 deck: ONLY non-crown cards (Agriculture, Pottery, etc.) - deterministic setup

Expected Results:
- 4 crown cards transferred from AI hand to human score pile
- AI drew 4 NON-CROWN cards (one after each transfer, replacing transferred cards)
  * Age 1 deck contains ONLY non-crown cards (deterministic test setup)
  * This ensures repeat stops after exactly 4 iterations
- AI hand size unchanged: 7 cards (transferred 4, drew 4)
- Demand repeated EXACTLY 4 times (stopped when AI had no crown cards left)
- Human hand unchanged during demand (no draws during compliance)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestOarsRepeatScenario:
    """Test Oars repeat_on_compliance mechanism."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Oars repeat scenario."""
        print("\n" + "="*70)
        print("SETUP: Creating Oars Repeat Scenario")
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

        # Set age 1 deck to contain ONLY non-crown cards
        # This ensures AI draws predictably replace transferred cards without adding more crowns
        non_crown_age1_cards = [
            "Agriculture", "Pottery", "The Wheel", "Masonry",
            "Tools", "Domestication", "Metalworking"
        ]
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-deck-order",
            json={
                "age": 1,
                "card_order": non_crown_age1_cards
            }
        )
        assert response.status_code == 200, f"Set deck order failed: {response.text}"
        print(f"✓ Age 1 deck set with {len(non_crown_age1_cards)} non-crown cards (deterministic)")

        # Enable tracing
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/tracing/start",
                json={"enabled": True}
            )
            print("✓ Tracing enabled")
        except Exception:
            print("⚠ Tracing not available")

        # Set up board: Human gets Oars on red stack (2 castles)
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
        print("✓ Oars added to human board (red) - 2 castles")

        # Give AI crown cards in hand (4 cards with crown symbol)
        crown_cards = ["City States", "Code of Laws", "Sailing", "Currency"]
        for card_name in crown_cards:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": ai_id,
                    "card_name": card_name,
                    "location": "hand"
                }
            )
            assert response.status_code == 200, f"Add {card_name} failed: {response.text}"
            print(f"✓ {card_name} added to AI hand (has crown)")

        # Give AI non-crown cards (3 cards without crown symbol)
        non_crown_cards = ["Archery", "Mysticism", "Road Building"]
        for card_name in non_crown_cards:
            response = requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={
                    "player_id": ai_id,
                    "card_name": card_name,
                    "location": "hand"
                }
            )
            assert response.status_code == 200, f"Add {card_name} failed: {response.text}"
            print(f"✓ {card_name} added to AI hand (no crown)")

        print(f"✓ AI has 7 cards total: 4 with crowns, 3 without")

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
        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def get_game_state(self, game_id: str) -> dict[str, Any]:
        """Get current game state."""
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        return response.json()

    def get_player(self, state: dict[str, Any], player_id: str) -> dict[str, Any]:
        """Get player from game state."""
        for player in state["players"]:
            if player["id"] == player_id:
                return player
        raise ValueError(f"Player {player_id} not found")

    def get_ai_interactions(self, game_id: str) -> list:
        """Get AI interaction history for this game."""
        response = requests.get(
            f"{BASE_URL}/api/v1/ai/interactions?limit=50&game_id={game_id}"
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("interactions", [])
        return []

    def get_execution_trace(self, game_id: str) -> list:
        """Get execution trace."""
        try:
            response = requests.get(
                f"{BASE_URL}/api/v1/games/{game_id}/tracing/list"
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception:
            return []

    def test_oars_repeat_complete(self):
        """
        Complete test of Oars repeat mechanism.
        Validates demand repeats until AI has no crown cards.
        """
        # Setup scenario
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]
        ai_id = scenario["ai_id"]

        print("\n" + "="*70)
        print("TEST: Oars Repeat Demand Mechanism")
        print("Game ID:", game_id)
        print("="*70)

        # Get initial state
        initial_state = self.get_game_state(game_id)
        initial_human = self.get_player(initial_state, human_id)
        initial_ai = self.get_player(initial_state, ai_id)

        print("\nInitial State:")
        print(f"  Human hand: {len(initial_human.get('hand', []))} cards")
        print(f"  Human score pile: {len(initial_human.get('score_pile', []))} cards")
        print(f"  AI hand: {len(initial_ai.get('hand', []))} cards")
        print(f"  AI score pile: {len(initial_ai.get('score_pile', []))} cards")

        # Activate Oars dogma
        print("\nActivating Oars dogma...")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Oars"}
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("✓ Oars dogma activated")

        # Wait for AI to respond to all demand iterations
        # Oars with repeat_on_compliance should iterate 4 times (once per crown card)
        print("\nWaiting for demand iterations to complete...")
        max_wait = 45
        waited = 0

        # Wait for all 4 AI interactions to complete
        # Each iteration: AI selects crown card -> transfer -> draw
        while waited < max_wait:
            time.sleep(1.0)
            waited += 1.0

            # Check AI interactions count
            ai_interactions = self.get_ai_interactions(game_id)
            select_cards_count = sum(
                1 for i in ai_interactions
                if i.get('metadata', {}).get('type') == 'select_cards'
            )

            # Also check if there's still a pending interaction
            state = self.get_game_state(game_id)
            pending = state.get('state', {}).get('pending_dogma_action')

            print(f"  Waiting... ({waited:.1f}s, AI select_cards: {select_cards_count}/4, pending: {bool(pending)})")

            # Done when we have 4 select_cards interactions and no pending
            if select_cards_count >= 4 and not pending:
                # Extra wait to ensure state is fully synced
                time.sleep(1.0)
                print(f"✓ Dogma completed after {waited + 1.0:.1f}s (4 iterations done)")
                break

            # Early exit if no pending and we have 3+ interactions but not increasing
            # (demand stopped due to no more crown cards)
            if not pending and select_cards_count >= 3:
                # Wait a bit more to see if 4th comes
                time.sleep(2.0)
                ai_interactions = self.get_ai_interactions(game_id)
                final_count = sum(
                    1 for i in ai_interactions
                    if i.get('metadata', {}).get('type') == 'select_cards'
                )
                if final_count == select_cards_count:
                    print(f"✓ Dogma appears complete after {waited + 2.0:.1f}s ({final_count} iterations)")
                    break

        # Get final state
        final_state = self.get_game_state(game_id)
        final_human = self.get_player(final_state, human_id)
        final_ai = self.get_player(final_state, ai_id)

        print("\nFinal State:")
        print(f"  Human hand: {len(final_human.get('hand', []))} cards")
        print(f"  Human score pile: {len(final_human.get('score_pile', []))} cards")
        print(f"  AI hand: {len(final_ai.get('hand', []))} cards")
        print(f"  AI score pile: {len(final_ai.get('score_pile', []))} cards")

        # Get AI interactions
        ai_interactions = self.get_ai_interactions(game_id)
        print(f"\nAI Interactions: {len(ai_interactions)} total")
        for i, interaction in enumerate(ai_interactions):
            interaction_type = interaction.get('metadata', {}).get('type', 'unknown')
            print(f"  {i+1}. {interaction_type}")

        # Get execution trace
        trace = self.get_execution_trace(game_id)
        print(f"\nExecution Trace: {len(trace)} entries")

        print("\n" + "="*70)
        print("ASSERTIONS")
        print("="*70)

        # === ASSERTION 1: Human score pile increased by 4 (received 4 crown cards) ===
        initial_human_score = len(initial_human.get('score_pile', []))
        final_human_score = len(final_human.get('score_pile', []))
        score_increase = final_human_score - initial_human_score
        print(f"\n1. Human score pile increased by 4 crown cards")
        print(f"   Initial: {initial_human_score}, Final: {final_human_score}, Increase: {score_increase}")
        assert score_increase == 4, f"Expected human score pile +4, got +{score_increase}"
        print("   ✓ PASS")

        # === ASSERTION 2: AI hand size UNCHANGED (transferred 4, drew 4) ===
        # Per corrected spec: OPPONENT draws after each transfer (replaces card)
        # So AI hand should stay at 7 cards throughout
        initial_ai_hand = len(initial_ai.get('hand', []))
        final_ai_hand = len(final_ai.get('hand', []))
        print(f"\n2. AI hand size unchanged (transferred 4, drew 4 replacements)")
        print(f"   Initial: {initial_ai_hand}, Final: {final_ai_hand}")
        assert final_ai_hand == initial_ai_hand, f"Expected AI hand to stay at {initial_ai_hand}, got {final_ai_hand}"
        print("   ✓ PASS")

        # === ASSERTION 3: Verify AI still has 7 cards (same as initial) ===
        print(f"\n3. AI hand verification (should be {initial_ai_hand} cards)")
        print(f"   Initial: {initial_ai_hand}, Final: {final_ai_hand}")
        assert final_ai_hand == 7, f"Expected AI hand to remain at 7, got {final_ai_hand}"
        print("   ✓ PASS")

        # === ASSERTION 4: AI had 4 select_cards interactions (one per repeat) ===
        select_cards_count = sum(
            1 for i in ai_interactions
            if i.get('metadata', {}).get('type') == 'select_cards'
        )
        print(f"\n4. AI had 4 select_cards interactions (demand repeated 4 times)")
        print(f"   Count: {select_cards_count}")
        assert select_cards_count == 4, f"Expected 4 select_cards interactions, got {select_cards_count}"
        print("   ✓ PASS")

        # === ASSERTION 4: Human hand UNCHANGED (no draws during compliance) ===
        initial_human_hand = len(initial_human.get('hand', []))
        final_human_hand = len(final_human.get('hand', []))
        # Effect 1: "Draw a 1 and meld a card from your hand"
        # So: +1 (draw) -1 (meld) = 0 net change from Effect 1
        # Per corrected spec: Human does NOT draw during compliance iterations
        # Total expected: 0 from demand + 0 from Effect 1 = 0
        human_hand_change = final_human_hand - initial_human_hand
        print(f"\n4. Human hand unchanged (no draws during compliance)")
        print(f"   Initial: {initial_human_hand}, Final: {final_human_hand}, Change: {human_hand_change}")
        assert human_hand_change == 0, f"Expected human hand unchanged (0), got {human_hand_change:+d}"
        print("   ✓ PASS")

        # === ASSERTION 5: AI has 7 cards (same as initial, composition changed) ===
        print(f"\n5. AI has 7 cards remaining in hand (drew 4 age-1 replacements)")
        print(f"   Remaining: {final_ai_hand}")
        assert final_ai_hand == 7, f"Expected AI to have 7 cards, has {final_ai_hand}"
        print("   ✓ PASS")

        # === ASSERTION 6: Demand completed (no longer pending) ===
        print(f"\n6. Demand completed (no pending interaction)")
        pending = final_state.get('pending_interaction')
        print(f"   Pending: {pending}")
        assert not pending, f"Expected no pending interaction, got {pending}"
        print("   ✓ PASS")

        print("\n" + "="*70)
        print("ALL ASSERTIONS PASSED! ✓")
        print("="*70)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
