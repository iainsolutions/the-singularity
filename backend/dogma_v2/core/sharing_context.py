"""
Sharing Context

This module provides a dedicated context for managing sharing state during dogma execution.
Encapsulates sharing-specific state and behavior to simplify the main execution flow.
"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class SharingContext:
    """
    Encapsulates all sharing-related state and operations.

    This context manages the sharing phase state including:
    - Which players are eligible to share
    - Who has already shared
    - Current sharing player
    - Whether anyone has shared yet
    """

    # Players eligible to participate in sharing
    sharing_players: list[str]

    # Players who have completed their sharing opportunity
    completed_sharing: set[str]

    # Current player being asked to share (None if not actively sharing)
    current_sharing_player: str | None

    # Whether any player has successfully shared during this dogma
    anyone_shared: bool

    @classmethod
    def create_for_dogma(cls, eligible_players: list[str]) -> "SharingContext":
        """
        Create a new sharing context for a dogma execution.

        Args:
            eligible_players: List of player IDs eligible to share

        Returns:
            New SharingContext ready for sharing phase
        """
        return cls(
            sharing_players=eligible_players.copy(),
            completed_sharing=set(),
            current_sharing_player=None,
            anyone_shared=False,
        )

    @classmethod
    def empty(cls) -> "SharingContext":
        """Create an empty sharing context (for non-sharing dogmas)."""
        return cls(
            sharing_players=[],
            completed_sharing=set(),
            current_sharing_player=None,
            anyone_shared=False,
        )

    def start_sharing_for_player(self, player_id: str) -> "SharingContext":
        """
        Mark a player as the current sharing player.

        Args:
            player_id: Player ID to start sharing for

        Returns:
            Updated context with current sharing player set

        Raises:
            ValueError: If player is not eligible for sharing or has already completed sharing
        """
        if player_id not in self.sharing_players:
            raise ValueError(f"Player {player_id} is not eligible for sharing")

        if player_id in self.completed_sharing:
            raise ValueError(f"Player {player_id} has already completed sharing")

        return replace(self, current_sharing_player=player_id)

    def complete_sharing_for_player(
        self, player_id: str, shared: bool
    ) -> "SharingContext":
        """
        Mark a player as having completed their sharing opportunity.

        Args:
            player_id: Player ID who completed sharing
            shared: Whether the player actually shared a card

        Returns:
            Updated context with player marked as completed

        Raises:
            ValueError: If player was not the current sharing player
        """
        if self.current_sharing_player != player_id:
            raise ValueError(f"Player {player_id} was not the current sharing player")

        new_completed = self.completed_sharing | {player_id}
        new_anyone_shared = self.anyone_shared or shared

        return replace(
            self,
            completed_sharing=new_completed,
            current_sharing_player=None,
            anyone_shared=new_anyone_shared,
        )

    def with_cleared_completed(self) -> "SharingContext":
        """
        Clear the completed_sharing set for processing the next effect.

        Innovation rules: Sharing players execute EVERY effect on a card.
        Between effects, we clear who has completed sharing so they can
        participate in the next effect.

        Returns:
            Updated context with completed_sharing cleared and current_sharing_player reset
        """
        return replace(
            self,
            completed_sharing=set(),
            current_sharing_player=None,
        )

    def get_next_sharing_player(self) -> str | None:
        """
        Get the next player who should be asked to share.

        Returns:
            Player ID of next sharing player, or None if sharing is complete
        """
        for player_id in self.sharing_players:
            if player_id not in self.completed_sharing:
                return player_id
        return None

    def is_sharing_complete(self) -> bool:
        """
        Check if all eligible players have completed sharing.

        Returns:
            True if sharing phase is complete
        """
        return len(self.completed_sharing) >= len(self.sharing_players)

    def is_sharing_active(self) -> bool:
        """
        Check if sharing is currently in progress.

        Returns:
            True if there is a current sharing player
        """
        return self.current_sharing_player is not None

    def get_remaining_players(self) -> list[str]:
        """
        Get list of players who haven't completed sharing yet.

        Returns:
            List of player IDs who still need to share
        """
        return [
            player_id
            for player_id in self.sharing_players
            if player_id not in self.completed_sharing
        ]

    def get_sharing_stats(self) -> dict:
        """
        Get statistics about the current sharing state.

        Returns:
            Dictionary with sharing statistics
        """
        return {
            "total_eligible": len(self.sharing_players),
            "completed": len(self.completed_sharing),
            "remaining": len(self.sharing_players) - len(self.completed_sharing),
            "anyone_shared": self.anyone_shared,
            "is_active": self.is_sharing_active(),
            "is_complete": self.is_sharing_complete(),
            "current_player": self.current_sharing_player,
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "sharing_players": self.sharing_players,
            "completed_sharing": list(self.completed_sharing),  # Convert set to list
            "current_sharing_player": self.current_sharing_player,
            "anyone_shared": self.anyone_shared,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SharingContext":
        """Create SharingContext from dictionary."""
        return cls(
            sharing_players=data.get("sharing_players", []),
            completed_sharing=set(
                data.get("completed_sharing", [])
            ),  # Convert list back to set
            current_sharing_player=data.get("current_sharing_player"),
            anyone_shared=data.get("anyone_shared", False),
        )
