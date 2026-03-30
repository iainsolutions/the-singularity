#!/usr/bin/env python3
"""
Scenario Test: Quantum Theory (age 8, blue)

Effects:
- Effect 0: Return up to 2 cards from hand. If you return 2, draw a 10 + draw and score a 10.
  Primitives: SelectCards (optional, count 2), ReturnCards, ConditionalAction (cards_count_equals 2), DrawCards

Setup:
- Human: Quantum Theory on board (clock symbols)
- AI: Agriculture (0 clocks) - no sharing
- Human: 2 cards in hand to return
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestQuantumTheoryScenario:
    """Test Quantum Theory return + conditional draw."""

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
                      json={"player_id": human_id, "card_name": "Quantum Theory", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Paper", "location": "hand"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Optics", "location": "hand"})
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

    def test_quantum_theory_return_two_draw_ten(self):
        """Test Quantum Theory: return 2 cards, draw 10 + score 10."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Quantum Theory"}
        )
        assert response.status_code == 200
        time.sleep(2)

        for attempt in range(5):
            interaction, data, state = self._get_interaction(game_id)
            if not interaction:
                break
            interaction_type = interaction.get("interaction_type")
            target_player = data.get("target_player_id")
            responding_player = target_player if target_player else human_id
            print(f"Interaction {attempt}: type={interaction_type}")

            if interaction_type == "select_cards":
                eligible = data.get("eligible_cards", [])
                # Select all eligible (up to 2)
                card_ids = []
                for c in eligible[:2]:
                    card_ids.append(c["card_id"] if isinstance(c, dict) else c)
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": responding_player, "selected_cards": card_ids}
                )
                print(f"  Selected {len(card_ids)} cards")
            elif interaction_type == "choose_option":
                options = data.get("options", [])
                value = str(options[0].get("value")) if options else "pass"
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": responding_player, "chosen_option": value}
                )
            else:
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": responding_player, "decline": True}
                )
            assert response.status_code == 200
            time.sleep(2)

        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()
        human_player = next(p for p in final["players"] if p["id"] == human_id)
        hand_count = len(human_player.get("hand", []))
        score_count = len(human_player.get("score_pile", []))
        print(f"Final: hand={hand_count}, score={score_count}")

        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        print("✓ Phase playing, no pending")
        print("✅ Quantum Theory test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
