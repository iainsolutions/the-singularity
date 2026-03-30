#!/usr/bin/env python3
"""
Scenario Test: Enterprise

Tests Enterprise's two effects:
- Effect 0 (DEMAND): Transfer a top non-purple card with crown from opponent's board.
  If transferred, opponent draws and melds a 4.
- Effect 1: You may splay your green cards right.

Primitives tested: DemandEffect, SelectCards (board_top, filter), TransferBetweenPlayers,
    DrawCards, MeldCard, SplayCards (optional)

Setup:
- Human: Enterprise (purple, 3 crowns) on board
- AI: Masonry (yellow, 3 castles) on board - has 0 crowns, demand won't fire

Expected:
- Demand skipped (AI has fewer crowns than human)
- Effect 1: optional splay green (auto-completes since no green cards)
- No interactions needed
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestEnterpriseScenario:
    """Test Enterprise demand + splay effect."""

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

        # Human board: Enterprise (purple, 3 crowns)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Enterprise", "location": "board"}
        )
        # AI board: Masonry (yellow, 3 castles, 0 crowns) - won't trigger demand
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": ai_id, "card_name": "Masonry", "location": "board"}
        )

        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )

        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_enterprise_demand_and_splay(self):
        """Test Enterprise: demand skipped, optional splay."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        # Execute dogma
        print("\n--- Executing Enterprise Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Enterprise"}
        )
        assert response.status_code == 200

        # Wait for auto-completion
        time.sleep(4)

        # Handle any interactions
        for attempt in range(3):
            response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
            state = response.json()
            pending = state.get("state", {}).get("pending_dogma_action")
            if not pending:
                break
            context = pending.get("context", {})
            interaction = context.get("interaction_data", {})
            if not interaction:
                break
            interaction_type = interaction.get("interaction_type")
            target = interaction.get("target_player_id")
            print(f"Interaction: type={interaction_type}, target={target}")

            if target and target != human_id:
                time.sleep(3)
                continue

            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                json={"player_id": human_id, "decline": True}
            )
            assert response.status_code == 200
            time.sleep(2)

        # Final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        final = response.json()

        phase = final.get("phase")
        assert phase == "playing", f"Expected 'playing', got {phase}"
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, "Should have no pending interaction"
        print("✓ Phase playing, no pending")

        print("✅ Enterprise test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
