#!/usr/bin/env python3
"""
Scenario Test: Feudalism (age 3, purple)

Effects:
- Effect 0 (DEMAND): Transfer a card with castle from opponent's hand to my hand.
  If done, junk all available special achievements.
- Effect 1: You may splay yellow or purple cards left. If you do, draw a 3.

Primitives: DemandEffect, SelectCards, ConditionalAction, TransferBetweenPlayers,
            FilterCards, ReturnCards, ChooseOption, SplayCards, DrawCards

Setup:
- Human: Feudalism on board (castle symbols)
- AI: Agriculture on board (0 castles) - demand skipped
- Human also has Clothing on board (yellow) for splay target
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestFeudalismScenario:
    """Test Feudalism demand + splay choice."""

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
        # Feudalism on board + Clothing for yellow splay target
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Feudalism", "location": "board"})
        requests.post(f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                      json={"player_id": human_id, "card_name": "Clothing", "location": "board"})
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

    def test_feudalism_demand_and_splay(self):
        """Test Feudalism: demand skipped (AI has fewer castles), splay choice."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Feudalism"}
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
                # AI interaction - auto-respond
                if interaction_type == "select_cards":
                    eligible = data.get("eligible_cards", [])
                    card_id = eligible[0] if eligible else None
                    response = requests.post(
                        f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                        json={"player_id": target_player, "selected_cards": [card_id] if card_id else []}
                    )
                else:
                    response = requests.post(
                        f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                        json={"player_id": target_player, "decline": True}
                    )
            elif interaction_type == "choose_option":
                options = data.get("options", [])
                # Choose yellow to splay
                value = "yellow"
                for opt in options:
                    if opt.get("value") == "yellow":
                        value = "yellow"
                        break
                else:
                    value = options[0].get("value") if options else "yellow"
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
            else:
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "decline": True}
                )

            assert response.status_code == 200
            time.sleep(2)

        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()
        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        print("✓ Phase playing, no pending")
        print("✅ Feudalism test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
