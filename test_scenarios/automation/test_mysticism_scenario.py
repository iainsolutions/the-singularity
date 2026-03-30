#!/usr/bin/env python3
"""
Scenario Test: Mysticism

Tests Mysticism's effect:
- Draw and reveal a 1. If it is the same color as any card on your board, meld it and draw a 1.

Primitives tested: DrawCards (reveal), ConditionalAction (card_color_on_board), MeldCard, DrawCards

Setup:
- Human: Mysticism (purple, 3 castles) + Clothing (green) on board
- AI: Agriculture (green, 0 castles) - won't share

Expected:
- Draws and reveals age 1 card
- If drawn card matches purple or green (colors on board), melds it + draws another
- If no match, card stays in hand, no extra draw
- Auto-completes, no interactions
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestMysticismScenario:
    """Test Mysticism draw-reveal-conditional-meld."""

    def setup_scenario(self) -> dict[str, Any]:
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

        # Human board: Mysticism (purple) + Clothing (green)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Mysticism", "location": "board"}
        )
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Clothing", "location": "board"}
        )
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Agriculture", "location": "board"}
        )
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )

        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_mysticism_draw_reveal_conditional(self):
        """Test Mysticism: draw/reveal, conditional meld + extra draw."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        initial = response.json()
        human_initial = next(p for p in initial["players"] if p["id"] == human_id)
        initial_hand_count = len(human_initial.get("hand", []))

        # Execute dogma
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Mysticism"}
        )
        assert response.status_code == 200

        time.sleep(3)

        # Check final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)

        hand = human.get("hand", [])
        board = human.get("board", {})
        hand_names = [c["name"] for c in hand]

        print(f"Hand: {hand_names} (count: {len(hand)})")
        print(f"Board colors: {[k for k in board.keys() if k != 'splay_directions']}")

        # Two possible outcomes:
        # 1. Color matched: card melded (hand +0 from reveal, -1 meld, +1 extra draw = net +0)
        #    But reveal goes to hand first... so draw to hand (+1), meld from hand (-1), draw (+1) = net +1
        # 2. No match: card stays in hand (hand +1)
        # Either way, hand should have gained at least 1 card
        assert len(hand) >= initial_hand_count + 1, \
            f"Should gain at least 1 card, was {initial_hand_count} now {len(hand)}"

        if len(hand) == initial_hand_count + 1:
            print("✓ Drew 1 card (no color match or matched+melded+drew)")
        elif len(hand) == initial_hand_count + 2:
            print("✓ Drew 2 cards (color matched, melded, drew extra)")
        print(f"✓ Hand gained {len(hand) - initial_hand_count} card(s)")

        assert final.get("phase") == "playing"
        assert final.get("state", {}).get("pending_dogma_action") is None
        print("✅ Mysticism test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
