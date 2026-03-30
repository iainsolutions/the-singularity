"""
Immutable context for dogma execution.

This module provides the DogmaContext class, which is an immutable
container for all state needed during dogma execution. The context
is passed through the phase pipeline and updated via functional
methods that return new context instances.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType as FrozenDict
from typing import TYPE_CHECKING, Any

from models.card import Card
from models.game import Game
from models.player import Player

if TYPE_CHECKING:
    from .sharing_context import SharingContext

from ..state_tracker import StateChangeTracker


@dataclass(frozen=True)
class StateSnapshot:
    """Immutable snapshot of game state for rollback"""

    timestamp: datetime
    phase_name: str
    player_states: FrozenDict[str, dict[str, Any]]
    variables: FrozenDict[str, Any]

    @classmethod
    def from_game_state(
        cls, game: Game, phase_name: str, variables: dict[str, Any]
    ) -> StateSnapshot:
        """Create snapshot from current game state"""
        from ..state.capture import StateCapture

        player_states = {}
        for player in game.players:
            player_states[player.id] = StateCapture.capture_player_state(player)

        return cls(
            timestamp=datetime.now(),
            phase_name=phase_name,
            player_states=FrozenDict(player_states),
            variables=FrozenDict(variables),
        )


@dataclass(frozen=True)
class DogmaContext:
    """
    Immutable context passed through phase pipeline.

    This context contains all state needed for dogma execution and is
    updated via functional methods that return new context instances.
    This ensures no mutations and provides a clear audit trail.
    """

    # Core references (never change)
    game: Game  # Current game state
    activating_player: Player  # Player who activated dogma
    card: Card  # Card being dogma'd
    transaction_id: str  # Unique transaction ID

    # Execution state (changes via with_* methods)
    current_player: Player  # Player currently acting
    variables: FrozenDict[str, Any]  # Execution variables
    results: tuple[str, ...]  # Accumulated results

    # Sharing state (encapsulated in SharingContext)
    sharing: SharingContext

    # State change tracking for detailed action logs
    state_tracker: StateChangeTracker

    # Tracking for debugging and rollback
    phase_history: tuple[str, ...] = ()
    state_snapshots: tuple[StateSnapshot, ...] = ()

    @classmethod
    def create_initial(
        cls,
        game: Game,
        activating_player: Player,
        card: Card,
        transaction_id: str | None = None,
    ) -> DogmaContext:
        """Create initial context for dogma execution"""
        from .sharing_context import (  # Import at runtime to avoid circular imports
            SharingContext,
        )

        # Create state tracker and set up player mappings
        tracker = StateChangeTracker()
        tracker.set_player_mapping(game.players)

        return cls(
            game=game,
            activating_player=activating_player,
            card=card,
            transaction_id=transaction_id or str(uuid.uuid4()),
            current_player=activating_player,
            variables=FrozenDict({}),
            results=(),
            sharing=SharingContext.empty(),  # Start with empty sharing context
            state_tracker=tracker,
            phase_history=(),
            state_snapshots=(),
        )

    def with_variable(self, key: str, value: Any) -> DogmaContext:
        """Return new context with added/updated variable"""
        new_vars = dict(self.variables)
        new_vars[key] = value
        return replace(self, variables=FrozenDict(new_vars))

    def with_variables(self, variables: dict[str, Any]) -> DogmaContext:
        """Return new context with multiple variables updated"""
        new_vars = dict(self.variables)
        new_vars.update(variables)
        return replace(self, variables=FrozenDict(new_vars))

    def without_variable(self, key: str) -> DogmaContext:
        """Return new context with variable removed"""
        if key not in self.variables:
            return self
        new_vars = dict(self.variables)
        del new_vars[key]
        return replace(self, variables=FrozenDict(new_vars))

    def with_result(self, result: str) -> DogmaContext:
        """Return new context with added result"""
        return replace(self, results=(*self.results, result))

    def with_results(self, results: tuple[str, ...]) -> DogmaContext:
        """Return new context with multiple results added"""
        return replace(self, results=self.results + results)

    def with_player(self, player: Player) -> DogmaContext:
        """Return new context for different player"""
        return replace(self, current_player=player)

    def with_phase_entered(self, phase_name: str) -> DogmaContext:
        """Return new context with phase added to history"""
        return replace(self, phase_history=(*self.phase_history, phase_name))

    def with_snapshot(self, phase_name: str) -> DogmaContext:
        """Return new context with current state snapshot"""
        snapshot = StateSnapshot.from_game_state(
            self.game, phase_name, dict(self.variables)
        )
        return replace(self, state_snapshots=(*self.state_snapshots, snapshot))

    def with_sharing_context(self, sharing_context: SharingContext) -> DogmaContext:
        """Return new context with updated sharing context"""
        return replace(self, sharing=sharing_context)

    def initialize_sharing(self, eligible_players: list[str]) -> DogmaContext:
        """Initialize sharing context for dogma execution"""
        from .sharing_context import SharingContext

        sharing_context = SharingContext.create_for_dogma(eligible_players)
        return replace(self, sharing=sharing_context)

    def start_sharing_for_player(self, player_id: str) -> DogmaContext:
        """Mark a player as the current sharing player"""
        updated_sharing = self.sharing.start_sharing_for_player(player_id)
        return replace(self, sharing=updated_sharing)

    def complete_sharing_for_player(self, player_id: str, shared: bool) -> DogmaContext:
        """Mark a player as having completed their sharing opportunity"""
        updated_sharing = self.sharing.complete_sharing_for_player(player_id, shared)
        return replace(self, sharing=updated_sharing)

    def get_next_sharing_player(self) -> str | None:
        """Get the next player who should be asked to share"""
        return self.sharing.get_next_sharing_player()

    def is_sharing_complete(self) -> bool:
        """Check if all eligible players have completed sharing"""
        return self.sharing.is_sharing_complete()

    def is_sharing_active(self) -> bool:
        """Check if sharing is currently in progress"""
        return self.sharing.is_sharing_active()

    def anyone_shared(self) -> bool:
        """Check if anyone has shared during this dogma"""
        return self.sharing.anyone_shared

    def get_variable(self, key: str, default: Any = None) -> Any:
        """Safely get variable with optional default"""
        return self.variables.get(key, default)

    def get(self, key: str, default: Any = None) -> Any:
        """Alias for get_variable to maintain compatibility"""
        return self.get_variable(key, default)

    def has_variable(self, key: str) -> bool:
        """Check if variable exists"""
        return key in self.variables

    def get_latest_snapshot(self) -> StateSnapshot | None:
        """Get most recent state snapshot"""
        return self.state_snapshots[-1] if self.state_snapshots else None

    def get_results_list(self) -> list[str]:
        """Convert results tuple to list for external APIs"""
        return list(self.results)

    def create_isolated_context(self, player: Player) -> DogmaContext:
        """
        Create isolated context for different player.

        This creates a new context for a different player (e.g., for sharing)
        with isolated variables to prevent pollution.
        """
        return DogmaContext(
            game=self.game,
            activating_player=self.activating_player,
            card=self.card,
            transaction_id=self.transaction_id,
            current_player=player,
            variables=FrozenDict({}),  # Start with empty variables
            results=(),  # Start with empty results
            sharing=self.sharing,  # Share the same sharing context
            state_tracker=self.state_tracker,  # Share the same state tracker
            phase_history=self.phase_history,
            state_snapshots=self.state_snapshots,
        )

    def merge_isolated_results(self, isolated_context: DogmaContext) -> DogmaContext:
        """
        Merge results from isolated context back into this context.

        Used after sharing player execution to collect their results.
        """
        return self.with_results(isolated_context.results).with_sharing_context(
            isolated_context.sharing
        )

    def __str__(self) -> str:
        """String representation for debugging"""
        sharing_info = ""
        if self.sharing.sharing_players:
            sharing_stats = self.sharing.get_sharing_stats()
            sharing_info = f", sharing={sharing_stats['completed']}/{sharing_stats['total_eligible']}"

        return (
            f"DogmaContext(transaction={self.transaction_id[:8]}..., "
            f"player={self.current_player.name}, card={self.card.name}, "
            f"variables={len(self.variables)}, results={len(self.results)}{sharing_info})"
        )

    def __repr__(self) -> str:
        return self.__str__()


# Variable scope validation helpers

GLOBAL_VARIABLES = {
    "featured_symbol",
    "transaction_id",
    "dogma_card",
}

DOGMA_SCOPE_VARIABLES = {
    "sharing_players",
    "anyone_shared",
    "demand_transferred_count",
    "effect_index",
}

EFFECT_SCOPE_VARIABLES = {
    "selected_cards",
    "selected_card",
    "selected_achievements",
    "selected_achievement",
    "chosen_option",
    "player_choice",
    "decline",
    "interaction_cancelled",
}

PLAYER_SCOPE_VARIABLES = {
    "hand_before",
    "score_before",
    "board_before",
    "complied",
    "transferred_cards",
    "affected_cards",
    "processed_cards",
}


def validate_variable_scope(key: str, scope: str) -> bool:
    """Validate that variable is being used in correct scope"""
    scope_sets = {
        "GLOBAL": GLOBAL_VARIABLES,
        "DOGMA": DOGMA_SCOPE_VARIABLES,
        "EFFECT": EFFECT_SCOPE_VARIABLES,
        "PLAYER": PLAYER_SCOPE_VARIABLES,
    }

    return key in scope_sets.get(scope, set())


def clear_player_scope_variables(context: DogmaContext) -> DogmaContext:
    """
    Clear all player-scoped and effect-scoped variables from context.

    This utility removes variables that are specific to individual players
    (like hand_before, score_before, etc.) and effect-scoped variables
    (like selected_achievement, selected_cards, etc.) while preserving
    global and dogma-scoped variables that should persist across players.

    Used after sharing player execution to prevent variable pollution
    when merging contexts back to the activating player.

    Args:
        context: The DogmaContext to clean

    Returns:
        New DogmaContext with player-scoped and effect-scoped variables removed
    """
    cleaned_variables = {}

    for key, value in context.variables.items():
        # Keep variables that are not player-scoped or effect-scoped
        if key not in PLAYER_SCOPE_VARIABLES and key not in EFFECT_SCOPE_VARIABLES:
            cleaned_variables[key] = value

    return context.with_variables({}).with_variables(cleaned_variables)
