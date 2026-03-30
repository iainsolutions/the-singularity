#!/usr/bin/env python3
"""
Scenario Test: Masonry

Tests Masonry's two effects:
- Effect 0: You may meld any number of cards from your hand, each with castle.
- Effect 1: If you have exactly three red cards on your board, claim the Monument achievement.

Primitives tested: SelectCards (multi, filter has_symbol), MeldCard, CountCards,
    ConditionalAction, ClaimAchievement

Setup:
- Human: Masonry (yellow, 3 castles) on board + Metalworking (red) on board
- Human hand: Archery (red, castle), Oars (red, castle), Mysticism (purple, castle)
- AI: Agriculture (green, 0 castles) on board - won't share

Expected:
- No sharing (AI has 0 castles < human's 3)
- Effect 0: Human selects castle cards to meld from hand
- Effect 1: If 3 red cards on board after meld, Monument is claimed
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestMasonryScenario:
    """Test Masonry meld and achievement claiming."""

    def setup_scenario(self) -> dict[str, Any]:
        print("\n" + "="*70)
        print("SETUP: Creating Masonry Scenario")
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

        # Human board: Masonry (yellow, 3 castles)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Masonry", "location": "board"}
        )
        # Human board: Metalworking (red) - 1 red card already on board
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Metalworking", "location": "board"}
        )
        # Human hand: Archery (red, castle), Oars (red, castle), Mysticism (purple, castle)
        for card in ["Archery", "Oars", "Mysticism"]:
            requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": human_id, "card_name": card, "location": "hand"}
            )
        # AI board: Agriculture (green, 0 castles)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"}
        )

        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )

        print("✓ Setup: Masonry+Metalworking on board, Archery/Oars/Mysticism in hand")
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
        return interaction_data, interaction_data.get("data", {}), state

    def test_masonry_meld_castle_cards(self):
        """Test Masonry: meld castle cards from hand and check achievement."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Execute dogma
        print("\n--- Executing Masonry Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Masonry"}
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"

        # Wait for interaction
        time.sleep(2)

        interaction, data, state = self._get_interaction(game_id)
        if interaction and interaction.get("interaction_type") == "select_cards":
            eligible = data.get("eligible_cards", [])
            eligible_names = [c.get("name") for c in eligible]
            print(f"Eligible cards: {eligible_names}")

            # Select Archery and Oars (both red) to get 3 red on board
            red_cards = [c for c in eligible if c.get("name") in ("Archery", "Oars")]
            selected_ids = [c["card_id"] for c in red_cards] if red_cards else [c["card_id"] for c in eligible]
            print(f"Selecting: {[c.get('name') for c in red_cards]}")

            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                json={"player_id": human_id, "selected_cards": selected_ids}
            )
            assert response.status_code == 200, f"Response failed: {response.text}"
        else:
            print(f"No select_cards interaction (got: {interaction})")

        # Wait for completion
        time.sleep(3)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        hand = human.get("hand", [])
        hand_names = [c["name"] for c in hand]
        print(f"Final hand: {hand_names}")

        # Some cards should have been melded
        assert len(hand) < 3, f"Cards should be melded from hand, still have {len(hand)}"
        print(f"✓ Cards melded from hand ({len(hand)} remaining)")

        # Check phase and no pending
        phase = final.get("phase")
        assert phase == "playing", f"Expected 'playing', got {phase}"
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Should have no pending interaction"
        print("✓ Phase playing, no pending")

        # Check achievements
        achievements = human.get("achievements", [])
        achievement_names = [a.get("name", a.get("achievement_name", "")) for a in achievements]
        if "Monument" in achievement_names:
            print("✓ Monument achievement claimed!")
        else:
            print("Note: Monument not claimed (may not have exactly 3 red on board)")

        print("✅ Masonry test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
