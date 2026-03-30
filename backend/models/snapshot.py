"""
Data models for the game snapshot system.

This module defines the core data structures used by the snapshot system
for saving and restoring game state.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class GameSnapshot:
    """Immutable game state snapshot with metadata.

    This represents a complete snapshot of a game at a specific point in time,
    including validation status and metadata for debugging.
    """

    # Identity
    snapshot_id: str  # UUID
    game_id: str

    # Timing
    created_at: datetime
    game_turn: int
    game_phase: str

    # State
    game_state: dict[str, Any]  # Complete serialized game state
    checksum: str  # SHA256 of game_state

    # Validation
    validation_status: str  # "valid", "warning", "invalid"
    validation_messages: list[str]

    # Metadata
    snapshot_type: str  # "manual", "auto", "debug"
    description: str  # User/system description
    tags: list[str]  # ["pre-archery", "debug", "turn-3"]

    # Restoration tracking
    restored_from: Optional[str] = None  # Previous snapshot_id if this is a restore
    restore_count: int = 0  # How many times this snapshot was restored


@dataclass
class ValidationResult:
    """Result of snapshot validation.

    Contains detailed information about validation checks performed
    on a game state before saving or after loading.
    """

    is_valid: bool
    severity: str  # "error", "warning", "info"

    checks: dict[str, bool]  # Check name -> passed
    messages: list[str]

    # Specific validation results
    player_count_ok: bool
    phase_valid: bool
    references_valid: bool
    game_structure_ok: bool

    def can_save(self) -> bool:
        """Can this state be saved?

        Returns True if the state can be saved (no errors).
        Warnings are allowed for saves.
        """
        return self.severity != "error"

    def can_load(self) -> bool:
        """Can this state be loaded?

        Returns True if the state can be loaded.
        More permissive than can_save - allows warnings.
        """
        return self.is_valid or self.severity == "warning"


@dataclass
class CreateSnapshotRequest:
    """Request to create a snapshot via API."""

    description: str = ""
    snapshot_type: str = "manual"
    tags: Optional[list[str]] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class RestoreSnapshotRequest:
    """Request to restore a snapshot via API."""

    target_game_id: Optional[str] = None  # If None, restore to original game_id


@dataclass
class CreateSnapshotResponse:
    """Response after creating a snapshot."""

    success: bool
    snapshot_id: str
    created_at: str  # ISO format string
    validation: dict[str, Any]  # Validation status and messages
    message: Optional[str] = None  # Optional user message


@dataclass
class RestoreSnapshotResponse:
    """Response after restoring a snapshot."""

    success: bool
    game_id: str
    message: str
    ai_reconnected: int = 0  # Number of AI players reconnected
    player_access: Optional[
        list[dict[str, str]]
    ] = None  # Access info for each player  # Number of AI players reconnected


@dataclass
class SnapshotListItem:
    """Summary information for a snapshot in a list."""

    snapshot_id: str
    game_id: str
    created_at: str  # ISO format string
    game_turn: int
    game_phase: str
    description: str
    tags: list[str]
    validation_status: str
    restore_count: int


@dataclass
class SnapshotListResponse:
    """Response containing a list of snapshots."""

    snapshots: list[SnapshotListItem]
    total: int  # Total number of snapshots


@dataclass
class SnapshotDetailsResponse:
    """Detailed information about a specific snapshot."""

    snapshot_id: str
    game_id: str
    created_at: str  # ISO format string
    game_turn: int
    game_phase: str
    description: str
    tags: list[str]
    validation: dict[str, Any]  # Validation status and messages
    checksum: str
    restore_count: int
    restored_from: Optional[str]
    snapshot_type: str
    player_count: int  # Convenience field
    has_ai_players: bool  # Convenience field


# Result types for operations that can fail
@dataclass
class Success:
    """Represents a successful operation result."""

    value: Any


@dataclass
class Failure:
    """Represents a failed operation result."""

    error: str


# Union type for results
Result = Success | Failure
