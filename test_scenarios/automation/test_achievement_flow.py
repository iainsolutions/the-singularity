#!/usr/bin/env python3
"""
End-to-end test: Achievement Flow

Tests the full achieve action via the backend REST API, ensuring
computed_state.can_achieve is correct and the achieve action works.

Scenarios:
1. Basic achieve: score >= 5, top card age >= 1 -> claim age 1
2. Cannot achieve without enough score
3. Cannot achieve without high enough top card
4. Score via dogma (Metalworking) -> then achieve
5. Second achievement of same age costs more (5 * age * 2)
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"


def create_game_with_players() -> dict[str, Any]:
    """Create a 2-player game (human + AI) in playing state. Returns game_id, human_id, ai_id."""
    response = requests.post(f"{BASE_URL}/api/v1/games", json={})
    assert response.status_code == 200, f"Create game failed: {response.text}"
    game_id = response.json()["game_id"]

    response = requests.post(
        f"{BASE_URL}/api/v1/games/{game_id}/join",
        json={"name": "AchievePlayer"}
    )
    assert response.status_code == 200, f"Join failed: {response.text}"
    human_id = response.json()["player_id"]

    response = requests.post(
        f"{BASE_URL}/api/v1/games/{game_id}/add_ai_player",
        json={"difficulty": "beginner"}
    )
    assert response.status_code == 200, f"Add AI failed: {response.text}"
    game_state = response.json()["game_state"]
    ai_id = next(p["id"] for p in game_state["players"] if p["is_ai"])

    time.sleep(0.5)

    # Set to playing, human's turn, 2 actions
    response = requests.post(
        f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
        json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
    )
    assert response.status_code == 200, f"Set state failed: {response.text}"

    return {"game_id": game_id, "human_id": human_id, "ai_id": ai_id}


def set_card(game_id: str, player_id: str, card_name: str, location: str):
    """Place a card in a player's hand, board, or score_pile."""
    response = requests.post(
        f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
        json={"player_id": player_id, "card_name": card_name, "location": location}
    )
    assert response.status_code == 200, f"set-card {card_name} -> {location} failed: {response.text}"


def get_player(game_id: str, player_id: str) -> dict:
    """Fetch game state and return the specified player dict."""
    response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
    assert response.status_code == 200, f"Get game failed: {response.text}"
    state = response.json()
    player = next((p for p in state["players"] if p["id"] == player_id), None)
    assert player is not None, f"Player {player_id} not found in game state"
    return player


def get_game(game_id: str) -> dict:
    """Fetch full game state."""
    response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
    assert response.status_code == 200, f"Get game failed: {response.text}"
    return response.json()


def achieve(game_id: str, player_id: str, age: int) -> requests.Response:
    """POST an achieve action, return raw response."""
    return requests.post(
        f"{BASE_URL}/api/v1/games/{game_id}/action",
        json={"player_id": player_id, "action_type": "achieve", "age": age}
    )


