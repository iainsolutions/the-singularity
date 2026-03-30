"""
Sharing phase for dogma processing.

This phase handles the sharing mechanics where eligible players
execute the same effects as the activating player.
"""

import logging
from typing import Any

from logging_config import EventType, activity_logger
from models.player import Player

from ..core.context import DogmaContext
from ..core.phases import DogmaPhase, PhaseResult
from .completion import CompletionPhase
from .execution import EffectExecutionPhase

logger = logging.getLogger(__name__)


class SharingPhase(DogmaPhase):
    """
    Phase for handling sharing mechanics.

    This phase executes the same effects for sharing players as were
    executed for the activating player. It uses the encapsulated
    SharingContext to manage state and player rotation automatically.
    """

    def __init__(self, effects: list[Any]):
        """
        Initialize sharing phase.

        Args:
            effects: List of effects to execute for sharing players
        """
        self.effects = effects

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Execute sharing effects for eligible players"""
        self.log_phase_start(context)

        # Check if sharing is complete
        if context.is_sharing_complete():
            logger.info("All sharing players complete - moving to completion")
            self._log_sharing_completion(context)
            completion_phase = CompletionPhase()
            return PhaseResult.success(completion_phase, context)

        # Get next sharing player
        next_player_id = context.get_next_sharing_player()
        if next_player_id is None:
            logger.info("No more sharing players - moving to completion")
            completion_phase = CompletionPhase()
            return PhaseResult.success(completion_phase, context)

        # Find the player object
        sharing_player = self._find_player_by_id(context, next_player_id)
        if sharing_player is None:
            logger.warning(f"Sharing player {next_player_id} not found - skipping")
            # Mark as completed and try next player
            updated_context = context.complete_sharing_for_player(next_player_id, False)
            return self.execute(updated_context)

        logger.info(f"Executing sharing effects for {sharing_player.name}")

        # Mark this player as currently sharing
        sharing_context = context.start_sharing_for_player(next_player_id)

        # Add action log entry for UI display
        from models.game import ActionType

        sharing_context.game.add_log_entry(
            player_name=sharing_player.name,
            action_type=ActionType.DOGMA,
            description=f"shared {sharing_context.card.name} (has enough {sharing_context.get_variable('featured_symbol', 'required symbol')})",
        )

        # Log detailed sharing phase start
        self._log_sharing_start(sharing_context, sharing_player)

        # Enhanced structured logging for sharing player's turn start
        self._log_sharing_turn_start(sharing_context, sharing_player)

        # Create isolated context for sharing player (prevents variable pollution)
        isolated_context = sharing_context.create_isolated_context(sharing_player)

        # CRITICAL FIX: Preserve response variables ONLY if resuming for the SAME player
        # Check if the last suspended player matches the current sharing player
        last_responding_player = sharing_context.get_variable(
            "_last_responding_player_id"
        )
        if last_responding_player == next_player_id:
            # Resuming for same player - preserve their response variables
            response_vars = [
                "decline",
                "selected_achievement",
                "selected_achievements",
                "selected_cards",
                "chosen_option",
                "interaction_cancelled",
            ]
            for var in response_vars:
                if sharing_context.has_variable(var):
                    isolated_context = isolated_context.with_variable(
                        var, sharing_context.get_variable(var)
                    )
            logger.info(
                f"SHARING: Preserved response variables for resuming player {sharing_player.name}"
            )

        # Preserve critical variables and mark sharing phase
        isolated_context = isolated_context.with_variable(
            "featured_symbol", sharing_context.get_variable("featured_symbol")
        )
        # Store original sharing context for later merging
        isolated_context = isolated_context.with_variable(
            "_original_sharing_context", sharing_context
        )
        isolated_context = isolated_context.with_variable("is_sharing_phase", True)

        # Create effect execution phase for sharing player
        execution_phase = EffectExecutionPhase(self.effects, 0)
        execution_phase.is_sharing = True  # Mark as sharing execution

        return PhaseResult.success(execution_phase, isolated_context)

    def _find_player_by_id(
        self, context: DogmaContext, player_id: str
    ) -> Player | None:
        """Find player object by ID"""
        for player in context.game.players:
            if player.id == player_id:
                return player
        return None

    def _log_sharing_start(self, context: DogmaContext, sharing_player: Player) -> None:
        """Log the start of sharing for a player"""
        if activity_logger:
            activity_logger.log_dogma_sharing_benefit(
                game_id=context.game.game_id,
                sharing_player_id=sharing_player.id,
                triggering_player_id=context.activating_player.id,
                card_name=context.card.name,
                benefit_description=f"Sharing {context.card.name} effects - has sufficient {context.get_variable('featured_symbol', 'required symbol')} symbols",
                sharing_reason=f"Has sufficient {context.get_variable('featured_symbol', 'required symbol')} symbols",
                effect_count=len(self.effects),
                sharing_player_name=sharing_player.name,
                activating_player_name=context.activating_player.name,
                phase="sharing_start",
            )

    def _log_sharing_completion(self, context: DogmaContext) -> None:
        """Log the completion of all sharing"""
        if activity_logger:
            activity_logger.log_dogma_sharing_benefit(
                game_id=context.game.game_id,
                sharing_player_id="all_players",
                triggering_player_id=context.activating_player.id,
                card_name=context.card.name,
                benefit_description="All sharing players completed their effects",
                sharing_reason="All sharing players completed their effects",
                effect_count=len(self.effects),
                sharing_player_name="All sharing players",
                activating_player_name=context.activating_player.name,
                phase="sharing_complete",
                anyone_shared=context.anyone_shared(),
            )

    def _log_sharing_turn_start(
        self, context: DogmaContext, sharing_player: Player
    ) -> None:
        """Log structured message when starting a sharing player's turn"""
        if activity_logger:
            # Get sharing state information
            sharing_stats = context.sharing.get_sharing_stats()
            remaining_players = [
                player_id
                for player_id in context.sharing.sharing_players
                if player_id not in context.sharing.completed_sharing
            ]

            # Log using activity_logger.log_game_event for structured logging
            activity_logger.log_game_event(
                event_type=EventType.DOGMA_SHARING_BENEFIT,
                game_id=context.game.game_id,
                player_id=sharing_player.id,
                message=f"Starting sharing turn for {sharing_player.name}",
                data={
                    "transaction_id": context.transaction_id,
                    "card_name": context.card.name,
                    "activating_player_id": context.activating_player.id,
                    "activating_player_name": context.activating_player.name,
                    "sharing_player_id": sharing_player.id,
                    "sharing_player_name": sharing_player.name,
                    "anyone_shared": context.anyone_shared(),
                    "featured_symbol": context.get_variable("featured_symbol"),
                    "effect_count": len(self.effects),
                    "sharing_stats": sharing_stats,
                    "remaining_players": remaining_players,
                    "phase": "sharing_turn_start",
                },
            )

            # Also log phase transition
            activity_logger.log_phase_transition(
                game_id=context.game.game_id,
                transaction_id=context.transaction_id,
                player_id=sharing_player.id,
                card_name=context.card.name,
                phase_name="SharingPhase",
                transition_type="enter",
                context_variables={
                    "featured_symbol": context.get_variable("featured_symbol"),
                    "anyone_shared": context.anyone_shared(),
                    "sharing_stats": sharing_stats,
                    "remaining_players": remaining_players,
                    "effect_count": len(self.effects),
                },
            )

    def get_phase_name(self) -> str:
        """Return phase name with current sharing status"""
        return f"SharingPhase - effects: {len(self.effects)}"

    def estimate_remaining_phases(self) -> int:
        """Estimate phases remaining"""
        # Each sharing player could have multiple effects plus interactions
        # Plus completion phase - conservative estimate since we don't have context here
        return len(self.effects) + 1
