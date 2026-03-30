#!/usr/bin/env python3
"""
Scenario Test: Engineering

Tests Engineering's demand with count="each_color" SelectCards:
- Effect 1 (demand): Transfer top card with castle of EACH color from
  opponent board to active score pile.
- Effect 2: You may splay your red cards left.

Primitives tested: DemandEffect, SelectCards (count="each_color", has_symbol filter),
TransferBetweenPlayers, SplayCards (optional)

Setup:
- Human: Engineering (red, 2 castles) + Paper (green, 0 castles) on board
  → Human has 2 castles total
- AI: Archery (red, 3 castles) + Masonry (yellow, 3 castles) on board
  → AI has 6 castles... too many. Need AI with fewer castles.
  Actually: Human has Engineering (2 castles). AI needs fewer.
  AI: Clothing (green, 0 castles) + Sailing (green, 0 castles) → 0 castles
  But AI needs castle cards on board TO transfer. Let's give AI cards with castle
  but fewer total castles than human.

Revised Setup:
- Human: Engineering (red, 2 castles) + Writing (blue, 0 castles) + Compass (green, 2 crowns)
  → 2 castles total
- AI: Domestication (yellow, 2 castles) → 2 castles (tie means no demand)
  Need AI with < 2 castles.
- AI: City States (purple, 1 castle) + Clothing (green, 0 castles) on board
  → 1 castle total. AI is vulnerable.
  City States has 1 castle → eligible for transfer (has castle).
  Clothing has 0 castles → not eligible.

Expected:
- Demand: AI's City States (has castle) gets transferred to human score
- Clothing stays (no castle)
- Effect 2: Optional splay red left (auto-complete since only human)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


class TestEngineeringScenario:
    """Test Engineering demand with count=each_color."""

    def setup_scenario(self) -> dict[str, Any]:
        print("\n" + "="*70)
        print("SETUP: Creating Engineering each_color Demand Scenario")
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

        # Human board: Engineering (red, 2 castles)
        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={"player_id": human_id, "card_name": "Engineering", "location": "board"}
        )
        print("✓ Human board: Engineering (red, 2 castles)")

        # AI board: City States (purple, 1 castle) + Clothing (green, 0 castles)
        for card in ["City States", "Clothing"]:
            requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": ai_id, "card_name": card, "location": "board"}
            )
        print("✓ AI board: City States (1 castle), Clothing (0 castles)")

        requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
        )
        print("✓ Setup complete")

        return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}

    def test_engineering_demand_each_color(self):
        """Test Engineering: transfer top cards with castle of each color."""
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]
        ai_id = scenario["ai_id"]

        print("\n--- Executing Engineering Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Engineering"}
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"

        # Wait for AI demand processing
        time.sleep(6)

        # Get final state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final = response.json()
        human = next(p for p in final["players"] if p["id"] == human_id)
        ai = next(p for p in final["players"] if p["id"] == ai_id)

        # Check human score pile
        score = human.get("score_pile", [])
        score_names = [c["name"] for c in score]
        print(f"Human score pile: {score_names}")

        # City States (has castle) should be transferred to human score
        assert "City States" in score_names, \
            f"City States (has castle) should be in human score, got {score_names}"
        print("✓ City States transferred to human score (has castle)")

        # Check AI board
        ai_board = ai.get("board", {})
        ai_cards = []
        for cards in ai_board.values():
            if isinstance(cards, list):
                ai_cards.extend([c["name"] for c in cards])
        print(f"AI board: {ai_cards}")

        # Clothing should remain (no castle)
        assert "Clothing" in ai_cards, \
            f"Clothing (no castle) should stay on AI board, got {ai_cards}"
        # City States should be gone
        assert "City States" not in ai_cards, \
            f"City States should have been transferred, still on board: {ai_cards}"
        print("✓ Clothing stayed (no castle), City States gone")

        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Game should complete"
        print("✅ Engineering test PASSED")
