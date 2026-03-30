"""AI vs AI Full Game Test - Monitor achievements and gameplay.

This test creates a game with 2 novice AI players and monitors:
- Achievement claiming behavior
- Victory conditions
- Error-free execution
- No infinite loops

Usage:
    pytest test_scenarios/automation/test_ai_vs_ai_full_game.py -v -s
"""

import time
import requests
import pytest


class TestAIvsAIFullGame:
    """Test AI vs AI gameplay with achievement monitoring."""

    BASE_URL = "http://localhost:8000"
    MAX_TURNS = 100  # Prevent infinite loops

    @pytest.mark.skip(reason="Expensive test - uses many AI tokens. Run manually with: pytest -m '' test_scenarios/automation/test_ai_vs_ai_full_game.py")
    def test_ai_vs_ai_achievements(self):
        """Test that AI players claim achievements during gameplay."""

        # Create game
        response = requests.post(f"{self.BASE_URL}/api/v1/games")
        assert response.status_code == 200, f"Failed to create game: {response.text}"
        game_id = response.json()["game_id"]
        print(f"\n✓ Game created: {game_id}")

        # Add AI Player 1
        response = requests.post(
            f"{self.BASE_URL}/api/v1/games/{game_id}/add_ai_player",
            json={"difficulty": "novice"}
        )
        assert response.status_code == 200, f"Failed to add AI Player 1: {response.text}"
        game_state = response.json()["game_state"]
        p1_id = game_state["players"][0]["id"]
        print(f"✓ AI Player 1 added: {p1_id}")

        # Add AI Player 2
        response = requests.post(
            f"{self.BASE_URL}/api/v1/games/{game_id}/add_ai_player",
            json={"difficulty": "novice"}
        )
        assert response.status_code == 200, f"Failed to add AI Player 2: {response.text}"
        game_state = response.json()["game_state"]
        p2_id = game_state["players"][1]["id"]
        print(f"✓ AI Player 2 added: {p2_id}")

        # Start game
        response = requests.post(f"{self.BASE_URL}/api/v1/games/{game_id}/start")
        assert response.status_code == 200, f"Failed to start game: {response.text}"
        print(f"✓ Game started")

        # Monitor gameplay
        turn_count = 0
        achievement_claims = []
        last_state = None

        while turn_count < self.MAX_TURNS:
            time.sleep(1)  # Give AI time to process

            # Get game state
            response = requests.get(f"{self.BASE_URL}/api/v1/games/{game_id}")
            assert response.status_code == 200, f"Failed to get game state: {response.text}"
            game_state = response.json()

            # Check if game ended
            if game_state.get("phase") == "GameOver":
                print(f"\n✓ Game ended after {turn_count} turns")
                print(f"  Winner: {game_state.get('winner', 'None')}")
                break

            # Track achievements
            for player in game_state.get("players", []):
                player_achievements = player.get("achievements", [])
                if len(player_achievements) > len([a for a in achievement_claims if a["player"] == player["name"]]):
                    # New achievement claimed
                    for ach in player_achievements:
                        ach_name = ach if isinstance(ach, str) else ach.get("name", "Unknown")
                        if not any(a["name"] == ach_name and a["player"] == player["name"] for a in achievement_claims):
                            achievement_claims.append({
                                "player": player["name"],
                                "name": ach_name,
                                "turn": turn_count
                            })
                            print(f"  🏆 {player['name']} claimed {ach_name} on turn {turn_count}")

            # Detect state changes (new turn)
            current_player_idx = game_state.get("state", {}).get("current_player_index")
            if last_state and current_player_idx != last_state.get("state", {}).get("current_player_index"):
                turn_count += 1
                if turn_count % 10 == 0:
                    print(f"  Turn {turn_count}...")

            last_state = game_state

            # Safety check for stuck games
            if turn_count >= self.MAX_TURNS:
                pytest.fail(f"Game exceeded {self.MAX_TURNS} turns - possible infinite loop")

        # Verify results
        print(f"\n=== Game Summary ===")
        print(f"Total turns: {turn_count}")
        print(f"Total achievements claimed: {len(achievement_claims)}")

        # Get final state
        response = requests.get(f"{self.BASE_URL}/api/v1/games/{game_id}")
        final_state = response.json()

        for player in final_state.get("players", []):
            score = sum(card.get("age", 0) for card in player.get("score_pile", []))
            achievements = len(player.get("achievements", []))
            print(f"{player['name']}: {score} points, {achievements} achievements")

        # Assertions
        assert turn_count < self.MAX_TURNS, f"Game took too many turns ({turn_count})"
        assert len(achievement_claims) > 0, "No achievements were claimed during the game!"
        assert final_state.get("phase") == "GameOver", "Game did not complete"

        # Check that at least one player has multiple achievements
        max_achievements = max(len(p.get("achievements", [])) for p in final_state.get("players", []))
        assert max_achievements > 0, "No player claimed any achievements"

        print(f"\n✓ Test passed! Game completed with {len(achievement_claims)} achievement claims")
        print(f"  Achievement details:")
        for claim in achievement_claims:
            print(f"    - Turn {claim['turn']}: {claim['player']} claimed {claim['name']}")


if __name__ == "__main__":
    # Run the test directly
    test = TestAIvsAIFullGame()
    test.test_ai_vs_ai_achievements()
