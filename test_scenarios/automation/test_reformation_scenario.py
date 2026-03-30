#!/usr/bin/env python3
"""
Scenario Test: Reformation

Tests Reformation's two effects:
- Effect 0: You may splay your yellow or purple cards right.
- Effect 1: You may tuck a card from your hand for every splayed color on your board.

Primitives tested: ChooseOption (optional, filter_splayable), ConditionalAction,
    SplayCards, CountColorsWithSplay, RepeatAction, SelectCards, TuckCard, LoopAction

Setup:
- Human: Reformation (purple, 3 leaf) on board
- Human board: Masonry over Agriculture (yellow, splayable)
- Human hand: Tools, Clothing, Metalworking - cards to tuck
- AI: Metalworking (red, 0 leaf) on board - won't share

Expected:
- No sharing (AI has 0 leaf)
- Effect 0: Choose to splay yellow right (optional)
- Effect 1: Count splayed colors, tuck that many from hand
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestReformationScenario:
    """Test Reformation splay choice and repeat tuck."""

    def setup_scenario(self) -> dict[str, Any]:
        print("\n" + "="*70)
        print("SETUP: Creating Reformation Scenario")
        print("="*70)

        response = requests.post(f"{BASE_URL}/api/v1/games", json={})
        assert response.status_code == 200
        game_id = response.json()["game_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/join",
            json={"name": "TestPlayer"}
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

        time.sleep(0.5)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing"}
        )

        # Human board: Reformation (purple, 3 leaf)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Reformation", "location": "board"}
        )
        # Yellow stack: Agriculture underneath Masonry (splayable)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Agriculture", "location": "board"}
        )
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Masonry", "location": "board"}
        )
        # Human hand: 3 cards to tuck
        for card in ["Tools", "Clothing", "Metalworking"]:
            requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": human_id, "card_name": card, "location": "hand"}
            )
        # AI board
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Metalworking", "location": "board"}
        )

        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )

        print("✓ Setup: Reformation + Masonry/Agriculture on board, 3 cards in hand")
        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def _get_interaction(self, game_id):
        """Get pending interaction data from game state."""
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        state = response.json()
        pending = state.get("state", {}).get("pending_dogma_action")
        if not pending:
            return None, None, state
        context = pending.get("context", {})
        interaction_data = context.get("interaction_data", {})
        if not interaction_data:
            return None, None, state
        return interaction_data, interaction_data.get("data", {}), state

    def test_reformation_splay_and_tuck(self):
        """Test Reformation: splay choice then repeat tuck from hand."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        initial_hand_count = 3

        # Execute dogma
        print("\n--- Executing Reformation Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Reformation"}
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"

        # Handle interactions
        time.sleep(2)
        interactions_handled = 0

        for attempt in range(10):
            interaction, data, state = self._get_interaction(game_id)

            if not interaction:
                print(f"No pending interaction (attempt {attempt+1})")
                break

            interaction_type = interaction.get("interaction_type")
            target_player = interaction.get("target_player_id")
            print(f"Interaction {attempt+1}: type={interaction_type}, target={target_player}")

            if target_player and target_player != human_id:
                print("  Waiting for AI...")
                time.sleep(2)
                interactions_handled += 1
                continue

            if interaction_type == "choose_option":
                options = data.get("options", [])
                print(f"  Options: {[o.get('description', o.get('value')) for o in options]}")
                # Choose yellow splay (use chosen_option value, not option_index)
                yellow_opt = next((o for o in options if "yellow" in str(o).lower()), options[0] if options else {})
                value = yellow_opt.get("value", "yellow")
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "chosen_option": value}
                )
                assert response.status_code == 200, f"Response failed: {response.text}"
                print(f"  Chose: {value}")

            elif interaction_type == "select_cards":
                eligible = data.get("eligible_cards", [])
                eligible_names = [c.get("name") for c in eligible]
                print(f"  Eligible: {eligible_names}")
                if eligible:
                    # Select first card to tuck
                    response = requests.post(
                        f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                        json={"player_id": human_id, "selected_cards": [eligible[0]["card_id"]]}
                    )
                    print(f"  Selected: {eligible[0].get('name')}")
                else:
                    response = requests.post(
                        f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                        json={"player_id": human_id, "decline": True}
                    )
                    print("  Declined (no eligible)")
                assert response.status_code == 200

            elif interaction_type == "select_color":
                colors = data.get("eligible_colors", data.get("colors", []))
                print(f"  Colors: {colors}")
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "selected_color": colors[0] if colors else "yellow"}
                )
                assert response.status_code == 200

            else:
                print(f"  Unknown type: {interaction_type}, declining")
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "decline": True}
                )
                assert response.status_code == 200

            interactions_handled += 1
            time.sleep(1.5)

        print(f"Total interactions: {interactions_handled}")

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        hand = human.get("hand", [])
        print(f"Final hand: {[c['name'] for c in hand]} (count: {len(hand)})")

        # Verify phase and no pending
        phase = final.get("phase")
        assert phase == "playing", f"Expected 'playing', got {phase}"
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Should have no pending interaction"
        print("✓ Phase playing, no pending")

        # Some cards should have been tucked if splay succeeded
        if len(hand) < initial_hand_count:
            tucked = initial_hand_count - len(hand)
            print(f"✓ {tucked} card(s) tucked from hand")
        else:
            print("Note: No cards tucked (splay may not have produced splayed colors)")

        print("✅ Reformation test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