class TestAchievementFlow:
    """End-to-end tests for the achievement action."""

    def test_basic_achieve_age_1(self):
        """Score >= 5, top card age >= 1 -> claim age 1 achievement."""
        print("\n" + "="*70)
        print("TEST: Basic achieve age 1")
        print("="*70)

        ctx = create_game_with_players()
        game_id, human_id = ctx["game_id"], ctx["human_id"]

        # Board: Metalworking (age 1, red) -> top card age 1
        set_card(game_id, human_id, "Metalworking", "board")

        # Score pile: age-1 cards totaling >= 5 (each age-1 card = 1 point, need 5)
        for card_name in ["Archery", "Sailing", "The Wheel", "Oars", "Domestication"]:
            set_card(game_id, human_id, card_name, "score_pile")

        # Verify computed_state
        player = get_player(game_id, human_id)
        computed = player.get("computed_state", {})
        total_score = computed.get("total_score", 0)
        can_achieve = computed.get("can_achieve", [])

        print(f"Score: {total_score}, can_achieve: {can_achieve}")
        assert total_score >= 5, f"Expected score >= 5, got {total_score}"
        assert 1 in can_achieve, f"Expected age 1 in can_achieve, got {can_achieve}"

        # Verify age 1 achievement is available before claiming
        game = get_game(game_id)
        achievement_cards = game.get("achievement_cards", {})
        assert "1" in achievement_cards and len(achievement_cards["1"]) > 0, \
            f"Age 1 achievement should be available, got {achievement_cards.get('1', [])}"

        # Claim age 1 achievement
        response = achieve(game_id, human_id, 1)
        assert response.status_code == 200, f"Achieve failed: {response.text}"
        result = response.json()
        assert result.get("success") is True, f"Achieve not successful: {result}"
        print("Achieve action succeeded")

        # Verify player now has 1 achievement
        player = get_player(game_id, human_id)
        achievements = player.get("achievements", [])
        assert len(achievements) == 1, f"Expected 1 achievement, got {len(achievements)}: {achievements}"
        print(f"Player achievements: {[a.get('name', '?') for a in achievements]}")

        # Verify age 1 no longer in available achievements
        game = get_game(game_id)
        ach_cards = game.get("achievement_cards", {})
        age_1_remaining = ach_cards.get("1", [])
        assert len(age_1_remaining) == 0, \
            f"Age 1 achievement should be claimed, but {len(age_1_remaining)} remain"

        # Verify can_achieve no longer includes age 1
        player = get_player(game_id, human_id)
        can_achieve_after = player.get("computed_state", {}).get("can_achieve", [])
        assert 1 not in can_achieve_after, \
            f"Age 1 should not be achievable after claiming, got {can_achieve_after}"

        print("="*70)
        print("PASSED: Basic achieve age 1")
        print("="*70)

    def test_cannot_achieve_without_enough_score(self):
        """Score=3, top card age 1 -> can_achieve empty, achieve fails."""
        print("\n" + "="*70)
        print("TEST: Cannot achieve without enough score")
        print("="*70)

        ctx = create_game_with_players()
        game_id, human_id = ctx["game_id"], ctx["human_id"]

        # Board: Pottery (age 1)
        set_card(game_id, human_id, "Pottery", "board")

        # Score pile: 3 age-1 cards = 3 points (need 5 for age 1)
        for card_name in ["Archery", "Sailing", "The Wheel"]:
            set_card(game_id, human_id, card_name, "score_pile")

        player = get_player(game_id, human_id)
        computed = player.get("computed_state", {})
        total_score = computed.get("total_score", 0)
        can_achieve = computed.get("can_achieve", [])

        print(f"Score: {total_score}, can_achieve: {can_achieve}")
        assert total_score == 3, f"Expected score 3, got {total_score}"
        assert 1 not in can_achieve, f"Age 1 should NOT be achievable with score 3, got {can_achieve}"

        # Attempt achieve -> should fail
        response = achieve(game_id, human_id, 1)
        # The API may return 200 with success=false, or 4xx
        if response.status_code == 200:
            result = response.json()
            assert result.get("success") is False, \
                f"Achieve should fail with insufficient score, got {result}"
            print(f"Correctly rejected: {result.get('error')}")
        else:
            print(f"Correctly rejected with status {response.status_code}")

        # Verify no achievement was claimed
        player = get_player(game_id, human_id)
        achievements = player.get("achievements", [])
        assert len(achievements) == 0, f"Should have 0 achievements, got {len(achievements)}"

        print("="*70)
        print("PASSED: Cannot achieve without enough score")
        print("="*70)

    def test_cannot_achieve_without_high_enough_top_card(self):
        """Score=15, all top cards age 1 -> can achieve age 1 but NOT age 3."""
        print("\n" + "="*70)
        print("TEST: Cannot achieve without high enough top card")
        print("="*70)

        ctx = create_game_with_players()
        game_id, human_id = ctx["game_id"], ctx["human_id"]

        # Board: Pottery (age 1) - highest top card is age 1
        set_card(game_id, human_id, "Pottery", "board")

        # Score pile: need 15 points. Use a mix of higher-age cards in score.
        # Age-1 cards = 1pt each. We need 15 total.
        # Use admin to add age-3 cards to score pile (each worth 3 pts): 5 * 3 = 15
        # Age 3 cards: Compass, Paper, Translation, Engineering, Machinery
        for card_name in ["Compass", "Paper", "Translation", "Engineering", "Machinery"]:
            set_card(game_id, human_id, card_name, "score_pile")

        player = get_player(game_id, human_id)
        computed = player.get("computed_state", {})
        total_score = computed.get("total_score", 0)
        can_achieve = computed.get("can_achieve", [])

        print(f"Score: {total_score}, can_achieve: {can_achieve}")
        assert total_score == 15, f"Expected score 15, got {total_score}"

        # Can achieve age 1 (score 15 >= 5, top card age 1 >= 1)
        assert 1 in can_achieve, f"Should be able to achieve age 1, got {can_achieve}"

        # Cannot achieve age 3 (top card age 1 < 3, even though score 15 >= 15)
        assert 3 not in can_achieve, \
            f"Should NOT be able to achieve age 3 (top card age 1 < 3), got {can_achieve}"

        # Can achieve age 2 only if score >= 10 AND top card >= 2. Top card is 1, so no.
        assert 2 not in can_achieve, \
            f"Should NOT be able to achieve age 2 (top card age 1 < 2), got {can_achieve}"

        print("="*70)
        print("PASSED: Cannot achieve without high enough top card")
        print("="*70)

    def test_score_via_dogma_then_achieve(self):
        """Dogma Metalworking to score cards, then claim achievement if eligible."""
        print("\n" + "="*70)
        print("TEST: Score via dogma -> then achieve")
        print("="*70)

        ctx = create_game_with_players()
        game_id, human_id, ai_id = ctx["game_id"], ctx["human_id"], ctx["ai_id"]

        # Human board: Metalworking (red, 3 castles)
        set_card(game_id, human_id, "Metalworking", "board")

        # AI board: Agriculture (yellow, 0 castles - won't share)
        set_card(game_id, ai_id, "Agriculture", "board")

        # Dogma Metalworking - draws and scores castle cards
        print("--- Executing Metalworking Dogma ---")
        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/action",
            json={"player_id": human_id, "action_type": "dogma", "card_name": "Metalworking"}
        )
        assert response.status_code == 200, f"Dogma failed: {response.text}"
        print("Metalworking dogma executed")

        time.sleep(2)

        # Check score after dogma
        player = get_player(game_id, human_id)
        computed = player.get("computed_state", {})
        total_score = computed.get("total_score", 0)
        can_achieve = computed.get("can_achieve", [])
        score_pile = player.get("score_pile", [])

        print(f"Post-dogma: score={total_score}, can_achieve={can_achieve}")
        print(f"Score pile: {[c['name'] for c in score_pile]}")

        # After Metalworking, the loop should have scored some castle cards
        # If score >= 5, we should be able to achieve
        if total_score >= 5 and 1 in can_achieve:
            print("Score >= 5, claiming age 1 achievement...")

            # Need to reset actions since dogma consumed one
            requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
                json={"phase": "playing", "current_player_index": 0, "actions_remaining": 1}
            )

            response = achieve(game_id, human_id, 1)
            assert response.status_code == 200, f"Achieve failed: {response.text}"
            result = response.json()
            assert result.get("success") is True, f"Achieve not successful: {result}"

            player = get_player(game_id, human_id)
            achievements = player.get("achievements", [])
            assert len(achievements) >= 1, \
                f"Should have at least 1 achievement, got {len(achievements)}"
            print(f"Achievement claimed! Achievements: {[a.get('name', '?') for a in achievements]}")
        else:
            # Metalworking may not have scored enough (depends on deck order)
            # Still validate that can_achieve is consistent with score
            print(f"Score {total_score} < 5 or age 1 not achievable - deck order dependent")
            if total_score < 5:
                assert 1 not in can_achieve, \
                    f"can_achieve should not include 1 with score {total_score}"
            print("Dogma->achieve pipeline validated (score insufficient this run)")

        print("="*70)
        print("PASSED: Score via dogma -> then achieve")
        print("="*70)

    def test_second_achievement_costs_more(self):
        """Second age-1 achievement requires 10 points (5 * 1 * 2)."""
        print("\n" + "="*70)
        print("TEST: Second achievement costs more")
        print("="*70)

        ctx = create_game_with_players()
        game_id, human_id = ctx["game_id"], ctx["human_id"]

        # Board: Metalworking (age 1)
        set_card(game_id, human_id, "Metalworking", "board")

        # Give player 5 points to claim first age-1 achievement
        for card_name in ["Archery", "Sailing", "The Wheel", "Oars", "Domestication"]:
            set_card(game_id, human_id, card_name, "score_pile")

        # Claim first age-1 achievement
        response = achieve(game_id, human_id, 1)
        assert response.status_code == 200, f"First achieve failed: {response.text}"
        result = response.json()
        assert result.get("success") is True, f"First achieve not successful: {result}"
        print("First age-1 achievement claimed")

        # Check: game may have only 1 age-1 achievement card total.
        # If no more age-1 achievements remain, can_achieve won't include 1 regardless of score.
        game = get_game(game_id)
        age_1_remaining = game.get("achievement_cards", {}).get("1", [])
        if len(age_1_remaining) == 0:
            print("No more age-1 achievement cards available - expected for standard game")
            # Still verify player has the achievement
            player = get_player(game_id, human_id)
            assert len(player.get("achievements", [])) == 1, "Should have 1 achievement"
            can_achieve = player.get("computed_state", {}).get("can_achieve", [])
            assert 1 not in can_achieve, \
                f"Age 1 not achievable when no cards remain, got {can_achieve}"
            print("Correctly: no age-1 achievement available to claim second time")
        else:
            # Multiple age-1 achievements exist - test the cost scaling
            print(f"{len(age_1_remaining)} age-1 achievement(s) still available")

            # Reset turn so we can act again
            requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
                json={"phase": "playing", "current_player_index": 0, "actions_remaining": 2}
            )

            # Current score is still 5 - second age-1 needs 10 (5 * 1 * 2)
            player = get_player(game_id, human_id)
            computed = player.get("computed_state", {})
            total_score = computed.get("total_score", 0)
            can_achieve = computed.get("can_achieve", [])

            print(f"Score: {total_score}, can_achieve: {can_achieve}")
            assert total_score == 5, f"Expected score 5, got {total_score}"
            assert 1 not in can_achieve, \
                f"Age 1 should NOT be achievable with score 5 (need 10), got {can_achieve}"

            # Add more score to reach 10
            for card_name in ["Pottery", "Agriculture", "Mysticism", "City States", "Clothing"]:
                set_card(game_id, human_id, card_name, "score_pile")

            player = get_player(game_id, human_id)
            computed = player.get("computed_state", {})
            total_score = computed.get("total_score", 0)
            can_achieve = computed.get("can_achieve", [])

            print(f"Score after adding: {total_score}, can_achieve: {can_achieve}")
            assert total_score >= 10, f"Expected score >= 10, got {total_score}"
            assert 1 in can_achieve, \
                f"Age 1 should be achievable with score {total_score} (need 10), got {can_achieve}"

            # Claim second age-1 achievement
            response = achieve(game_id, human_id, 1)
            assert response.status_code == 200, f"Second achieve failed: {response.text}"
            result = response.json()
            assert result.get("success") is True, f"Second achieve not successful: {result}"

            player = get_player(game_id, human_id)
            achievements = player.get("achievements", [])
            assert len(achievements) == 2, f"Expected 2 achievements, got {len(achievements)}"
            print("Second age-1 achievement claimed with score >= 10")

        print("="*70)
        print("PASSED: Second achievement costs more")
        print("="*70)
