"""
Action Scheduler - Unified action execution.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from dogma_v2.core.constants import SYSTEM_CONTEXT_VARS
from dogma_v2.core.context import DogmaContext
from dogma_v2.interaction_request import InteractionRequest
from models.player import Player

from .result import ActionExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class SchedulerResult:
    """
    Result of executing a complete ActionPlan.

    This aggregates the outcomes of all PlannedActions in the plan,
    providing summary information and final context state.
    """

    success: bool
    context: "DogmaContext"  # type: ignore
    all_results: list  # Aggregated results from all actions

    # Completion state
    completed_actions: int  # Number of actions completed
    total_actions: int  # Total actions in plan

    # Suspension state
    requires_interaction: bool = False
    interaction: Optional[InteractionRequest] = None
    suspended_at_action: int = 0  # Which action index suspended at
    resume_action_index: int = (
        0  # For mid-action resumption (which primitive to resume at)
    )

    # Demand routing state
    routes_to_demand: bool = False
    demand_config: dict | None = None

    # Error state
    error: str | None = None

    # Tracing state (Phase 10)
    trace: Optional["ExecutionTrace"] = None  # type: ignore


class ActionScheduler:
    """
    Executes actions with uniform handling of cross-cutting concerns.

    Phase 2 Implementation: Just the execute_action method.
    Plan execution will be added in Phase 4.
    """

    def __init__(self, trace_recorder: Optional["TraceRecorder"] = None):  # type: ignore
        """
        Initialize scheduler.

        Args:
            trace_recorder: Optional trace recorder for execution tracing (Phase 10)
        """
        self.trace_recorder = trace_recorder

    def execute_action(
        self,
        effect: list[dict],
        effect_index: int,
        player: Player,
        is_sharing: bool,
        context: DogmaContext,
        resume_action_index: int = 0,
        is_resuming_after_interaction: bool = False,
        continuing_after_sharing: bool = False,
        is_demand: bool = False,
    ) -> ActionExecutionResult:
        """
        Execute all primitives in an effect for a player.

        This method replaces:
        - SharingPhase._execute_effect_for_player()
        - ExecutionPhase._execute_activating_effect()

        Args:
            effect: List of action primitive dicts
            effect_index: Which effect number (0, 1, 2...)
            player: Player to execute for
            is_sharing: Is this a sharing execution?
            context: Current dogma context
            resume_action_index: Action index to start from (for resumption)
            is_resuming_after_interaction: True if resuming same action after interaction suspension

        Returns:
            ActionExecutionResult with outcome
        """
        from dogma_v2.effects.factory import EffectFactory

        try:
            # CRITICAL: Clear effect-scoped variables ONLY when activating player starts truly fresh execution
            # The key insight: resume_action_index > 0 means THIS action is resuming mid-effect
            # (after its own suspension), so variables must be preserved for subsequent primitives
            #
            # Clear variables when:
            # - Activating player (not is_sharing AND not is_demand)
            # - Starting from beginning (resume_action_index == 0)
            # - NOT resuming after interaction response (has_interaction_response)
            #
            # This ensures:
            # 1. Sharing players' variables are cleared before activating player starts (fresh execution)
            # 2. Activating player's own variables are preserved when resuming after suspension
            # 3. Demand executions preserve variables (vulnerable opponents need their selected_cards)
            execution_context = context
            has_interaction_response = context.has_variable("interaction_response")
            should_clear = (
                not is_sharing
                and not is_demand
                and resume_action_index == 0
                and not has_interaction_response
            )

            # CRITICAL: Clear interaction_response AFTER checking it
            # This allows nested actions (like ConditionalAction) to see that we're
            # resuming after an interaction, so they don't clear selected_cards
            if has_interaction_response:
                logger.debug(
                    f"SCHEDULER: Clearing interaction_response after checking it "
                    f"(resume_action_index={resume_action_index})"
                )
                execution_context = execution_context.without_variable(
                    "interaction_response"
                )

            if should_clear:
                # This is activating player starting fresh execution (not resuming mid-effect)
                # Clear any effect-scoped variables that may have been set by sharing players
                logger.info(
                    f"SCHEDULER: Clearing effect-scoped variables for activating player {player.name} "
                    f"(starting fresh, resume_action_index={resume_action_index})"
                )
                effect_scoped_vars = [
                    "selected_cards",
                    "selected_card",
                    "selected_achievements",
                    "selected_achievement",
                    "chosen_option",
                    "player_choice",
                    "decline",
                    "interaction_cancelled",
                ]
                for var_name in effect_scoped_vars:
                    if execution_context.has_variable(var_name):
                        logger.info(f"SCHEDULER: Clearing variable: {var_name}")
                        execution_context = execution_context.without_variable(var_name)
            elif resume_action_index > 0:
                # Resuming mid-effect - DO NOT clear effect-scoped variables
                # They must persist so subsequent primitives can access them
                logger.info(
                    f"SCHEDULER: NOT clearing variables for {player.name} "
                    f"(resuming mid-effect at action {resume_action_index + 1}, is_sharing={is_sharing})"
                )

            # Set current player for execution
            execution_context = execution_context.with_player(player)

            # CRITICAL: Initialize sharing context before executing effect for sharing player
            if is_sharing:
                if execution_context.sharing.current_sharing_player != player.id:
                    logger.debug(f"SCHEDULER: Starting sharing for {player.name}")
                    execution_context = execution_context.start_sharing_for_player(
                        player.id
                    )
                else:
                    logger.debug(
                        f"SCHEDULER: Resuming sharing for {player.name} (already started)"
                    )

            # CRITICAL: Set demanding_player for demand effects
            # When executing demand actions, the current_player is the vulnerable target
            # but we need access to the demanding player (activating_player) for sources like "demanding_player_hand"
            if is_demand and not execution_context.get_variable("demanding_player"):
                logger.debug(f"SCHEDULER: Setting demanding_player to {context.activating_player.name} for demand execution")
                execution_context = execution_context.with_variable(
                    "demanding_player", context.activating_player
                )

            # Set effect context for state tracking
            effect_context = f"effect_{effect_index + 1}"
            execution_context = execution_context.with_variable(
                "current_effect_context", effect_context
            )
            execution_context = execution_context.with_variable(
                "current_effect_index", effect_index
            )
            execution_context = execution_context.with_variable(
                "is_sharing_execution", is_sharing
            )

            # Execute all action primitives in this effect
            all_results = []

            if resume_action_index > 0:
                logger.info(
                    f"SCHEDULER: *** RESUMING effect from action {resume_action_index + 1}/{len(effect)} "
                    f"(effect has {len(effect)} primitives, will execute primitives {resume_action_index + 1} through {len(effect)})"
                )
            else:
                logger.info(
                    f"SCHEDULER: Starting effect from beginning, {len(effect)} primitives to execute"
                )

            logger.info(
                f"SCHEDULER: Executing loop range({resume_action_index}, {len(effect)}) "
                f"for player {player.name}, effect_index={effect_index}"
            )

            # DEBUG: Track loop entry
            logger.debug(
                f"SCHEDULER DEBUG: LOOP ENTRY - range({resume_action_index}, {len(effect)}) "
                f"= iterations [{resume_action_index}..{len(effect)-1}], total={len(effect)-resume_action_index} iterations"
            )

            for action_idx in range(resume_action_index, len(effect)):
                # DEBUG: Track each iteration
                logger.debug(
                    f"SCHEDULER DEBUG: LOOP ITERATION START - action_idx={action_idx}, "
                    f"primitive #{action_idx + 1}/{len(effect)}"
                )

                primitive = effect[action_idx]
                logger.info(
                    f"SCHEDULER: *** Executing Action {action_idx + 1}/{len(effect)}: {primitive.get('type', 'unknown')} "
                    f"(resume_action_index was {resume_action_index})"
                )
                logger.debug(
                    f"SCHEDULER DEBUG: Primitive details - type={primitive.get('type')}, "
                    f"config={primitive}"
                )

                # Create and execute primitive
                effect_instance = EffectFactory.create(primitive)
                result = effect_instance.execute(execution_context)

                # DEBUG: Track primitive execution result
                logger.debug(
                    f"SCHEDULER DEBUG: PRIMITIVE EXECUTED - action_idx={action_idx}, "
                    f"type={primitive.get('type')}, success={result.success}, "
                    f"requires_interaction={result.requires_interaction}, "
                    f"routes_to_demand={result.routes_to_demand}"
                )

                # Update context with variables
                if result.variables:
                    for key, value in result.variables.items():
                        execution_context = execution_context.with_variable(key, value)

                # Check for interaction required
                if result.requires_interaction:
                    logger.debug(
                        f"SCHEDULER: Action {action_idx + 1} requires interaction"
                    )
                    # CRITICAL FIX: Resume at SAME action (not next), because:
                    # 1. Container actions (ConditionalAction, ChooseOption) may have
                    #    sub-actions after the interactive one that still need to execute
                    # 2. All interactive primitives are idempotent on re-execution -
                    #    they check for existing selections and return SUCCESS immediately
                    logger.debug(
                        f"SCHEDULER DEBUG: SUSPENDING FOR INTERACTION - action_idx={action_idx}, "
                        f"resume_action_index will be {action_idx}, "
                        f"same primitive #{action_idx + 1}/{len(effect)} will re-execute on resumption"
                    )
                    return ActionExecutionResult(
                        success=result.success,
                        context=execution_context,
                        results=all_results + result.results,
                        requires_interaction=True,
                        interaction=result.interaction_request,
                        resume_action_index=action_idx,  # Resume at SAME action (idempotent)
                    )

                # Check for demand routing
                if result.routes_to_demand:
                    logger.debug(f"SCHEDULER: Action {action_idx + 1} routes to demand")
                    # DEBUG: Track suspension
                    logger.debug(
                        f"SCHEDULER DEBUG: SUSPENDING FOR DEMAND - action_idx={action_idx}, "
                        f"resume_action_index will be {action_idx + 1}"
                    )
                    return ActionExecutionResult(
                        success=result.success,
                        context=execution_context,
                        results=all_results + result.results,
                        routes_to_demand=True,
                        demand_config=getattr(result, "demand_config", None),
                        resume_action_index=action_idx + 1,  # Resume at NEXT action
                    )

                # Check for failure
                if not result.success:
                    logger.error(
                        f"SCHEDULER: Action {action_idx + 1} failed: {result.error}"
                    )
                    return ActionExecutionResult(
                        success=False,
                        context=execution_context,
                        results=all_results + result.results,
                        error=result.error,
                    )

                # Collect results
                all_results.extend(result.results)

                # DEBUG: Track iteration completion
                logger.debug(
                    f"SCHEDULER DEBUG: LOOP ITERATION END - action_idx={action_idx} completed successfully, "
                    f"continuing to next iteration (if any)"
                )

            # DEBUG: Track loop exit
            logger.debug(
                f"SCHEDULER DEBUG: LOOP EXIT - All {len(effect)} primitives completed successfully"
            )

            # Cities expansion: Check if we need to double execution for endorsed dogma
            # Only double for activating player, non-demand effects
            is_endorsed = execution_context.get_variable("endorsed", False)
            is_activating_player = not is_sharing

            if is_endorsed and is_activating_player and not is_demand:
                logger.info(
                    f"ENDORSE: Dogma is endorsed - executing effect {effect_index + 1} a second time "
                    f"for activating player {player.name}"
                )

                # Execute the effect a second time (all primitives again)
                second_execution_results = []
                for action_idx in range(len(effect)):
                    primitive = effect[action_idx]
                    logger.info(
                        f"ENDORSE: *** Second Execution - Action {action_idx + 1}/{len(effect)}: "
                        f"{primitive.get('type', 'unknown')}"
                    )

                    # Create and execute primitive
                    effect_instance = EffectFactory.create(primitive)
                    result = effect_instance.execute(execution_context)

                    # Update context with variables
                    if result.variables:
                        for key, value in result.variables.items():
                            execution_context = execution_context.with_variable(key, value)

                    # Check for interaction required (suspend doubling)
                    if result.requires_interaction:
                        logger.warning(
                            f"ENDORSE: Second execution requires interaction at action {action_idx + 1}, "
                            f"suspending doubling - NOT EXPECTED (primitives should be deterministic)"
                        )
                        # Don't double if interaction required - just return first execution results
                        break

                    # Check for demand routing (suspend doubling)
                    if result.routes_to_demand:
                        logger.warning(
                            f"ENDORSE: Second execution routes to demand at action {action_idx + 1}, "
                            f"suspending doubling - demands should NOT be doubled"
                        )
                        # Don't double if demand routed - just return first execution results
                        break

                    # Check for failure
                    if not result.success:
                        logger.error(
                            f"ENDORSE: Second execution failed at action {action_idx + 1}: {result.error}"
                        )
                        # Don't fail entire effect, just return first execution results
                        break

                    # Collect results from second execution
                    second_execution_results.extend(result.results)

                # Merge second execution results with first execution
                all_results.extend(second_execution_results)
                logger.info(
                    f"ENDORSE: Completed doubled execution - "
                    f"{len(all_results)} total results (first + second execution)"
                )

            # All actions in effect completed successfully (possibly doubled)
            return ActionExecutionResult(
                success=True,
                context=execution_context,
                results=all_results,
            )

        except Exception as e:
            logger.error(
                f"SCHEDULER: Exception executing effect: {e}",
                exc_info=True,
            )
            return ActionExecutionResult(
                success=False,
                context=context,
                results=[],
                error=f"Effect execution failed: {e}",
            )

    def _apply_result(
        self,
        context: DogmaContext,
        result: ActionExecutionResult,
        action: "PlannedAction",  # type: ignore
    ) -> DogmaContext:
        """
        Apply execution result to context.

        Handles:
        - Adding results to context
        - Clearing player-scoped variables if needed
        - Updating sharing context if needed

        Args:
            context: Current context
            result: Execution result
            action: Action that was executed

        Returns:
            Updated context
        """
        updated_context = result.context

        # Add results
        for new_result in result.results:
            updated_context = updated_context.with_result(new_result)

        # CRITICAL FIX: Track demand transfers for inline demand execution
        # When demand_actions are executed inline (not through DemandPhase), we need to
        # accumulate transferred_cards and set demand_transferred_count for conditional checks
        if action.is_demand:
            transferred_this_action = updated_context.get_variable("transferred_cards", [])
            if transferred_this_action:
                # Accumulate total demand transfers across all vulnerable players
                total_demand_transfers = updated_context.get_variable(
                    "_demand_transfer_count_accumulator", 0
                )
                total_demand_transfers += len(transferred_this_action)
                updated_context = updated_context.with_variable(
                    "_demand_transfer_count_accumulator", total_demand_transfers
                )
                logger.info(
                    f"SCHEDULER: Demand transfer count accumulated: {total_demand_transfers} "
                    f"(+{len(transferred_this_action)} from {action.player.name})"
                )

        # Clear player-specific variables if needed
        if action.clear_variables_after:
            logger.debug("SCHEDULER: Clearing player-specific variables")
            system_vars = SYSTEM_CONTEXT_VARS
            for var_name in list(updated_context.variables.keys()):
                if var_name not in system_vars:
                    updated_context = updated_context.without_variable(var_name)

        # Update sharing context if needed
        if action.update_sharing_context:
            # Determine if player actually shared (did something with cards)
            shared = self._did_player_share(
                updated_context, action.player, action.effect_index
            )

            if shared:
                logger.debug(
                    f"SCHEDULER: {action.player.name} shared on effect {action.effect_index + 1}"
                )

            # Update sharing context
            updated_sharing = updated_context.sharing.complete_sharing_for_player(
                action.player.id, shared=shared
            )
            updated_context = updated_context.with_sharing_context(updated_sharing)

        return updated_context

    def _did_player_share(
        self,
        context: DogmaContext,
        player: Player,
        effect_index: int,
    ) -> bool:
        """
        Check if player actually did something with cards during this effect.

        Per The Singularity rules, sharing occurs when an opponent's use of the
        shared effect causes them to "do something with a card."

        Args:
            context: Current context with state_tracker
            player: Player to check
            effect_index: Effect index

        Returns:
            True if player performed any sharing-qualifying action
        """
        effect_context = f"effect_{effect_index + 1}"

        sharing_change_types = {
            "draw",
            "transfer",
            "meld",
            "score",
            "tuck",
            "splay",
            "return",
            "achieve",
        }

        for change in context.state_tracker.changes:
            if change.context != effect_context:
                continue

            if change.change_type not in sharing_change_types:
                continue

            player_name = change.data.get("player")
            from_player = change.data.get("from_player")
            to_player = change.data.get("to_player")

            if (
                player_name == player.name
                or from_player == player.name
                or to_player == player.name
            ):
                return True

        return False

    def execute_plan(
        self,
        plan: "ActionPlan",  # type: ignore
        context: "DogmaContext",  # type: ignore
    ) -> SchedulerResult:
        """
        Execute a complete ActionPlan.

        This method will be used in Phase 5+ to replace the manual iteration
        loops in SharingPhase and ExecutionPhase.

        Args:
            plan: The ActionPlan to execute
            context: Current dogma context

        Returns:
            SchedulerResult with aggregated outcomes
        """
        from datetime import datetime

        from dogma_v2.scheduling.plan import ActionPlan
        from dogma_v2.scheduling.trace import TraceEvent

        logger.debug(
            f"SCHEDULER: Executing plan with {len(plan.actions)} actions "
            f"(starting at action {plan.resumption_index})"
        )

        # Start trace if recorder is enabled
        trace = None
        if self.trace_recorder:
            card_name = context.variables.get("card_name", "Unknown")
            plan_type = (
                "sharing" if any(a.is_sharing for a in plan.actions) else "execution"
            )
            trace = self.trace_recorder.start_trace(
                game_id=context.game.game_id,
                card_name=card_name,
                plan_type=plan_type,
                total_actions=len(plan.actions),
            )

        current_context = context
        all_results = []
        current_plan = plan

        # Track if we're resuming after interaction suspension
        # This happens when plan starts at non-zero index (was previously suspended)
        initial_resumption_index = plan.resumption_index
        is_first_action = True
        previous_action = None

        # Execute actions until plan is complete or suspended
        while not current_plan.is_complete:
            action = current_plan.get_next_action()
            if action is None:
                break

            action_num = current_plan.resumption_index + 1
            total_actions = len(current_plan.actions)

            logger.info(
                f"🔄 SCHEDULER: Executing action {action_num}/{total_actions} "
                f"(Effect {action.effect_index}, Player={action.player.name}, "
                f"sharing={action.is_sharing}, demand={action.is_demand}, "
                f"resume_index={action.resume_action_index})"
            )

            # Record action start event
            if self.trace_recorder and trace:
                primitive_type = (
                    list(action.effect)[action.resume_action_index].get("type") 
                    if action.effect and action.resume_action_index < len(action.effect)
                    else None
                )
                event = TraceEvent(
                    timestamp=datetime.now().isoformat(),
                    event_type="action_start",
                    player_id=action.player.id,
                    player_name=action.player.name,
                    effect_index=action.effect_index,
                    is_sharing=action.is_sharing,
                    primitive_type=primitive_type,
                    primitive_index=action.resume_action_index,
                )
                self.trace_recorder.record_event(event)

            # Determine if we're resuming after interaction suspension
            # This is true if: (1) this is the first action we're executing AND
            # (2) the plan started at a non-zero index (was suspended previously)
            is_resuming_after_interaction = (
                is_first_action and initial_resumption_index > 0
            )
            logger.debug(
                f"SCHEDULER DEBUG: Resumption check - is_first_action={is_first_action}, "
                f"initial_resumption_index={initial_resumption_index}, "
                f"is_resuming_after_interaction={is_resuming_after_interaction}, "
                f"action.resume_action_index={action.resume_action_index}"
            )
            is_first_action = False

            # Check if previous action was sharing with same effect
            # If so, activating player continues the effect and shouldn't clear variables
            continuing_after_sharing = (
                previous_action is not None
                and previous_action.is_sharing
                and previous_action.effect_index == action.effect_index
                and not action.is_sharing
            )

            # Execute the action
            logger.debug(
                f"SCHEDULER DEBUG: About to execute action - effect_length={len(action.effect)}, "
                f"resume_action_index={action.resume_action_index}, "
                f"effect[0]={list(action.effect)[0].get('type') if action.effect else None}, "
                f"effect_types={[p.get('type') for p in list(action.effect)]}"
            )
            result = self.execute_action(
                effect=list(action.effect),  # Convert tuple back to list
                effect_index=action.effect_index,
                player=action.player,
                is_sharing=action.is_sharing,
                context=current_context,
                resume_action_index=action.resume_action_index,
                is_resuming_after_interaction=is_resuming_after_interaction,
                continuing_after_sharing=continuing_after_sharing,
                is_demand=action.is_demand,
            )
            logger.debug(
                f"SCHEDULER DEBUG: Action executed - success={result.success}, "
                f"requires_interaction={result.requires_interaction}, "
                f"routes_to_demand={result.routes_to_demand}, "
                f"error={result.error}"
            )

            # Track this action for next iteration
            previous_action = action

            # Update context
            current_context = result.context

            # Collect results
            all_results.extend(result.results)

            # Check for interaction suspension
            if result.requires_interaction:
                logger.debug(
                    f"SCHEDULER: Plan suspended at action {action_num} for interaction"
                )

                # Record suspension event
                if self.trace_recorder and trace:
                    interaction_type = (
                        result.interaction.interaction_type
                        if result.interaction
                        else None
                    )
                    event = TraceEvent(
                        timestamp=datetime.now().isoformat(),
                        event_type="suspension",
                        player_id=action.player.id,
                        player_name=action.player.name,
                        effect_index=action.effect_index,
                        is_sharing=action.is_sharing,
                        requires_interaction=True,
                        interaction_type=interaction_type,
                    )
                    self.trace_recorder.record_event(event)
                    trace = self.trace_recorder.suspend_trace()

                # Update the current action with resume index if mid-effect suspension
                # CRITICAL: Use >= 0 not > 0 because resume_action_index=0 is valid
                # (means re-execute from beginning, needed for container primitives like ConditionalAction)
                if result.resume_action_index is not None and result.resume_action_index >= 0:
                    logger.debug(
                        f"SCHEDULER DEBUG: Updating action with resume_index={result.resume_action_index}, "
                        f"current_action_index={current_plan.resumption_index}, "
                        f"action.resume_action_index before={action.resume_action_index}"
                    )
                    # Action suspended mid-execution - update it with resume index
                    updated_action = action.with_resume_index(
                        result.resume_action_index
                    )
                    logger.debug(
                        f"SCHEDULER DEBUG: Updated action resume_index={updated_action.resume_action_index}"
                    )
                    # Replace the action in the plan
                    updated_actions = list(current_plan.actions)
                    updated_actions[current_plan.resumption_index] = updated_action
                    current_plan = ActionPlan(
                        actions=tuple(updated_actions),
                        resumption_index=current_plan.resumption_index,
                    )
                    logger.debug(
                        f"SCHEDULER DEBUG: Plan updated with new action at index {current_plan.resumption_index}"
                    )
                # NOTE: Don't call mark_complete() here anymore - the main loop handles advancement

                return SchedulerResult(
                    success=result.success,
                    context=current_context,
                    all_results=all_results,
                    completed_actions=current_plan.resumption_index,
                    total_actions=total_actions,
                    requires_interaction=True,
                    interaction=result.interaction,
                    suspended_at_action=current_plan.resumption_index,
                    resume_action_index=result.resume_action_index,  # Pass through for ExecutionPhase
                    trace=trace,
                )

            # Check for demand routing
            if result.routes_to_demand:
                logger.debug(
                    f"SCHEDULER: Plan suspended at action {action_num} for demand routing"
                )

                # Record suspension event for demand
                if self.trace_recorder and trace:
                    event = TraceEvent(
                        timestamp=datetime.now().isoformat(),
                        event_type="suspension",
                        player_id=action.player.id,
                        player_name=action.player.name,
                        effect_index=action.effect_index,
                        is_sharing=action.is_sharing,
                        requires_interaction=False,
                        interaction_type="demand",
                    )
                    self.trace_recorder.record_event(event)
                    trace = self.trace_recorder.suspend_trace()

                # Update similar to interaction case
                if result.resume_action_index is not None and result.resume_action_index >= 0:
                    updated_action = action.with_resume_index(
                        result.resume_action_index
                    )
                    updated_actions = list(current_plan.actions)
                    updated_actions[current_plan.resumption_index] = updated_action
                    current_plan = ActionPlan(
                        actions=tuple(updated_actions),
                        resumption_index=current_plan.resumption_index,
                    )
                else:
                    current_plan = current_plan.mark_complete(
                        current_plan.resumption_index
                    )

                return SchedulerResult(
                    success=result.success,
                    context=current_context,
                    all_results=all_results,
                    completed_actions=current_plan.resumption_index,
                    total_actions=total_actions,
                    routes_to_demand=True,
                    demand_config=result.demand_config,
                    resume_action_index=result.resume_action_index,  # Pass through for ExecutionPhase
                    trace=trace,
                )

            # Check for failure
            if not result.success:
                logger.error(
                    f"SCHEDULER: Plan failed at action {action_num}: {result.error}"
                )
                logger.error(
                    f"SCHEDULER DEBUG: Failure details - action_idx={current_plan.resumption_index}, "
                    f"effect_index={action.effect_index}, player={action.player.name}, "
                    f"resume_action_index={action.resume_action_index}, "
                    f"is_resuming_after_interaction={is_resuming_after_interaction}"
                )

                # Record error event
                if self.trace_recorder and trace:
                    event = TraceEvent(
                        timestamp=datetime.now().isoformat(),
                        event_type="error",
                        player_id=action.player.id,
                        player_name=action.player.name,
                        effect_index=action.effect_index,
                        is_sharing=action.is_sharing,
                        success=False,
                        error=result.error,
                    )
                    self.trace_recorder.record_event(event)
                    trace = self.trace_recorder.fail_trace(
                        result.error or "Unknown error"
                    )

                return SchedulerResult(
                    success=False,
                    context=current_context,
                    all_results=all_results,
                    completed_actions=current_plan.resumption_index,
                    total_actions=total_actions,
                    error=result.error,
                    trace=trace,
                )

            # Record action complete event
            if self.trace_recorder and trace:
                event = TraceEvent(
                    timestamp=datetime.now().isoformat(),
                    event_type="action_complete",
                    player_id=action.player.id,
                    player_name=action.player.name,
                    effect_index=action.effect_index,
                    is_sharing=action.is_sharing,
                    success=True,
                    results_count=len(result.results),
                )
                self.trace_recorder.record_event(event)

            # Action completed successfully - apply result to context
            current_context = self._apply_result(current_context, result, action)

            # Check if we're moving to a different effect or player
            next_action_index = current_plan.resumption_index + 1
            next_action = None
            if next_action_index < len(current_plan.actions):
                next_action = current_plan.actions[next_action_index]

            # CRITICAL FIX: Clear effect-scoped variables when moving between different players
            # in the SAME effect (e.g., from sharing player to activating player)
            # This ensures each player gets fresh variables for their execution
            if (
                next_action is not None
                and next_action.effect_index == action.effect_index
                and next_action.player.id != action.player.id
            ):
                logger.info(
                    f"🔄 SCHEDULER: PLAYER TRANSITION in Effect {action.effect_index}: "
                    f"{action.player.name} → {next_action.player.name}"
                )
                logger.info("🔄   Clearing effect-scoped variables")
                logger.info(
                    f"🔄   Variables before: {list(current_context.variables.keys())}"
                )
                effect_scoped_vars = [
                    "selected_achievement",
                    "selected_achievements",
                    "selected_cards",
                    "selected_card",
                    "chosen_option",
                    "player_choice",
                    "decline",
                    "interaction_cancelled",
                ]
                for var_name in effect_scoped_vars:
                    if current_context.has_variable(var_name):
                        logger.debug(f"SCHEDULER: Clearing {var_name} between players")
                        current_context = current_context.without_variable(var_name)

            # Clear sharing context when moving to a new effect
            # This is critical for multi-effect cards with sharing to prevent
            # "Player has already completed sharing" errors on subsequent effects
            if (
                next_action is not None
                and next_action.effect_index != action.effect_index
            ):
                logger.info(
                    f"🔀 SCHEDULER: EFFECT TRANSITION {action.effect_index} → {next_action.effect_index}"
                )

                # CRITICAL FIX: After demand effect completes, set demand_transferred_count
                # This is needed for conditional checks in subsequent effects (e.g., Gunpowder)
                if action.is_demand:
                    total_demand_transfers = current_context.get_variable(
                        "_demand_transfer_count_accumulator", 0
                    )
                    current_context = current_context.with_variable(
                        "demand_transferred_count", total_demand_transfers
                    )
                    logger.info(
                        f"🔀 SCHEDULER: Demand effect complete - set demand_transferred_count={total_demand_transfers}"
                    )
                    # Clear accumulator for next demand effect (if any)
                    current_context = current_context.without_variable(
                        "_demand_transfer_count_accumulator"
                    )

                # DEBUG: Log variable state before transition
                logger.info(
                    f"🔀   Variables before transition: {list(current_context.variables.keys())}"
                )
                for key in [
                    "selected_achievement",
                    "selected_achievements",
                    "selected_cards",
                ]:
                    val = current_context.get_variable(key)
                    if val is not None:
                        logger.info(f"🔀   {key} = {val}")

                # CRITICAL FIX: Clear ALL non-system variables on effect transitions.
                # Previous approach used a hardcoded list which missed custom store_result
                # variables like "to_return", causing ENIAC bug where demand's to_return
                # leaked into cooperative effect and skipped the SelectCards interaction.
                # Now uses SYSTEM_CONTEXT_VARS whitelist — only system vars survive transitions.
                from dogma_v2.core.constants import SYSTEM_CONTEXT_VARS

                # Also preserve demand_transferred_count (just set above) and endorsed
                preserve_vars = SYSTEM_CONTEXT_VARS | {"demand_transferred_count", "endorsed"}
                vars_to_clear = [
                    k for k in current_context.variables
                    if k not in preserve_vars and not k.startswith("_")
                ]
                for var_name in vars_to_clear:
                    logger.debug(
                        f"🔀 SCHEDULER: Clearing {var_name} on effect transition"
                    )
                    current_context = current_context.without_variable(var_name)

                # CRITICAL FIX: Clear demanding_player when transitioning from demand
                # to non-demand effect. demanding_player is a system var (needed across
                # demand phases) but must NOT leak into cooperative effects — SelectCards
                # checks it to decide if selection is optional, causing auto-select instead
                # of prompting the player.
                if action.is_demand and not next_action.is_demand:
                    if current_context.has_variable("demanding_player"):
                        logger.info(
                            "🔀 SCHEDULER: Clearing demanding_player on demand→cooperative transition"
                        )
                        current_context = current_context.without_variable(
                            "demanding_player"
                        )

                if any(a.is_sharing for a in current_plan.actions):
                    logger.debug(
                        f"SCHEDULER: Clearing completed_sharing for new effect "
                        f"(effect {action.effect_index} -> {next_action.effect_index})"
                    )
                    cleared_sharing = current_context.sharing.with_cleared_completed()
                    current_context = current_context.with_sharing_context(
                        cleared_sharing
                    )

            # ALWAYS advance to next action after completing current action
            # Each PlannedAction is a separate action in the plan, even if they're
            # for the same effect but different players
            current_plan = current_plan.mark_complete(current_plan.resumption_index)

            logger.info(
                f"✅ SCHEDULER: Action {action_num} completed ({len(result.results)} results)"
            )
            logger.info(
                f"✅   Next: resumption_index will advance from {current_plan.resumption_index} to {current_plan.resumption_index + 1}"
            )

        # All actions completed successfully
        logger.info(
            f"🏁 SCHEDULER: Plan completed successfully ({len(plan.actions)} actions executed)"
        )

        # Complete trace if recorder is enabled
        if self.trace_recorder and trace:
            trace = self.trace_recorder.complete_trace()

        return SchedulerResult(
            success=True,
            context=current_context,
            all_results=all_results,
            completed_actions=len(plan.actions),
            total_actions=len(plan.actions),
            trace=trace,
        )
