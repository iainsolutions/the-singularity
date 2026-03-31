from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    from .player import Player


class ScoreManager:
    """Manages scoring and victory conditions."""

    def get_achievements_needed_for_victory(self, num_players: int) -> int:
        """Calculate achievements needed for victory based on player count.

        Base game formula: 8 - (# of Players), minimum 3

        Returns:
            int: Number of achievements needed to win
        """
        return max(3, 8 - num_players)

    def check_achievement_victory(self, players: list["Player"]) -> Optional["Player"]:
        """Check if an achievement victory has been met.

        Returns:
            Player: The winning player, or None if no winner yet.
        """
        required_achievements = self.get_achievements_needed_for_victory(len(players))

        for player in players:
            if len(player.achievements) >= required_achievements:
                return player

        return None

    def check_score_victory(self, players: list["Player"]) -> Optional["Player"]:
        """Determine winner by score (used when age decks are exhausted).

        Returns:
            Player: The winning player (highest score).
        """
        max_score = -1
        winner = None
        for player in players:
            score = sum(card.age for card in player.score_pile)
            if score > max_score:
                max_score = score
                winner = player
            elif score == max_score:
                # Tie-breaking rules could be added here (e.g. most achievements)
                # For now, first player with that score keeps it (simple tie-break)
                pass

        return winner
