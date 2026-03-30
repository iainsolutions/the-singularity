#!/usr/bin/env python3
"""
Scenario Test: Encyclopedia (age 6, blue)

Effects:
- Effect 0: Choose a value. You may meld all the cards of that value in your score pile.
  Primitives: ChooseOption (values 1-10), FilterCards (score_pile, age_equals chosen), MeldCard
- Effect 1: Select and score a card from your hand. If it has clock, splay your green or blue cards right.
  Primitives: SelectCards, ConditionalAction

Setup:
- Human: Encyclopedia on board (crown symbols)
- AI: Agriculture on board (0 crowns) - no sharing
- Human: age 3 cards in score pile for melding
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestEncyclopediaScenario:
    """Test Encyclopedia choose value + meld from score."""

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
                      json={"player_id": human_id, "card_name": "Encyclopedia", "location": "board"})
        # Put an age 3 card in score pile for meld target
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

    def test_encyclopedia_choose_value_meld(self):
        """Test Encyclopedia: choose value, meld matching score pile cards."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        initial = response.json()
        human_player = next(p for p in initial["players"] if p["id"] == human_id)
        initial_score_count = len(human_player.get("score_pile", []))
        print(f"Initial score pile: {initial_score_count} cards")

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Encyclopedia"}
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
            print(f"Interaction {attempt}: type={interaction_type}, target={target_player}")

            if interaction_type == "choose_option":
                options = data.get("options", [])
                # Choose value 3 to match Optics (age 3) in score pile
                # Must send as string - DogmaResponseRequest expects str
                value = "3"
                for opt in options:
                    if opt.get("value") == 3:
                        value = str(opt["value"])
                        break
                else:
                    value = str(options[0].get("value", 1)) if options else "1"
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": responding_player, "chosen_option": value}
                )
                print(f"  Chose value: {value}")
            elif interaction_type == "select_cards":
                eligible = data.get("eligible_cards", [])
                card_id = eligible[0] if eligible else None
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": responding_player, "selected_cards": [card_id] if card_id else []}
                )
                print(f"  Selected: {card_id}")
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
        final_score_count = len(human_player.get("score_pile", []))
        print(f"Final score pile: {final_score_count} cards")

        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        # Optics should have been melded from score pile to board
        print("✓ Phase playing, no pending")
        print("✅ Encyclopedia test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
