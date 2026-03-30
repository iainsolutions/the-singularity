#!/usr/bin/env python3
"""
Scenario Test: Optics

Tests Optics' conditional flow with has_symbol on last_drawn card.

Expected Flow:
1. Execute Optics dogma
2. Draw and meld age 3 card (random)
3. ConditionalAction: has_symbol(crown, source=last_drawn)
   - If_true: Draw age 4 + score it (auto-complete)
   - If_false: SelectCards from score_pile + TransferBetweenPlayers (interaction or auto-complete)

Setup:
- Human: Optics on red board (3 crowns), Construction in score pile
- AI: Agriculture on yellow board (0 crowns, won't share)

Expected Results:
- Age 3 card drawn and melded on board
- If_true branch: score pile grows by 1 (age 4 card scored)
- If_false branch: score pile shrinks by 1 (Construction transferred) or unchanged (no valid opponent)
- No pending interaction after completion
- Phase still "playing"
- Action log contains Optics
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"

class TestOpticsScenario:
    """Test Optics scenario."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Optics scenario."""
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
        # Human board: Optics (red, 3 crowns)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Optics",
                "location": "board",
                "color": "red"
            }
        )
        assert response.status_code == 200

        # Human score pile: Construction (for if_false branch transfer)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Construction",
                "location": "score_pile"
            }
        )
        assert response.status_code == 200

        # AI board: Agriculture (0 crowns, won't share)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Agriculture",
                "location": "board",
                "color": "yellow"
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

    def test_optics_complete(self):
        """Test complete Optics flow (handles both conditional branches)."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()
        human_player = next(p for p in initial_state["players"] if p["id"] == human_id)
        initial_score_count = len(human_player["score_pile"])
        initial_board_cards = sum(len(stack) for stack in human_player["board"].values())

        # Execute Optics dogma
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Optics"
            }
        )
        assert response.status_code == 200

        # Poll for interaction (if if_false branch: select card from score pile)
        interaction_found = False
        construction_id = None
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

            # Found interaction - get Construction card ID
            if interaction_data and interaction_data.get("interaction_type") == "select_cards":
                print(f"✓ Interaction found after {(attempt + 1) * 0.5}s (if_false branch)")
                interaction_found = True
                # Get Construction card ID from eligible cards
                human_player = next(p for p in state["players"] if p["id"] == human_id)
                construction_card = next(
                    (c for c in human_player["score_pile"] if c["name"] == "Construction"),
                    None
                )
                if construction_card:
                    construction_id = construction_card["card_id"]
                break

            # Dogma completed without interaction
            if not pending_dogma:
                print(f"✓ Dogma completed after {(attempt + 1) * 0.5}s (if_true branch or auto-complete)")
                break

            if attempt % 6 == 0:
                print(f"  Waiting... (attempt {attempt+1}, pending={bool(pending_dogma)})")
        else:
            print(f"⚠ Warning: Timeout after 15s")

        # If interaction found, respond to it
        if interaction_found and construction_id:
            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                json={
                    "player_id": human_id,
                    "selected_cards": [construction_id]
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
        final_board_cards = sum(len(stack) for stack in human_player["board"].values())

        # ASSERTIONS
        # 1. Age 3 card was drawn and melded (board increased by 1)
        assert final_board_cards == initial_board_cards + 1, (
            f"Expected board to have {initial_board_cards + 1} cards (melded age 3), "
            f"but got {final_board_cards}"
        )

        # 2. Score pile changed based on branch
        # If_true: score pile +1 (scored age 4)
        # If_false: score pile -1 (transferred Construction) or 0 (no valid opponent)
        score_delta = final_score_count - initial_score_count
        assert score_delta in [-1, 0, 1], (
            f"Expected score pile delta in [-1, 0, 1] (depending on branch), got {score_delta}"
        )

        # Determine which branch executed
        if score_delta == 1:
            branch = "if_true"
            print("  - Branch: if_true (drawn age 3 card has crown)")
            # Verify age 4 card in score pile
            score_ages = [c["age"] for c in human_player["score_pile"]]
            assert 4 in score_ages, f"Expected age 4 card in score pile, got ages {score_ages}"
        else:
            branch = "if_false"
            print(f"  - Branch: if_false (drawn age 3 card has no crown, delta={score_delta})")
            # Verify Construction transferred or still present
            construction_in_score = any(c["name"] == "Construction" for c in human_player["score_pile"])
            if score_delta == -1:
                assert not construction_in_score, "Expected Construction to be transferred from score pile"
            elif score_delta == 0:
                assert construction_in_score, "Expected Construction to remain in score pile (no valid transfer)"

        # 3. No pending interaction
        pending_dogma = final_state.get("state", {}).get("pending_dogma_action")
        assert pending_dogma is None, "Expected no pending dogma action"

        # 4. Phase should still be 'playing'
        assert final_state["phase"] == "playing", (
            f"Expected phase 'playing', got '{final_state['phase']}'"
        )

        # 5. Optics should be in action log
        action_log = final_state.get("action_log", [])
        optics_actions = [
            log for log in action_log
            if "Optics" in log.get("description", "") or "Optics" in log.get("message", "")
        ]
        assert len(optics_actions) > 0, "Expected Optics in action log"

        print(f"Game ID: {game_id}")
        print("✅ ALL ASSERTIONS PASSED")
        print(f"  - Drew and melded age 3 card")
        print(f"  - Conditional has_symbol(crown, last_drawn) executed: {branch}")
        if branch == "if_true":
            print(f"  - Drew and scored age 4 card")
        else:
            print(f"  - SelectCards + TransferBetweenPlayers (score delta: {score_delta})")
        print(f"  - Primitives tested: ConditionalAction with has_symbol on last_drawn")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
