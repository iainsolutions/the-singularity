"""
DemandTargetPhase - Process individual target player for demand effects.

This phase handles the execution of demand actions on a specific target player,
including context switching, compliance detection, and reward processing.

IMPORTANT: This phase uses the Effect abstraction layer and never directly
imports or interacts with action primitives, following the ActionPrimitiveAdapter
pattern specified in DOGMA_TECHNICAL_SPECIFICATION.md.
"""

import logging
from typing import Any

from ..core.context import DogmaContext
from ..core.phases import DogmaPhase, PhaseResult
from ..effects import EffectFactory
from ..state.capture import StateCapture

logger = logging.getLogger(__name__)


class DemandTargetPhase(DogmaPhase):
    """
    Process demand actions for a specific target player.

    This phase implements DOGMA_SPECIFICATION.md Section 3.3:
    1. Switch context to target player
    2. Execute demand actions
    3. Detect compliance (actual state changes)
    4. Report back to parent DemandPhase
    """

    def __init__(
        self,
        target_player,
        demand_actions: list[dict[str, Any]],
        parent_demand,
    ):
        """
        Initialize demand target phase.

        Args:
            target_player: The player who must comply with the demand
            demand_actions: List of actions the target must perform
            parent_demand: Parent DemandPhase for callbacks
        """
        self.target_player = target_player
        self.demand_actions = demand_actions
        self.parent_demand = parent_demand

        # Track state for compliance detection
        self.state_before = None
        self.state_after = None
        self.complied = False
        self.current_action_index = 0

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Execute demand processing for target player"""
        self.log_phase_start(context)

        # First execution - capture initial state
        if self.state_before is None:
            logger.info(
                f"Processing demand for target player: {self.target_player.name}"
            )
            self.state_before = StateCapture.capture_player_state(self.target_player)

            # Switch context to target player
            target_context = context.with_player(self.target_player)
            target_context = target_context.with_variable(
                "demanding_player", context.activating_player
            )
            target_context = target_context.with_variable("is_demand_target", True)

            # Start executing demand actions
            return self._execute_next_action(target_context)

        # Resuming after interaction or continuing
        # Ensure demanding_player is set in context (may be lost during resume)
        resume_context = context
        if not resume_context.get_variable("demanding_player"):
            resume_context = resume_context.with_variable(
                "demanding_player", context.activating_player
            )
        return self._execute_next_action(resume_context)

    def _execute_next_action(self, context: DogmaContext) -> PhaseResult:
        """Execute the next demand action in sequence"""

        # DEBUG: Check if demanding_player is in context
        demanding_player_var = context.get_variable("demanding_player")
        logger.info(
            f"DemandTarget._execute_next_action: index={self.current_action_index}, total={len(self.demand_actions)}, "
            f"demanding_player={'None' if not demanding_player_var else demanding_player_var.name}"
        )
        logger.info(f"DemandTarget: demand_actions={self.demand_actions}")

        # Check if all actions complete
        if self.current_action_index >= len(self.demand_actions):
            logger.debug(
                "DemandTarget: No more actions to execute, completing demand processing"
            )
            return self._complete_demand_processing(context)

        action_config = self.demand_actions[self.current_action_index]
        logger.debug(
            f"Executing demand action {self.current_action_index}: {action_config}"
        )

        try:
            # Create and execute effect using Effect abstraction
            effect = EffectFactory.create(action_config)

            # Determine which player should execute this action.
            # Default to target player, but allow actions to run as the activating (demanding) player.
            # Supports both target_player and execute_as parameters (target_player takes precedence).
            # target_player: "activating" | "current" (target) | "opponent" | "all"
            # execute_as: "activating" | "demanding" | "active" | "target" (legacy)

            # CRITICAL: Get the demanding player from context variable, NOT context.activating_player
            # because the context has been switched to the target player
            demanding_player = context.get_variable("demanding_player")

            logger.debug(f"DemandTarget: context.activating_player = {context.activating_player.name if context.activating_player else None}")
            logger.debug(f"DemandTarget: demanding_player (from variable) = {demanding_player.name if demanding_player else None}")
            logger.debug(f"DemandTarget: target_player = {self.target_player.name}")

            target_param = (
                (action_config.get("target_player") or action_config.get("execute_as") or "current").lower()
                if isinstance(action_config, dict)
                else "current"
            )
            logger.debug(f"DemandTarget: target_param = {target_param}")

            if target_param in ("activating", "demanding", "active"):
                exec_player = demanding_player
                logger.info(f"DemandTarget: Action executing as DEMANDING player ({exec_player.name if exec_player else 'None'})")
                # CRITICAL: Update BOTH current_player AND activating_player so interactions go to the right player
                # StandardInteractionBuilder uses activating_player for interaction player_id
                from dataclasses import replace
                exec_context = replace(context, current_player=exec_player, activating_player=exec_player)
            else:
                exec_player = self.target_player
                logger.info(f"DemandTarget: Action executing as TARGET player ({exec_player.name})")
                exec_context = context.with_player(exec_player)

            # For demand selections, force manual confirmation even when auto-selection would suffice
            # This ensures players see what they're transferring in response to demands
            # For AI players, this triggers an interaction that the AI agent will respond to
            if isinstance(action_config, dict) and action_config.get("type") in (
                "SelectHighest",
                "SelectLowest",
                "SelectCards",
            ):
                exec_context = exec_context.with_variable(
                    "force_manual_selection", True
                )

            result = effect.execute(exec_context)

            if result.requires_interaction:
                # Determine which player should respond to the interaction
                # (same player that executed the action)
                interaction_player = exec_player
                logger.info(
                    f"Demand action requires interaction from {interaction_player.name}"
                )
                # Action requires interaction - update context with clean results
                updated_context = context.with_variables(result.variables)
                updated_context = updated_context.with_results(tuple(result.results))

                # Check if we have interaction request from the effect in the context
                final_interaction_request = updated_context.get_variable(
                    "final_interaction_request"
                )
                if final_interaction_request:
                    # CRITICAL FIX: The final_interaction_request from StandardInteractionBuilder
                    # is already a complete DogmaInteractionRequest ready for WebSocket transmission.
                    # Just update the game_id and player_id fields directly.

                    # Update the player_id and game_id on the Pydantic model
                    final_interaction_request.player_id = interaction_player.id
                    final_interaction_request.game_id = getattr(
                        context.game, "game_id", ""
                    )

                    interaction = final_interaction_request

                    logger.info(
                        f"Using StandardInteractionBuilder request directly for {interaction_player.name}"
                    )
                else:
                    # No interaction data provided, create a basic one
                    logger.warning(
                        "Effect requires interaction but no request data provided"
                    )
                    from uuid import uuid4

                    from ..interaction_request import (
                        InteractionRequest,
                        InteractionType,
                    )

                    # Create a basic interaction request
                    card_name = context.card.name if context.card else "Card"
                    demanding_player_name = (
                        context.activating_player.name
                        if context.activating_player
                        else "Opponent"
                    )

                    # Build proper interaction data in StandardInteractionBuilder format
                    interaction_data = {
                        "type": "select_cards",
                        "message": f"Respond to {card_name} demand",
                        "eligible_cards": [],  # Empty but properly formatted
                        "max_count": 1,
                        "min_count": 0,
                        "source": "hand",
                    }

                    interaction = InteractionRequest(
                        id=str(uuid4()),
                        player_id=interaction_player.id,
                        type=InteractionType.SELECT_CARDS,
                        data=interaction_data,
                        message=f"{card_name} Demand from {demanding_player_name}: Respond to demand",
                    )

                # Return interaction required - this will bubble up to the executor
                return PhaseResult.interaction_required(
                    interaction, self, updated_context
                )

            elif result.success:
                # Update context with clean results (no internal signals)
                updated_context = context.with_variables(result.variables)
                updated_context = updated_context.with_results(tuple(result.results))

                # Move to next action
                self.current_action_index += 1
                return self._execute_next_action(updated_context)

            else:
                logger.warning(f"Demand action failed: {result.error}")
                # Action failed - target cannot comply
                # Move to completion without compliance
                return self._complete_demand_processing(context)

        except Exception as e:
            logger.error(f"Error executing demand action: {e}", exc_info=True)
            return PhaseResult.error(f"Demand action failed: {e}", context)

    def _complete_demand_processing(self, context: DogmaContext) -> PhaseResult:
        """Complete demand processing for this target"""

        # Capture final state
        self.state_after = StateCapture.capture_player_state(self.target_player)

        # Check for compliance (Spec 3.3)
        self.complied = self._check_compliance()

        # Important: Some demands include preparatory actions (e.g., DrawCards)
        # followed by transfers. The net hand_count for the target may not change
        # (draw 1, transfer 1), which would make pure state-diff detection miss
        # true compliance. Use the explicit 'demand_iteration_transferred' variable set by
        # TransferBetweenPlayers during THIS demand iteration only.
        try:
            # CRITICAL FIX: Check for cards transferred in THIS demand iteration only
            # The variable should be set by TransferBetweenPlayers during demand processing
            transferred_cards = (
                context.get_variable("demand_iteration_transferred") or []
            )
            if not self.complied and transferred_cards:
                logger.info(
                    f"COMPLIANCE INFERRED from demand_iteration_transferred variable: {[getattr(c, 'name', str(c)) for c in transferred_cards]}"
                )
                self.complied = True
        except Exception:
            pass

        if self.complied:
            logger.info(f"{self.target_player.name} complied with demand")

            # CRITICAL FIX: Check for immediate victory after demand compliance
            # A player could gain their 6th achievement during demand compliance
            from ..victory_checker import VictoryChecker

            victory_result = VictoryChecker.check_immediate_victory(
                context.game, context
            )
            if victory_result:
                logger.info(
                    f"IMMEDIATE VICTORY AFTER DEMAND COMPLIANCE: {victory_result}"
                )
                # Set victory flag and complete dogma immediately
                final_context = context.with_variable(
                    "victory_achieved", victory_result
                )
                final_context = final_context.with_result(f"VICTORY: {victory_result}")

                # Import completion phase for immediate completion
                from .completion import CompletionPhase

                return PhaseResult.success(CompletionPhase(), final_context)

            # Activity: per-target demand outcome with transferred cards if available
            try:
                from logging_config import activity_logger

                if activity_logger:
                    transferred_cards = context.get_variable("transferred_cards") or []
                    card_names = [getattr(c, "name", str(c)) for c in transferred_cards]
                    activity_logger.log_dogma_demand_outcome(
                        game_id=context.game.game_id,
                        demanding_player_id=context.activating_player.id,
                        target_player_id=self.target_player.id,
                        card_name=context.card.name,
                        transferred=True,
                        cards_transferred=card_names,
                        transfer_count=len(card_names),
                        phase="target_complete",
                        target_player_name=self.target_player.name,
                        demanding_player_name=context.activating_player.name,
                    )
            except Exception:
                pass
        else:
            logger.info(
                f"{self.target_player.name} did not comply with demand (no state change)"
            )
            # Activity: per-target non-compliance
            try:
                from logging_config import activity_logger

                if activity_logger:
                    activity_logger.log_dogma_demand_outcome(
                        game_id=context.game.game_id,
                        demanding_player_id=context.activating_player.id,
                        target_player_id=self.target_player.id,
                        card_name=context.card.name,
                        transferred=False,
                        transfer_count=0,
                        decline_reason="No valid cards to transfer",
                        phase="target_complete",
                        target_player_name=self.target_player.name,
                        demanding_player_name=context.activating_player.name,
                    )
            except Exception:
                pass

        # Notify parent demand of completion
        self.parent_demand.on_target_completed(self.complied)

        # Return to parent demand phase
        # The parent will handle moving to next target or completing
        return PhaseResult.success(self.parent_demand, context)

    def _check_compliance(self) -> bool:
        """
        Check if the target player actually complied with the demand.

        According to Spec 3.3, compliance is detected by actual state changes:
        - Cards transferred (hand/board/score changes)
        - Cards returned to deck
        - Cards archived, junked, scored, melded, or exchanged
        """
        if not self.state_before or not self.state_after:
            logger.warning(
                f"COMPLIANCE CHECK FAILED: Missing states for {self.target_player.name} (before={self.state_before is not None}, after={self.state_after is not None})"
            )
            return False

        # Get detailed changes
        changes = StateCapture.get_state_changes(self.state_before, self.state_after)

        # Log all detected state changes for debugging
        logger.info(f"COMPLIANCE CHECK for {self.target_player.name}:")
        logger.info(f"  State changes detected: {list(changes.keys())}")
        for change_type, change_data in changes.items():
            logger.info(f"  {change_type}: {change_data}")

        # Check for meaningful changes that indicate compliance
        compliance_indicators = [
            "hand_count",  # Cards transferred to/from hand
            "score_pile_count",  # Cards scored
            "board_cards",  # Cards melded or removed from board
            "achievement_count",  # Achievements gained (rare in demands)
        ]

        complied = False
        for indicator in compliance_indicators:
            if indicator in changes:
                logger.info(
                    f"COMPLIANCE DETECTED for {self.target_player.name} via {indicator} change: {changes[indicator]}"
                )
                complied = True

        if not complied:
            logger.info(
                f"NO COMPLIANCE DETECTED for {self.target_player.name} - no meaningful state changes"
            )

        return complied

    def get_phase_name(self) -> str:
        """Return phase name with target player"""
        return f"DemandTargetPhase[{self.target_player.name}]"

    def estimate_remaining_phases(self) -> int:
        """Estimate phases remaining"""
        remaining_actions = len(self.demand_actions) - self.current_action_index
        # Each action could require interaction, plus completion
        return remaining_actions + 1
