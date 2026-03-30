#!/usr/bin/env python3
"""
Scenario Test: Chemistry

Tests Chemistry's GetCardAge, CalculateValue, and ReturnCards primitives.

Expected Flow:
1. Execute Chemistry dogma
2. Effect 0: Optional splay blue right (only 1 blue card, auto-completes)
3. Effect 1: SelectHighest finds Chemistry(5) as highest top card
4. GetCardAge extracts age=5
5. CalculateValue: 5+1=6
6. Draw and score age 6 card
7. Human selects card from score pile to return
8. ReturnCards moves selected card to age deck

Setup:
- Human: Chemistry on blue board, Masonry on yellow board, Archery in score pile
- AI: Agriculture on green board (0 factory, won't share)

Expected Results:
- Effect 0: Auto-completes (can't splay 1 card)
- Effect 1: Draws age 6 card, scores it
- Human gets interaction to select from score pile
- Human returns Archery
- Final: Score pile has age 6 card, Archery returned to age 1 deck
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"

class TestChemistryScenario:
    """Test Chemistry scenario."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Chemistry scenario."""
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
        # Human board: Chemistry (blue), Masonry (yellow)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Chemistry",
                "location": "board",
                "color": "blue"
            }
        )
        assert response.status_code == 200

        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Masonry",
                "location": "board",
                "color": "yellow"
            }
        )
        assert response.status_code == 200

        # Human score pile: Archery (to return)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Archery",
                "location": "score_pile"
            }
        )
        assert response.status_code == 200

        # AI board: Agriculture (0 factory, won't share)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Agriculture",
                "location": "board",
                "color": "green"
            }
        )
        assert response.status_code == 200

        # SET GAME TO PLAYING STATE
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

    def test_chemistry_complete(self):
        """Test complete Chemistry flow."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()
        human_player = next(p for p in initial_state["players"] if p["id"] == human_id)
        initial_score_count = len(human_player["score_pile"])

        # Execute Chemistry dogma
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Chemistry"
            }
        )
        assert response.status_code == 200

        # Poll for interaction (select card from score pile to return)
        interaction_data = None
        archery_id = None
        for attempt in range(30):
            time.sleep(0.5)
            response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
            state = response.json()
            pending_dogma = state.get("state", {}).get("pending_dogma_action")
            interaction_data = (
                pending_dogma.get("context", {}).get("interaction_data", {})
                if pending_dogma
                else {}
            )

            # Found interaction - get Archery card ID
            if interaction_data and interaction_data.get("interaction_type") == "select_cards":
                print(f"✓ Interaction found after {(attempt + 1) * 0.5}s")
                # Get Archery card ID from eligible cards
                human_player = next(p for p in state["players"] if p["id"] == human_id)
                archery_card = next(c for c in human_player["score_pile"] if c["name"] == "Archery")
                archery_id = archery_card["card_id"]
                break

            # Dogma completed without interaction
            if not pending_dogma:
                print(f"✓ Dogma completed after {(attempt + 1) * 0.5}s (no interaction needed)")
                break

            if attempt % 6 == 0:
                print(f"  Waiting... (attempt {attempt+1}, pending={bool(pending_dogma)})")
        else:
            print(f"⚠ Warning: Timeout after 15s")

        # Respond to interaction - select Archery to return
        assert archery_id is not None, "Expected to find Archery card in score pile"
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
            json={
                "player_id": human_id,
                "selected_cards": [archery_id]
            }
        )
        assert response.status_code == 200

        # Wait for dogma completion
        for attempt in range(20):
            time.sleep(0.5)
            response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
            state = response.json()
            pending = state.get("state", {}).get("pending_dogma_action")
            if not pending:
                print(f"✓ Dogma completed after {(attempt + 1) * 0.5} seconds")
                break
        else:
            print("⚠ Warning: Dogma still pending after 10s")

        # Extra wait for state persistence
        time.sleep(0.5)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        # Get human player
        human_player = next(p for p in final_state["players"] if p["id"] == human_id)
        final_score_count = len(human_player["score_pile"])

        # ASSERTIONS
        # 1. Score pile count same (scored age 6 card, returned Archery)
        assert final_score_count == initial_score_count, (
            f"Expected score pile count to remain {initial_score_count} (scored 1, returned 1), "
            f"but got {final_score_count}"
        )

        # 2. Archery not in score pile anymore
        archery_in_score = any(c["name"] == "Archery" for c in human_player["score_pile"])
        assert not archery_in_score, "Expected Archery to be returned from score pile"

        # 3. Score pile should have age 6 card
        score_ages = [c["age"] for c in human_player["score_pile"]]
        assert 6 in score_ages, f"Expected age 6 card in score pile, got ages {score_ages}"

        # 4. Phase should still be 'playing'
        assert final_state["phase"] == "playing", (
            f"Expected phase 'playing', got '{final_state['phase']}'"
        )

        # 5. Chemistry should be in action log
        action_log = final_state.get("action_log", [])
        chemistry_actions = [
            log for log in action_log
            if "Chemistry" in log.get("description", "") or "Chemistry" in log.get("message", "")
        ]
        assert len(chemistry_actions) > 0, "Expected Chemistry in action log"

        print(f"Game ID: {game_id}")
        print("✅ ALL ASSERTIONS PASSED")
        print(f"  - Effect 0: Splay auto-completed (only 1 blue card)")
        print(f"  - Effect 1: GetCardAge extracted Chemistry age=5")
        print(f"  - CalculateValue computed 5+1=6")
        print(f"  - Drew and scored age 6 card")
        print(f"  - Human returned Archery from score pile")
        print(f"  - New primitives tested: GetCardAge, CalculateValue, ReturnCards")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
