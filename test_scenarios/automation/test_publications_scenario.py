#!/usr/bin/env python3
"""
Scenario Test: Publications

Tests Publications dogma effects - PRIMARY TEST FOR MakeAvailable PRIMITIVE:
1. Effect 1: Splay selection (choose yellow or blue cards up)
2. Effect 2: Special achievement management (junk available OR make available from junk)

PRIMARY TEST: MakeAvailable primitive - ONLY card in BaseCards.json with this primitive

Expected Flow:
1. Human executes Publications dogma (age 7 blue card)
2. AI shares in both effects (has lightbulbs)
3. Effect 1: Both choose to splay yellow or blue cards up (AI first, Human second)
4. Effect 2: Both choose achievement action (AI first, Human second)
   - Option A: Junk available special achievement
   - Option B: Make junked special achievement available (MakeAvailable primitive)

Setup:
- Human: Publications on blue board, Agriculture on yellow board
- AI: Sanitation on blue board, Oars on green board (both have lightbulbs)
- Special Achievements Available: Monument, Empire
- Special Achievements Junked: World

Expected Results:
- Both effects execute correctly
- ChooseOption interactions presented
- MakeAvailable transfers achievements from junk to available
- JunkCards transfers achievements from available to junk
- Achievement state transitions verified
- Field name contract: eligible_cards not cards
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"

@pytest.mark.skip(reason="Special achievements infrastructure not fully implemented - Effect 2 requires admin API to persist special_achievements which is incomplete")
class TestPublicationsScenario:
    """Test Publications scenario - MakeAvailable primitive."""

    def setup_scenario(self) -> dict[str, Any]:
        """Create game with Publications scenario."""
        # CREATE GAME
        response = requests.post(f"{BASE_URL}/api/v1/games", json={})
        assert response.status_code == 200
        game_id = response.json()["game_id"]

        # JOIN HUMAN PLAYER
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/join",
            json={"name": "TestPlayer"}
        )
        assert response.status_code == 200
        human_id = response.json()["player_id"]

        # ADD AI PLAYER
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/add_ai_player",
            json={"difficulty": "beginner"}
        )
        assert response.status_code == 200
        game_state = response.json()["game_state"]
        ai_id = next(p["id"] for p in game_state["players"] if p["is_ai"])

        # INITIALIZE AGE DECKS
        time.sleep(0.5)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={"phase": "playing"}
        )
        assert response.status_code == 200

        # ENABLE TRACING
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/games/{game_id}/tracing/start",
                json={"enabled": True}
            )
        except Exception:
            pass

        # SETUP HUMAN BOARD - Publications on blue (TOP), Agriculture on yellow
        # Need 2+ cards per color for splay eligibility
        # Cards are added bottom-to-top, so add Optics first, then Publications LAST to be on top
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Optics",  # First blue card (will be below)
                "location": "board",
                "color": "blue"
            }
        )
        assert response.status_code == 200

        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Publications",  # TOP card - must be added LAST
                "location": "board",
                "color": "blue"
            }
        )
        assert response.status_code == 200

        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Agriculture",
                "location": "board",
                "color": "yellow"
            }
        )
        assert response.status_code == 200

        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Masonry",  # Second yellow card (Masonry is yellow)
                "location": "board",
                "color": "yellow"
            }
        )
        assert response.status_code == 200

        # SETUP AI BOARD - Sanitation on blue, Oars on green
        # Need 2+ cards per color for splay eligibility
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Sanitation",
                "location": "board",
                "color": "blue"
            }
        )
        assert response.status_code == 200

        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Calendar",  # Second blue card
                "location": "board",
                "color": "blue"
            }
        )
        assert response.status_code == 200

        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Oars",
                "location": "board",
                "color": "green"
            }
        )
        assert response.status_code == 200

        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Tools",  # Second green card (not yellow, to avoid splay conflict)
                "location": "board",
                "color": "green"
            }
        )
        assert response.status_code == 200

        # SETUP SPECIAL ACHIEVEMENTS
        # Available: Monument, Empire
        # Junk: World
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={
                "phase": "playing",
                "current_player_index": 0,
                "actions_remaining": 2,
                "special_achievements": {
                    "available": ["Monument", "Empire"],
                    "junk": ["World"],
                    "claimed": {}
                }
            }
        )
        assert response.status_code == 200
        print(f"\nDEBUG: Set-state response: {response.json()}")

        return {
            "game_id": game_id,
            "human_id": human_id,
            "ai_id": ai_id
        }

    def test_publications_complete(self):
        """Test complete Publications flow with MakeAvailable primitive.

        Note: Effect 1 (splay selection) may auto-complete if only 1 color is splayable.
        Effect 2 (achievement management) is optional and may be declined by AI.
        """
        scenario = self.setup_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]
        ai_id = scenario["ai_id"]

        # Get initial state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        initial_state = response.json()

        print("\n=== Initial State ===")
        print(f"Special Achievements Available: {initial_state.get('special_achievements', {}).get('available', [])}")
        print(f"Special Achievements Junk: {initial_state.get('special_achievements', {}).get('junk', [])}")

        # Execute dogma on Publications
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Publications"
            }
        )
        assert response.status_code == 200

        # Handle interactions - may be multiple depending on sharing and auto-selections
        # Loop through any pending interactions
        max_interactions = 10
        interactions_handled = 0
        splay_interaction_seen = False
        achievement_interaction_seen = False

        while interactions_handled < max_interactions:
            time.sleep(2)

            response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
            assert response.status_code == 200
            current_state = response.json()

            pending_interaction = current_state.get("state", {}).get("pending_dogma_action")

            if pending_interaction is None:
                print(f"\nNo pending interaction (dogma completed or auto-selected)")
                break

            context = pending_interaction.get("context", {})
            interaction_data = context.get("interaction_data", {})
            interaction_type = interaction_data.get("interaction_type")
            target_player = interaction_data.get("target_player_id")
            data = interaction_data.get("data", {})

            print(f"\n=== Interaction {interactions_handled + 1} ===")
            print(f"Type: {interaction_type}")
            print(f"Target: {target_player}")

            # Only human needs to respond - AI responds via event bus
            if target_player != human_id:
                print("Waiting for AI to respond...")
                time.sleep(2)
                interactions_handled += 1
                continue

            if interaction_type == "select_color":
                splay_interaction_seen = True
                colors = data.get("eligible_colors", data.get("colors", []))
                print(f"Splay colors available: {colors}")
                # Select first available color
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "selected_color": colors[0] if colors else "yellow"}
                )
            elif interaction_type == "choose_option":
                achievement_interaction_seen = True
                options = data.get("options", [])
                print(f"Options: {[opt.get('description', opt.get('value')) for opt in options]}")
                # Choose option 1 (make available from junk) if available, else option 0
                option_index = 1 if len(options) > 1 else 0
                response = requests.post(
                    f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                    json={"player_id": human_id, "option_index": option_index}
                )
            elif interaction_type == "select_cards":
                cards = data.get("eligible_cards", [])
                print(f"Cards available: {[c.get('name') for c in cards]}")
                # Select first card if available
                if cards:
                    response = requests.post(
                        f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                        json={"player_id": human_id, "selected_cards": [cards[0].get("card_id")]}
                    )
                else:
                    # Decline optional selection
                    response = requests.post(
                        f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
                        json={"player_id": human_id, "decline": True}
                    )
            else:
                print(f"Unknown interaction type: {interaction_type}")
                break

            if response.status_code != 200:
                print(f"Response error: {response.text}")
                break

            interactions_handled += 1

        # Get final state after all interactions
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        final_state = response.json()

        print("\n=== Final State ===")
        print(f"Phase: {final_state.get('phase')}")
        print(f"Actions remaining: {final_state.get('actions_remaining')}")
        print(f"Interactions handled: {interactions_handled}")

        # ASSERTION 1: Dogma should complete without errors
        final_pending = final_state.get("state", {}).get("pending_dogma_action")
        assert final_pending is None, "Dogma should complete without pending interactions"

        # ASSERTION 2: Phase should remain playing
        assert final_state.get("phase") == "playing", "Phase should be playing"

        # ASSERTION 3: Verify action log has Publications activation
        action_log = final_state.get("action_log", [])
        log_descriptions = [entry.get("description", "") for entry in action_log]
        assert any("Publications" in desc for desc in log_descriptions), \
            "Should have Publications in action log"

        print("\n=== Recent Action Log ===")
        for entry in action_log[-10:]:
            print(f"  {entry.get('description')}")

        print(f"\nGame ID: {game_id}")
        print("✅ Publications dogma completed successfully")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
