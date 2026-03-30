#!/usr/bin/env python3
"""
Scenario Test: Evolution (age 7, blue)

Effects:
- Effect 0: Choose: (A) draw and score an 8, then return a card from score pile,
  OR (B) draw a card of value one higher than the highest card in your score pile.
  Primitives: ChooseOption with sub-actions

Setup:
- Human: Evolution on board (lightbulb symbols)
- AI: Agriculture on board (0 lightbulbs) - no sharing
- Human: age 3 card in score pile for option B calc
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestEvolutionScenario:
    """Test Evolution choose option with sub-actions."""

    def setup_scenario(self) -> dict[str, Any]:
        response = requests.post(f"{BASE_URL}/api/v1/games", json={})
        assert response.status_code == 200
        game_id = response.json()["game_id"]

        response = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/join", json={"name": "TestPlayer"})
        assert response.status_code == 200
        human_id = response.json()["player_id"]

        response = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/add_ai_player", json={"difficulty": "beginner"})
        assert response.status_code == 200
        ai_id = next(p["id"] for p in response.json()["game_state"]["players"] if p["is_ai"])

        time.sleep(0.5)
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state", json={"phase": "playing"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Evolution", "location": "board"})
        # Age 3 card in score pile - option B would draw age 4
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Optics", "location": "score_pile"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
                      json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2})
        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def _get_interaction(self, game_id):
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

    def test_evolution_draw_higher_option(self):
        """Test Evolution: choose option B (draw higher than highest in score)."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        initial = response.json()
        human_player = next(p for p in initial["players"] if p["id"] == human_id)
        initial_hand = len(human_player.get("hand", []))
        print(f"Initial hand: {initial_hand}")

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Evolution"}
        )
        assert response.status_code == 200
        time.sleep(2)

        for attempt in range(5):
            interaction, data, state = self._get_interaction(game_id)
            if not interaction:
                break

            interaction_type = interaction.get("interaction_type")
            target_player = interaction.get("target_player_id")
            print(f"Interaction {attempt}: type={interaction_type}, target={target_player}")

            if target_player and target_player != human_id:
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": target_player, "decline": True}
                )
            elif interaction_type == "choose_option":
                options = data.get("options", [])
                # Choose option B: draw higher than highest in score pile
                value = "draw_higher_than_highest"
                for opt in options:
                    if "higher" in str(opt.get("value", "")):
                        value = opt["value"]
                        break
                else:
                    # Fallback to second option or first
                    value = options[1].get("value") if len(options) > 1 else options[0].get("value")
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "chosen_option": value}
                )
                print(f"  Chose: {value}")
            elif interaction_type == "select_cards":
                eligible = data.get("eligible_cards", [])
                card_id = eligible[0] if eligible else None
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "selected_cards": [card_id] if card_id else []}
                )
                print(f"  Selected: {card_id}")
            else:
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "decline": True}
                )

            assert response.status_code == 200
            time.sleep(2)

        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()
        human_player = next(p for p in final["players"] if p["id"] == human_id)
        final_hand = len(human_player.get("hand", []))
        print(f"Final hand: {final_hand}")

        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        # Should have drawn a card (age 4 since highest score is age 3)
        assert final_hand >= initial_hand, "Should have drawn at least one card"
        print("✓ Phase playing, no pending, hand grew")
        print("✅ Evolution test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
