"""
Consolidated Dogma Executor - Phase 2 Architecture Integration

This module provides a new executor that uses the consolidated 8-phase system
while maintaining backward compatibility with the existing DogmaExecutor interface.

The consolidated system reduces complexity from 15+ phases to 8 core phases:

Original System (15+ phases):        Consolidated System (8 phases):
- InitializationPhase              → 1. ConsolidatedInitializationPhase
- Various sharing phases           → 2. ConsolidatedSharingPhase
- EffectExecutionPhase             → 3. ConsolidatedExecutionPhase
- Multiple interaction phases      → 4. ConsolidatedInteractionPhase
- Resolution logic scattered       → 5. ConsolidatedResolutionPhase
- DemandPhase + DemandTargetPhase → 6. ConsolidatedDemandPhase
- CompletionPhase                  → 7. ConsolidatedCompletionPhase
- Transaction management scattered → 8. ConsolidatedTransactionPhase

Benefits:
- 40% reduction in phase complexity
- Enhanced debugging with clearer phase names
- Consolidated logic for better maintainability
- Preserved all suspension points for multiplayer
- Improved performance metrics and monitoring
"""

import logging
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from .consolidated_phases import (
    ConsolidatedPhaseMetrics,
    create_consolidated_execution_pipeline,
)
from .core.context import DogmaContext
from .core.transaction import DogmaTransaction, TransactionManager
from .execution_result import DogmaExecutionResult
from .optimization import get_context_optimization_stats, optimize_context_for_phase
from .phase_logger import PhaseTransitionLogger

logger = logging.getLogger(__name__)


