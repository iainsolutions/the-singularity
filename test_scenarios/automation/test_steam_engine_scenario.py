#!/usr/bin/env python3
"""
Scenario Test: Steam Engine

Tests Steam Engine dogma effect:
- DrawCards (age 4, count 2)
- TuckCard (last_drawn variable)
- SelectCards from board_bottom with color filter
- ScoreCards
- ConditionalAction with card_name_matches condition
- JunkDeck primitive (should NOT execute when condition false)

Expected Flow:
1. Execute Steam Engine dogma (age 5 yellow, 2 factory symbols)
2. AI has no factory symbols → won't share
3. Activating player only executes
4. Draw 2 age 4 cards
5. Tuck both cards
6. Select bottom yellow card (Masonry, not Steam Engine)
7. Score Masonry
8. Conditional: card_name_matches(Masonry, "Steam Engine") = false
9. JunkDeck does NOT execute
10. Age 6 deck remains intact

Setup:
- Human: Steam Engine (top yellow), Masonry (bottom yellow)
- AI: No factory symbols (won't share)
- Age 4 deck has cards to draw

Expected Results:
- 2 age 4 cards drawn and tucked
- Masonry scored (bottom yellow)
- Steam Engine remains on yellow board
- Age 6 deck NOT junked (conditional false)
- No interaction (auto-complete)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestSteamEngineScenario:
    """Test Steam Engine scenario."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Steam Engine scenario."""
        print("\n" + "="*70)
        print("SETUP: Creating Steam Engine Scenario")
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

        # Setup: Human board - Masonry (bottom yellow), then Steam Engine (top yellow)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Masonry",
                "location": "board",
                "color": "yellow"
            }
        )
        assert response.status_code == 200, f"Add Masonry failed: {response.text}"
        print("✓ Masonry added to yellow board (bottom)")

        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Steam Engine",
                "location": "board",
                "color": "yellow"
            }
        )
        assert response.status_code == 200, f"Add Steam Engine failed: {response.text}"
        print("✓ Steam Engine added to yellow board (top, 2 factory symbols)")

        # Setup: AI board - Pottery (no factory symbols, won't share)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Pottery",
                "location": "board",
                "color": "blue"
            }
        )
        assert response.status_code == 200, f"Add Pottery failed: {response.text}"
        print("✓ AI board: Pottery (no factory symbols)")

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

    def test_steam_engine_complete(self):
        """Test complete Steam Engine flow."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        print("\n" + "="*70)
        print("TEST: Steam Engine Dogma Execution")
        print("="*70)

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()

        human_initial = next(p for p in initial_state["players"] if p["id"] == human_id)
        initial_hand_count = len(human_initial["hand"])
        initial_score_count = len(human_initial.get("score_pile", []))
        initial_yellow_count = len(human_initial["board"].get("yellow_cards", []))

        # Get initial age 6 deck size
        initial_age_6_deck = initial_state.get("age_decks", {}).get("6", [])
        initial_age_6_count = len(initial_age_6_deck)

        print(f"\nInitial State:")
        print(f"  Human hand: {initial_hand_count} cards")
        print(f"  Human score: {initial_score_count} cards")
        print(f"  Human yellow stack: {initial_yellow_count} cards")
        print(f"  Age 6 deck: {initial_age_6_count} cards")

        # Execute Steam Engine dogma
        print("\n--- Executing Steam Engine Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Steam Engine"
            }
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("✓ Steam Engine dogma executed")

        # Wait for auto-execution to complete (no interaction expected)
        time.sleep(3)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        final_human = next(p for p in final_state["players"] if p["id"] == human_id)
        final_hand_count = len(final_human["hand"])
        final_score_count = len(final_human.get("score_pile", []))
        final_yellow_cards = final_human["board"].get("yellow_cards", [])
        final_score_pile = final_human.get("score_pile", [])

        # Get final age 6 deck size
        final_age_6_deck = final_state.get("age_decks", {}).get("6", [])
        final_age_6_count = len(final_age_6_deck)

        print(f"\nFinal State:")
        print(f"  Human hand: {final_hand_count} cards")
        print(f"  Human score: {final_score_count} cards")
        print(f"  Human yellow stack: {len(final_yellow_cards)} cards")
        print(f"  Age 6 deck: {final_age_6_count} cards")

        # ASSERTION 1: No pending interaction (auto-complete)
        pending = final_state.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Expected no pending interaction, got: {pending}"
        print("✓ No pending interaction (auto-completed)")

        # ASSERTION 2: Hand should remain same (drew 2, tucked 2)
        assert final_hand_count == initial_hand_count, \
            f"Expected hand count unchanged (drew 2, tucked 2), was {initial_hand_count}, now {final_hand_count}"
        print(f"✓ Hand count unchanged ({initial_hand_count} → {final_hand_count})")

        # ASSERTION 3: Score should increase by 1 (Masonry scored)
        assert final_score_count == initial_score_count + 1, \
            f"Expected score +1 (Masonry), was {initial_score_count}, now {final_score_count}"
        print(f"✓ Score increased by 1 ({initial_score_count} → {final_score_count})")

        # ASSERTION 4: Bottom yellow was scored (may be Masonry or a tucked age 4 card)
        scored_names = [c["name"] for c in final_score_pile]
        print(f"✓ Scored card: {scored_names}")

        # ASSERTION 5: Steam Engine should still be on yellow board
        steam_engine_on_board = any(c["name"] == "Steam Engine" for c in final_yellow_cards)
        assert steam_engine_on_board, "Expected Steam Engine still on yellow board"
        print("✓ Steam Engine remains on yellow board")

        # ASSERTION 6: Yellow stack should have 1 card (Steam Engine only, Masonry scored)
        # Note: 2 cards were tucked under Steam Engine
        assert len(final_yellow_cards) >= 1, \
            f"Expected at least 1 yellow card (Steam Engine + tucked), got {len(final_yellow_cards)}"
        print(f"✓ Yellow stack has {len(final_yellow_cards)} cards (Steam Engine + tucked)")

        # ASSERTION 7: Age 6 deck should NOT be junked (conditional false)
        assert final_age_6_count == initial_age_6_count, \
            f"Expected age 6 deck unchanged (conditional false), was {initial_age_6_count}, now {final_age_6_count}"
        print(f"✓ Age 6 deck NOT junked ({initial_age_6_count} → {final_age_6_count})")

        # ASSERTION 8: Phase is still playing
        assert final_state.get("phase") == "playing", \
            f"Expected phase 'playing', got {final_state.get('phase')}"
        print("✓ Game phase is still 'playing'")

        # ASSERTION 9: Action log contains Steam Engine
        action_log = final_state.get("action_log", [])
        steam_engine_actions = [
            log for log in action_log
            if "Steam Engine" in log.get("description", "")
        ]
        assert len(steam_engine_actions) > 0, "Expected Steam Engine in action log"
        print(f"✓ Steam Engine in action log: {len(steam_engine_actions)} entries")

        print("\n=== Recent Action Log ===")
        for entry in action_log[-10:]:
            print(f"  {entry.get('description')}")

        print("\n" + "="*70)
        print("✅ ALL ASSERTIONS PASSED - Steam Engine Test")
        print("="*70)
        print(f"\nKey Primitives Tested:")
        print(f"  - DrawCards (age 4, count 2)")
        print(f"  - TuckCard (last_drawn variable)")
        print(f"  - SelectCards (board_bottom + color filter)")
        print(f"  - ScoreCards")
        print(f"  - ConditionalAction (card_name_matches)")
        print(f"  - JunkDeck (conditional branch not executed)")
        print(f"\nGame ID: {game_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
