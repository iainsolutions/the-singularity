"""Effect execution phase for dogma processing.

This phase executes individual effects in sequence, routing demand effects
to specialized phases and handling state capture properly.

IMPORTANT: This phase uses the Effect abstraction layer and never directly
imports or interacts with action primitives, following the ActionPrimitiveAdapter
pattern specified in DOGMA_TECHNICAL_SPECIFICATION.md.
"""

import logging
import os
from typing import Any

from logging_config import activity_logger


def safe_get(obj, attr, default=None):
    """Safely get attribute from Pydantic object or dictionary."""
    if hasattr(obj, attr):  # Pydantic object
        return getattr(obj, attr, default)
    elif isinstance(obj, dict):  # Dictionary
        return obj.get(attr, default)
    else:
        return default


from ..core.context import DogmaContext
from ..core.phases import DogmaPhase, PhaseResult
from ..effects import EffectFactory, EffectResult
from ..state.capture import StateCapture
from .completion import CompletionPhase

logger = logging.getLogger(__name__)


class EffectExecutionPhase(DogmaPhase):
    """Phase 2: Execute individual effects in sequence.

    This phase handles:
    1. Standard effect execution with state capture
    2. Routing demand effects to DemandPhase
    3. Handling interactions
    4. Transitioning to sharing/completion
    """

    def __init__(self, effects: list[Any], current_index: int = 0):
        """Initialize effect execution phase.

        Args:
            effects: List of effects to execute
            current_index: Index of current effect (for resumption)
        """
        self.effects = effects
        self.current_index = current_index
        self.is_sharing = False  # Set to True when executing for sharing players

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Execute effects in sequence."""
        self.log_phase_start(context)

        # Check if all effects complete
        if self.current_index >= len(self.effects):
            if self.is_sharing:
                # Done with sharing, move to completion
                return self._complete_sharing(context)
            else:
                # Done with activating player, check for sharing
                return self._start_sharing_if_applicable(context)

        # Note: In The Singularity, non-demand effects still execute for the active player
        # even if a demand had no compliance. The active player always gets their rewards.

        # Get current effect
        effect = self.effects[self.current_index]

        # Execute the effect first, then route based on result
        return self._execute_and_route(effect, context)

    def _is_demand_effect(self, effect_config: Any) -> bool:
        """Check if effect is a demand effect."""
        if isinstance(effect_config, dict):
            return safe_get(effect_config, "type") == "DemandEffect"
        return False

    def _requires_interaction(self, effect_config: Any) -> bool:
        """Check if effect requires player interaction."""
        # DemandEffect always requires interaction as opponents need to respond
        if self._is_demand_effect(effect_config):
            return True

        # Check configuration for known interactive effect types
        if isinstance(effect_config, dict):
            effect_type = safe_get(effect_config, "type", "")
            if effect_type in {"SelectCards", "SelectAchievement", "ChooseOption"}:
                return True

            # Fall back to effect adapter's classification
            try:
                effect = EffectFactory.create(effect_config)
                from ..effects import EffectType

                return getattr(effect, "type", None) == EffectType.INTERACTION
            except Exception:
                return False

        return False

    def _execute_and_route(
        self, effect_config: Any, context: DogmaContext
    ) -> PhaseResult:
        """Execute effect and route based on EffectResult flags."""
        logger.debug(
            f"Executing and routing effect {self.current_index}: {effect_config}"
        )

        # Cities expansion: Check if we need to double execution for endorsed dogma
        is_endorsed = context.get_variable("endorsed", False)
        is_activating_player = not self.is_sharing
        is_demand = self._is_demand_effect(effect_config)

        # Execute the effect using the clean interface
        try:
            if hasattr(self, "_execute_effect_primitive"):
                result = self._execute_effect_primitive(effect_config, context)
            else:
                result = self._execute_effect(effect_config, context)

            # Cities expansion: Double non-demand effects for endorsed dogmas
            if is_endorsed and is_activating_player and not is_demand:
                logger.info(f"Endorsed dogma: Executing effect {self.current_index} twice")

                # Create updated context with results from first execution
                # This ensures second execution sees state changes from first execution
                temp_context = context.with_variables(result.variables)
                temp_context = temp_context.with_results(tuple(result.results))

                # Execute the effect a second time with updated context
                if hasattr(self, "_execute_effect_primitive"):
                    second_result = self._execute_effect_primitive(effect_config, temp_context)
                else:
                    second_result = self._execute_effect(effect_config, temp_context)

                # Merge results from second execution
                # This ensures both executions contribute to the final state
                result.variables.update(second_result.variables)
                result.results.extend(second_result.results)

        except Exception as e:
            error_msg = f"Error executing effect {self.current_index}: {e}"
            logger.error(error_msg, exc_info=True)
            return PhaseResult.error(error_msg, context)

        # Update context with results immediately so routing branches can use them
        updated_context = context.with_variables(result.variables)
        updated_context = updated_context.with_results(tuple(result.results))

        # Route based on explicit EffectResult flags
        if result.routes_to_demand:
            logger.debug("Effect result routes to demand - creating DemandPhase")
            return self._route_to_demand_phase(result.demand_config, updated_context)
        elif (
            result.requires_interaction
            or (updated_context.get_variable("final_interaction_request") is not None)
            or getattr(result, "interaction_request", None)
        ):
            # Treat REQUIRES_INTERACTION as a routable outcome, not a failure
            logger.debug(
                "Effect result indicates interaction required or prepared; routing to InteractionPhase"
            )
            # Log interaction required as activity event for UI visibility
            try:
                if activity_logger:
                    from logging_config import EventType

                    game_id_safe = str(
                        getattr(updated_context.game, "game_id", "test-game")
                    )
                    player_id_safe = str(
                        getattr(updated_context.current_player, "id", "player")
                    )
                    card_name_safe = str(getattr(updated_context.card, "name", "Card"))
                    activity_logger.log_game_event(
                        event_type=EventType.DOGMA_INTERACTION_REQUIRED,
                        game_id=game_id_safe,
                        player_id=player_id_safe,
                        data={
                            "card_name": card_name_safe,
                            "effect_index": self.current_index,
                        },
                    )
            except Exception:
                pass
            return self._route_to_interaction_phase(result, updated_context)
        else:
            # At this point, if success is False it is a real failure
            if not result.success:
                effect_type = (
                    safe_get(effect_config, "type")
                    if isinstance(effect_config, dict)
                    else str(type(effect_config))
                )
                error_detail = result.error or f"no details (type={effect_type})"
                error_msg = f"Effect {self.current_index} failed: {error_detail}"
                logger.error(error_msg)
                return PhaseResult.error(error_msg, updated_context)

            # Standard effect - continue to next
            logger.debug("Effect completed successfully - continuing to next effect")
            self.current_index += 1
            return self.execute(updated_context)

    def _route_to_demand_phase(
        self, demand_config: dict, context: DogmaContext
    ) -> PhaseResult:
        """Route to DemandPhase with the given configuration."""
        from .demand import DemandPhase

        logger.info("Routing to DemandPhase for demand effect")

        # Create return phase for after demand completes
        return_phase = EffectExecutionPhase(self.effects, self.current_index + 1)
        return_phase.is_sharing = self.is_sharing

        # Create and transition to demand phase
        demand_phase = DemandPhase(demand_config, return_phase)
        return PhaseResult.success(demand_phase, context)

    def _route_to_interaction_phase(
        self, result: EffectResult, context: DogmaContext
    ) -> PhaseResult:
        """Route to InteractionPhase with the given interaction request."""
        from .interaction import InteractionPhase

        # Get interaction request from result or context
        interaction_request = result.interaction_request or context.get_variable(
            "final_interaction_request"
        )

        if not interaction_request:
            error_msg = f"Effect {self.current_index} requires interaction but no request was provided"
            logger.error(error_msg)
            return PhaseResult.error(error_msg, context)

        if not isinstance(interaction_request, dict):
            error_msg = f"Invalid interaction request type: expected dict, got {type(interaction_request)}"
            logger.error(error_msg)
            return PhaseResult.error(error_msg, context)

        # Normalize StandardInteractionBuilder format (wrapper) to InteractionPhase expectations
        wrapper_type = safe_get(interaction_request, "type")
        wrapper_data = safe_get(interaction_request, "data")

        if not wrapper_type or wrapper_data is None:
            error_msg = "Invalid interaction request: missing 'type' or 'data' field"
            logger.error(error_msg)
            return PhaseResult.error(error_msg, context)

        # If this is a StandardInteractionBuilder wrapper (type='dogma_interaction'),
        # pass the INNER type to InteractionPhase and the FULL WRAPPER as data so the
        # WebSocket layer receives the expected structure.
        if wrapper_type == "dogma_interaction" and isinstance(wrapper_data, dict):
            inner_type = safe_get(wrapper_data, "type")
            if not inner_type:
                error_msg = (
                    "Invalid StandardInteractionBuilder request: inner 'type' missing"
                )
                logger.error(error_msg)
                return PhaseResult.error(error_msg, context)

            interaction_type = inner_type
            interaction_data = (
                interaction_request  # pass full wrapper to InteractionPhase
            )
            logger.info(
                f"Routing to InteractionPhase for interaction: {interaction_type} (wrapped)"
            )
        else:
            # Legacy/compatibility: pass through as-is
            interaction_type = wrapper_type
            interaction_data = wrapper_data
            logger.info(
                f"Routing to InteractionPhase for interaction: {interaction_type}"
            )

        # Create return phase for after interaction completes
        return_phase = EffectExecutionPhase(self.effects, self.current_index + 1)
        return_phase.is_sharing = self.is_sharing
        # Preserve executor-controlled sharing linkage so that after resuming
        # from sharing interactions we return to the executor to run the
        # activating player's effects next.
        if (
            hasattr(self, "executor_controlled_sharing_phase")
            and self.executor_controlled_sharing_phase
        ):
            return_phase.executor_controlled_sharing_phase = (
                self.executor_controlled_sharing_phase
            )

        # Create and transition to interaction phase with correct signature
        interaction_phase = InteractionPhase(
            interaction_type=interaction_type,
            interaction_data=interaction_data,
            return_phase=return_phase,
        )
        return PhaseResult.success(interaction_phase, context)

    def _handle_demand(self, effect: Any, context: DogmaContext) -> PhaseResult:
        """Handle demand effect by routing to DemandPhase."""
        from .demand import DemandPhase

        logger.info(f"Routing to DemandPhase for effect: {effect}")

        # Create return phase for after demand completes
        return_phase = EffectExecutionPhase(self.effects, self.current_index + 1)
        return_phase.is_sharing = self.is_sharing
        # Preserve executor-controlled sharing linkage across demand routing
        if (
            hasattr(self, "executor_controlled_sharing_phase")
            and self.executor_controlled_sharing_phase
        ):
            return_phase.executor_controlled_sharing_phase = (
                self.executor_controlled_sharing_phase
            )

        # Create and transition to demand phase
        demand_phase = DemandPhase(effect, return_phase)
        return PhaseResult.success(demand_phase, context)

    def _handle_interactive(self, effect: Any, context: DogmaContext) -> PhaseResult:
        """Handle effect that requires interaction."""
        logger.debug(f"Executing interactive effect {self.current_index}: {effect}")

        # Execute effect to allow primitives to prepare interaction request
        if hasattr(self, "_execute_effect_primitive"):
            result = self._execute_effect_primitive(effect, context)
        else:
            result = self._execute_effect(effect, context)

        # Update context with any variables/results from effect execution
        updated_context = context.with_variables(result.variables)
        updated_context = updated_context.with_results(tuple(result.results))

        if not result.requires_interaction:
            # Effect completed without needing interaction
            self.current_index += 1
            return self.execute(updated_context)

        # Determine interaction request
        final_request = (
            updated_context.get_variable("final_interaction_request")
            or result.interaction_request
        )
        if not final_request:
            error_msg = f"Effect {self.current_index} requires interaction but no request was provided"
            logger.error(error_msg)
            return PhaseResult.error(error_msg, updated_context)

        try:
            from interaction.builder import StandardInteractionBuilder
        except ImportError as e:
            error_msg = f"Failed to import StandardInteractionBuilder: {e}. Check that interaction module is available."
            logger.error(error_msg)
            return PhaseResult.error(error_msg, updated_context)

        # Enhanced validation for malformed interaction data
        try:
            if not isinstance(final_request, dict):
                error_msg = f"Invalid interaction request type: expected dict, got {type(final_request)}"
                logger.error(error_msg)
                return PhaseResult.error(error_msg, updated_context)

            if not safe_get(final_request, "type"):
                error_msg = "Invalid interaction request: missing 'type' field"
                logger.error(error_msg)
                return PhaseResult.error(error_msg, updated_context)
            interaction_data = safe_get(final_request, "data")
            if interaction_data is None:
                error_msg = "Invalid interaction request: missing 'data' field"
                logger.error(error_msg)
                return PhaseResult.error(error_msg, updated_context)

            if not isinstance(interaction_data, dict):
                error_msg = f"Invalid interaction data type: expected dict, got {type(interaction_data)}"
                logger.error(error_msg)
                return PhaseResult.error(error_msg, updated_context)

        except Exception as e:
            error_msg = f"Error validating interaction request: {e}"
            logger.error(error_msg)
            return PhaseResult.error(error_msg, updated_context)

        # Field name contract: Only use 'eligible_cards' - no legacy 'cards' injection
        # StandardInteractionBuilder ensures canonical field names

        # Best-effort validation of interaction format with final request
        is_valid, error = StandardInteractionBuilder.validate_interaction_request(
            final_request
        )
        if not is_valid:
            logger.warning(f"Validation warning for interaction request: {error}")

        return self._handle_direct_interaction_request(final_request, updated_context)

    # Backward-compatible hook for tests that patch primitive execution
    def _execute_effect_primitive(
        self, effect_config: Any, context: DogmaContext
    ) -> "EffectResult":
        """Compatibility wrapper to execute an effect (used by tests)."""
        return self._execute_effect(effect_config, context)

    def _handle_direct_interaction_request(
        self, interaction_request: dict[str, Any], context: DogmaContext
    ) -> PhaseResult:
        """Handle direct interaction request from StandardInteractionBuilder (NEW APPROACH)."""
        import uuid

        from ..interaction_request import InteractionRequest, InteractionType
        from ..result_type import ResultType

        logger.info(
            f"Processing direct interaction request: {safe_get(interaction_request, 'type')}"
        )

        # Map StandardInteractionBuilder type to InteractionType
        interaction_data_type = safe_get(
            safe_get(interaction_request, "data", {}), "type", ""
        )
        type_mapping = {
            "select_cards": InteractionType.SELECT_CARDS,
            "select_achievement": InteractionType.SELECT_ACHIEVEMENT,
            "choose_option": InteractionType.CHOOSE_OPTION,
            "return_cards": InteractionType.RETURN_CARDS,
            "select_color": InteractionType.SELECT_COLOR,
            "select_symbol": InteractionType.SELECT_SYMBOL,
            "choose_highest_tie": InteractionType.CHOOSE_HIGHEST_TIE,
        }

        interaction_type = type_mapping.get(
            interaction_data_type, InteractionType.CHOOSE_OPTION
        )

        if interaction_type == InteractionType.CHOOSE_OPTION:
            logger.debug(
                f"Mapped interaction type '{interaction_data_type}' to CHOOSE_OPTION"
            )
        else:
            logger.debug(
                f"Mapped interaction type '{interaction_data_type}' to {interaction_type}"
            )

        interaction_id = str(uuid.uuid4())

        # Create return phase for after interaction completes
        return_phase = EffectExecutionPhase(self.effects, self.current_index + 1)
        return_phase.is_sharing = self.is_sharing

        # Field name contract: Only use 'eligible_cards' - no legacy field injection
        # StandardInteractionBuilder ensures canonical field names

        # Extract message from the interaction data
        default_message = "Please make your selection"
        interaction_data = safe_get(interaction_request, "data", {})
        message = safe_get(interaction_data, "message") or safe_get(
            interaction_request, "message", default_message
        )

        # Create InteractionRequest with the final WebSocket message
        interaction_request_obj = InteractionRequest(
            id=interaction_id,
            player_id=context.current_player.id,
            type=interaction_type,
            data=interaction_data,  # Pass the interaction data
            message=message,
        )

        # Return as interaction result - the DogmaExecutor will handle the WebSocket send
        return PhaseResult(
            type=ResultType.INTERACTION,  # type: ignore
            next_phase=return_phase,
            context=context,
            interaction=interaction_request_obj,  # type: ignore
        )

    def _handle_interaction_request(
        self, interaction_config: dict[str, Any], context: DogmaContext
    ) -> PhaseResult:
        """Handle interaction request from action primitive (LEGACY - via adapter)."""
        from .interaction import InteractionPhase

        logger.info(f"Creating interaction phase for {interaction_config['type']}")

        # Create return phase for after interaction completes
        return_phase = EffectExecutionPhase(self.effects, self.current_index)
        return_phase.is_sharing = self.is_sharing

        # Create interaction phase with sharing context
        context_updates = {
            safe_get(interaction_config, "store_result", "selected_cards"): [],
            "is_sharing_phase": self.is_sharing,  # Pass sharing context
        }

        # Use interaction_config directly - frontend expects eligible_cards
        logger.info(
            f"Interaction config field names: {list(interaction_config.keys())}"
        )
        if safe_get(interaction_config, "eligible_cards"):
            logger.info(
                f"Number of eligible cards: {len(safe_get(interaction_config, 'eligible_cards', []))}"
            )
            logger.info(
                f"First eligible card: {safe_get(interaction_config, 'eligible_cards')[0]}"
            )

        interaction_phase = InteractionPhase(
            interaction_type=interaction_config["type"],
            interaction_data=interaction_config,
            return_phase=return_phase,
            context_updates=context_updates,
        )

        return PhaseResult.success(interaction_phase, context)

    def _handle_standard(
        self, effect_config: Any, context: DogmaContext
    ) -> PhaseResult:
        """Handle standard (non-demand, non-interactive) effect."""
        logger.debug(f"Executing standard effect {self.current_index}: {effect_config}")

        # Log effect execution start
        if activity_logger:
            try:
                effect_description = (
                    safe_get(effect_config, "description", str(effect_config))
                    if isinstance(effect_config, dict)
                    else str(effect_config)
                )
                effect_type = "sharing_effect" if self.is_sharing else "self_effect"
                game_id_safe = str(getattr(context.game, "game_id", "test-game"))
                player_id_safe = str(getattr(context.current_player, "id", "player"))
                card_name_safe = str(getattr(context.card, "name", "Card"))
                activity_logger.log_dogma_effect_executed(
                    game_id=game_id_safe,
                    player_id=player_id_safe,
                    card_name=card_name_safe,
                    effect_index=self.current_index,
                    effect_description=effect_description,
                    effect_type=effect_type,
                    is_sharing=self.is_sharing,
                )
            except Exception:
                pass

        # Capture state before effect
        state_before = None
        game_state_before = None
        try:
            state_before = StateCapture.capture_player_state(context.current_player)
            game_state_before = StateCapture.capture_game_state(context.game)
        except Exception:
            pass

        try:
            # Execute the effect using the Effect abstraction
            # Allow tests to patch primitive execution hook
            if hasattr(self, "_execute_effect_primitive"):
                result = self._execute_effect_primitive(effect_config, context)
            else:
                result = self._execute_effect(effect_config, context)

            if result.success:
                # Check if we need to route to demand phase (clean interface)
                if result.routes_to_demand:
                    logger.debug(
                        "Effect signaled demand routing through clean interface"
                    )
                    # Update context with clean variables (no internal signals)
                    updated_context = context.with_variables(result.variables)
                    updated_context = updated_context.with_results(
                        tuple(result.results)
                    )
                    return self._handle_demand(result.demand_config, updated_context)

                # Update context with results
                updated_context = context.with_variables(result.variables)
                updated_context = updated_context.with_results(tuple(result.results))

                # Capture state after effect
                state_after = None
                game_state_after = None
                try:
                    state_after = StateCapture.capture_player_state(
                        context.current_player
                    )
                    game_state_after = StateCapture.capture_game_state(context.game)
                except Exception:
                    pass

                # Check for meaningful change (important for sharing detection)
                # Check both player state and game state changes
                if (
                    self.is_sharing
                    and state_before
                    and state_after
                    and (
                        StateCapture.states_differ(state_before, state_after)
                        or (
                            game_state_before
                            and game_state_after
                            and StateCapture.game_states_differ(
                                game_state_before, game_state_after
                            )
                        )
                    )
                ):
                    # Sharing context automatically tracks when sharing occurs
                    logger.debug(
                        f"Sharing player {context.current_player.name} made meaningful change"
                    )

                # Log state changes and detailed action results
                if (
                    state_before
                    and state_after
                    and StateCapture.states_differ(state_before, state_after)
                ):
                    changes = StateCapture.get_state_changes(state_before, state_after)
                    logger.info(
                        f"Effect {self.current_index} caused changes: {changes}"
                    )

                    # Add action log entries for UI display
                    self._add_action_log_entries(context, result, changes)

                    # Log detailed card actions if activity logger is available
                    if activity_logger:
                        self._log_detailed_card_actions(
                            context, result, changes, state_before, state_after
                        )

                # CRITICAL FIX: Check for immediate victory conditions after each effect
                # According to The Singularity Ultimate rules, victory should be checked immediately
                # when conditions are met, not just at end of dogma
                from ..victory_checker import VictoryChecker

                victory_result = VictoryChecker.check_immediate_victory(
                    updated_context.game, updated_context
                )
                if victory_result:
                    logger.info(f"IMMEDIATE VICTORY DETECTED: {victory_result}")
                    # Set victory flag and complete dogma immediately
                    final_context = updated_context.with_variable(
                        "victory_achieved", victory_result
                    )
                    final_context = final_context.with_result(
                        f"VICTORY: {victory_result}"
                    )

                    # Import completion phase for immediate completion
                    from .completion import CompletionPhase

                    return PhaseResult.success(CompletionPhase(), final_context)

                # Move to next effect
                self.current_index += 1
                return self.execute(updated_context)

            elif result.requires_interaction:
                # PRECEDENCE VALIDATION: Check for conflicts between interaction and demand routing
                if result.routes_to_demand and result.requires_interaction:
                    logger.warning(
                        f"Effect {self.current_index} signals both demand routing and interaction. "
                        "Demand routing takes precedence over interaction for rule compliance."
                    )
                    # Route to demand phase instead of interaction
                    updated_context = context.with_variables(result.variables)
                    updated_context = updated_context.with_results(
                        tuple(result.results)
                    )

                    from .demand import DemandPhase

                    return_phase = EffectExecutionPhase(
                        self.effects, self.current_index + 1
                    )
                    return_phase.is_sharing = self.is_sharing
                    demand_config = result.demand_config or {}
                    demand_phase = DemandPhase(demand_config, return_phase)
                    return PhaseResult.success(demand_phase, updated_context)

                # Update context with results first (needed for interaction handling)
                updated_context = context.with_variables(result.variables)
                updated_context = updated_context.with_results(tuple(result.results))

                # NEW APPROACH: Check for direct interaction request from primitive first
                final_request = updated_context.get_variable(
                    "final_interaction_request"
                )
                # NEW APPROACH: Check for direct interaction request from primitive first
                final_request = updated_context.get_variable(
                    "final_interaction_request",
                )
                if final_request:
                    logger.debug(
                        f"Effect created direct interaction request: {safe_get(final_request, 'type', 'unknown')}"
                    )
                    if (
                        isinstance(final_request, dict)
                        and safe_get(final_request, "type") == "dogma_interaction"
                    ):
                        from interaction.builder import StandardInteractionBuilder

                        (
                            is_valid,
                            error,
                        ) = StandardInteractionBuilder.validate_interaction_request(
                            final_request
                        )
                        if not is_valid:
                            logger.warning(
                                f"Validation warning for interaction request: {error}"
                            )

                        return self._handle_direct_interaction_request(
                            final_request, updated_context
                        )

                    raise NotImplementedError(
                        "Interactive effects must provide StandardInteractionBuilder 'dogma_interaction' requests"
                    )
                # LEGACY: Check if we have interaction request from the effect adapter
                elif result.interaction_request:
                    logger.debug(
                        f"Effect requires interaction: {safe_get(result.interaction_request, 'type', 'unknown')}"
                    )
                    return self._handle_interaction_request(
                        result.interaction_request, updated_context
                    )
                else:
                    # No interaction config provided
                    error_msg = f"Effect {self.current_index} requires interaction but no config provided"
                    logger.error(error_msg)
                    return PhaseResult.error(error_msg, context)

            else:
                # Effect failed
                effect_type = (
                    safe_get(effect_config, "type")
                    if isinstance(effect_config, dict)
                    else str(type(effect_config))
                )
                error_detail = result.error or f"no details (type={effect_type})"
                error_msg = f"Effect {self.current_index} failed: {error_detail}"
                logger.error(error_msg)
                return PhaseResult.error(error_msg, context)

        except Exception as e:
            error_msg = f"Error executing effect {self.current_index}: {e}"
            logger.error(error_msg, exc_info=True)
            return PhaseResult.error(error_msg, context)

    def _execute_effect(
        self, effect_config: Any, context: DogmaContext
    ) -> EffectResult:
        """Execute effect using configured execution path.

        By default, use the Effect adapter layer to ensure clean translation
        and consistent error handling. The direct primitive path can be enabled
        via env var DOGMA_USE_DIRECT_PRIMITIVES=true.
        """
        use_direct = os.getenv("DOGMA_USE_DIRECT_PRIMITIVES", "false").lower() == "true"

        if use_direct:
            try:
                logger.debug(
                    f"Using direct primitive execution for effect: {safe_get(effect_config, 'type', 'unknown')}"
                )
                result = self._execute_primitive_directly(effect_config, context)
                logger.info(
                    f"Direct execution completed for {safe_get(effect_config, 'type', 'unknown')}"
                )
                return result
            except Exception as e:
                logger.warning(
                    f"Direct primitive execution failed for {safe_get(effect_config, 'type', 'unknown')}, "
                    f"falling back to adapter: {e}"
                )

        # Adapter execution (default)
        logger.debug(
            f"Using adapter execution path for effect: {safe_get(effect_config, 'type', 'unknown')}"
        )
        result = self._execute_effect_via_adapter(effect_config, context)
        logger.info(
            f"Adapter execution completed for {safe_get(effect_config, 'type', 'unknown')}"
        )
        return result

    def _execute_primitive_directly(
        self, effect_config: Any, context: DogmaContext
    ) -> EffectResult:
        """Execute action primitive directly without adapter translation."""
        from action_primitives import create_action_primitive
        from action_primitives.base import ActionContext, ActionResult

        # Validate effect configuration before primitive execution
        if not isinstance(effect_config, dict):
            error_msg = (
                f"Effect configuration must be a dictionary, got: {type(effect_config)}"
            )
            logger.error(f"PRIMITIVE EXECUTION FAILED: {error_msg}")
            return EffectResult(success=False, error=error_msg)

        # DEBUG: Log the critical field name check
        logger.debug(
            f"Effect config validation: effect_config keys = {list(effect_config.keys())}"
        )

        if "type" not in effect_config:
            error_msg = (
                f"Effect configuration missing required 'type' field: {effect_config}"
            )
            logger.error(f"PRIMITIVE EXECUTION FAILED: {error_msg}")
            return EffectResult(success=False, error=error_msg)

        action_name = safe_get(effect_config, "type")
        logger.debug(f"Found effect type: {action_name}")

        # Create action primitive with better error handling
        try:
            primitive = create_action_primitive(effect_config)
            if not primitive:
                error_msg = f"Failed to create primitive for type '{action_name}': create_action_primitive returned None"
                logger.error(f"PRIMITIVE CREATION FAILED: {error_msg}")
                return EffectResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Failed to create primitive for type '{action_name}': {type(e).__name__}: {e}"
            logger.error(f"PRIMITIVE CREATION FAILED: {error_msg}")
            logger.error(f"Effect config that caused the failure: {effect_config}")
            return EffectResult(success=False, error=error_msg)

        # Validate action name
        if not action_name or not isinstance(action_name, str):
            error_msg = f"Effect 'type' must be a non-empty string, got: {action_name}"
            logger.error(f"PRIMITIVE EXECUTION FAILED: {error_msg}")
            return EffectResult(success=False, error=error_msg)

        # Create ActionContext from DogmaContext
        action_context = ActionContext(
            game=context.game,
            player=context.current_player,
            card=context.card,
            variables=dict(context.variables),
            results=[],
            state_tracker=context.state_tracker,
        )

        # Execute primitive with better error handling
        try:
            result = primitive.execute(action_context)
            logger.debug(f"Primitive execution result: {result}")
        except Exception as e:
            error_msg = f"Primitive execution failed for type '{action_name}': {type(e).__name__}: {e}"
            logger.error(f"PRIMITIVE EXECUTION FAILED: {error_msg}")
            logger.error(f"Exception details: {e}", exc_info=True)
            return EffectResult(success=False, error=error_msg)

        # Validate result
        if result is None:
            error_msg = f"Primitive execution returned None for type '{action_name}'"
            logger.error(f"PRIMITIVE EXECUTION FAILED: {error_msg}")
            return EffectResult(success=False, error=error_msg)

        # Convert ActionResult to EffectResult with better failure messaging
        if result == ActionResult.FAILURE:
            err = (
                action_context.variables.get("error")
                or action_context.variables.get("error_message")
                or f"Primitive '{action_name}' returned FAILURE"
            )
            return EffectResult(
                success=False,
                error=str(err),
                variables=dict(action_context.variables),
                results=list(action_context.results),
            )

        effect_result = EffectResult(
            success=(result == ActionResult.SUCCESS),
            requires_interaction=(result == ActionResult.REQUIRES_INTERACTION),
            variables=dict(action_context.variables),
            results=list(action_context.results),
        )

        # Check for demand routing
        if "pending_demand_config" in action_context.variables:
            demand_config = action_context.variables["pending_demand_config"]
            if (
                demand_config
                and isinstance(demand_config, dict)
                and safe_get(demand_config, "type") == "DemandEffect"
            ):
                effect_result.routes_to_demand = True
                effect_result.demand_config = demand_config

        return effect_result

    def _execute_effect_via_adapter(
        self, effect_config: Any, context: DogmaContext
    ) -> EffectResult:
        """Execute effect using the Effect abstraction layer (LEGACY).

        This method creates an Effect adapter and executes it, receiving
        a clean EffectResult with no internal signals or primitive details.
        """
        # Create effect adapter using factory
        try:
            effect = EffectFactory.create(effect_config)
        except Exception as e:
            logger.error(
                f"Failed to create effect for config: {effect_config}, error: {e}"
            )
            return EffectResult(
                success=False,
                error=f"Invalid effect configuration: {e}",
                variables={},
                results=[],
            )

        # Execute the effect through the clean interface
        try:
            result = effect.execute(context)

            # The result is already clean - no internal signals to handle
            logger.debug(
                f"Effect execution result: success={result.success}, "
                f"routes_to_demand={result.routes_to_demand}, "
                f"requires_interaction={result.requires_interaction}"
            )

            return result

        except Exception as e:
            logger.error(f"Error executing effect: {e}", exc_info=True)
            return EffectResult(
                success=False,
                error=f"Effect execution failed: {e}",
                variables={},
                results=[],
            )

    def _start_sharing_if_applicable(self, context: DogmaContext) -> PhaseResult:
        """Check if sharing should occur and start sharing phase if needed."""
        # DISABLED: Sharing is now controlled by the executor
        logger.info(
            "PHASE SHARING DISABLED: Sharing is now handled by executor-controlled sharing"
        )

        # No sharing, move to completion
        logger.debug("No sharing players, moving to completion")
        completion_phase = CompletionPhase()
        return PhaseResult.success(completion_phase, context)

    def _complete_sharing(self, context: DogmaContext) -> PhaseResult:
        """Complete sharing for current player and determine next step."""
        logger.debug("Sharing effects complete for this player")

        # Get the original sharing context that was stored when creating isolated context
        original_sharing_context = context.get_variable("_original_sharing_context")

        if original_sharing_context is not None:
            # Merge the isolated context results back to the original sharing context
            logger.debug(
                f"Merging isolated context results from player {context.current_player.name}"
            )
            merged_context = original_sharing_context.merge_isolated_results(context)

            # Clear player-scoped variables to prevent pollution between sharing players
            from ..core.context import clear_player_scope_variables

            cleaned_context = clear_player_scope_variables(merged_context)
            logger.debug("Cleared player-scoped variables from merged context")

            # Log completion and context merging
            self._log_sharing_turn_complete(context, cleaned_context)
        else:
            # Fallback to current context if no original context stored
            logger.warning("No original sharing context found - using current context")
            cleaned_context = context

        # Determine if this sharing player made meaningful changes
        player_shared = False
        try:
            # Heuristic: look for common action results or variables set by primitives
            for r in context.results or []:
                if isinstance(r, str):
                    rl = r.lower()
                    if (
                        rl.startswith("drew")
                        or rl.startswith("melded")
                        or rl.startswith("scored")
                        or "archive" in rl
                        or "junk" in rl
                        or "returned" in rl
                    ):
                        player_shared = True
                        break
            # Variables set by primitives (cards_drawn, melded_cards, etc.)
            if not player_shared:
                if (
                    context.get_variable("cards_drawn", 0)
                    or context.get_variable("cards_drawn_this_turn", 0)
                    or context.get_variable("melded_cards", None)
                ):
                    player_shared = True
        except Exception:
            player_shared = False

        # Mark current player as having completed sharing
        updated_context = cleaned_context.complete_sharing_for_player(
            context.current_player.id, player_shared
        )

        # Ensure context returns to the activating player before proceeding
        updated_context = updated_context.with_player(updated_context.activating_player)

        # EXECUTOR CONTROL: Check if we're under executor-controlled sharing
        if (
            hasattr(self, "executor_controlled_sharing_phase")
            and self.executor_controlled_sharing_phase
        ):
            logger.info(
                "EXECUTOR SHARING: Returning control to ExecutorControlledSharingPhase"
            )
            # Always return to executor - it will handle activating player execution
            return PhaseResult.success(
                self.executor_controlled_sharing_phase, updated_context
            )

        # Only check sharing completion if NOT under executor control
        if updated_context.is_sharing_complete():
            # All sharing complete, move to completion
            logger.info("All sharing players complete - moving to completion")

            # Clean up sharing phase markers before returning to activating player
            final_context = self._clean_sharing_phase_markers(updated_context)

            # Log handoff to activating player
            self._log_handoff_to_activating_player(final_context)

            completion_phase = CompletionPhase()
            return PhaseResult.success(completion_phase, final_context)
        else:
            # Continue with next sharing player
            from .sharing import SharingPhase

            sharing_phase = SharingPhase(effects=self.effects)
            return PhaseResult.success(sharing_phase, updated_context)

    def _log_sharing_turn_complete(
        self, isolated_context: DogmaContext, cleaned_context: DogmaContext
    ) -> None:
        """Log structured message when completing sharing turn and merging context"""
        from logging_config import EventType, activity_logger

        if activity_logger:
            # Get merging statistics
            isolated_vars = dict(isolated_context.variables)
            cleaned_vars = dict(cleaned_context.variables)
            removed_vars = [key for key in isolated_vars if key not in cleaned_vars]
            preserved_vars = list(cleaned_vars.keys())

            activity_logger.log_game_event(
                event_type=EventType.DOGMA_SHARING_BENEFIT,
                game_id=isolated_context.game.game_id,
                player_id=isolated_context.current_player.id,
                message=f"Completed sharing turn for {isolated_context.current_player.name} - context merged and cleaned",
                data={
                    "transaction_id": isolated_context.transaction_id,
                    "card_name": isolated_context.card.name,
                    "sharing_player_id": isolated_context.current_player.id,
                    "sharing_player_name": isolated_context.current_player.name,
                    "anyone_shared": isolated_context.anyone_shared(),
                    "results_count": len(isolated_context.results),
                    "isolated_variable_count": len(isolated_vars),
                    "cleaned_variable_count": len(cleaned_vars),
                    "removed_player_variables": removed_vars,
                    "preserved_variables": preserved_vars,
                    "phase": "sharing_turn_complete",
                },
            )

            # Also log phase transition for context merging
            activity_logger.log_phase_transition(
                game_id=isolated_context.game.game_id,
                transaction_id=isolated_context.transaction_id,
                player_id=isolated_context.current_player.id,
                card_name=isolated_context.card.name,
                phase_name="EffectExecutionPhase",
                transition_type="exit",
                context_variables={
                    "isolated_variable_count": len(isolated_vars),
                    "cleaned_variable_count": len(cleaned_vars),
                    "removed_player_variables": removed_vars,
                    "preserved_variables": preserved_vars,
                    "results_count": len(isolated_context.results),
                    "anyone_shared": isolated_context.anyone_shared(),
                },
            )

    def _log_handoff_to_activating_player(self, context: DogmaContext) -> None:
        """Log structured message for handoff to activating player"""
        from logging_config import EventType, activity_logger

        if activity_logger:
            # Get final sharing statistics
            sharing_stats = (
                context.sharing.get_sharing_stats() if context.sharing else {}
            )

            activity_logger.log_game_event(
                event_type=EventType.DOGMA_COMPLETED,
                game_id=context.game.game_id,
                player_id=context.activating_player.id,
                message=f"All sharing complete - handing off to activating player {context.activating_player.name}",
                data={
                    "transaction_id": context.transaction_id,
                    "card_name": context.card.name,
                    "activating_player_id": context.activating_player.id,
                    "activating_player_name": context.activating_player.name,
                    "anyone_shared": context.anyone_shared(),
                    "total_results": len(context.results),
                    "sharing_stats": sharing_stats,
                    "final_variables": list(context.variables.keys()),
                    "phase": "handoff_to_activating_player",
                },
            )

            # Also log phase transition for handoff to activating player
            activity_logger.log_phase_transition(
                game_id=context.game.game_id,
                transaction_id=context.transaction_id,
                player_id=context.activating_player.id,
                card_name=context.card.name,
                phase_name="CompletionPhase",
                transition_type="enter",
                context_variables={
                    "anyone_shared": context.anyone_shared(),
                    "total_results": len(context.results),
                    "sharing_stats": sharing_stats,
                    "final_variables": list(context.variables.keys()),
                },
            )

    def _clean_sharing_phase_markers(self, context: DogmaContext) -> DogmaContext:
        """Clean up sharing phase marker variables from context"""
        # Remove sharing phase markers that might affect subsequent execution
        cleaned_context = context

        # Remove is_sharing_phase marker
        if context.has_variable("is_sharing_phase"):
            cleaned_context = cleaned_context.without_variable("is_sharing_phase")
            logger.debug("Removed is_sharing_phase marker from context")

        # Remove in_sharing_phase marker
        if context.has_variable("in_sharing_phase"):
            cleaned_context = cleaned_context.without_variable("in_sharing_phase")
            logger.debug("Removed in_sharing_phase marker from context")

        return cleaned_context

    def get_phase_name(self) -> str:
        """Return phase name with current effect index."""
        sharing_suffix = " (sharing)" if self.is_sharing else ""
        return f"EffectExecutionPhase[{self.current_index}/{len(self.effects)}]{sharing_suffix}"

    def estimate_remaining_phases(self) -> int:
        """Estimate phases remaining."""
        remaining_effects = len(self.effects) - self.current_index
        # Each effect could potentially be a demand (adds 2 phases)
        # Plus sharing (1 phase) plus completion (1 phase)
        return remaining_effects * 2 + 2

    def _add_action_log_entries(
        self, context: DogmaContext, result: "EffectResult", changes: dict
    ) -> None:
        """Add action log entries for UI display based on effect results."""
        from models.game import ActionType

        try:
            # Add entries based on action primitive results
            for action_result in result.results:
                if isinstance(action_result, str):
                    # Parse common action result patterns and add to action log
                    if (
                        "drew" in action_result.lower()
                        or "scored" in action_result.lower()
                        or "melded" in action_result.lower()
                        or "revealed" in action_result.lower()
                        or "transferred" in action_result.lower()
                        or "returned" in action_result.lower()
                        or "archived" in action_result.lower()
                        or "splayed" in action_result.lower()
                        or "selected" in action_result.lower()
                        or "condition" in action_result.lower()
                        or "no cards" in action_result.lower()
                        or "none" in action_result.lower()
                        or "using previously" in action_result.lower()
                        or "found" in action_result.lower()
                    ):
                        context.game.add_log_entry(
                            player_name=context.current_player.name,
                            action_type=ActionType.DOGMA,
                            description=f"{action_result} (from {context.card.name})",
                        )
                        # Mirror into activity stream for UI visibility
                        try:
                            from logging_config import EventType, activity_logger

                            activity_logger.log_game_event(
                                event_type=EventType.DOGMA_EFFECT_EXECUTED,
                                game_id=context.game.game_id,
                                player_id=context.current_player.id,
                                data={
                                    "card_name": context.card.name,
                                    "result": action_result,
                                },
                                message=action_result,
                            )
                        except Exception:
                            pass

            # Add entries based on state changes if no specific action results
            if not result.results and changes:
                if changes.get("hand_size_change"):
                    change = changes["hand_size_change"]
                    if change > 0:
                        context.game.add_log_entry(
                            player_name=context.current_player.name,
                            action_type=ActionType.DOGMA,
                            description=f"gained {change} cards to hand (from {context.card.name})",
                        )
                    elif change < 0:
                        context.game.add_log_entry(
                            player_name=context.current_player.name,
                            action_type=ActionType.DOGMA,
                            description=f"lost {abs(change)} cards from hand (from {context.card.name})",
                        )

                if changes.get("score_pile_change"):
                    change = changes["score_pile_change"]
                    if change > 0:
                        context.game.add_log_entry(
                            player_name=context.current_player.name,
                            action_type=ActionType.DOGMA,
                            description=f"scored {change} cards (from {context.card.name})",
                        )
                    elif change < 0:
                        context.game.add_log_entry(
                            player_name=context.current_player.name,
                            action_type=ActionType.DOGMA,
                            description=f"lost {abs(change)} score cards (from {context.card.name})",
                        )

                if changes.get("board_changes"):
                    for color, board_change in changes["board_changes"].items():
                        if board_change.get("cards_added", 0) > 0:
                            context.game.add_log_entry(
                                player_name=context.current_player.name,
                                action_type=ActionType.DOGMA,
                                description=f"deployed {board_change['cards_added']} cards to {color} stack (from {context.card.name})",
                            )

        except Exception as e:
            logger.warning(f"Error adding action log entries: {e}")

    def _log_detailed_card_actions(
        self,
        context: DogmaContext,
        result: "EffectResult",
        changes: dict,
        _state_before: Any,
        _state_after: Any,
    ) -> None:
        """Log detailed card actions based on state changes and action results."""
        try:
            # Log specific card actions based on results from action primitives
            for action_result in result.results:
                if isinstance(action_result, str):
                    # Parse common action result patterns
                    if "drew" in action_result.lower():
                        # Extract draw information
                        parts = action_result.split()
                        if "age" in action_result.lower():
                            age_match = [p for p in parts if p.isdigit()]
                            age = int(age_match[0]) if age_match else None
                            activity_logger.log_dogma_card_action(
                                game_id=context.game.game_id,
                                player_id=context.current_player.id,
                                card_name=context.card.name,
                                action_type="drawn",
                                cards=[],
                                target_age=age,
                                description=action_result,
                                effect_index=self.current_index,
                            )

                    elif "scored" in action_result.lower():
                        activity_logger.log_dogma_card_action(
                            game_id=context.game.game_id,
                            player_id=context.current_player.id,
                            card_name=context.card.name,
                            action_type="scored",
                            cards=[],
                            description=action_result,
                            effect_index=self.current_index,
                        )

                    elif "melded" in action_result.lower():
                        activity_logger.log_dogma_card_action(
                            game_id=context.game.game_id,
                            player_id=context.current_player.id,
                            card_name=context.card.name,
                            action_type="melded",
                            cards=[],
                            description=action_result,
                            effect_index=self.current_index,
                        )

                    elif "revealed" in action_result.lower():
                        activity_logger.log_dogma_card_action(
                            game_id=context.game.game_id,
                            player_id=context.current_player.id,
                            card_name=context.card.name,
                            action_type="revealed",
                            cards=[],
                            description=action_result,
                            effect_index=self.current_index,
                        )

                    elif "transferred" in action_result.lower():
                        activity_logger.log_dogma_card_action(
                            game_id=context.game.game_id,
                            player_id=context.current_player.id,
                            card_name=context.card.name,
                            action_type="transferred",
                            cards=[],
                            description=action_result,
                            effect_index=self.current_index,
                        )

            # Log state-based changes for additional detail
            if changes.get("hand_size_change"):
                change = changes["hand_size_change"]
                if change > 0:
                    activity_logger.log_dogma_card_action(
                        game_id=context.game.game_id,
                        player_id=context.current_player.id,
                        card_name=context.card.name,
                        action_type="hand_change",
                        cards=[],
                        description=f"Hand size increased by {change}",
                        effect_index=self.current_index,
                        card_count=change,
                    )
                elif change < 0:
                    activity_logger.log_dogma_card_action(
                        game_id=context.game.game_id,
                        player_id=context.current_player.id,
                        card_name=context.card.name,
                        action_type="hand_change",
                        cards=[],
                        description=f"Hand size decreased by {abs(change)}",
                        effect_index=self.current_index,
                        card_count=abs(change),
                    )

            if changes.get("score_pile_change"):
                change = changes["score_pile_change"]
                if change != 0:
                    activity_logger.log_dogma_card_action(
                        game_id=context.game.game_id,
                        player_id=context.current_player.id,
                        card_name=context.card.name,
                        action_type="score_change",
                        cards=[],
                        description=f"Score pile changed by {change}",
                        effect_index=self.current_index,
                        card_count=abs(change),
                    )

            if changes.get("board_changes"):
                for color, board_change in changes["board_changes"].items():
                    if board_change.get("cards_added", 0) > 0:
                        activity_logger.log_dogma_card_action(
                            game_id=context.game.game_id,
                            player_id=context.current_player.id,
                            card_name=context.card.name,
                            action_type="melded",
                            cards=[],
                            description=f"Added {board_change['cards_added']} cards to {color} stack",
                            effect_index=self.current_index,
                            card_count=board_change["cards_added"],
                            target_color=color,
                        )

        except Exception as e:
            logger.warning(f"Error in detailed card action logging: {e}")


# Note: EffectResult is now imported from the effects package
# which provides a clean interface with no internal signals