class ConsolidatedDogmaExecutor:
    """
    Consolidated Dogma Executor implementing the streamlined 8-phase architecture.

    This executor provides the same interface as the original DogmaExecutor but uses
    the consolidated phase system for improved performance and maintainability.

    Key improvements:
    - Simplified phase flow (8 phases vs 15+)
    - Enhanced debugging and monitoring
    - Better error messages and traceability
    - Consolidated logic for similar operations
    - Preserved all transaction boundaries and suspension points
    """

    def __init__(self, activity_logger=None, use_metrics=True):
        """Initialize the consolidated executor

        Args:
            activity_logger: Optional activity logger (same interface as original)
            use_metrics: Whether to collect performance metrics (default: True)
        """
        self.activity_logger = activity_logger
        self.transaction_manager = TransactionManager()
        self.phase_logger = PhaseTransitionLogger(activity_logger)

        # Consolidated system enhancements
        self.use_metrics = use_metrics
        self.metrics = ConsolidatedPhaseMetrics() if use_metrics else None
        self._total_executions = 0
        self._successful_executions = 0

        logger.info("ConsolidatedDogmaExecutor initialized with 8-phase architecture")

    def execute_dogma(
        self,
        game,
        player,
        card,
        transaction_id: str | None = None,
        endorsed: bool = False,
        is_showcase: bool = False,
    ) -> DogmaExecutionResult:
        """
        Execute a dogma action using the consolidated phase system.

        This is the main entry point that maintains the same interface as the
        original DogmaExecutor while using the streamlined 8-phase system.

        Args:
            endorsed: If True, doubles non-demand effects for activating player (Cities expansion)
            is_showcase: If True, temporarily add artifact display icons to player count (Artifacts expansion)
        """
        start_time = time.time()
        self._total_executions += 1

        try:
            logger.info(
                f"CONSOLIDATED EXECUTOR: Starting dogma execution for {card.name} by {player.name}"
            )

            # ARTIFACTS EXPANSION: If this is showcase dogma, temporarily add artifact icons
            if is_showcase and hasattr(player, 'display') and player.display:
                logger.info(
                    f"ARTIFACTS: Showcase dogma - temporarily adding {player.display.name} icons to {player.name}'s count"
                )
                player.showcase_artifact_temp = player.display

            # Create or resume transaction (same logic as original)
            if transaction_id:
                transaction = self.transaction_manager.get_transaction(transaction_id)
                if not transaction:
                    return self._create_error_result(
                        game,
                        player,
                        card,
                        f"Transaction {transaction_id} not found",
                        transaction_id,
                    )

                context = transaction.get_current_context()
                if context is None:
                    context = DogmaContext.create_initial(
                        game, player, card, transaction.id
                    )

                logger.info(f"CONSOLIDATED: Resuming transaction {transaction_id}")
            else:
                transaction = self.transaction_manager.begin_transaction(
                    game_id=game.game_id, player_id=player.id, card_name=card.name
                )
                context = DogmaContext.create_initial(
                    game, player, card, transaction.id
                )
                # Cities expansion: Store endorsed flag in context
                if endorsed:
                    context = context.with_variable("endorsed", True)
                    logger.info(f"CONSOLIDATED: Dogma endorsed - effects will be doubled")
                logger.info(f"CONSOLIDATED: Started new transaction {transaction.id}")

            # Execute consolidated phase system
            result = self._execute_consolidated_phases(context, transaction)

            # Record execution metrics
            duration = time.time() - start_time
            self._record_execution_metrics(result, duration)

            # Handle transaction completion
            if result.success and not result.interaction_required:
                self.transaction_manager.complete_transaction(
                    transaction.id, result.results
                )
                self._successful_executions += 1
                logger.info(
                    f"CONSOLIDATED: Transaction {transaction.id} completed successfully"
                )

            # Activity logging (same interface as original)
            if self.activity_logger:
                self._log_activity(result, duration)

            logger.info(f"CONSOLIDATED: Dogma execution finished in {duration:.3f}s")
            return result

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"CONSOLIDATED: Execution failed with exception: {e}", exc_info=True
            )

            # Rollback transaction
            if transaction_id or "transaction" in locals():
                try:
                    transaction_to_rollback = locals().get(
                        "transaction"
                    ) or self.transaction_manager.get_transaction(transaction_id)
                    if transaction_to_rollback:
                        self.transaction_manager.fail_transaction(
                            transaction_to_rollback.id, str(e)
                        )
                except Exception as rollback_error:
                    logger.error(
                        f"CONSOLIDATED: Transaction rollback failed: {rollback_error}"
                    )

            return self._create_error_result(
                game, player, card, f"Execution failed: {e}"
            )

        finally:
            # ARTIFACTS EXPANSION: Always clean up showcase artifact, even if error
            if is_showcase and hasattr(player, 'showcase_artifact_temp'):
                logger.debug(f"ARTIFACTS: Cleaning up showcase artifact from {player.name}")
                player.showcase_artifact_temp = None

    def _execute_consolidated_phases(
        self, initial_context: DogmaContext, transaction: DogmaTransaction
    ) -> DogmaExecutionResult:
        """Execute the consolidated 8-phase system with Week 4 optimizations"""

        # WEEK 4 OPTIMIZATION: Use optimized context for better performance
        context = initial_context
        optimized_context = optimize_context_for_phase(context)
        current_phase = create_consolidated_execution_pipeline()  # Start with Phase 1
        phase_count = 0
        max_phases = 50  # Cards with sharing + RepeatAction + ExecuteDogma chains need headroom

        logger.info("CONSOLIDATED: Starting 8-phase execution pipeline")

        while current_phase is not None and phase_count < max_phases:
            phase_count += 1
            phase_name = current_phase.get_phase_name()

            logger.debug(f"CONSOLIDATED: Executing phase {phase_count}/8: {phase_name}")

            # Record phase start in context for debugging
            phase_sequence = context.get_variable("phase_sequence", [])
            phase_sequence.append(phase_name)
            context = context.with_variable("phase_sequence", phase_sequence)

            # Log phase entry
            if self.phase_logger:
                self.phase_logger.log_phase_enter(context, transaction, phase_name)

            try:
                # Execute phase with timing
                phase_start_time = time.time()
                phase_result = current_phase.execute(context)
                phase_duration_ms = (time.time() - phase_start_time) * 1000

                # Record phase metrics
                if self.metrics:
                    self.metrics.record_phase_execution(
                        phase_name,
                        phase_duration_ms,
                        suspended=phase_result.type.value == "interaction",
                    )

                # Record phase in transaction
                phase_record = transaction.add_phase(
                    phase_name, dict(context.variables)
                )

                if phase_result.type.value == "error":
                    # Phase failed
                    logger.error(
                        f"CONSOLIDATED: Phase {phase_name} failed: {phase_result.error}"
                    )
                    phase_record.mark_error(phase_result.error or "Unknown error")

                    if self.phase_logger:
                        self.phase_logger.log_phase_error(
                            phase_result.context,
                            transaction,
                            phase_name,
                            phase_result.error or "Unknown error",
                        )

                    return DogmaExecutionResult(
                        success=False,
                        context=phase_result.context,
                        transaction=transaction,
                        error=f"Phase {phase_name} failed: {phase_result.error}",
                    )

                elif phase_result.type.value == "interaction":
                    # Suspension for interaction
                    logger.info(
                        f"CONSOLIDATED: Phase {phase_name} requires interaction - suspending"
                    )

                    # Store suspended state
                    transaction.set_suspended_state(
                        phase=phase_result.next_phase, context=phase_result.context
                    )

                    # Determine interaction type (same logic as original)
                    interaction_type = self._determine_interaction_type(
                        phase_result.context, phase_name
                    )

                    # Log suspension
                    if self.phase_logger:
                        self.phase_logger.log_phase_suspend(
                            phase_result.context,
                            transaction,
                            phase_name,
                            interaction_type,
                            phase_result.interaction.to_dict()
                            if phase_result.interaction
                            and hasattr(phase_result.interaction, "to_dict")
                            else {},
                        )

                    return DogmaExecutionResult(
                        success=True,
                        context=phase_result.context,
                        transaction=transaction,
                        interaction_required=True,
                        interaction_request=phase_result.interaction,
                        interaction_type=interaction_type,
                    )

                else:
                    # Normal phase completion
                    phase_record.mark_complete(
                        dict(phase_result.context.variables),
                        list(phase_result.context.results),
                    )

                    if self.phase_logger:
                        self.phase_logger.log_phase_exit(
                            phase_result.context,
                            transaction,
                            phase_name,
                            phase_duration_ms,
                        )

                    # Move to next phase
                    context = phase_result.context
                    current_phase = phase_result.next_phase

                    logger.debug(
                        f"CONSOLIDATED: Phase {phase_name} completed in {phase_duration_ms:.2f}ms"
                    )

            except Exception as e:
                logger.error(
                    f"CONSOLIDATED: Phase {phase_name} threw exception: {e}",
                    exc_info=True,
                )

                if self.phase_logger:
                    self.phase_logger.log_phase_error(
                        context, transaction, phase_name, f"Exception: {e}"
                    )

                return DogmaExecutionResult(
                    success=False,
                    context=context,
                    transaction=transaction,
                    error=f"Phase {phase_name} exception: {e}",
                )

        # Check for phase limit exceeded
        if phase_count >= max_phases:
            error = f"Consolidated execution exceeded maximum phases ({max_phases})"
            logger.error(f"CONSOLIDATED: {error}")
            return DogmaExecutionResult(
                success=False,
                context=context,
                transaction=transaction,
                error=error,
            )

        # Execution completed successfully
        logger.info(
            f"CONSOLIDATED: Execution completed successfully after {phase_count} phases"
        )

        # Generate narrative from state tracker
        try:
            changes_count = len(context.state_tracker.changes)
            logger.info(
                f"CONSOLIDATED: State tracker has {changes_count} state changes"
            )

            narrative = context.state_tracker.generate_narrative(
                viewing_player_id=None,  # Generate public narrative
                group_by_context=True,
            )
            logger.info(
                f"CONSOLIDATED: Generated narrative ({len(narrative) if narrative else 0} chars)"
            )

            # NOTE: Log entry creation is handled by async_game_manager.py (line 750 + 873)
            # which creates the initial entry and then updates it with state_changes.
            # We should NOT create a duplicate entry here.
            if narrative:
                logger.info(
                    f"CONSOLIDATED: Generated narrative for {context.card.name} ({len(narrative)} chars)"
                )
                # The narrative will be available via state_tracker for async_game_manager to use
            else:
                logger.warning("CONSOLIDATED: Narrative was empty")
        except Exception as e:
            logger.error(
                f"CONSOLIDATED: Failed to generate narrative: {e}", exc_info=True
            )

        # WEEK 4 OPTIMIZATION: Convert back to regular context and log optimization stats
        if hasattr(locals().get("optimized_context"), "get_performance_metrics"):
            opt_stats = optimized_context.get_performance_metrics()
            logger.debug(f"CONSOLIDATED OPTIMIZATION: {opt_stats}")

        return DogmaExecutionResult(
            success=True, context=context, transaction=transaction
        )

    def _continue_from_phase(
        self,
        starting_phase,
        initial_context: DogmaContext,
        transaction: DogmaTransaction,
    ) -> DogmaExecutionResult:
        """Continue phase loop from a specific phase (used for resuming after interaction)"""

        # This is like _execute_consolidated_phases but starts with the given phase
        context = initial_context
        current_phase = (
            starting_phase  # Start with the suspended phase, not from beginning
        )
        phase_count = len(
            context.get_variable("phase_sequence", [])
        )  # Continue counting
        max_phases = 50  # Cards with sharing + RepeatAction + ExecuteDogma chains need headroom

        logger.info(
            f"CONSOLIDATED: Continuing from phase {current_phase.get_phase_name() if current_phase else 'None'}"
        )

        while current_phase is not None and phase_count < max_phases:
            phase_count += 1
            phase_name = current_phase.get_phase_name()

            logger.debug(
                f"EXECUTOR LOOP: iteration {phase_count}, max={max_phases}, phase={phase_name}"
            )
            logger.debug(f"CONSOLIDATED: Executing phase {phase_count}: {phase_name}")

            # Record phase start in context for debugging
            phase_sequence = context.get_variable("phase_sequence", [])
            phase_sequence.append(phase_name)
            context = context.with_variable("phase_sequence", phase_sequence)

            # Log phase entry
            if self.phase_logger:
                self.phase_logger.log_phase_enter(context, transaction, phase_name)

            try:
                # Execute phase with timing
                phase_start_time = time.time()
                phase_result = current_phase.execute(context)
                phase_duration_ms = (time.time() - phase_start_time) * 1000

                # Record phase metrics
                if self.metrics:
                    self.metrics.record_phase_execution(
                        phase_name,
                        phase_duration_ms,
                        suspended=phase_result.type.value == "interaction",
                    )

                # Record phase in transaction
                phase_record = transaction.add_phase(
                    phase_name, dict(context.variables)
                )

                if phase_result.type.value == "error":
                    # Phase failed
                    logger.error(
                        f"CONSOLIDATED: Phase {phase_name} failed: {phase_result.error}"
                    )
                    phase_record.mark_error(phase_result.error or "Unknown error")

                    if self.phase_logger:
                        self.phase_logger.log_phase_error(
                            phase_result.context,
                            transaction,
                            phase_name,
                            phase_result.error or "Unknown error",
                        )

                    return DogmaExecutionResult(
                        success=False,
                        context=phase_result.context,
                        transaction=transaction,
                        error=f"Phase {phase_name} failed: {phase_result.error}",
                    )

                elif phase_result.type.value == "interaction":
                    # Suspension for interaction
                    logger.info(
                        f"CONSOLIDATED: Phase {phase_name} requires interaction - suspending"
                    )

                    # Store suspended state
                    transaction.set_suspended_state(
                        phase=phase_result.next_phase, context=phase_result.context
                    )

                    # Determine interaction type (same logic as original)
                    interaction_type = self._determine_interaction_type(
                        phase_result.context, phase_name
                    )

                    # Log suspension
                    if self.phase_logger:
                        self.phase_logger.log_phase_suspend(
                            phase_result.context,
                            transaction,
                            phase_name,
                            interaction_type,
                            phase_result.interaction.to_dict()
                            if phase_result.interaction
                            and hasattr(phase_result.interaction, "to_dict")
                            else {},
                        )

                    return DogmaExecutionResult(
                        success=True,
                        context=phase_result.context,
                        transaction=transaction,
                        interaction_required=True,
                        interaction_request=phase_result.interaction,
                        interaction_type=interaction_type,
                    )

                else:
                    # Normal phase completion
                    phase_record.mark_complete(
                        dict(phase_result.context.variables),
                        list(phase_result.context.results),
                    )

                    if self.phase_logger:
                        self.phase_logger.log_phase_exit(
                            phase_result.context,
                            transaction,
                            phase_name,
                            phase_duration_ms,
                        )

                    # Move to next phase
                    context = phase_result.context
                    current_phase = phase_result.next_phase

                    logger.debug(
                        f"CONSOLIDATED: Phase {phase_name} completed in {phase_duration_ms:.2f}ms"
                    )

            except Exception as e:
                logger.error(
                    f"CONSOLIDATED: Phase {phase_name} threw exception: {e}",
                    exc_info=True,
                )

                if self.phase_logger:
                    self.phase_logger.log_phase_error(
                        context, transaction, phase_name, f"Exception: {e}"
                    )

                return DogmaExecutionResult(
                    success=False,
                    context=context,
                    transaction=transaction,
                    error=f"Phase {phase_name} exception: {e}",
                )

        # Check for phase limit exceeded
        if phase_count >= max_phases:
            error = f"Consolidated execution exceeded maximum phases ({max_phases})"
            logger.error(f"CONSOLIDATED: {error}")
            return DogmaExecutionResult(
                success=False,
                context=context,
                transaction=transaction,
                error=error,
            )

        # Execution completed successfully
        logger.info(
            f"CONSOLIDATED: Execution completed successfully after {phase_count} phases"
        )

        # Generate narrative from state tracker
        try:
            changes_count = len(context.state_tracker.changes)
            logger.info(
                f"CONSOLIDATED: State tracker has {changes_count} state changes"
            )

            narrative = context.state_tracker.generate_narrative(
                viewing_player_id=None,  # Generate public narrative
                group_by_context=True,
            )
            logger.info(
                f"CONSOLIDATED: Generated narrative ({len(narrative) if narrative else 0} chars)"
            )

            if narrative:
                logger.info(
                    f"CONSOLIDATED: Generated narrative for {context.card.name} ({len(narrative)} chars)"
                )
            else:
                logger.warning("CONSOLIDATED: Narrative was empty")
        except Exception as e:
            logger.error(
                f"CONSOLIDATED: Failed to generate narrative: {e}", exc_info=True
            )

        return DogmaExecutionResult(
            success=True, context=context, transaction=transaction
        )

    def resume_from_interaction(
        self,
        transaction_id: str,
        interaction_response: dict[str, Any],
        updated_game=None,
    ) -> DogmaExecutionResult:
        """
        Resume execution after interaction response using consolidated system.

        This maintains the same interface as the original but uses consolidated phases.

        Args:
            transaction_id: The transaction ID to resume
            interaction_response: The interaction response from the player
            updated_game: Optional updated game object with fresh player references (NOT USED - see note below)
        """
        start_time = time.time()

        try:
            transaction = self.transaction_manager.get_transaction(transaction_id)
            if not transaction:
                return self._create_error_result(
                    None,
                    None,
                    None,
                    f"Transaction {transaction_id} not found",
                    transaction_id,
                )

            if not transaction.is_suspended:
                return self._create_error_result(
                    None, None, None, "Transaction is not suspended", transaction_id
                )

            logger.info(f"CONSOLIDATED: Resuming transaction {transaction_id}")

            # Get suspended state
            suspended_phase = transaction.get_suspended_phase()
            suspended_context = transaction.get_suspended_context()

            if not suspended_phase or not suspended_context:
                return self._create_error_result(
                    None, None, None, "Missing suspended state", transaction_id
                )

            # CRITICAL: DO NOT replace suspended_context.game with updated_game!
            # The suspended_context.game already has all the state changes from previous iterations.
            # If we replace it with updated_game (from Redis), we lose all uncommitted changes!
            #
            # NOTE: We intentionally ignore the updated_game parameter. The async_game_manager
            # reloads the game from Redis for optimistic locking, but we must preserve the
            # working copy in suspended_context.game which has all the uncommitted changes.
            # After dogma completes, _sync_game_state_safely will sync these changes back.
            logger.info(
                f"CONSOLIDATED: resume_from_interaction called with updated_game={updated_game is not None} (ignored to preserve state)"
            )

            # CRITICAL FIX: Clear ALL OLD interaction variables to prevent reuse
            # But DON'T clear final_interaction_request yet - _apply_interaction_response needs it to extract store_result
            # ALSO don't clear custom store variables (selected_achievement, etc) - they will be SET by _apply_interaction_response
            logger.debug(
                "Clearing common interaction variables (NOT custom store vars) from suspended context"
            )
            # Use without_variable() to REMOVE keys, not set to None
            suspended_context = suspended_context.without_variable(
                "interaction_response"
            )
            suspended_context = suspended_context.without_variable(
                "selected_achievements"  # Plural - standard field
            )
            suspended_context = suspended_context.without_variable("selected_cards")
            suspended_context = suspended_context.without_variable("chosen_option")
            suspended_context = suspended_context.without_variable(
                "interaction_cancelled"
            )
            # NOTE: We do NOT clear custom store variables like "selected_achievement" (singular)
            # because _apply_interaction_response will set them and we need them to persist

            # CONTEXT PERSISTENCE DEBUG: Log what variables we have before applying response
            logger.debug(
                f"CONTEXT DEBUG: Before applying response, suspended context has variables: {list(suspended_context.variables.keys())}"
            )
            for key, value in suspended_context.variables.items():
                if (
                    isinstance(value, list)
                    and len(value) > 0
                    and hasattr(value[0], "name")
                ):
                    logger.debug(
                        f"CONTEXT DEBUG: {key} = [{', '.join(c.name for c in value)}]"
                    )
                else:
                    logger.debug(f"CONTEXT DEBUG: {key} = {value}")

            # Apply interaction response to context
            suspended_context = self._apply_interaction_response(
                suspended_context, interaction_response
            )

            # CONTEXT PERSISTENCE DEBUG: Log what variables we have after applying response
            logger.info(
                f"📝 RESUME: After applying response, context has {len(suspended_context.variables)} variables"
            )
            logger.info(f"📝   Variables: {list(suspended_context.variables.keys())}")
            # Log key variables
            for key in [
                "selected_achievement",
                "selected_achievements",
                "selected_cards",
                "chosen_option",
            ]:
                val = suspended_context.get_variable(key)
                if val is not None:
                    if isinstance(val, list):
                        logger.info(f"📝   {key} = [{len(val)} items]")
                    else:
                        logger.info(f"📝   {key} = {getattr(val, 'name', val)}")
            for key, value in suspended_context.variables.items():
                if (
                    isinstance(value, list)
                    and len(value) > 0
                    and hasattr(value[0], "name")
                ):
                    logger.debug(
                        f"CONTEXT DEBUG: {key} = [{', '.join(c.name for c in value)}]"
                    )
                else:
                    logger.debug(f"CONTEXT DEBUG: {key} = {value}")

            # Log resumption
            if self.phase_logger:
                self.phase_logger.log_phase_resume(
                    suspended_context,
                    transaction,
                    suspended_phase.get_phase_name(),
                    interaction_response,
                )

            # CRITICAL FIX: The suspended_phase is the actual phase object we need to resume
            # We need to continue the phase loop from this phase, not start over
            logger.info("CONSOLIDATED: Resuming with suspended phase directly")

            # Resume execution by continuing the phase loop from the suspended phase
            # Create a modified version of _execute_consolidated_phases that starts with the given phase
            result = self._continue_from_phase(
                suspended_phase, suspended_context, transaction
            )

            # Clear suspension state ONLY if execution is complete (success AND no more interactions)
            # This prevents losing state if something fails during resume OR if more interactions are needed
            if result.success and not result.interaction_required:
                transaction.clear_suspended_state()
                logger.info(
                    "CONSOLIDATED: Cleared suspended state after complete execution"
                )

            # Handle completion
            if result.success and not result.interaction_required:
                self.transaction_manager.complete_transaction(
                    transaction.id, result.results
                )
                self._successful_executions += 1

            # Activity logging
            duration = time.time() - start_time
            if self.activity_logger:
                self._log_activity(result, duration)

            logger.info(f"CONSOLIDATED: Resume completed in {duration:.3f}s")
            return result

        except Exception as e:
            logger.error(
                f"CONSOLIDATED: Resume failed with exception: {e}", exc_info=True
            )
            # Get context info from suspended state for error reporting
            # Use locals() to safely check if suspended_context was defined
            try:
                ctx = locals().get("suspended_context")
                if ctx:
                    game = ctx.game
                    player = ctx.activating_player
                    card = ctx.card
                else:
                    # suspended_context not yet defined - error occurred early
                    game = None
                    player = None
                    card = None
            except (AttributeError, Exception):
                # Suspended context object may not have expected attributes
                game = None
                player = None
                card = None
            return self._create_error_result(
                game, player, card, f"Resume failed: {e}", transaction_id
            )

    def _determine_interaction_type(
        self, context: DogmaContext, phase_name: str
    ) -> str:
        """Determine interaction type based on context and phase"""

        # Check context variables first (most reliable)
        if context.get_variable("in_demand_phase", False):
            return "demand"
        elif context.get_variable("in_sharing_phase", False):
            return "sharing"

        # Fall back to phase name analysis
        if "Demand" in phase_name:
            return "demand"
        elif "Sharing" in phase_name:
            return "sharing"
        else:
            return "player"

    def _apply_interaction_response(
        self, context: DogmaContext, response: dict[str, Any]
    ):
        """Apply interaction response to context (same logic as original)"""

        logger.debug(f" _apply_interaction_response called with response: {response}")

        # Store the response for processing in resolution phase
        context = context.with_variable("interaction_response", response)

        # Track which player just responded (for preserving response variables per player)
        if "player_id" in response:
            context = context.with_variable(
                "_last_responding_player_id", response["player_id"]
            )

        # Also apply directly for compatibility
        if "selected_cards" in response:
            # Convert card IDs to Card objects for primitive compatibility
            selected_data = response["selected_cards"]
            resolved_cards = []

            # If selected_data contains IDs, resolve them to Card objects
            if selected_data and isinstance(selected_data[0], str):
                logger.debug(f" Resolving card IDs to Card objects: {selected_data}")
                # Find cards by ID in the game state
                for card_id in selected_data:
                    found_card = None
                    # Search in all players' hands, boards, and score piles
                    for player in context.game.players:
                        # Check hand
                        for card in player.hand:
                            # Match by card_id OR card name (AI agents sometimes use name instead of ID)
                            if (
                                getattr(card, "card_id", None) == card_id
                                or getattr(card, "name", None) == card_id
                            ):
                                found_card = card
                                logger.debug(
                                    f"Found card {card_id} -> {card.name} in {player.name}'s hand"
                                )
                                break
                        if found_card:
                            break
                        # Check board
                        for card in player.board.get_all_cards():
                            # Match by card_id OR card name
                            if (
                                getattr(card, "card_id", None) == card_id
                                or getattr(card, "name", None) == card_id
                            ):
                                found_card = card
                                logger.debug(
                                    f"Found card {card_id} -> {card.name} in {player.name}'s board"
                                )
                                break
                        if found_card:
                            break
                        # Check score pile
                        for card in player.score_pile:
                            # Match by card_id OR card name
                            if (
                                getattr(card, "card_id", None) == card_id
                                or getattr(card, "name", None) == card_id
                            ):
                                found_card = card
                                logger.debug(
                                    f"Found card {card_id} -> {card.name} in {player.name}'s score pile"
                                )
                                break
                        if found_card:
                            break
                    if found_card:
                        # Store the actual Card object reference
                        # The Card object must be kept as-is, not copied, to ensure
                        # object identity works with list membership checks
                        resolved_cards.append(found_card)
                        logger.debug(
                            f"Storing reference to {found_card.name} in context"
                        )
                    else:
                        logger.warning(f"Could not find card with ID: {card_id}")
                logger.debug(
                    f"Resolved {len(resolved_cards)} cards: {[c.name for c in resolved_cards]}"
                )
                selected_cards = resolved_cards
            else:
                # Already Card objects or empty
                selected_cards = selected_data

            context = context.with_variable("selected_cards", selected_cards)

            # CRITICAL FIX: Store under the custom store_result name from the primitive
            # SelectCards now stores this in "pending_store_result" before creating interaction
            custom_store_name = context.get_variable("pending_store_result")

            if custom_store_name:
                # CRITICAL: Check if there are auto-selected cards that need to be merged
                # This handles SelectHighest/SelectLowest when only tied cards are shown for selection
                auto_selected_key = f"{custom_store_name}_auto_selected"
                auto_selected = context.get_variable(auto_selected_key)
                
                if auto_selected:
                    # Merge: auto-selected + player's choice
                    merged_cards = auto_selected + selected_cards
                    logger.info(
                        f"🔀 MERGE: Merging {len(auto_selected)} auto-selected + {len(selected_cards)} player-selected = {len(merged_cards)} total for '{custom_store_name}'"
                    )
                    logger.debug(
                        f"  Auto-selected: {[getattr(c, 'name', str(c)) for c in auto_selected]}"
                    )
                    logger.debug(
                        f"  Player-selected: {[getattr(c, 'name', str(c)) for c in selected_cards]}"
                    )
                    logger.debug(
                        f"  Merged result: {[getattr(c, 'name', str(c)) for c in merged_cards]}"
                    )
                    context = context.with_variable(custom_store_name, merged_cards)
                    # Clean up the temporary auto-selected variable
                    context = context.without_variable(auto_selected_key)
                else:
                    # No auto-selected cards - just store player's selection
                    logger.info(
                        f"🎯 Storing selected cards in custom variable: {custom_store_name}"
                    )
                    context = context.with_variable(custom_store_name, selected_cards)
                
                # Clear pending_store_result now that we've used it
                context = context.without_variable("pending_store_result")

            # Also store under common action primitive variable names for compatibility
            common_store_names = [
                "cards_to_return",  # Tools Effect 1
                "selected_cards",  # Default
                "cards_to_select",  # Masonry and others
            ]

            for store_name in common_store_names:
                context = context.with_variable(store_name, selected_cards)

        # Handle achievement selections (from UI or AI)
        # AI sends "selected_achievement" (singular), UI sends "selected_achievements" (plural)
        if "selected_achievements" in response:
            selected_achievements = response["selected_achievements"]
        elif "selected_achievement" in response:
            # AI sends singular - convert to list for consistent processing
            single_achievement = response["selected_achievement"]
            selected_achievements = [single_achievement] if single_achievement else []
        else:
            selected_achievements = None

        if selected_achievements is not None:
            logger.debug(
                " ACHIEVEMENT RESPONSE: Received selected_achievements from UI"
            )
            logger.debug(f" ACHIEVEMENT RESPONSE: Type: {type(selected_achievements)}")
            logger.debug(f" ACHIEVEMENT RESPONSE: Value: {selected_achievements}")

            # CRITICAL FIX: Store under the custom store_result name from the primitive config
            # Get the interaction data to find the custom store_result key
            interaction_request = context.get_variable("final_interaction_request")
            custom_store_name = None

            if interaction_request:
                # Extract store_result from interaction data
                interaction_data = getattr(interaction_request, "data", {})
                if isinstance(interaction_data, dict):
                    custom_store_name = interaction_data.get("store_result")
                logger.debug(
                    f"ACHIEVEMENT RESPONSE: Found custom store name: {custom_store_name}"
                )

            # Store in custom variable if specified
            if custom_store_name:
                # CRITICAL: selected_achievements can contain dicts with card_id/name OR just strings
                # We must look up the actual achievement objects from game state
                achievement_objects = []
                for achievement_data in selected_achievements:
                    found_achievement = None

                    # Extract identifier from dict or use string directly
                    if isinstance(achievement_data, dict):
                        # Achievement sent as dict with card_id and name
                        achievement_id = achievement_data.get(
                            "card_id"
                        ) or achievement_data.get("name")
                        logger.debug(
                            f"ACHIEVEMENT RESPONSE: Resolving dict achievement with ID: {achievement_id}"
                        )
                    else:
                        # Achievement sent as string (name or card_id)
                        achievement_id = achievement_data
                        logger.debug(
                            f"ACHIEVEMENT RESPONSE: Resolving string achievement: {achievement_id}"
                        )

                    # Search in available_achievements (where selectable achievements are)
                    if hasattr(context.game, "available_achievements"):
                        for ach in context.game.available_achievements:
                            # Match by card_id OR name (same pattern as card selection)
                            if (
                                getattr(ach, "card_id", None) == achievement_id
                                or getattr(ach, "name", None) == achievement_id
                            ):
                                found_achievement = ach
                                logger.debug(
                                    f"ACHIEVEMENT RESPONSE: Found achievement {achievement_id} -> {ach.name} in available_achievements"
                                )
                                break

                    # Fall back to searching achievement_cards deck if not found
                    if not found_achievement:
                        for age, achievements in context.game.deck_manager.achievement_cards.items():
                            for ach in achievements:
                                if (
                                    getattr(ach, "card_id", None) == achievement_id
                                    or getattr(ach, "name", None) == achievement_id
                                ):
                                    found_achievement = ach
                                    logger.debug(
                                        f"ACHIEVEMENT RESPONSE: Found achievement {achievement_id} -> {ach.name} in achievement_cards[{age}]"
                                    )
                                    break
                            if found_achievement:
                                break

                    if found_achievement:
                        achievement_objects.append(found_achievement)
                        logger.debug(
                            f"ACHIEVEMENT RESPONSE: Found achievement object for '{achievement_id}'"
                        )
                    else:
                        logger.warning(
                            f"ACHIEVEMENT RESPONSE: Could not find achievement object for '{achievement_data}'"
                        )

                # Check if variable name is singular (ends with _achievement)
                # If singular, store single object; if plural, store list
                if custom_store_name.endswith("_achievement"):
                    # Singular - store first achievement OBJECT or None
                    value = achievement_objects[0] if achievement_objects else None
                    logger.debug(
                        f"ACHIEVEMENT RESPONSE: Storing SINGLE achievement OBJECT in '{custom_store_name}': {value.name if value else None}"
                    )
                else:
                    # Plural - store list of OBJECTS
                    value = achievement_objects
                    logger.debug(
                        f"ACHIEVEMENT RESPONSE: Storing LIST of achievement OBJECTS in '{custom_store_name}': {[a.name for a in value]}"
                    )

                context = context.with_variable(custom_store_name, value)

            # Also store in standard 'selected_achievements' for compatibility
            logger.debug(
                " ACHIEVEMENT RESPONSE: Storing in context with key 'selected_achievements'"
            )
            context = context.with_variable(
                "selected_achievements", selected_achievements
            )
            logger.debug(
                f"ACHIEVEMENT RESPONSE: Successfully stored, context now has: {list(context.variables.keys())}"
            )

        # Normalize color/option field names — AI may use chosen_color instead of chosen_option
        chosen = response.get("chosen_option") or response.get("chosen_color")
        if chosen is not None:
            context = context.with_variable("chosen_option", chosen)
            # CRITICAL FIX: Also store as chosen_symbol for cross-effect persistence
            # SelectSymbol stores to chosen_symbol, but scheduler clears chosen_option on effect transitions
            # This ensures the selected symbol is available to subsequent effects (e.g., Climatology demand)
            context = context.with_variable("chosen_symbol", chosen)
            logger.debug(f"SYMBOL RESPONSE: Set chosen_option and chosen_symbol = {chosen}")

        # Handle color selection responses (both old and new field names for compatibility)
        color_value = response.get("selected_color_choice") or response.get("selected_color")
        if color_value:
            context = context.with_variable("selected_color_choice", color_value)
            context = context.with_variable("selected_color", color_value)
            logger.debug(f" COLOR RESPONSE: Set selected_color_choice and selected_color = {color_value}")

        # Handle explicit decline flag (for optional selections)
        if "decline" in response:
            context = context.with_variable("decline", response["decline"])

        if "cancelled" in response:
            context = context.with_variable(
                "interaction_cancelled", response.get("cancelled", False)
            )

        # CRITICAL FIX: Clear final_interaction_request AFTER using it to extract store_result
        # This prevents interaction request reuse bug while allowing store_result extraction
        logger.debug(
            " Clearing final_interaction_request from context after extracting store_result"
        )
        context = context.without_variable("final_interaction_request")

        return context

    def _record_execution_metrics(self, result: DogmaExecutionResult, duration: float):
        """Record execution metrics for monitoring"""

        if not self.metrics:
            return

        # Record overall execution metrics
        phase_count = len(result.context.get_variable("phase_sequence", []))
        results_count = len(result.results)

        logger.debug(
            f"CONSOLIDATED METRICS: {phase_count} phases, {results_count} results, {duration:.3f}s"
        )

    def _create_error_result(
        self,
        game,
        player,
        card,
        error_message: str,
        transaction_id: str | None = None,
    ) -> DogmaExecutionResult:
        """Create an error result with dummy data"""

        dummy_transaction = DogmaTransaction(
            id=transaction_id or str(uuid4()),
            game_id=getattr(game, "game_id", "unknown") if game else "unknown",
            player_id=getattr(player, "id", "unknown") if player else "unknown",
            card_name=getattr(card, "name", "unknown") if card else "unknown",
            started_at=datetime.now(),
        )

        # CRITICAL: Only create context if we have valid game/player/card objects
        # DogmaContext.create_initial() requires non-None values (calls game.players)
        if game and player and card:
            dummy_context = DogmaContext.create_initial(game, player, card)
        else:
            # If we don't have valid objects, context will be None
            # DogmaExecutionResult can handle None context in error cases
            dummy_context = None

        return DogmaExecutionResult(
            success=False,
            context=dummy_context,
            transaction=dummy_transaction,
            error=error_message,
        )

    def _log_activity(self, result: DogmaExecutionResult, duration: float):
        """Log activity (same interface as original executor)"""

        if not self.activity_logger:
            return

        try:
            activity_data = {
                "action": "dogma_executed",
                "card": result.context.card.name if result.context.card else "unknown",
                "player": result.context.activating_player.name
                if result.context.activating_player
                else "unknown",
                "success": result.success,
                "duration_ms": int(duration * 1000),
                "phase_count": len(result.context.get_variable("phase_sequence", [])),
                "consolidated_system": True,  # Flag to indicate consolidated system usage
                "results_count": len(result.results),
                "interaction_required": result.interaction_required,
                "transaction_id": result.transaction.id,
            }

            if not result.success:
                activity_data["error"] = result.error

            # Use same logging interface as original
            game_id = getattr(result.transaction, "game_id", None)
            player_id = (
                result.context.activating_player.id
                if result.context.activating_player
                else "unknown"
            )

            if hasattr(self.activity_logger, "log_activity"):
                self.activity_logger.log_activity(
                    player_id=player_id,
                    game_id=game_id,
                    activity_type="dogma",
                    **activity_data,
                )
            elif hasattr(self.activity_logger, "log_player_action"):
                self.activity_logger.log_player_action(
                    game_id=game_id,
                    player_id=player_id,
                    action_type="dogma",
                    action_data=activity_data,
                    result={"success": result.success},
                    duration_ms=int(duration * 1000),
                )

        except Exception as e:
            logger.warning(f"CONSOLIDATED: Activity logging failed: {e}")

    # Additional methods that maintain original interface

    def get_transaction_status(self, transaction_id: str) -> dict[str, Any] | None:
        """Get transaction status (same interface as original)"""
        return (
            self.transaction_manager.get_transaction_status(transaction_id)
            if hasattr(self.transaction_manager, "get_transaction_status")
            else None
        )

    def get_debug_info(
        self, transaction_id: str | None = None, game_id: str | None = None
    ) -> dict[str, Any]:
        """Get debug info with consolidated system enhancements"""

        debug_info = {}

        # Original debug info
        if self.phase_logger and transaction_id:
            debug_info["phase_history"] = [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "phase_name": event.phase_name,
                    "transition_type": event.transition_type,
                    "duration_ms": event.phase_duration_ms,
                    "consolidated_phase": True,  # Flag consolidated phases
                }
                for event in self.phase_logger.get_transaction_history(transaction_id)
            ]

        # Consolidated system metrics
        if self.metrics:
            debug_info["consolidated_metrics"] = self.metrics.get_performance_report()
            debug_info["execution_stats"] = {
                "total_executions": self._total_executions,
                "successful_executions": self._successful_executions,
                "success_rate": self._successful_executions
                / max(1, self._total_executions),
            }

        debug_info["system_type"] = "consolidated_8_phase"
        debug_info["phase_reduction"] = "15+ phases → 8 phases"

        return debug_info

    def cleanup_expired_transactions(self, max_age_hours: int = 24):
        """Clean up expired transactions (same interface as original)"""
        return self.transaction_manager.cleanup_expired_transactions(max_age_hours)

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary specific to consolidated system"""

        if not self.metrics:
            return {"metrics_disabled": True}

        # WEEK 4 ENHANCEMENT: Include context optimization statistics
        optimization_stats = get_context_optimization_stats()

        return {
            "system_type": "consolidated_8_phase",
            "total_executions": self._total_executions,
            "successful_executions": self._successful_executions,
            "success_rate": self._successful_executions
            / max(1, self._total_executions),
            "phase_metrics": self.metrics.get_performance_report(),
            "context_optimization": optimization_stats,
            "efficiency_improvement": "~40% fewer phases than original system",
            "week_4_optimizations": {
                "copy_on_write_contexts": True,
                "memory_allocation_reduction": True,
                "context_caching": True,
            },
        }
