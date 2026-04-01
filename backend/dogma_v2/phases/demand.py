"""
Demand effect processing phases.

This module implements the demand processing logic according to
DOGMA_SPECIFICATION.md Section 3, with proper state tracking and
variable management that fixes the Archery regression bug.

IMPORTANT: This phase uses the Effect abstraction layer and never directly
imports or interacts with action primitives, following the ActionPrimitiveAdapter
pattern specified in DOGMA_TECHNICAL_SPECIFICATION.md.
"""

import logging
from enum import Enum
from typing import Any

from logging_config import activity_logger
from utils.symbol_mapping import string_to_symbol

from ..core.context import DogmaContext
from ..core.phases import DogmaPhase, PhaseResult, ValidationResult
from ..effects import EffectFactory
from .demand_target import DemandTargetPhase

logger = logging.getLogger(__name__)


class DemandState(Enum):
    """States for demand processing"""

    INITIALIZING = "initializing"
    VALIDATING = "validating"
    PROCESSING = "processing"
    COMPLETE = "complete"


class DemandPhase(DogmaPhase):
    """
    Phase 2a: Handle demand effects with proper state tracking.

    This phase implements DOGMA_SPECIFICATION.md Section 3 and fixes
    the critical bug where demand_transferred_count was never set.

    Key fixes:
    1. ALWAYS set demand_transferred_count (even when 0)
    2. Capture states before/after demand processing
    3. Proper compliance detection
    4. Handle fallback actions correctly
    """

    def __init__(self, effect_config: dict[str, Any], return_phase: DogmaPhase):
        """
        Initialize demand phase.

        Args:
            effect_config: Demand effect configuration from card
            return_phase: Phase to return to after demand completes
        """
        self.effect_config = effect_config
        self.return_phase = return_phase

        # Extract configuration
        self.required_symbol = effect_config.get("required_symbol")
        self.demand_actions = effect_config.get("actions", [])
        self.repeat_on_compliance = effect_config.get("repeat_on_compliance", False)
        self.fallback_actions = effect_config.get("fallback_actions", [])
        self.is_compel = effect_config.get("is_compel", False)  # Artifacts expansion

        # Processing state
        self.state = DemandState.INITIALIZING
        self.affected_players = []
        self.can_comply = []
        self.current_target_index = 0
        self.compliance_count = 0
        self.total_compliance_count = 0
        self.repeat_iteration = 0  # Track number of repeat iterations
        self.max_repeat_iterations = 10  # Safety limit for repeat_on_compliance  # NEW: Track total across all iterations
        self.endorse_second_pass_complete = False  # Cities: Track if endorsed second pass done

    def validate(self, context: DogmaContext) -> ValidationResult:
        """Validate demand configuration"""
        if not self.required_symbol:
            return ValidationResult.invalid("Demand missing required_symbol")

        if not self.demand_actions:
            return ValidationResult.invalid("Demand missing demand_actions")

        # Validate symbol
        try:
            symbol = string_to_symbol(self.required_symbol)
            if not symbol:
                return ValidationResult.invalid(
                    f"Invalid symbol: {self.required_symbol}"
                )
        except Exception as e:
            return ValidationResult.invalid(
                f"Error parsing symbol '{self.required_symbol}': {e}"
            )

        return ValidationResult.valid()

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Execute demand processing state machine"""
        self.log_phase_start(context)

        # FALLBACK-ONLY MODE: Skip demand routing, execute fallback immediately
        # This happens when there are no vulnerable players but fallback_actions exist
        is_fallback_only = context.has_variable("is_fallback_only") and context.get_variable("is_fallback_only")
        if is_fallback_only and self.state == DemandState.INITIALIZING:
            logger.info("🔥 FALLBACK-ONLY: No vulnerable players, executing fallback actions directly")
            # Set demand_transferred_count to 0 (required for repeat logic)
            updated_context = context.with_variable("demand_transferred_count", 0)

            if self.fallback_actions:
                return self._execute_fallback_actions(updated_context)
            else:
                # No fallback despite flag - shouldn't happen but handle gracefully
                logger.warning("is_fallback_only=True but no fallback_actions defined")
                updated_context = updated_context.with_result("No vulnerable players and no fallback actions")
                return self._transition_to(DemandState.COMPLETE, updated_context)

        # Validate configuration
        validation = self.validate(context)
        if not validation.is_valid:
            logger.error(f"Demand validation failed: {validation.message}")
            return PhaseResult.error(validation.message, context)

        # Execute current state
        if self.state == DemandState.INITIALIZING:
            return self._initialize_demand(context)
        elif self.state == DemandState.VALIDATING:
            return self._validate_targets(context)
        elif self.state == DemandState.PROCESSING:
            return self._process_next_target(context)
        elif self.state == DemandState.COMPLETE:
            return self._complete_demand(context)
        else:
            return PhaseResult.error(f"Unknown demand state: {self.state}", context)

    def _initialize_demand(self, context: DogmaContext) -> PhaseResult:
        """Phase 1: Initialize demand and find affected players"""
        logger.info(f"Initializing demand for {self.required_symbol} symbol")

        # Find affected players (Spec 3.1)
        if not self.required_symbol:
            logger.error("Demand phase missing required symbol")
            return PhaseResult.error("Demand missing required_symbol", context)

        symbol = string_to_symbol(self.required_symbol)
        demanding_player = context.activating_player
        demanding_count = demanding_player.count_symbol(symbol)

        logger.info(
            f"{demanding_player.name} has {demanding_count} {self.required_symbol} symbols"
        )

        # Log detailed demand execution start
        if activity_logger:
            # Use transaction game_id for consistency
            game_id = context.game.game_id
            logger.debug(
                f"DemandPhase: Using game_id {game_id} from context.game.game_id"
            )
            logger.debug(
                f"DemandPhase: Game object id: {id(context.game)}, has game_id: {hasattr(context.game, 'game_id')}"
            )
            activity_logger.log_dogma_demand_executed(
                game_id=game_id,
                demanding_player_id=demanding_player.id,
                target_player_id=demanding_player.id,  # Will be updated per target
                card_name=context.card.name,
                symbol_requirement=self.required_symbol,
                target_symbol_count=demanding_count,
                has_sufficient_symbols=True,
                demanding_player_name=demanding_player.name,
                phase="initialization",
            )

        self.affected_players = []
        logger.debug(
            f"🔍 DEMAND INIT: context.game object id={id(context.game)}, game.players list id={id(context.game.players)}"
        )
        for player in context.game.players:
            logger.debug(
                f"🔍 DEMAND INIT: Checking player {player.name} (player_obj_id={id(player)}, hand_id={id(player.hand) if hasattr(player, 'hand') else None})"
            )
            if player.id != demanding_player.id:
                player_count = player.count_symbol(symbol)
                logger.debug(
                    f"{player.name} has {player_count} {self.required_symbol} symbols"
                )

                # Log symbol check for each player
                meets_requirement = player_count >= demanding_count

                # Record in state tracker for action log
                context.state_tracker.record_symbol_check(
                    player_name=player.name,
                    symbol=self.required_symbol,
                    count=player_count,
                    context="demand_check",
                    meets_requirement=meets_requirement,
                    required_count=demanding_count,
                )

                if activity_logger:
                    activity_logger.log_dogma_symbol_check(
                        game_id=game_id,
                        player_id=player.id,
                        card_name=context.card.name,
                        symbol=self.required_symbol,
                        player_count=player_count,
                        required_count=demanding_count,
                        meets_requirement=meets_requirement,
                        player_name=player.name,
                        comparison_type="demand_check",
                    )

                # ARTIFACTS EXPANSION: Compel effects use inverted vulnerability
                # Standard demands: vulnerable if player_count < demanding_count
                # Compel: vulnerable if player_count > demanding_count
                is_vulnerable = (
                    player_count > demanding_count if self.is_compel
                    else player_count < demanding_count
                )

                if is_vulnerable:
                    self.affected_players.append(player)
                    compel_text = " (COMPEL)" if self.is_compel else ""
                    comparison = ">" if self.is_compel else "<"
                    logger.info(
                        f"{player.name} must comply with {compel_text} demand ({player_count} {comparison} {demanding_count})"
                    )
                else:
                    comparison = "<=" if self.is_compel else ">="
                    logger.debug(
                        f"{player.name} is not affected ({player_count} {comparison} {demanding_count})"
                    )

        # Move to validation state
        self.state = DemandState.VALIDATING
        return self.execute(context)

    def _validate_targets(self, context: DogmaContext) -> PhaseResult:
        """Phase 2: Check which affected players can actually comply"""
        logger.debug(
            f"Validating compliance ability for {len(self.affected_players)} affected players"
        )

        self.can_comply = []

        # Helper: some demands include preparatory actions (e.g., DrawCards) that enable compliance
        # CRITICAL: Only DrawCards that appears BEFORE selection/transfer actions is preparatory.
        # DrawCards inside ConditionalAction (compliance reward) should NOT count as preparatory.
        def has_preparatory_actions(actions: list[dict]) -> bool:
            try:
                selection_types = {
                    "SelectCards",
                    "SelectHighest",
                    "SelectLowest",
                    "TransferBetweenPlayers",
                }
                draw_types = {"DrawCards", "DrawUntil", "RevealAndProcess"}

                for a in actions or []:
                    atype = a.get("type") if isinstance(a, dict) else None

                    # If we encounter a draw action before any selection/transfer → preparatory
                    if atype in draw_types:
                        return True

                    # If we encounter selection/transfer before any draw → NOT preparatory
                    # (Draw actions after this are compliance rewards, not preparatory)
                    if atype in selection_types:
                        return False

                    # Don't recurse into ConditionalAction - draws inside are rewards

                return False
            except Exception:
                return False

        preparatory_present = has_preparatory_actions(self.demand_actions)

        for player in self.affected_players:
            can = self._can_player_comply(player, context)

            # NOTE: Removed misleading record_hand_check() here - it logged wrong symbol/location
            # for complex demands (e.g., "crown in hand" for City States castle-on-board demand)
            # The logger.info messages below provide clearer compliance status

            # If player appears unable now, but demand includes a Draw step that will give cards, allow processing
            if not can and preparatory_present:
                logger.info(
                    f"{player.name} initially lacks resources, but preparatory actions present (e.g., draw) - allowing processing"
                )
                can = True

            if can:
                self.can_comply.append(player)
                logger.info(f"{player.name} CAN comply with demand")
            else:
                logger.info(f"{player.name} CANNOT comply with demand (no valid cards)")
                # Activity log: Show player-visible feedback when demand fails
                if activity_logger:
                    activity_logger.log_dogma_demand_outcome(
                        game_id=context.game.game_id,
                        demanding_player_id=context.activating_player.id,
                        target_player_id=player.id,
                        card_name=context.card.name,
                        transferred=False,
                        transfer_count=0,
                        decline_reason=f"{player.name} has no eligible cards to transfer",
                        player_name=player.name,
                        phase="compliance_check",
                    )

        # Check if anyone can comply
        if not self.can_comply:
            logger.error(
                f"🔥 FALLBACK DEBUG: No players can comply. affected_players={len(self.affected_players)}, can_comply={len(self.can_comply)}, has_fallback={bool(self.fallback_actions)}"
            )
            logger.info("No players can comply with demand")
            # CRITICAL FIX: Always set demand_transferred_count, even when 0
            updated_context = context.with_variable("demand_transferred_count", 0)

            # Log demand outcome - no transfers
            if activity_logger:
                activity_logger.log_dogma_demand_outcome(
                    game_id=context.game.game_id,
                    demanding_player_id=context.activating_player.id,
                    target_player_id="all_targets",  # Multiple targets
                    card_name=context.card.name,
                    transferred=False,
                    transfer_count=0,
                    decline_reason="No players have required cards to transfer",
                    affected_players_count=len(self.affected_players),
                    complying_players_count=0,
                )

            # Execute fallback actions if defined
            if self.fallback_actions:
                logger.error(
                    f"🔥 FALLBACK DEBUG: Executing {len(self.fallback_actions)} fallback actions!"
                )
                logger.info("Executing fallback actions")

                # Log fallback activation
                if activity_logger:
                    activity_logger.log_dogma_fallback_activated(
                        game_id=context.game.game_id,
                        player_id=context.activating_player.id,
                        card_name=context.card.name,
                        fallback_reason="No cards were transferred due to this demand",
                        fallback_effect=f"{len(self.fallback_actions)} fallback actions",
                        fallback_actions=self.fallback_actions,
                    )

                return self._execute_fallback_actions(updated_context)
            else:
                # No fallback, complete demand with 0 transfers
                logger.info("No fallback actions, completing demand with 0 transfers")
                updated_context = updated_context.with_result(
                    f"No players affected by {self.required_symbol} demand"
                )
                return PhaseResult.success(self.return_phase, updated_context)

        # Players can comply, start processing
        logger.info(f"{len(self.can_comply)} players can comply with demand")
        self.state = DemandState.PROCESSING
        return self.execute(context)

    def _process_next_target(self, context: DogmaContext) -> PhaseResult:
        """Phase 3: Process each complying player"""
        if self.current_target_index >= len(self.can_comply):
            # All targets processed, complete demand
            self.state = DemandState.COMPLETE
            return self.execute(context)

        target = self.can_comply[self.current_target_index]
        logger.info(
            f"Processing demand for {target.name} (target {self.current_target_index + 1}/{len(self.can_comply)})"
        )

        # Create target phase for this specific player
        # Log per-target demand execution start for activity log
        try:
            if activity_logger:
                symbol = string_to_symbol(self.required_symbol)
                target_count = target.count_symbol(symbol) if symbol else 0
                demanding_count = (
                    context.activating_player.count_symbol(symbol) if symbol else 0
                )
                activity_logger.log_dogma_demand_executed(
                    game_id=context.game.game_id,
                    demanding_player_id=context.activating_player.id,
                    target_player_id=target.id,
                    card_name=context.card.name,
                    symbol_requirement=self.required_symbol,
                    target_symbol_count=target_count,
                    has_sufficient_symbols=(target_count < demanding_count),
                    phase="target_start",
                    demanding_player_name=context.activating_player.name,
                    target_player_name=target.name,
                    iteration=self.total_compliance_count + 1,
                )
        except Exception:
            pass

        target_phase = DemandTargetPhase(
            target_player=target,
            demand_actions=self.demand_actions,
            parent_demand=self,
        )

        return PhaseResult.success(target_phase, context)

    def _complete_demand(self, context: DogmaContext) -> PhaseResult:
        """Phase 4: Complete demand processing and set final variables"""
        logger.info(
            f"Completing demand: {self.compliance_count} players complied this iteration"
        )
        logger.info(
            f"🔄 OARS DEBUG: _complete_demand called - repeat_on_compliance={self.repeat_on_compliance}, compliance_count={self.compliance_count}, iteration={self.repeat_iteration}"
        )

        # CRITICAL FIX: Accumulate compliance across all iterations for repeating demands
        self.total_compliance_count += self.compliance_count

        # CRITICAL FIX: Always set demand_transferred_count based on total actual compliance
        # This fixes the Oars bug where the variable was reset to 0 on repeat iterations
        updated_context = context.with_variable(
            "demand_transferred_count", self.total_compliance_count
        )

        # Add result message
        if self.total_compliance_count > 0:
            result_msg = f"{self.total_compliance_count} player(s) complied with {self.required_symbol} demand"
        else:
            result_msg = f"No players complied with {self.required_symbol} demand"

        updated_context = updated_context.with_result(result_msg)

        logger.info(f"Demand complete: {result_msg}")
        logger.debug(f"Set demand_transferred_count = {self.total_compliance_count}")
        logger.debug(
            f"Current iteration compliance: {self.compliance_count}, Total compliance: {self.total_compliance_count}"
        )

        # Log final demand outcome
        if activity_logger:
            activity_logger.log_dogma_demand_outcome(
                game_id=context.game.game_id,
                demanding_player_id=context.activating_player.id,
                target_player_id="all_targets",  # Multiple targets
                card_name=context.card.name,
                transferred=self.total_compliance_count > 0,
                transfer_count=self.total_compliance_count,
                decline_reason=(
                    None
                    if self.total_compliance_count > 0
                    else "Players could not comply"
                ),
                total_affected_players=len(self.affected_players),
                total_complying_players=len(self.can_comply),
                final_compliance_count=self.total_compliance_count,
                phase="completion",
            )

        # Cities expansion: Check if we need to do a second pass for endorsed dogma
        # Per official rules: "When you issue a demand, affect each vulnerable
        # opponent twice (go around the table clockwise once and then a second time)"
        is_endorsed = updated_context.get_variable("endorsed", False)

        if is_endorsed and not self.endorse_second_pass_complete and len(self.can_comply) > 0:
            logger.info(
                f"Endorsed demand: Affecting {len(self.can_comply)} vulnerable opponents a second time (second pass)"
            )

            # Mark that we're doing the second pass
            self.endorse_second_pass_complete = True

            # Reset target index to process all complying players again
            self.current_target_index = 0

            # CRITICAL: Reset compliance_count before second pass
            # This prevents double-counting compliance events
            # First pass compliance was already accumulated to total_compliance_count
            self.compliance_count = 0

            # Set state back to PROCESSING to iterate through targets again
            self.state = DemandState.PROCESSING

            # Continue processing the second pass
            return self.execute(updated_context)

        # Check if we should repeat the demand (Oars logic)
        # "repeat this effect" means: keep repeating while players can still comply
        # For Oars: loop until opponent has no crown cards left in hand
        logger.info(
            f"🔄 OARS DEBUG: Checking repeat condition - repeat_on_compliance={self.repeat_on_compliance}, compliance_count={self.compliance_count}"
        )
        if self.repeat_on_compliance and self.compliance_count > 0:
            logger.info(
                "🔄 OARS DEBUG: REPEAT CONDITION MET! Proceeding with repeat checks..."
            )
            # Safety check: prevent infinite loops with max iteration limit
            if self.repeat_iteration >= self.max_repeat_iterations:
                logger.warning(
                    f"REPEAT DEMAND LIMIT REACHED: Max {self.max_repeat_iterations} iterations exceeded, stopping repeat"
                )
                # Add result message about limit
                updated_context = updated_context.with_result(
                    f"Demand repeat limit reached after {self.repeat_iteration} iterations"
                )
                # Fall through to normal completion (don't repeat)
            else:
                # Check if players can STILL comply after the current iteration
                # (e.g., for Oars, check if they still have crown cards after drawing)
                can_still_comply = []
                # CRITICAL: Use the player object that was modified during execution
                # ALWAYS get player from game.players list after sync, never use current_player
                # because current_player is a frozen reference from before the primitive executed
                for old_player in self.affected_players:
                    # Get the current player state from the game.players list
                    # This is where TransferBetweenPlayers syncs the modified player object
                    fresh_player = next(
                        (
                            p
                            for p in updated_context.game.players
                            if p.id == old_player.id
                        ),
                        None,
                    )
                    logger.info(
                        f"🔧 REPEAT FIX: Using game.players for {old_player.name} "
                        f"(obj_id={id(fresh_player) if fresh_player else None}, "
                        f"hand_size={len(fresh_player.hand) if fresh_player else 0})"
                    )
                    # For repeat demands, we need a simpler check - just see if they have the required cards
                    # Don't check the full action sequence since "selected_cards" won't exist anymore
                    if fresh_player:
                        # Check if player has cards that match the demand filter
                        # This is specifically for Oars which needs crown cards
                        has_compliant_cards = False
                        for action in self.demand_actions:
                            if action.get("type") in [
                                "SelectCards",
                                "SelectHighest",
                                "SelectLowest",
                            ]:
                                source = action.get("source", "hand")
                                cards = self._get_cards_from_source(
                                    fresh_player, source
                                )
                                filter_config = action.get("filter", {})
                                if filter_config:
                                    cards = self._apply_filter(cards, filter_config)
                                if cards:
                                    has_compliant_cards = True
                                    break

                        if has_compliant_cards:
                            can_still_comply.append(fresh_player)
                            logger.info(
                                f"REPEAT CHECK: {fresh_player.name} still has {len(cards)} cards matching demand filter"
                            )
                            logger.info(
                                f"  Cards in hand: {[c.name for c in fresh_player.hand]}"
                            )
                            logger.info(f"  Matching cards: {[c.name for c in cards]}")
                        else:
                            logger.info(
                                f"REPEAT CHECK: {fresh_player.name} has NO cards matching demand filter"
                            )
                            logger.info(
                                f"  Cards in hand: {[c.name for c in fresh_player.hand]}"
                            )

                if not can_still_comply:
                    logger.info(
                        "REPEAT DEMAND STOPPED: No players can comply anymore (e.g., out of crown cards)"
                    )
                    logger.info(
                        f"🔄 OARS DEBUG: Repeat stopped - no players can comply anymore after {self.repeat_iteration} iterations"
                    )
                    updated_context = updated_context.with_result(
                        f"Demand completed after {self.repeat_iteration} iterations - no players can comply anymore"
                    )
                    # Fall through to normal completion (don't repeat)
                else:
                    logger.info(
                        f"🔄 OARS DEBUG: {len(can_still_comply)} players can still comply - REPEATING!"
                    )
                    # Increment iteration counter and repeat
                    self.repeat_iteration += 1
                    logger.info(
                        f"REPEAT DEMAND: {self.compliance_count} players complied, {len(can_still_comply)} can still comply, repeating demand for {self.required_symbol} (iteration {self.repeat_iteration}/{self.max_repeat_iterations})"
                    )
                    logger.info(
                        f"Total compliance so far: {self.total_compliance_count}"
                    )

                    # Activity: indicate repeat is occurring
                    try:
                        if activity_logger:
                            activity_logger.log_dogma_demand_executed(
                                game_id=context.game.game_id,
                                demanding_player_id=context.activating_player.id,
                                target_player_id="all_targets",
                                card_name=context.card.name,
                                symbol_requirement=self.required_symbol,
                                target_symbol_count=0,
                                has_sufficient_symbols=True,
                                phase="repeat",
                                total_compliance=self.total_compliance_count,
                            )
                    except Exception:
                        pass

                    # Reset the demand for a fresh iteration (but preserve total_compliance_count)
                    self.state = DemandState.INITIALIZING
                    self.affected_players = []
                    self.can_comply = []
                    self.current_target_index = 0
                    self.compliance_count = 0  # Reset current iteration count only
                    # NOTE: self.total_compliance_count is preserved across iterations

                    # CRITICAL: Clear iteration-specific variables to prevent false compliance detection
                    # IMPORTANT: Use without_variable() not with_variable(..., []) because
                    # SelectCards checks "if existing_selection is not None" which treats [] as a valid selection!
                    updated_context = updated_context.without_variable(
                        "demand_iteration_transferred"
                    )
                    updated_context = updated_context.without_variable(
                        "transferred_cards"
                    )
                    # CRITICAL: Clear ALL card selection variables to force new selection in next iteration
                    # _apply_interaction_response stores selected cards in multiple variables
                    updated_context = updated_context.without_variable("selected_cards")
                    updated_context = updated_context.without_variable(
                        "cards_to_return"
                    )
                    updated_context = updated_context.without_variable(
                        "cards_to_select"
                    )
                    # CRITICAL: Also clear interaction_response to prevent reusing the same response
                    updated_context = updated_context.without_variable(
                        "interaction_response"
                    )

                    # CRITICAL FIX: Refresh player references from synced game.players list
                    # The sync in TransferBetweenPlayers updated game.players, but updated_context
                    # still references the OLD player objects from before the sync.
                    # Get fresh player object from the synced game.players list.
                    fresh_activating_player = next(
                        (
                            p
                            for p in updated_context.game.players
                            if p.id == context.activating_player.id
                        ),
                        context.activating_player,  # fallback
                    )
                    logger.info(
                        f"🔄 REPEAT REFRESH: Using fresh activating player from game.players "
                        f"(obj_id={id(fresh_activating_player)}, score_pile_size={len(fresh_activating_player.score_pile)})"
                    )

                    # Refresh context with fresh player references
                    updated_context = updated_context.with_player(
                        fresh_activating_player
                    )
                    updated_context = updated_context.with_variable(
                        "activating_player", fresh_activating_player
                    )

                    # Execute the demand again with the refreshed context
                    return self.execute(updated_context)
        else:
            logger.info(
                f"🔄 OARS DEBUG: Repeat condition NOT met - repeat_on_compliance={self.repeat_on_compliance}, compliance_count={self.compliance_count}"
            )

        # CRITICAL: Reset current_player to activating_player for non-demand effects
        # The demand may have changed current_player to an opponent
        final_context = updated_context.with_player(context.activating_player)

        # Return to the phase that initiated the demand
        return PhaseResult.success(self.return_phase, final_context)

    def _execute_fallback_actions(self, context: DogmaContext) -> PhaseResult:
        """Execute fallback actions when no one can comply"""
        logger.info(f"Executing {len(self.fallback_actions)} fallback actions")

        # Activity: log fallback activation before executing actions (e.g., draw a 1)
        try:
            if activity_logger:
                activity_logger.log_dogma_fallback_activated(
                    game_id=context.game.game_id,
                    player_id=context.activating_player.id,
                    card_name=context.card.name,
                    fallback_reason="No players could comply with demand",
                    fallback_effect=f"{len(self.fallback_actions)} action(s)",
                )
        except Exception:
            pass

        # Execute fallback actions inline (simplified approach)

        try:
            fallback_context = context
            # ENHANCEMENT: Set context for state tracking to identify this as demand fallback
            fallback_context = fallback_context.with_variable(
                "current_effect_context", "demand_fallback"
            )

            for i, action_config in enumerate(self.fallback_actions):
                logger.debug(f"Executing fallback action {i}: {action_config}")

                # CRITICAL FIX: Check execute_as to determine which player executes the action
                # Fallback actions should execute for the ACTIVATING player by default
                exec_as = (
                    (action_config.get("execute_as") or "activating").lower()
                    if isinstance(action_config, dict)
                    else "activating"
                )
                if exec_as in ("activating", "demanding", "active"):
                    exec_player = context.activating_player
                else:
                    # This shouldn't happen for fallback actions, but handle it
                    exec_player = context.player

                # Switch context to the correct player
                exec_context = fallback_context.with_player(exec_player)

                logger.info(
                    f"Executing fallback action for {exec_player.name} (execute_as={exec_as})"
                )

                # Execute action using Effect abstraction
                effect = EffectFactory.create(action_config)
                result = effect.execute(exec_context)

                if result.success:
                    # Update context with clean results (no internal signals)
                    fallback_context = fallback_context.with_variables(result.variables)
                    fallback_context = fallback_context.with_results(
                        tuple(result.results)
                    )
                else:
                    logger.warning(f"Fallback action {i} failed: {result.error}")

            # Complete with fallback results
            return PhaseResult.success(self.return_phase, fallback_context)

        except Exception as e:
            logger.error(f"Error executing fallback actions: {e}", exc_info=True)
            return PhaseResult.error(f"Fallback actions failed: {e}", context)

    def _can_player_comply(self, player, context: DogmaContext) -> bool:
        """
        Check if player can potentially comply with demand.

        This implements comprehensive compliance checking (Spec 3.2)
        by examining each demand action to see if the player has
        the required resources.
        """
        logger.debug(f"Checking if {player.name} can comply with demand")

        return self._can_comply_with_actions(player, self.demand_actions)

    def _can_comply_with_actions(self, player, actions: list[dict[str, Any]]) -> bool:
        """
        Recursively check if player can comply with a list of actions.

        Handles ConditionalAction by checking both branches.
        """
        logger.debug(
            f"🔍 COMPLIANCE CHECK: Checking {player.name} for {len(actions)} actions"
        )

        for action in actions:
            action_type = action.get("type")
            logger.debug(f"  Checking action type: {action_type}")

            if action_type in ["SelectCards", "SelectHighest", "SelectLowest"]:
                # Check if player has cards in required source
                source = action.get("source", "hand")
                cards = self._get_cards_from_source(player, source)
                logger.debug(f"  🔍 {player.name} has {len(cards)} cards in {source}")
                logger.debug(f"     Cards: {[c.name for c in cards]}")

                # Apply any filters
                filter_config = action.get("filter", {})
                if filter_config:
                    logger.debug(f"  🔍 Applying filter: {filter_config}")
                    filtered_cards = self._apply_filter(cards, filter_config)
                    logger.debug(f"  🔍 After filter: {len(filtered_cards)} cards match")
                    logger.debug(
                        f"     Matching cards: {[c.name for c in filtered_cards]}"
                    )
                    cards = filtered_cards

                if not cards:
                    logger.warning(
                        f"❌ {player.name} CANNOT COMPLY: No cards in {source} matching filter {filter_config}"
                    )
                    return False
                else:
                    logger.debug(
                        f"✅ {player.name} CAN comply: {len(cards)} matching cards found"
                    )

            elif action_type == "TransferBetweenPlayers":
                # Check if player has cards to transfer
                from_location = action.get("from_location", "hand")
                from_cards = self._get_cards_from_source(player, from_location)
                logger.debug(
                    f"  🔍 Transfer check: {player.name} has {len(from_cards)} cards in {from_location}"
                )
                if not from_cards:
                    logger.warning(
                        f"❌ {player.name} CANNOT COMPLY: No cards in {from_location} to transfer"
                    )
                    return False

            elif action_type == "ConditionalAction":
                # For conditional actions, check if player can comply with either branch
                # We check both branches because we can't evaluate conditions without running the demand
                if_true = action.get("if_true", [])
                if_false = action.get("if_false", [])

                logger.debug("  Checking ConditionalAction branches")
                # Player can comply if they can satisfy either branch
                can_comply_true = (
                    self._can_comply_with_actions(player, if_true) if if_true else True
                )
                can_comply_false = (
                    self._can_comply_with_actions(player, if_false)
                    if if_false
                    else True
                )

                # If they can't comply with either branch, they can't comply with the demand
                if not (can_comply_true or can_comply_false):
                    logger.warning(
                        f"❌ {player.name} CANNOT COMPLY: Cannot satisfy either branch of conditional"
                    )
                    return False

            elif action_type in [
                "CountSymbols",
                "DrawCards",
                "DrawUntil",
                "RevealAndProcess",
            ]:
                # These are preparatory actions that don't block compliance
                # CountSymbols just counts, DrawCards gives them cards to use
                logger.debug(f"  Skipping preparatory action: {action_type}")
                continue

            # Add more action type checks as needed

        logger.debug(
            f"✅ {player.name} CAN COMPLY with all {len(actions)} demand actions"
        )
        return True

    def _get_cards_from_source(self, player, source: str):
        """Get cards from specified source location"""
        if source == "hand":
            return getattr(player, "hand", [])
        elif source == "score_pile":
            return getattr(player, "score_pile", [])
        elif source == "board":
            board = getattr(player, "board", None)
            return board.get_all_cards() if board else []
        elif source == "board_top":
            board = getattr(player, "board", None)
            return board.get_top_cards() if board else []
        elif source == "board_bottom":
            # Bottom cards from each color stack
            board = getattr(player, "board", None)
            if not board:
                return []
            bottom_cards = []
            for color in ["red", "blue", "green", "yellow", "purple"]:
                cards = getattr(board, f"{color}_cards", [])
                if cards:
                    bottom_cards.append(cards[0])  # First card is bottom
            return bottom_cards
        elif source == "achievements":
            return getattr(player, "achievements", [])
        elif source == "achievements_available":
            # Available achievement cards from the game (flatten the dict to a list)
            if hasattr(self, "context") and hasattr(self.context, "game"):
                achievement_cards_dict = getattr(
                    self.context.game, "achievement_cards", {}
                )
                # Flatten the dict[int, list[Card]] to list[Card]
                available_achievements = []
                for age_achievements in achievement_cards_dict.values():
                    available_achievements.extend(age_achievements)
                return available_achievements
            return []
        elif source == "opponent_hand":
            # This is tricky - in a demand context, we need to check all opponents
            # But this method only has access to one player, so this might need game context
            logger.warning(
                "opponent_hand source requires game context - may not work in demand phase"
            )
            return []
        elif source == "revealed":
            # Cards in reveal location (temporary holding)
            return getattr(player, "revealed_cards", [])
        elif source == "filtered":
            # This refers to cards from a previous FilterCards action
            # In demand context, this would need to be stored in demand state
            logger.warning(
                "filtered source requires action context - may not work in demand phase"
            )
            return []
        elif source.startswith("deck_"):
            # Age deck sources like deck_2, deck_3, etc.
            try:
                age = int(source[5:])  # Extract number after "deck_"
                if hasattr(self, "context") and hasattr(self.context, "game"):
                    age_decks = getattr(self.context.game, "age_decks", {})
                    return age_decks.get(age, [])
            except (ValueError, AttributeError):
                pass
            logger.warning(f"Age deck source {source} requires game context")
            return []
        elif source == "stack_beneath":
            # Cards beneath the top card in board stacks
            board = getattr(player, "board", None)
            if not board:
                return []
            beneath_cards = []
            for color in ["red", "blue", "green", "yellow", "purple"]:
                cards = getattr(board, f"{color}_cards", [])
                if len(cards) > 1:  # If there are cards beneath the top
                    beneath_cards.extend(cards[:-1])  # All except the last (top)
            return beneath_cards
        elif source == "last_drawn":
            # Cards from most recent DrawCards action
            return getattr(player, "last_drawn_cards", [])
        elif source == "selected_cards":
            # Cards from previous SelectCards action
            return getattr(player, "selected_cards", [])
        elif source == "cards_to_return":
            # Cards selected to be returned to age decks
            return getattr(player, "cards_to_return", [])
        elif source == "cards_to_return_effect2":
            # Cards selected in a secondary return action
            return getattr(player, "cards_to_return_effect2", [])
        elif source == "last_returned":
            # Cards from most recent ReturnCards action
            return getattr(player, "last_returned_cards", [])
        elif source == "deck" or source == "age_deck":
            # Generic age deck - needs context for which age
            logger.warning("Generic deck/age_deck source needs age specification")
            return []
        elif source == "available":
            # Cards available for some action (context-dependent)
            logger.warning("available source requires action context")
            return []
        elif source in [
            "special_achievements_available",
            "achievements_special_available",
        ]:
            # Special achievement cards available
            if hasattr(self, "context") and hasattr(self.context, "game"):
                return getattr(self.context.game, "special_achievement_cards", [])
            return []
        elif source == "special_achievements_junk":
            # Special achievements in junk pile
            logger.warning("special_achievements_junk source not implemented")
            return []
        else:
            logger.warning(f"Invalid card source: {source}")
            return []

    def _apply_filter(self, cards, filter_config: dict[str, Any]):
        """Apply filter configuration to card list"""
        if not filter_config:
            return cards

        filtered_cards = cards

        logger.debug(f"🔍 FILTER: Applying filter {filter_config} to {len(cards)} cards")

        # Apply has_symbol filter (support string or enum)
        if "has_symbol" in filter_config:
            from models.card import Symbol  # local import to avoid cycles
            from utils.symbol_mapping import string_to_symbol

            required_symbol_cfg = filter_config["has_symbol"]
            logger.debug(f"  Filter requires symbol: {required_symbol_cfg}")

            # Convert string names to Symbol enum when needed
            required_symbol_enum = (
                string_to_symbol(required_symbol_cfg)
                if isinstance(required_symbol_cfg, str)
                else required_symbol_cfg
            )
            logger.debug(f"  Converted to enum: {required_symbol_enum}")

            def _card_has_symbol(card, sym) -> bool:
                if not hasattr(card, "symbols"):
                    logger.debug(f"    {card.name} has no symbols attribute")
                    return False

                card_symbols = card.symbols
                logger.debug(f"    {card.name} symbols: {card_symbols}")

                if isinstance(sym, Symbol):
                    has_it = sym in card_symbols
                    logger.debug(f"    {card.name} has {sym}? {has_it}")
                    return has_it

                # Fallback: compare by value strings
                try:
                    has_it = any(getattr(s, "value", s) == sym for s in card_symbols)
                    logger.debug(f"    {card.name} has {sym} (string match)? {has_it}")
                    return has_it
                except Exception as e:
                    logger.debug(f"    {card.name} symbol check failed: {e}")
                    return False

            filtered_cards = [
                card
                for card in filtered_cards
                if _card_has_symbol(card, required_symbol_enum)
            ]

            logger.debug(f"  ✅ After has_symbol filter: {len(filtered_cards)} cards")
            logger.debug(f"     Matching cards: {[c.name for c in filtered_cards]}")

        # Add more filter types as needed

        return filtered_cards

    def on_target_completed(self, complied: bool) -> None:
        """Called by DemandTargetPhase when target processing completes"""
        logger.info(
            f"🔄 OARS DEBUG: on_target_completed called - complied={complied}, current_compliance_count={self.compliance_count}"
        )
        if complied:
            self.compliance_count += 1
            logger.info(
                f"🔄 OARS DEBUG: Target complied! Incremented compliance_count to {self.compliance_count}"
            )
        else:
            logger.info(
                f"🔄 OARS DEBUG: Target did NOT comply, compliance_count remains {self.compliance_count}"
            )

        # Move to next target
        self.current_target_index += 1

        # If no more targets, complete demand
        if self.current_target_index >= len(self.can_comply):
            logger.info("🔄 OARS DEBUG: All targets processed, moving to COMPLETE state")
            self.state = DemandState.COMPLETE

    def get_phase_name(self) -> str:
        """Return phase name with current state"""
        return f"DemandPhase[{self.state.value}]({self.required_symbol})"

    def estimate_remaining_phases(self) -> int:
        """Estimate remaining phases"""
        remaining_targets = len(self.can_comply) - self.current_target_index
        # Each target adds 1 phase, plus completion
        return remaining_targets + 1
