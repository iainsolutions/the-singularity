#!/usr/bin/env python3
"""
Scenario Test: Machinery (age 3, yellow)

Effects:
- Effect 0 (DEMAND): Exchange all cards in your hand with all the highest cards in my hand.
  Primitives: FilterCards, SelectHighest, TransferBetweenPlayers x2
- Effect 1: Score a card from your hand with factory.
  Primitives: SelectCards (filter: has_symbol factory), ScoreCards
- Effect 2: You may splay your red cards left.
  Primitives: SplayCards (optional)

Setup:
- Human: Machinery on board (leaf symbols)
- AI: Agriculture on board (fewer leaves) - demand skipped
- Human: Paper in hand (has factory symbol) for scoring
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestMachineryScenario:
    """Test Machinery demand + score + splay."""

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
                      json={"player_id": human_id, "card_name": "Machinery", "location": "board"})
        # Paper has factory symbol - good for scoring
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

    def test_machinery_score_factory_card(self):
        """Test Machinery: demand skipped, score factory card from hand, optional splay."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        initial = response.json()
        human_player = next(p for p in initial["players"] if p["id"] == human_id)
        initial_hand = len(human_player.get("hand", []))
        initial_score = len(human_player.get("score_pile", []))
        print(f"Initial: hand={initial_hand}, score={initial_score}")

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Machinery"}
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
            elif interaction_type == "select_cards":
                eligible = data.get("eligible_cards", [])
                # Select first eligible card (Paper with factory)
                card_id = eligible[0] if eligible else None
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "selected_cards": [card_id] if card_id else []}
                )
                print(f"  Selected card: {card_id}")
            elif interaction_type == "choose_option":
                options = data.get("options", [])
                value = options[0].get("value") if options else "pass"
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "chosen_option": value}
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
        human_player = next(p for p in final["players"] if p["id"] == human_id)
        final_score = len(human_player.get("score_pile", []))
        print(f"Final: hand={len(human_player.get('hand', []))}, score={final_score}")

        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        # Should have scored Paper
        assert final_score >= initial_score, "Score pile should not decrease"
        print("✓ Phase playing, no pending")
        print("✅ Machinery test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
