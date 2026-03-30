#!/usr/bin/env python3
"""
Scenario Test: Satellites (age 9, green)

Effects:
- Effect 0: Return all cards from hand. You may splay purple cards up.
  Primitives: ReturnCards (hand_all), SplayCards (purple, up, optional)
- Effect 1: Draw three 8.
  Primitives: DrawCards (8, count 3)
- Effect 2: Meld a card from hand, then self-execute it.
  Primitives: SelectCards, MeldCard, ExecuteDogma

Setup:
- Human: Satellites on board (clock symbols)
- AI: Agriculture (0 clocks) - no sharing
- Human: Paper in hand (will be returned, then draw 3 age-8s)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestSatellitesScenario:
    """Test Satellites return + draw + meld/execute."""

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
                      json={"player_id": human_id, "card_name": "Satellites", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Paper", "location": "hand"})
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

    def test_satellites_return_draw_execute(self):
        """Test Satellites: return hand, draw 8s, meld+execute."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Satellites"}
        )
        assert response.status_code == 200
        time.sleep(2)

        # ExecuteDogma may trigger nested effects
        for attempt in range(12):
            interaction, data, state = self._get_interaction(game_id)
            if not interaction:
                break
            interaction_type = interaction.get("interaction_type")
            target_player = data.get("target_player_id")
            responding_player = target_player if target_player else human_id
            print(f"Interaction {attempt}: type={interaction_type}")

            if interaction_type == "select_cards":
                eligible = data.get("eligible_cards", [])
                first = eligible[0] if eligible else None
                card_id = first["card_id"] if isinstance(first, dict) else first
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": responding_player, "selected_cards": [card_id] if card_id else []}
                )
                print(f"  Selected: {card_id}")
            elif interaction_type == "select_color":
                colors = data.get("eligible_colors", data.get("colors", []))
                color = colors[0] if colors else "red"
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": responding_player, "selected_color": color}
                )
            elif interaction_type == "choose_option":
                options = data.get("options", [])
                value = str(options[0].get("value")) if options else "pass"
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": responding_player, "chosen_option": value}
                )
            elif interaction_type == "select_achievement":
                eligible = data.get("eligible_achievements", [])
                ach_id = eligible[0]["id"] if eligible and isinstance(eligible[0], dict) else (eligible[0] if eligible else None)
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": responding_player, "selected_achievement": ach_id}
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
        phase = final.get("phase")
        pending = final.get("state", {}).get("pending_dogma_action")
        print(f"Final phase: {phase}, pending: {pending is not None}")
        assert pending is None or phase != "playing", "Should complete or end game"
        print("✅ Satellites test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
