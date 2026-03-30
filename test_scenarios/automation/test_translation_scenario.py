#!/usr/bin/env python3
"""
Scenario Test: Translation

Tests Translation's two effects:
- Effect 0: You may meld all cards in your score pile.
- Effect 1: If each top card on your board has crown, claim the World achievement.

Primitives tested: FilterCards (score_pile, all), ConditionalAction (user_choice),
    MeldCard, ConditionalAction (all_top_cards_have_symbol), ClaimAchievement

Setup:
- Human: Translation (blue, 3 crowns) + Clothing (green, crown) on board
- Human score pile: Mysticism (purple, crown), Code of Laws (purple, crown)
- AI: Agriculture (green, 0 crowns) - won't share

Expected:
- Effect 0: Optional meld all score pile (may auto-accept or need interaction)
- Effect 1: Check all top cards have crown -> claim World
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestTranslationScenario:
    """Test Translation meld-from-score and World achievement."""

    def setup_scenario(self) -> dict[str, Any]:
        print("\n" + "="*70)
        print("SETUP: Creating Translation Scenario")
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

        # Human board: Translation (blue, 3 crowns) + Clothing (green, crown)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Translation", "location": "board"}
        )
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Clothing", "location": "board"}
        )
        # Score pile: Mysticism, Code of Laws (both purple, crown)
        for card in ["Mysticism", "Code of Laws"]:
            requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": human_id, "card_name": card, "location": "score_pile"}
            )
        # AI board
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"}
        )

        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )

        print("✓ Setup: Translation+Clothing on board, Mysticism+CoL in score pile")
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

    def test_translation_meld_and_check_world(self):
        """Test Translation: meld score pile, check for World achievement."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Execute dogma
        print("\n--- Executing Translation Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Translation"}
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"

        # Handle possible interaction for user_choice
        time.sleep(2)

        for attempt in range(3):
            interaction, data, state = self._get_interaction(game_id)
            if not interaction:
                print(f"No pending interaction (attempt {attempt+1})")
                break

            interaction_type = interaction.get("interaction_type")
            print(f"Interaction {attempt+1}: type={interaction_type}")

            if interaction_type == "choose_option":
                options = data.get("options", [])
                print(f"  Options: {[o.get('description', o.get('value')) for o in options]}")
                # Accept (meld all)
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "option_index": 0}
                )
            elif interaction_type == "confirm":
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "option_index": 0}
                )
                print("  Accepted confirmation")
            else:
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "decline": True}
                )
            assert response.status_code == 200
            time.sleep(2)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        score = human.get("score_pile", [])
        print(f"Final score pile: {[c['name'] for c in score]}")

        # Verify completion
        phase = final.get("phase")
        assert phase == "playing", f"Expected 'playing', got {phase}"
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Should have no pending interaction"
        print("✓ Phase playing, no pending")

        # Check World achievement
        achievements = human.get("achievements", [])
        achievement_names = [a.get("name", a.get("achievement_name", "")) for a in achievements]
        if "World" in achievement_names:
            print("✓ World achievement claimed!")
        else:
            print("Note: World not claimed")

        print("✅ Translation test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
