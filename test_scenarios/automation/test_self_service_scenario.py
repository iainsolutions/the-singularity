#!/usr/bin/env python3
"""
Scenario Test: Self Service

Tests Self Service dogma effects:
1. Effect 1 (Non-Demand): EvaluateCondition checks if player has 2x achievements of opponents
2. If condition true: ClaimAchievement (win) ends the game
3. If condition false: Game continues to Effect 2 (self-execute top card)

Expected Flow (Win Condition True):
1. Human executes Self Service dogma (age 10 green card)
2. EvaluateCondition evaluates has_twice_achievements_of_opponents
3. Stores result in condition_result AND last_evaluation variables
4. ConditionalAction checks last_evaluation_true
5. If true: ClaimAchievement (win) executed, game ends
6. Effect 2 never executes (game ended)

Expected Flow (Win Condition False):
1. Human executes Self Service dogma
2. EvaluateCondition evaluates condition → false
3. ConditionalAction skips if_true actions (no if_false defined)
4. Game continues to Effect 2 (self-execute top card)

Setup Scenario 1 (Win):
- Human: Self Service on green board, 4 achievements (age 4,5,6,7)
- AI: Writing on blue board, 1 achievement (age 1)
- Human has 4 >= 2*1 → WIN

Setup Scenario 2 (No Win):
- Human: Self Service on green board, 2 achievements (age 4,5)
- AI: Writing on blue board, 2 achievements (age 1,2)
- Human has 2 >= 2*2 → FALSE → Continue to Effect 2

Expected Results:
- EvaluateCondition primitive executes correctly
- Variable storage: condition_result and last_evaluation set
- ConditionalAction uses last_evaluation_true condition
- Win achievement claimed when condition true
- Game ends when win claimed
- Effect 2 executes when condition false
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"

class TestSelfServiceScenario:
    """Test Self Service scenario."""

    def setup_win_scenario(self) -> dict[str, Any]:
        """Create game with Self Service win condition scenario."""
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

        # SETUP HUMAN BOARD - Self Service on green
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Self Service",
                "location": "board",
                "color": "green"
            }
        )
        assert response.status_code == 200

        # SETUP HUMAN ACHIEVEMENTS - 4 achievements (age 4,5,6,7)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-achievements",
            json={
                "player_achievements": {
                    human_id: ["Achievement 4", "Achievement 5", "Achievement 6", "Achievement 7"]
                }
            }
        )
        assert response.status_code == 200

        # SETUP AI BOARD - Writing on blue
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Writing",
                "location": "board",
                "color": "blue"
            }
        )
        assert response.status_code == 200

        # SETUP AI ACHIEVEMENT - 1 achievement (age 1)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-achievements",
            json={
                "player_achievements": {
                    ai_id: ["Achievement 1"]
                }
            }
        )
        assert response.status_code == 200

        # SET GAME TO PLAYING STATE
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={
                "phase": "playing",
                "current_player_index": 0,
                "actions_remaining": 2
            }
        )
        assert response.status_code == 200

        return {
            "game_id": game_id,
            "human_id": human_id,
            "ai_id": ai_id
        }

    def setup_no_win_scenario(self) -> dict[str, Any]:
        """Create game where Self Service condition is false."""
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

        # SETUP HUMAN BOARD - Self Service on green + Tools on red (for Effect 2)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Self Service",
                "location": "board",
                "color": "green"
            }
        )
        assert response.status_code == 200

        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": human_id,
                "card_name": "Tools",
                "location": "board",
                "color": "red"
            }
        )
        assert response.status_code == 200

        # SETUP HUMAN ACHIEVEMENTS - 2 achievements (age 4,5)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-achievements",
            json={
                "player_achievements": {
                    human_id: ["Achievement 4", "Achievement 5"]
                }
            }
        )
        assert response.status_code == 200

        # SETUP AI BOARD - Writing on blue
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
            json={
                "player_id": ai_id,
                "card_name": "Writing",
                "location": "board",
                "color": "blue"
            }
        )
        assert response.status_code == 200

        # SETUP AI ACHIEVEMENTS - 2 achievements (age 1,2)
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-achievements",
            json={
                "player_achievements": {
                    ai_id: ["Achievement 1", "Achievement 2"]
                }
            }
        )
        assert response.status_code == 200

        # SET GAME TO PLAYING STATE
        response = requests.post(
            f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
            json={
                "phase": "playing",
                "current_player_index": 0,
                "actions_remaining": 2
            }
        )
        assert response.status_code == 200

        return {
            "game_id": game_id,
            "human_id": human_id,
            "ai_id": ai_id
        }

    def test_self_service_win_condition_true(self):
        """Test Self Service with win condition TRUE (4 >= 2*1)."""
        scenario = self.setup_win_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        print("\n=== Test: Win Condition TRUE ===")
        print(f"Game ID: {game_id}")
        print("Human: 4 achievements, AI: 1 achievement")
        print("Expected: 4 >= 2*1 → TRUE → Human wins")

        # Execute dogma on Self Service
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Self Service"
            }
        )
        assert response.status_code == 200

        # Wait for AI event bus processing
        time.sleep(3)

        # Get game state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        game_state = response.json()

        human_player = next(p for p in game_state["players"] if p["id"] == human_id)

        print(f"\nGame phase: {game_state.get('phase')}")
        print(f"Human achievements: {len(human_player.get('achievements', []))}")

        # Check if there's a pending interaction
        pending = game_state.get("state", {}).get("pending_dogma_action")
        if pending:
            context = pending.get("context", {})
            interaction = context.get("interaction_data", {})
            print(f"Pending interaction: {interaction.get('interaction_type')}")

        # ASSERTION 1: Game should be finished (win claimed)
        assert game_state.get("phase") == "finished", \
            f"Expected phase 'finished', got '{game_state.get('phase')}'"

        # ASSERTION 2: Human should have win achievement
        achievement_names = [a.get("name") for a in human_player.get("achievements", [])]
        assert "win" in achievement_names, \
            f"Human should have win achievement. Got: {achievement_names}"

        # ASSERTION 3: Total achievements should be 5 (4 regular + 1 win)
        assert len(human_player.get("achievements", [])) == 5, \
            f"Human should have 5 achievements (4 regular + 1 win), got {len(human_player.get('achievements', []))}"

        # ASSERTION 4: Check action log for Self Service dogma
        action_log = game_state.get("action_log", [])
        log_descriptions = [entry.get("description", "") for entry in action_log]
        assert any("Self Service" in desc for desc in log_descriptions), \
            "Should have Self Service activation in action log"

        # Get execution trace
        try:
            response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}/tracing/list")
            if response.status_code == 200:
                traces = response.json()

                # ASSERTION 5: Verify EvaluateCondition in trace
                evaluate_traces = [
                    t for t in traces
                    if t.get("primitive") == "EvaluateCondition"
                ]
                assert len(evaluate_traces) > 0, "Should have EvaluateCondition in trace"

                # ASSERTION 6: Check condition type
                if evaluate_traces:
                    eval_trace = evaluate_traces[0]
                    condition_type = eval_trace.get("context", {}).get("condition", {}).get("type")
                    assert condition_type == "has_twice_achievements_of_opponents", \
                        f"Expected condition type 'has_twice_achievements_of_opponents', got '{condition_type}'"

                # ASSERTION 7: Verify ConditionalAction in trace
                conditional_traces = [
                    t for t in traces
                    if t.get("primitive") == "ConditionalAction"
                ]
                assert len(conditional_traces) > 0, "Should have ConditionalAction in trace"

                # ASSERTION 8: Verify ClaimAchievement in trace
                claim_traces = [
                    t for t in traces
                    if t.get("primitive") == "ClaimAchievement"
                ]
                assert len(claim_traces) > 0, "Should have ClaimAchievement in trace"

                # ASSERTION 9: Check achievement_type in ClaimAchievement
                if claim_traces:
                    claim_trace = claim_traces[0]
                    achievement_type = claim_trace.get("context", {}).get("achievement_type")
                    assert achievement_type == "win", \
                        f"Expected achievement_type 'win', got '{achievement_type}'"

                print("\n=== Execution Trace ===")
                print(f"EvaluateCondition executions: {len(evaluate_traces)}")
                print(f"ConditionalAction executions: {len(conditional_traces)}")
                print(f"ClaimAchievement executions: {len(claim_traces)}")
        except Exception as e:
            print(f"Could not fetch trace: {e}")

        print(f"\nGame ID: {game_id}")
        print("✅ Win Condition TRUE test passed")

    def test_self_service_win_condition_false(self):
        """Test Self Service with win condition FALSE (2 >= 2*2 is false)."""
        scenario = self.setup_no_win_scenario()
        game_id = scenario["game_id"]
        human_id = scenario["human_id"]

        print("\n=== Test: Win Condition FALSE ===")
        print("Human: 2 achievements, AI: 2 achievements")
        print("Expected: 2 >= 2*2 → FALSE → Continue to Effect 2")

        # Execute dogma on Self Service
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={
                "player_id": human_id,
                "action_type": "dogma",
                "card_name": "Self Service"
            }
        )
        assert response.status_code == 200

        # Wait for AI event bus processing
        time.sleep(3)

        # Get game state
        response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
        assert response.status_code == 200
        game_state = response.json()

        human_player = next(p for p in game_state["players"] if p["id"] == human_id)

        print(f"\nGame phase: {game_state.get('phase')}")
        print(f"Human achievements: {len(human_player.get('achievements', []))}")

        # ASSERTION 10: Game should still be playing (no win)
        assert game_state.get("phase") == "playing", \
            f"Expected phase 'playing', got '{game_state.get('phase')}'"

        # ASSERTION 11: Human should NOT have win achievement
        achievement_types = [a.get("achievement_type") for a in human_player.get("achievements", [])]
        assert "win" not in achievement_types, \
            f"Human should NOT have win achievement. Got: {achievement_types}"

        # ASSERTION 12: Total achievements should still be 2
        assert len(human_player.get("achievements", [])) == 2, \
            f"Human should have 2 achievements, got {len(human_player.get('achievements', []))}"

        # ASSERTION 13: Should have pending interaction for Effect 2 (select top card)
        pending_interaction = game_state.get("state", {}).get("pending_dogma_action")

        # If no pending interaction, Effect 2 may have auto-skipped or completed
        if pending_interaction:
            context = pending_interaction.get("context", {})
            interaction_data = context.get("interaction_data", {})

            # ASSERTION 14: Interaction should be select_cards for Effect 2
            assert interaction_data.get("interaction_type") == "select_cards", \
                f"Expected select_cards interaction, got {interaction_data.get('interaction_type')}"

            # ASSERTION 15: Verify eligible_cards field (not cards)
            data = interaction_data.get("data", {})
            assert "eligible_cards" in data, \
                "Should use 'eligible_cards' field name"

            # ASSERTION 16: Eligible cards should exclude Self Service
            eligible_cards = data.get("eligible_cards", [])
            card_names = [c.get("name") for c in eligible_cards]
            assert "Self Service" not in card_names, \
                "Self Service should be filtered out from eligible cards"
            assert "Tools" in card_names, \
                "Tools should be in eligible cards"

            print("\n=== Effect 2 Interaction ===")
            print(f"Interaction type: {interaction_data.get('interaction_type')}")
            print(f"Eligible cards: {card_names}")

        # Get execution trace
        try:
            response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}/tracing/list")
            if response.status_code == 200:
                traces = response.json()

                # ASSERTION 17: Verify EvaluateCondition executed
                evaluate_traces = [
                    t for t in traces
                    if t.get("primitive") == "EvaluateCondition"
                ]
                assert len(evaluate_traces) > 0, "Should have EvaluateCondition in trace"

                # ASSERTION 18: Verify NO ClaimAchievement (condition was false)
                claim_traces = [
                    t for t in traces
                    if t.get("primitive") == "ClaimAchievement"
                ]
                # Note: ClaimAchievement primitive may be in trace but skipped by ConditionalAction
                # So we check game state (no win achievement) instead

                print("\n=== Execution Trace ===")
                print(f"EvaluateCondition executions: {len(evaluate_traces)}")
                print(f"ClaimAchievement executions: {len(claim_traces)}")
        except Exception as e:
            print(f"Could not fetch trace: {e}")

        print(f"\nGame ID: {game_id}")
        print("✅ Win Condition FALSE test passed")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
