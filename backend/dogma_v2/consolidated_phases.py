"""
Consolidated Phase System for Dogma v2.0 - Phase 2 Architecture Optimization

This module implements the streamlined 8-phase architecture that consolidates
the original 15+ phases while maintaining all transaction boundaries and
suspension points required for The Singularity's multiplayer turn-based gameplay.

Key improvements over the original system:
1. Reduced complexity: 15+ phases -> 8 core phases
2. Clear responsibilities: Each phase has a single, well-defined purpose
3. Enhanced debugging: Better phase naming and clearer execution flow
4. Preserved suspension points: All interaction points maintained
5. Optimized transitions: Reduced overhead between phases

Phase Architecture (Main Pipeline):
1. InitializationPhase  - Setup context, validate inputs, identify sharing players
2. SharingPhase         - Execute effects for all sharing players (ordered)
3. ExecutionPhase       - Execute card effects for activating player
   ├─> DemandPhase*     - Sub-phase for demand effects (routes back to ExecutionPhase)
4. InteractionPhase     - Handle player interactions (suspension point)
5. ResolutionPhase      - Apply interaction results and resolve effects
6. CompletionPhase      - Finalize results and prepare transaction completion
7. LoggingPhase         - Activity logging and event recording
8. TransactionPhase     - Transaction management and cleanup

*Note: DemandPhase is not a separate pipeline phase but a sub-phase invoked
from ExecutionPhase for demand effects (like Archery). After demand processing,
execution returns to ExecutionPhase to continue with remaining effects.

This consolidation maintains backward compatibility while significantly
improving developer experience and system maintainability.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .core.context import DogmaContext
from .core.phases import PhaseResult, ResultType
from .core.sharing_context import SharingContext
from .exceptions import DogmaError, InteractionError, StateError, ValidationError
from .interaction_request import InteractionRequest
from .phases.demand import DemandPhase
from .phases.execution import EffectExecutionPhase


logger = logging.getLogger(__name__)

TRACER_AVAILABLE = False


def get_execution_tracer():
    return None


@dataclass
class SharingExecutionResult:
    """Result of sharing player execution"""

    success: bool
    context: DogmaContext
    results: list[Any]
    requires_interaction: bool = False
    interaction: InteractionRequest | None = None
    error: str | None = None


# Import ActionExecutionResult from new scheduling module
from dogma_v2.scheduling.result import ActionExecutionResult


# Alias for backward compatibility during migration
EffectExecutionResult = ActionExecutionResult


@dataclass
class DemandExecutionResult:
    """Result of demand execution"""

    success: bool
    context: DogmaContext
    results: list[Any]
    requires_interaction: bool = False
    interaction: InteractionRequest | None = None
    error: str | None = None


class ConsolidatedPhaseType(Enum):
    """Types of consolidated phases in the streamlined architecture"""

    INITIALIZATION = "initialization"
    SHARING = "sharing"
    EXECUTION = "execution"
    INTERACTION = "interaction"
    RESOLUTION = "resolution"
    COMPLETION = "completion"
    LOGGING = "logging"
    TRANSACTION = "transaction"
    DEMAND = "demand"


@dataclass
class PhaseExecutionMetrics:
    """Metrics for phase execution performance monitoring"""

    phase_name: str
    duration_ms: float
    context_variables_count: int
    results_count: int
    suspension_occurred: bool
    error_count: int


class PhaseExecutor:
    """
    Middleware-style executor that centralizes cross-cutting concerns for phase execution.

    This abstraction separates phase orchestration (telemetry, timing, error handling,
    suspension) from domain logic, allowing phases to focus purely on business rules.

    **Responsibilities:**
    - Start/end timing and duration calculation
    - Telemetry tracking (phase_sequence, metrics recording)
    - Exception handling and error formatting
    - Suspension detection and handling
    - Consistent logging of phase lifecycle

    **Usage:**
    Instead of phases manually wrapping their logic in try/except with timing:
    ```python
    def execute(self, context):
        start_time = time.time()
        try:
            context = self._append_to_phase_sequence(context)
            # ... domain logic ...
            duration_ms = (time.time() - start_time) * 1000
            self._record_execution(duration_ms)
            return PhaseResult.success(next_phase, context)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._record_execution(duration_ms)
            return PhaseResult.error(str(e), context)
    ```

    Phases now delegate to PhaseExecutor:
    ```python
    def execute(self, context):
        return PhaseExecutor.execute_phase(self, context, self._execute_impl)

    def _execute_impl(self, context):
        # Pure domain logic without timing/logging boilerplate
        # ... validation, effect execution, etc ...
        return PhaseResult.success(next_phase, context)
    ```
    """

    @staticmethod
    def execute_phase(
        phase: "ConsolidatedPhase",
        context: DogmaContext,
        phase_logic: callable,
    ) -> PhaseResult:
        """
        Execute a phase with centralized cross-cutting concerns.

        Args:
            phase: The phase instance (for metrics recording and naming)
            context: The execution context
            phase_logic: Callable that implements the phase's domain logic
                        Signature: (context: DogmaContext) -> PhaseResult

        Returns:
            PhaseResult with timing, telemetry, and error handling applied
        """
        start_time = time.time()
        phase_name = phase.get_phase_name()

        try:
            logger.info(f"CONSOLIDATED: Starting {phase_name}")

            # Track phase entry for telemetry
            context = phase._append_to_phase_sequence(context)

            # Execute the phase's domain logic
            result = phase_logic(context)

            # Calculate duration and record metrics
            duration_ms = (time.time() - start_time) * 1000

            # Check if result requires suspension (INTERACTION type)
            if result.type == ResultType.INTERACTION:
                phase._record_execution(duration_ms, suspended=True)
                logger.info(
                    f"CONSOLIDATED: {phase_name} suspended for interaction "
                    f"after {duration_ms:.2f}ms"
                )
                return result

            # Normal completion
            phase._record_execution(duration_ms)

            # Check result type for logging
            if result.type == ResultType.SUCCESS:
                logger.info(
                    f"CONSOLIDATED: {phase_name} completed in {duration_ms:.2f}ms"
                )
            elif result.type == ResultType.ERROR:
                logger.error(
                    f"CONSOLIDATED: {phase_name} failed after {duration_ms:.2f}ms: {result.error}"
                )
            elif result.type == ResultType.COMPLETE:
                logger.info(
                    f"CONSOLIDATED: {phase_name} marked complete in {duration_ms:.2f}ms"
                )

            return result

        # Expected validation errors - log at warning level
        except ValidationError as e:
            duration_ms = (time.time() - start_time) * 1000
            phase._record_execution(duration_ms)

            error_msg = f"{phase_name} validation failed: {e}"
            logger.warning(
                f"CONSOLIDATED: Validation error in {phase_name} after {duration_ms:.2f}ms: {e}"
            )

            return PhaseResult.error(error_msg, context)

        # Expected state errors - log at warning level
        except StateError as e:
            duration_ms = (time.time() - start_time) * 1000
            phase._record_execution(duration_ms)

            error_msg = f"{phase_name} state error: {e}"
            logger.warning(
                f"CONSOLIDATED: State error in {phase_name} after {duration_ms:.2f}ms: {e}"
            )

            return PhaseResult.error(error_msg, context)

        # Interaction errors - these may be recoverable
        except InteractionError as e:
            duration_ms = (time.time() - start_time) * 1000
            phase._record_execution(duration_ms)

            error_msg = f"{phase_name} interaction error: {e}"
            # Log based on recoverability
            if e.recoverable:
                logger.warning(
                    f"CONSOLIDATED: Recoverable interaction error in {phase_name} "
                    f"after {duration_ms:.2f}ms: {e}"
                )
            else:
                logger.error(
                    f"CONSOLIDATED: Non-recoverable interaction error in {phase_name} "
                    f"after {duration_ms:.2f}ms: {e}",
                    exc_info=True,
                )

            return PhaseResult.error(error_msg, context)

        # Known dogma errors (base class) - log with appropriate level
        except DogmaError as e:
            duration_ms = (time.time() - start_time) * 1000
            phase._record_execution(duration_ms)

            error_msg = f"{phase_name} failed: {e}"
            # Log based on recoverability
            if e.recoverable:
                logger.warning(
                    f"CONSOLIDATED: Recoverable error in {phase_name} "
                    f"after {duration_ms:.2f}ms: {e}"
                )
            else:
                logger.error(
                    f"CONSOLIDATED: Non-recoverable error in {phase_name} "
                    f"after {duration_ms:.2f}ms: {e}",
                    exc_info=True,
                )

            return PhaseResult.error(error_msg, context)

        # Unexpected errors - log at error level with full traceback
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            phase._record_execution(duration_ms)

            error_msg = f"{phase_name} unexpected error: {e}"
            logger.error(
                f"CONSOLIDATED: Unexpected exception in {phase_name} "
                f"after {duration_ms:.2f}ms: {type(e).__name__}: {e}",
                exc_info=True,
            )

            return PhaseResult.error(error_msg, context)


class ConsolidatedPhase(ABC):
    """Base class for consolidated phases with enhanced debugging and metrics"""

    def __init__(self, phase_type: ConsolidatedPhaseType):
        self.phase_type = phase_type
        self._execution_count = 0
        self._total_duration_ms = 0.0
        self._suspension_count = 0

    @abstractmethod
    def execute(self, context: DogmaContext) -> PhaseResult:
        """Execute the phase logic and return results"""
        pass

    def get_phase_name(self) -> str:
        """Get standardized phase name for logging"""
        return f"Consolidated{self.phase_type.value.title()}Phase"

    def get_execution_metrics(self) -> dict[str, Any]:
        """Get performance metrics for this phase"""
        return {
            "phase_name": self.get_phase_name(),
            "execution_count": self._execution_count,
            "total_duration_ms": self._total_duration_ms,
            "average_duration_ms": self._total_duration_ms
            / max(1, self._execution_count),
            "suspension_count": self._suspension_count,
        }

    def _record_execution(self, duration_ms: float, suspended: bool = False):
        """Record execution metrics"""
        self._execution_count += 1
        self._total_duration_ms += duration_ms
        if suspended:
            self._suspension_count += 1

    def _append_to_phase_sequence(self, context: DogmaContext) -> DogmaContext:
        """Append this phase's name to the phase_sequence tracking list"""
        phase_sequence = context.get_variable("phase_sequence", [])
        phase_name = self.phase_type.value  # e.g., "sharing", "execution"
        phase_sequence.append(phase_name)
        return context.with_variable("phase_sequence", phase_sequence)


class ConsolidatedInitializationPhase(ConsolidatedPhase):
    """
    Phase 1: Initialization and Setup

    Consolidates:
    - Original InitializationPhase
    - Context validation
    - Sharing player identification
    - Effect loading and validation

    Responsibilities:
    1. Validate input parameters (game, player, card)
    2. Set up DogmaContext with initial state
    3. Identify sharing players based on icon counts
    4. Load and validate card effects
    5. Set up transaction context variables
    """

    def __init__(self):
        super().__init__(ConsolidatedPhaseType.INITIALIZATION)

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Initialize dogma execution context"""
        return PhaseExecutor.execute_phase(self, context, self._execute_impl)

    def _execute_impl(self, context: DogmaContext) -> PhaseResult:
        """Domain logic for initialization - pure business rules without boilerplate"""
        # Validate inputs
        if not context.game or not context.activating_player or not context.card:
            return PhaseResult.error(
                "Invalid context: missing game, player, or card", context
            )

        # Set up context variables
        start_time = time.time()  # For start_timestamp variable
        context = context.with_variable("start_timestamp", start_time)
        context = context.with_variable("card_name", context.card.name)
        context = context.with_variable(
            "activating_player_id", context.activating_player.id
        )
        context = context.with_variable("game_id", context.game.game_id)

        # Identify sharing players (this was scattered across multiple phases)
        context = self._identify_sharing_players(context)

        # Load and validate card effects
        context = self._load_card_effects(context)

        # Determine next phase based on sharing players
        if context.sharing.sharing_players:
            next_phase = ConsolidatedSharingPhase()
            logger.info(
                f"CONSOLIDATED: {len(context.sharing.sharing_players)} sharing players found, proceeding to SharingPhase"
            )
        else:
            next_phase = ConsolidatedExecutionPhase()
            logger.info(
                "CONSOLIDATED: No sharing players, proceeding directly to ExecutionPhase"
            )

        return PhaseResult.success(next_phase, context)

    def _identify_sharing_players(self, context: DogmaContext) -> DogmaContext:
        """Identify players who share the dogma effect AND vulnerable players for demands"""
        # This consolidates sharing player identification that was previously
        # scattered across multiple phases and the executor
        sharing_players = []
        vulnerable_players = []  # NEW: Track vulnerable players for demand effects

        # Get the dogma resource symbol (the icon that determines sharing)
        dogma_resource = context.card.dogma_resource
        if not dogma_resource:
            logger.debug(
                "CONSOLIDATED: Card has no dogma resource, no sharing possible"
            )
            # No sharing and no vulnerable players
            context = context.with_sharing_context(SharingContext.empty())
            context = context.with_variable("vulnerable_player_ids", [])
            return context

        # Count the active player's icons for the featured symbol
        active_player_icons = self._get_player_visible_icons(context.activating_player)
        active_player_count = active_player_icons.count(dogma_resource)

        # Record symbol check for active player
        context.state_tracker.record_symbol_check(
            player_name=context.activating_player.name,
            symbol=dogma_resource,
            count=active_player_count,
            context="sharing_active",
        )

        logger.debug(
            f"CONSOLIDATED: Active player {context.activating_player.name} has {active_player_count} {dogma_resource} icons"
        )

        # Check each other player for BOTH sharing and vulnerability
        # Per The Singularity rules:
        # - Sharing: opponent has >= active player's count (for non-demand effects)
        # - Vulnerable: opponent has < active player's count (for demand effects)
        # These are mutually exclusive!
        for player in context.game.players:
            if player.id == context.activating_player.id:
                continue  # Skip the activating player

            # Count this player's icons for the featured symbol
            player_icons = self._get_player_visible_icons(player)
            player_count = player_icons.count(dogma_resource)

            # Record symbol check for opponent
            context.state_tracker.record_symbol_check(
                player_name=player.name,
                symbol=dogma_resource,
                count=player_count,
                context="sharing_opponent",
                meets_requirement=(player_count >= active_player_count),
                required_count=active_player_count,
            )

            # Determine if player shares or is vulnerable (mutually exclusive)
            if player_count >= active_player_count:
                # Sharing: for non-demand effects
                sharing_players.append(player)
                logger.debug(
                    f"CONSOLIDATED: Player {player.name} shares with {player_count} >= {active_player_count} {dogma_resource} icons"
                )
            else:  # player_count < active_player_count
                # Vulnerable: for demand effects
                vulnerable_players.append(player)
                logger.debug(
                    f"CONSOLIDATED: Player {player.name} is VULNERABLE with {player_count} < {active_player_count} {dogma_resource} icons"
                )

        # Convert Player objects to player IDs for storage
        sharing_player_ids = [p.id for p in sharing_players]
        vulnerable_player_ids = [p.id for p in vulnerable_players]

        # Store sharing players in SharingContext
        context = context.with_sharing_context(
            SharingContext.create_for_dogma(sharing_player_ids)
        )
        context = context.with_variable("sharing_players_count", len(sharing_players))

        # Store vulnerable players in context variables
        context = context.with_variable("vulnerable_player_ids", vulnerable_player_ids)

        # Log results
        if sharing_players:
            logger.info(
                f"CONSOLIDATED: Identified {len(sharing_players)} sharing players: {[p.name for p in sharing_players]}"
            )
        else:
            logger.debug("CONSOLIDATED: No sharing players identified")

        if vulnerable_players:
            logger.info(
                f"CONSOLIDATED: Identified {len(vulnerable_players)} vulnerable players: {[p.name for p in vulnerable_players]}"
            )
        else:
            logger.debug("CONSOLIDATED: No vulnerable players identified")

        return context

    def _get_player_visible_icons(self, player) -> list[str]:
        """Get all visible icons for a player (consolidated from multiple locations)"""
        # Use the proper symbol counting that accounts for splays
        # Build a list of all visible symbols by counting each symbol type
        visible_icons = []

        # Base game symbols (also defined in select_symbol.py VALID_SYMBOLS)
        all_symbols = ["circuit", "data", "algorithm", "neural_net", "robot", "human_mind"]

        for symbol in all_symbols:
            count = player.count_symbol(symbol)
            # Add this symbol 'count' times to the list
            visible_icons.extend([symbol] * count)

        return visible_icons

    def _load_card_effects(self, context: DogmaContext) -> DogmaContext:
        """Load and validate card effects with metadata extraction"""
        try:
            # Get card effects
            effects = getattr(context.card, "dogma_effects", [])
            if not effects:
                logger.warning(f"CONSOLIDATED: Card {context.card.name} has no effects")
                return context.with_variable("effects", []).with_variable(
                    "effect_metadata", []
                )

            # CRITICAL FIX: Execute ALL dogma effects, not just one
            # The Singularity rules: All dogma effects on a card execute in order
            # This fixes Bug #2 where Archery's second effect was skipped

            validated_effects = []
            effect_metadata = []  # NEW: Track metadata for each effect

            # CRITICAL FIX: Keep dogma effects grouped, don't flatten actions
            # Each dogma effect should execute completely for each player before moving to next effect
            # This fixes the bug where Domestication's actions were being interleaved individually
            for effect_index, dogma_effect in enumerate(effects):
                logger.debug(
                    f"CONSOLIDATED: Processing dogma effect {effect_index + 1}/{len(effects)} on {context.card.name}"
                )

                # Check if this effect is a demand
                is_demand = False
                if hasattr(dogma_effect, "is_demand"):
                    is_demand = dogma_effect.is_demand
                elif isinstance(dogma_effect, dict):
                    is_demand = dogma_effect.get("is_demand", False)

                # Detect Compel effects (Artifacts expansion)
                is_compel = False
                if hasattr(dogma_effect, "is_compel"):
                    is_compel = dogma_effect.is_compel()

                # Extract actions from the DogmaEffect and keep them grouped
                # CRITICAL FIX: Initialize demand_effect_config to track DemandEffect wrapper
                demand_effect_config = None
                if hasattr(dogma_effect, "actions"):
                    # DogmaEffect object - extract all actions as a group
                    effect_actions = []
                    logger.debug(
                        f"CONSOLIDATED DEBUG: dogma_effect type = {type(dogma_effect)}, hasattr actions = True"
                    )
                    logger.debug(
                        f"CONSOLIDATED DEBUG: dogma_effect.actions = {len(dogma_effect.actions)} items, types = {[type(a) for a in dogma_effect.actions]}"
                    )

                    for action in dogma_effect.actions:
                        if not isinstance(action, dict):
                            logger.error(
                                f"CONSOLIDATED: Action in effect {effect_index + 1} on {context.card.name} is not a dictionary"
                            )
                            continue

                        # Basic validation
                        if "type" not in action:
                            logger.error(
                                f"CONSOLIDATED: Action in effect {effect_index + 1} on {context.card.name} missing 'type' field"
                            )
                            continue

                        # CRITICAL FIX FOR OARS: Check if demand has repeat_on_compliance
                        # If yes, keep the DemandEffect wrapper intact to route through DemandPhase
                        # If no, extract demand_actions for inline execution (existing behavior)
                        if action.get("type") == "DemandEffect" and is_demand:
                            demand_actions = action.get("actions", [])
                            repeat_on_compliance = action.get(
                                "repeat_on_compliance", False
                            )

                            if repeat_on_compliance:
                                # Keep DemandEffect wrapper to route through DemandPhase (has repeat logic)
                                logger.debug(
                                    f"CONSOLIDATED: Keeping DemandEffect wrapper (repeat_on_compliance=True) with {len(demand_actions)} demand_actions"
                                )
                                demand_effect_config = action
                                effect_actions.append(
                                    action
                                )  # Keep wrapper, don't extract
                            elif demand_actions:
                                # Extract demand_actions for inline execution (no repeat needed)
                                logger.debug(
                                    f"CONSOLIDATED: Extracting {len(demand_actions)} demand_actions from DemandEffect wrapper (no repeat)"
                                )
                                logger.debug(
                                    f"CONSOLIDATED DEBUG: demand_actions types = {[a.get('type') for a in demand_actions]}"
                                )
                                logger.debug(
                                    f"CONSOLIDATED DEBUG: effect_actions before extend = {len(effect_actions)}"
                                )
                                demand_effect_config = action
                                effect_actions.extend(
                                    demand_actions
                                )  # Extract for inline execution
                                logger.debug(
                                    f"CONSOLIDATED DEBUG: effect_actions after extend = {len(effect_actions)}"
                                )
                                logger.debug(
                                    f"CONSOLIDATED DEBUG: effect_actions types = {[a.get('type') for a in effect_actions]}"
                                )
                            else:
                                logger.warning(
                                    f"CONSOLIDATED: DemandEffect in {context.card.name} has no demand_actions"
                                )
                                demand_effect_config = None
                        else:
                            effect_actions.append(action)

                    # Store as a grouped effect (list of actions)
                    if effect_actions:
                        validated_effects.append(effect_actions)
                        # CRITICAL FIX: Store demand_config in metadata to preserve repeat_on_compliance
                        metadata = {"is_demand": is_demand}
                        if is_demand and demand_effect_config:
                            # Add is_compel flag to demand_config for Artifacts expansion
                            if is_compel and "is_compel" not in demand_effect_config:
                                demand_effect_config["is_compel"] = True

                            metadata["demand_config"] = demand_effect_config
                            logger.debug(
                                f"CONSOLIDATED: Stored demand_config with repeat_on_compliance={demand_effect_config.get('repeat_on_compliance', False)}, is_compel={is_compel}"
                            )
                        effect_metadata.append(metadata)
                        logger.debug(
                            f"CONSOLIDATED: Effect {effect_index} has {len(effect_actions)} actions, is_demand={is_demand}"
                        )
                    else:
                        # Entire effect had no valid actions - log warning to detect data errors
                        logger.warning(
                            f"CONSOLIDATED: Effect {effect_index + 1} on {context.card.name} has NO valid actions "
                            f"(all actions failed validation). This likely indicates a data error in BaseCards.json."
                        )

                elif isinstance(dogma_effect, dict):
                    # Already in dict format (legacy support) - single action
                    if "type" not in dogma_effect:
                        logger.error(
                            f"CONSOLIDATED: Effect {effect_index + 1} on {context.card.name} missing 'type' field"
                        )
                    else:
                        # Wrap single action in list to maintain consistent structure
                        validated_effects.append([dogma_effect])
                        effect_metadata.append({"is_demand": is_demand})
                else:
                    logger.warning(
                        f"CONSOLIDATED: Unknown dogma effect format in {context.card.name}: {dogma_effect}"
                    )

            # ALWAYS log how many effects we found
            total_actions = sum(len(effect) for effect in validated_effects)
            demand_count = sum(1 for meta in effect_metadata if meta.get("is_demand"))
            logger.info(
                f"CONSOLIDATED: Card {context.card.name} has {len(validated_effects)} dogma effects "
                f"({demand_count} demands, {len(validated_effects) - demand_count} non-demands) "
                f"with {total_actions} total actions (from {len(effects)} raw effects)"
            )

            context = context.with_variable("effects", validated_effects)
            context = context.with_variable("effect_metadata", effect_metadata)  # NEW
            context = context.with_variable("effects_count", len(validated_effects))
            # CRITICAL FIX: Initialize current_effect_index so ExecutionPhase can find it
            context = context.with_variable("current_effect_index", 0)
            logger.debug(
                f"CONSOLIDATED: Loaded {len(validated_effects)} actions from {len(effects)} dogma effects for {context.card.name}"
            )
            return context

        except Exception as e:
            logger.error(
                f"CONSOLIDATED: Failed to load effects for {context.card.name}: {e}",
                exc_info=True,
            )
            return context.with_variable("effects", []).with_variable(
                "effect_metadata", []
            )


class ConsolidatedSharingPhase(ConsolidatedPhase):
    """
    Phase 2: Interleaved Effect Execution (Sharing + Activating Player)

    CRITICAL: This phase implements the correct sharing flow where effects are
    interleaved between sharing players and the activating player:

    For each effect (1, 2, 3...):
        For each sharing player (clockwise order):
            Execute that effect
        For activating player:
            Execute that effect

    This replaces the previous incorrect implementation that executed all effects
    for each sharing player before moving to the activating player.

    Responsibilities:
    1. Execute effects in correct interleaved order
    2. Handle suspensions at the per-effect-per-player level
    3. Resume from the correct effect and player
    4. Transition to next phase when all effects complete
    """

    def __init__(self):
        super().__init__(ConsolidatedPhaseType.SHARING)

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Execute effects with correct interleaving"""
        return PhaseExecutor.execute_phase(self, context, self._execute_impl)

    def _execute_impl(self, context: DogmaContext) -> PhaseResult:
        """Domain logic for sharing phase - interleaved effect execution using ActionPlan"""

        effects = context.get_variable("effects", [])
        effect_metadata = context.get_variable("effect_metadata", [])  # NEW
        if not effects:
            logger.info(
                "CONSOLIDATED: No effects to execute, proceeding to InteractionPhase"
            )
            return PhaseResult.success(ConsolidatedInteractionPhase(), context)

        sharing_player_ids = context.sharing.sharing_players
        vulnerable_player_ids = context.get_variable("vulnerable_player_ids", [])  # NEW

        logger.info(
            f"CONSOLIDATED: Interleaved execution with {len(sharing_player_ids)} sharing players, "
            f"{len(vulnerable_player_ids)} vulnerable players, and {len(effects)} effects"
        )

        # Build player execution order for each effect: sharing players + activating player
        # CRITICAL: Order players clockwise from activating player's perspective
        sharing_players = self._get_sharing_players_in_clockwise_order(
            context.game, context.activating_player, sharing_player_ids
        )

        # NEW: Also get vulnerable players in clockwise order
        vulnerable_players = self._get_sharing_players_in_clockwise_order(
            context.game, context.activating_player, vulnerable_player_ids
        )

        players_per_effect = [*list(sharing_players), context.activating_player]

        # DEBUG: Log sharing context state at start
        logger.debug(
            f"CONSOLIDATED DEBUG: SharingContext state - "
            f"sharing_players={context.sharing.sharing_players}, "
            f"completed_sharing={context.sharing.completed_sharing}, "
            f"current_sharing_player={context.sharing.current_sharing_player}"
        )

        # DEBUG: Log player list details
        player_names = [p.name for p in players_per_effect]
        logger.debug(
            f"CONSOLIDATED DEBUG: players_per_effect = {player_names}, "
            f"sharing_count = {len(sharing_players)}, "
            f"activating = {context.activating_player.name}"
        )

        # Build ActionPlan for interleaved execution using the factory method
        from dogma_v2.scheduling.plan import ActionPlan
        from dogma_v2.scheduling.scheduler import ActionScheduler

        # Get resumption state
        # CRITICAL FIX: Use direct action index instead of calculating from effect/player indices
        # The old calculation was buggy and caused wrong action resumption (skipping to next player)
        resumed_action_index = context.get_variable("resumed_action_index", None)
        resume_primitive_index = context.get_variable("resume_primitive_index", None)

        # Use the ActionPlan factory for sharing with proper demand routing
        # NOTE: The factory routes based on effect metadata:
        # - Demand effects: Only vulnerable players execute (twice if endorsed)
        # - Non-demand effects: Sharing players + activating player execute

        # Cities expansion: Check if dogma is endorsed (doubles demand effects)
        is_endorsed = context.get_variable("endorsed", False)
        logger.info(f"CONSOLIDATED SHARING: Creating plan with endorsed={is_endorsed}")

        plan = ActionPlan.create_sharing_plan(
            effects=effects,
            sharing_players=list(sharing_players),
            activating_player=context.activating_player,
            vulnerable_players=list(vulnerable_players),  # NEW
            effect_metadata=effect_metadata,  # NEW
            effect_start_index=0,
            endorsed=is_endorsed,  # Cities: Double demands for endorsed dogmas
        )

        # Use stored action index directly (no calculation needed!)
        resumption_action_index = (
            resumed_action_index if resumed_action_index is not None else 0
        )

        if resumption_action_index > 0:
            logger.info(
                f"CONSOLIDATED: Resuming sharing at action index {resumption_action_index}"
            )
            plan = plan.reset_to(resumption_action_index)

        # CRITICAL FIX: If we have a mid-primitive resumption, update the action's resume_action_index
        # This happens when an effect has multiple primitives and we suspended at the first one
        logger.info(
            f"CONSOLIDATED SHARING: Checking for mid-primitive resumption - resume_primitive_index={resume_primitive_index}"
        )
        if resume_primitive_index is not None and resume_primitive_index >= 0:
            if resumption_action_index >= len(plan.actions):
                logger.error(
                    f"CONSOLIDATED SHARING: resumption_action_index={resumption_action_index} "
                    f"out of bounds (plan has {len(plan.actions)} actions)"
                )
                return plan
            logger.info(
                f"CONSOLIDATED SHARING: *** MID-PRIMITIVE RESUMPTION DETECTED *** "
                f"Setting resume_action_index={resume_primitive_index} on action {resumption_action_index} "
                f"(this will make scheduler resume at primitive {resume_primitive_index + 1}/{len(plan.actions[resumption_action_index].effect)})"
            )
            # Update the action at resumption_index to have the correct resume_action_index

            actions_list = list(plan.actions)
            current_action = actions_list[resumption_action_index]
            logger.info(
                f"CONSOLIDATED SHARING: Current action has {len(current_action.effect)} primitives, "
                f"current resume_action_index={current_action.resume_action_index}"
            )
            updated_action = current_action.with_resume_index(resume_primitive_index)
            actions_list[resumption_action_index] = updated_action
            plan = ActionPlan(
                actions=tuple(actions_list), resumption_index=resumption_action_index
            )
            logger.info(
                f"CONSOLIDATED SHARING: Updated action now has resume_action_index={updated_action.resume_action_index}"
            )
            # Clear the variable now that we've used it
            context = context.without_variable("resume_primitive_index")
        else:
            logger.info(
                f"CONSOLIDATED SHARING: No mid-primitive resumption (resume_primitive_index={resume_primitive_index})"
            )

        # CRITICAL: Handle sharing context initialization
        # We need to track which player is currently sharing for proper state management
        context = context.with_variable("in_sharing_phase", True)

        # Check if execution tracing is enabled
        trace_recorder = None
        if context.get_variable("_tracing_enabled", False):
            from dogma_v2.scheduling.trace import TraceRecorder

            trace_recorder = TraceRecorder(enabled=True)
            logger.debug("CONSOLIDATED SHARING: Tracing enabled, created TraceRecorder")

        # NOTE: demanding_player is now set only by demand-specific phases, not globally
        # This prevents non-demand effects from being incorrectly treated as demands

        # Execute the plan using ActionScheduler.execute_plan()
        scheduler = ActionScheduler(trace_recorder=trace_recorder)
        result = scheduler.execute_plan(plan, context)

        # Handle interaction suspension
        if result.requires_interaction:
            logger.info(
                f"CONSOLIDATED: Sharing suspended at action {result.suspended_at_action + 1} for interaction"
            )
            # CRITICAL FIX: Store the actual action index directly instead of converting to effect/player
            # The previous approach had a bug where player_idx calculation was incorrect,
            # causing resumption at the wrong action (skipping to next player instead of completing current player's primitives)
            resumed_action_index = result.suspended_at_action

            logger.info(
                f"CONSOLIDATED SHARING: Storing resumed_action_index={resumed_action_index} directly"
            )

            # Store the action index directly
            resumed_context = result.context.with_variable(
                "resumed_action_index", resumed_action_index
            )

            # CRITICAL FIX: Store current_player_in_effect so ResolutionPhase knows
            # which player responded and doesn't incorrectly clear variables.
            # Count how many actions with the same effect_index precede this one.
            suspended_action = plan.actions[resumed_action_index]
            player_in_effect = sum(
                1 for i in range(resumed_action_index)
                if plan.actions[i].effect_index == suspended_action.effect_index
            )
            resumed_context = resumed_context.with_variable(
                "current_player_in_effect", player_in_effect
            )
            logger.info(
                f"CONSOLIDATED SHARING: Set current_player_in_effect={player_in_effect} "
                f"for {suspended_action.player.name}"
            )

            # CRITICAL FIX: Always set resume_primitive_index from SchedulerResult.
            # The scheduler now returns action_idx (same primitive) for REQUIRES_INTERACTION,
            # so all interactive primitives re-execute on resume (they're idempotent).
            # resume_primitive_index=0 is valid and means "re-execute from beginning of effect".
            if result.resume_action_index is not None:
                logger.info(
                    f"CONSOLIDATED: Interaction suspension at primitive {result.resume_action_index}, "
                    f"will resume there on response"
                )
                resumed_context = resumed_context.with_variable(
                    "resume_primitive_index", result.resume_action_index
                )

            return PhaseResult.interaction_required(
                result.interaction,
                ConsolidatedInteractionPhase(),
                resumed_context,
            )

        # Handle demand routing
        if result.routes_to_demand:
            logger.info(
                f"CONSOLIDATED: Sharing suspended at action {result.suspended_at_action} for demand routing"
            )
            # CRITICAL FIX: Store the actual action index directly
            resumed_action_index = result.suspended_at_action

            logger.info(
                f"CONSOLIDATED SHARING: Storing resumed_action_index={resumed_action_index} for demand"
            )

            resumed_context = result.context.with_variable(
                "resumed_action_index", resumed_action_index
            )
            resumed_context = resumed_context.with_variable(
                "demand_config", result.demand_config
            )
            resumed_context = resumed_context.with_variable(
                "demand_invoked_from_phase", "sharing"
            )

            # Preserve mid-primitive resume index for demand routing too
            if result.resume_action_index is not None:
                logger.info(
                    f"CONSOLIDATED: Suspension at primitive {result.resume_action_index} before demand"
                )
                resumed_context = resumed_context.with_variable(
                    "resume_primitive_index", result.resume_action_index
                )

            return PhaseResult.success(ConsolidatedDemandPhase(), resumed_context)

        # Handle failure
        if not result.success:
            error = f"Sharing execution failed: {result.error}"
            logger.error(f"CONSOLIDATED: {error}")
            return PhaseResult.error(error, result.context)

        # All effects completed successfully
        logger.info(
            "CONSOLIDATED: All sharing effects completed, proceeding to InteractionPhase"
        )

        # CRITICAL FIX: Clear resumption variables after sharing completes
        # SharingPhase routes directly to InteractionPhase, bypassing ResolutionPhase
        # which normally clears these variables. Without clearing, stale resume indices
        # cause infinite loops where subsequent phases keep trying to resume at invalid positions.
        logger.info(
            "CONSOLIDATED SHARING: Clearing resumption variables after sharing completion"
        )
        current_context = result.context.without_variable("resume_primitive_index")
        current_context = current_context.without_variable("resumed_action_index")

        current_context = current_context.with_variable("in_sharing_phase", False)
        current_context = current_context.with_variable("in_execution_phase", False)

        return PhaseResult.success(ConsolidatedInteractionPhase(), current_context)

    def _build_interleaved_plan(
        self, effects: list, players_per_effect: list, num_sharing_players: int
    ):
        """Build ActionPlan for interleaved execution (effect1->all players, effect2->all players, etc.)"""
        from dogma_v2.scheduling.plan import ActionPlan, PlannedAction

        actions = []
        for effect_idx, effect in enumerate(effects):
            # Check if this effect is a DemandEffect
            is_demand_effect = self._is_demand_effect(effect)

            for player_idx, player in enumerate(players_per_effect):
                is_sharing = player_idx < num_sharing_players

                # CRITICAL FIX: Skip DemandEffect for sharing players
                # Demands ONLY execute for the activating player, never for sharing players
                if is_demand_effect and is_sharing:
                    logger.debug(
                        f"SHARING: Skipping DemandEffect (effect {effect_idx}) for sharing player {player.name}"
                    )
                    continue

                actions.append(
                    PlannedAction(
                        effect=tuple(effect),
                        effect_index=effect_idx,
                        player=player,
                        is_sharing=is_sharing,
                        clear_variables_after=(
                            player_idx < len(players_per_effect) - 1
                        ),
                        update_sharing_context=is_sharing,
                    )
                )

        return ActionPlan(actions=tuple(actions))

    def _is_demand_effect(self, effect: list) -> bool:
        """Check if an effect list contains a DemandEffect primitive.

        Args:
            effect: List of action primitive dicts

        Returns:
            True if the effect contains a DemandEffect, False otherwise
        """
        if not effect or not isinstance(effect, list):
            return False

        # Check each action primitive in the effect
        for primitive in effect:
            if isinstance(primitive, dict) and primitive.get("type") == "DemandEffect":
                return True

        return False

    def _execute_plan_with_context_management(
        self,
        plan,
        context: DogmaContext,
        players_per_effect: list,
        num_sharing_players: int,
        effects: list,
    ) -> PhaseResult:
        """Execute plan while managing sharing context, variable clearing, etc."""
        from dogma_v2.scheduling.scheduler import ActionScheduler

        scheduler = ActionScheduler()
        current_context = context

        while not plan.is_complete:
            action = plan.get_next_action()
            if action is None:
                break

            # Calculate which effect and player we're on
            action_index = plan.resumption_index
            effect_index = action.effect_index
            player_index = action_index % len(players_per_effect)
            player = action.player
            is_sharing = action.is_sharing

            logger.info(
                f"CONSOLIDATED: Effect {effect_index+1} for player {player.name} "
                f"({'sharing' if is_sharing else 'activating'})"
            )

            # Set effect context for state tracking
            effect_context = f"effect_{effect_index + 1}"
            current_context = current_context.with_variable(
                "current_effect_context", effect_context
            )
            current_context = current_context.with_variable(
                "current_effect_index", effect_index
            )
            current_context = current_context.with_variable(
                "current_player_in_effect", player_index
            )
            current_context = current_context.with_variable(
                "is_sharing_execution", is_sharing
            )

            # CRITICAL: Set current sharing player BEFORE executing effect
            if is_sharing:
                if current_context.sharing.current_sharing_player != player.id:
                    logger.debug(f"CONSOLIDATED: Starting sharing for {player.name}")
                    current_context = current_context.start_sharing_for_player(
                        player.id
                    )
                else:
                    logger.debug(
                        f"CONSOLIDATED: Resuming sharing for {player.name} (already started)"
                    )

            # Clear player-specific effect variables when switching to a DIFFERENT player
            # This prevents variable leaking between sharing players (e.g. to_return from AI reused by human)
            # Do NOT clear when resuming for the SAME player (they need their interaction response)
            prev_player_id = current_context.get_variable("_last_executing_player_id")
            if prev_player_id and prev_player_id != player.id:
                # Clear ALL non-system variables to prevent any leaking between players
                # Cards use arbitrary store_result names (to_meld, drawn_cards, etc.)
                # so a hardcoded list will always miss some
                system_vars = {
                    "phase_sequence", "start_timestamp", "card_name", "activating_player_id",
                    "game_id", "sharing_players_count", "vulnerable_player_ids",
                    "effects", "effect_metadata", "effects_count",
                    "current_effect_index", "current_effect_context",
                    "in_sharing_phase", "in_execution_phase",
                    "is_sharing_execution", "demanding_player",
                    "resumed_action_index", "current_player_in_effect",
                    "_last_executing_player_id", "_last_responding_player_id",
                    "_demand_transfer_count_accumulator",
                }
                for var_name in list(current_context.variables.keys()):
                    if var_name not in system_vars:
                        current_context = current_context.without_variable(var_name)
            current_context = current_context.with_variable("_last_executing_player_id", player.id)

            # Execute the action via scheduler
            result = scheduler.execute_action(
                effect=list(action.effect),
                effect_index=effect_index,
                player=player,
                is_sharing=is_sharing,
                context=current_context,
                resume_action_index=action.resume_action_index,
                is_demand=action.is_demand,  # CRITICAL FIX: Pass demand flag for demanding_player context
            )

            # Handle suspension for interaction
            if result.requires_interaction:
                resumed_context = result.context.with_variable(
                    "current_player_in_effect", player_index
                )
                logger.info(
                    f"CONSOLIDATED: Player {player.name} requires interaction at effect {effect_index+1}, "
                    f"will resume at player index {player_index}"
                )
                return PhaseResult.interaction_required(
                    result.interaction,
                    ConsolidatedInteractionPhase(),
                    resumed_context,
                )

            # Handle failure
            if not result.success:
                error = (
                    f"Effect {effect_index+1} failed for {player.name}: {result.error}"
                )
                logger.error(f"CONSOLIDATED: {error}")
                return PhaseResult.error(error, current_context)

            # Handle demand routing
            if result.routes_to_demand:
                logger.info(
                    f"CONSOLIDATED SHARING: Effect {effect_index+1} for {player.name} routes to demand"
                )
                resumed_context = result.context.with_variable(
                    "current_player_in_effect", player_index
                )
                resumed_context = resumed_context.with_variable(
                    "demand_config", result.demand_config
                )
                resumed_context = resumed_context.with_variable(
                    "demand_invoked_from_phase", "sharing"
                )
                return PhaseResult.success(ConsolidatedDemandPhase(), resumed_context)

            # Update context with results
            current_context = result.context
            for new_result in result.results:
                current_context = current_context.with_result(new_result)

            # Clear player-specific variables if not the last player
            if action.clear_variables_after:
                logger.debug(
                    "CONSOLIDATED: Clearing player-specific variables before next player"
                )
                system_vars = {
                    "phase_sequence", "start_timestamp", "card_name", "activating_player_id",
                    "game_id", "sharing_players_count", "vulnerable_player_ids",
                    "effects", "effect_metadata", "effects_count",
                    "current_effect_index", "current_effect_context",
                    "in_sharing_phase", "in_execution_phase",
                    "is_sharing_execution", "demanding_player",
                    "resumed_action_index", "current_player_in_effect",
                    "_last_executing_player_id", "_last_responding_player_id",
                    "_demand_transfer_count_accumulator",
                }
                for var_name in list(current_context.variables.keys()):
                    if var_name not in system_vars:
                        current_context = current_context.without_variable(var_name)

            # Track sharing results
            if is_sharing:
                shared = self._did_player_share(current_context, player, effect_index)
                if shared:
                    logger.debug(
                        f"CONSOLIDATED: {player.name} shared on effect {effect_index+1}"
                    )

                updated_sharing = current_context.sharing.complete_sharing_for_player(
                    player.id, shared=shared
                )
                current_context = current_context.with_sharing_context(updated_sharing)

            # CRITICAL FIX: Track demand transfers for inline demand execution
            # When demand_actions are executed inline (not through DemandPhase), we need to
            # accumulate transferred_cards and set demand_transferred_count for conditional checks
            if action.is_demand:
                transferred_this_action = current_context.get_variable("transferred_cards", [])
                if transferred_this_action:
                    # Accumulate total demand transfers across all vulnerable players
                    total_demand_transfers = current_context.get_variable(
                        "_demand_transfer_count_accumulator", 0
                    )
                    total_demand_transfers += len(transferred_this_action)
                    current_context = current_context.with_variable(
                        "_demand_transfer_count_accumulator", total_demand_transfers
                    )
                    logger.debug(
                        f"CONSOLIDATED: Demand transfer count accumulated: {total_demand_transfers} "
                        f"(+{len(transferred_this_action)} from {player.name})"
                    )

            # Check if we completed all players for this effect
            if player_index == len(players_per_effect) - 1:
                # All players completed this effect - reset player index for next effect
                current_context = current_context.with_variable(
                    "current_player_in_effect", 0
                )

                # CRITICAL FIX: After demand effect completes for all vulnerable players,
                # set demand_transferred_count for conditional checks in subsequent effects
                if action.is_demand:
                    total_demand_transfers = current_context.get_variable(
                        "_demand_transfer_count_accumulator", 0
                    )
                    current_context = current_context.with_variable(
                        "demand_transferred_count", total_demand_transfers
                    )
                    logger.info(
                        f"CONSOLIDATED: Demand effect {effect_index+1} complete - "
                        f"set demand_transferred_count={total_demand_transfers}"
                    )
                    # Clear accumulator for next demand effect (if any)
                    current_context = current_context.without_variable(
                        "_demand_transfer_count_accumulator"
                    )

                # Clear completed_sharing set for next effect
                if effect_index < len(effects) - 1:
                    logger.debug(
                        "CONSOLIDATED: Clearing completed_sharing set for next effect"
                    )
                    cleared_sharing = current_context.sharing.with_cleared_completed()
                    current_context = current_context.with_sharing_context(
                        cleared_sharing
                    )

                logger.debug(
                    f"CONSOLIDATED: Effect {effect_index+1} complete for all players"
                )

            # Advance plan
            plan = plan.mark_complete(action_index)

        # All effects complete
        current_context = current_context.with_variable("in_sharing_phase", False)
        current_context = current_context.with_variable("in_execution_phase", False)

        logger.info(
            "CONSOLIDATED: All effects completed, proceeding to InteractionPhase"
        )
        return PhaseResult.success(ConsolidatedInteractionPhase(), current_context)

    def _did_player_share(
        self, context: DogmaContext, player, effect_index: int
    ) -> bool:
        """
        Check if a player actually did something with cards during this effect.

        Per The Singularity rules (p. 947-952), sharing occurs when an opponent's use of
        the shared effect causes them to "do something with a card." This includes:
        - splay, meld, tuck, exchange, transfer, draw, achieve, etc.

        Revealing a card does NOT count for sharing.

        Args:
            context: Current dogma context with state_tracker
            player: Player to check for state changes
            effect_index: Current effect index (for context filtering)

        Returns:
            True if player performed any sharing-qualifying action
        """
        # Get the effect context identifier
        effect_context = f"effect_{effect_index + 1}"

        # PERFORMANCE: Use effect-scoped change tracking to avoid iterating
        # through all state changes in long games
        effect_changes = context.state_tracker.get_changes_for_effect(effect_context)

        # Types of state changes that qualify for sharing
        # (excluding symbol_check and hand_check which are just checks)
        sharing_change_types = {
            "draw",
            "transfer",
            "meld",
            "score",
            "tuck",
            "splay",
            "return",
            "achieve",  # If we track achievements
        }

        # Check effect-specific changes for this player
        for change in effect_changes:
            # Check if this is a sharing-qualifying change type
            if change.change_type not in sharing_change_types:
                continue

            # Check if this change was made by the sharing player
            # Different change types store player differently:
            # - Most: data["player"]
            # - Transfer: data["from_player"] or data["to_player"]
            player_name = change.data.get("player")
            from_player = change.data.get("from_player")
            to_player = change.data.get("to_player")

            if (
                player_name == player.name
                or from_player == player.name
                or to_player == player.name
            ):
                logger.debug(
                    f"CONSOLIDATED: {player.name} performed {change.change_type} "
                    f"in {effect_context}, qualifies for sharing"
                )
                return True

        # No qualifying state changes found
        logger.debug(
            f"CONSOLIDATED: {player.name} made no state changes in {effect_context}, "
            f"does not qualify for sharing"
        )
        return False

    def _get_sharing_players_in_clockwise_order(
        self, game, activating_player, sharing_player_ids: set[str]
    ) -> list:
        """
        Get sharing players in clockwise order starting after the activating player.

        CRITICAL: This method ensures correct player ordering independent of
        Game.players list order. The Singularity rules require opponents to execute
        shared effects in clockwise order from the activating player.

        Args:
            game: The Game object
            activating_player: The player who activated the dogma
            sharing_player_ids: Set of player IDs eligible for sharing

        Returns:
            List of Player objects in clockwise order

        Raises:
            ValueError: If activating player is not found in game.players
        """
        # Find activating player's position in the players list
        try:
            activating_index = next(
                i for i, p in enumerate(game.players) if p.id == activating_player.id
            )
        except StopIteration:
            # CRITICAL: This should never happen - activating player must be in game
            # Log error with full context and raise exception to catch bugs early
            logger.error(
                f"CONSOLIDATED: Activating player {activating_player.name} "
                f"(ID: {activating_player.id}) not found in game.players list. "
                f"Game has {len(game.players)} players: "
                f"{[f'{p.name}({p.id})' for p in game.players]}"
            )
            raise ValueError(
                f"Activating player {activating_player.id} not found in game.players. "
                f"This indicates a serious game state corruption bug."
            )

        # Rotate the players list so activating player is first
        # Then take players after the activating player (clockwise order)
        rotated_players = (
            game.players[activating_index:] + game.players[:activating_index]
        )

        # Filter for sharing players only, maintaining clockwise order
        sharing_players = [p for p in rotated_players if p.id in sharing_player_ids]

        return sharing_players


class ConsolidatedExecutionPhase(ConsolidatedPhase):
    """
    Phase 3: Activating Player Execution

    Consolidates:
    - Original EffectExecutionPhase
    - Effect adapter coordination
    - Non-demand effect processing

    Responsibilities:
    1. Execute card effects for the activating player
    2. Handle non-demand effects (transfer, calculation, board, etc.)
    3. Manage effect sequencing and dependencies
    4. Collect execution results
    """

    def __init__(self):
        super().__init__(ConsolidatedPhaseType.EXECUTION)

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Execute card effects for the activating player"""
        return PhaseExecutor.execute_phase(self, context, self._execute_impl)

    def _execute_impl(self, context: DogmaContext) -> PhaseResult:
        """Domain logic for execution phase - activating player effect execution using ActionPlan"""
        from dogma_v2.scheduling.plan import ActionPlan
        from dogma_v2.scheduling.scheduler import ActionScheduler

        # CRITICAL: Ensure current_player is set to activating_player
        if context.current_player != context.activating_player:
            logger.warning(
                f"CONSOLIDATED: current_player was {context.current_player.name}, "
                f"restoring to activating_player {context.activating_player.name}"
            )
            context = context.with_player(context.activating_player)

        # Get effects to execute
        effects = context.get_variable("effects", [])
        effect_metadata = context.get_variable("effect_metadata", [])  # NEW
        if not effects:
            logger.info(
                "CONSOLIDATED: No effects to execute, proceeding to InteractionPhase"
            )
            return PhaseResult.success(ConsolidatedInteractionPhase(), context)

        context = context.with_variable("in_execution_phase", True)

        # Get current effect index (for resumption after interactions)
        current_effect_index = context.get_variable("current_effect_index", 0)

        # NEW: Get vulnerable players for demand routing (even when no sharing players)
        vulnerable_player_ids = context.get_variable("vulnerable_player_ids", [])
        vulnerable_players = []
        if vulnerable_player_ids:
            # Get vulnerable players in clockwise order
            for player in context.game.players:
                if player.id in vulnerable_player_ids:
                    vulnerable_players.append(player)

        logger.info(
            f"CONSOLIDATED EXECUTION: Processing effects from index {current_effect_index}, "
            f"total effects: {len(effects)}, vulnerable players: {len(vulnerable_players)}"
        )

        # Build ActionPlan for execution with demand routing
        # CRITICAL FIX: Use create_sharing_plan instead of create_execution_plan
        # to properly route demands to vulnerable players

        # Cities expansion: Check if dogma is endorsed (doubles demand effects)
        is_endorsed = context.get_variable("endorsed", False)
        logger.info(
            f"CONSOLIDATED EXECUTION: Creating plan with endorsed={is_endorsed}"
        )

        plan = ActionPlan.create_sharing_plan(
            effects=effects,
            sharing_players=[],  # No sharing players (that's why we're in ExecutionPhase)
            activating_player=context.activating_player,
            vulnerable_players=vulnerable_players,  # NEW: Route demands to vulnerable players
            effect_metadata=effect_metadata,  # NEW: Pass effect metadata for routing
            effect_start_index=0,
            endorsed=is_endorsed,  # Cities: Double demands for endorsed dogmas
        )

        # Resume from correct position if needed
        if current_effect_index > 0:
            logger.info(
                f"CONSOLIDATED EXECUTION: Resuming after demand/interaction, continuing with effect {current_effect_index + 1}/{len(effects)}"
            )
            plan = plan.reset_to(current_effect_index)

        # CRITICAL FIX: Apply mid-primitive resumption if needed
        # This handles the case where an effect has multiple primitives and suspended at the first one
        resume_primitive_index = context.get_variable("resume_primitive_index", None)
        if resume_primitive_index is not None and resume_primitive_index >= 0:
            logger.info(
                f"CONSOLIDATED EXECUTION: Mid-primitive resumption detected - "
                f"will resume at primitive {resume_primitive_index + 1} within effect {current_effect_index + 1}"
            )
            # Update the action at current_effect_index to have the correct resume_action_index
            actions_list = list(plan.actions)
            if current_effect_index < len(actions_list):
                current_action = actions_list[current_effect_index]
                logger.info(
                    f"CONSOLIDATED EXECUTION: Current action has {len(current_action.effect)} primitives, "
                    f"setting resume_action_index to {resume_primitive_index}"
                )
                updated_action = current_action.with_resume_index(
                    resume_primitive_index
                )
                actions_list[current_effect_index] = updated_action
                plan = ActionPlan(
                    actions=tuple(actions_list), resumption_index=current_effect_index
                )
                logger.info(
                    f"CONSOLIDATED EXECUTION: Updated action now has resume_action_index={updated_action.resume_action_index}"
                )
            # Clear the variable now that we've used it
            context = context.without_variable("resume_primitive_index")
        else:
            logger.info(
                f"CONSOLIDATED EXECUTION: No mid-primitive resumption (resume_primitive_index={resume_primitive_index})"
            )

        # Check if execution tracing is enabled
        trace_recorder = None
        if context.get_variable("_tracing_enabled", False):
            from dogma_v2.scheduling.trace import TraceRecorder

            trace_recorder = TraceRecorder(enabled=True)
            logger.debug(
                "CONSOLIDATED EXECUTION: Tracing enabled, created TraceRecorder"
            )

        # NOTE: demanding_player is now set only by demand-specific phases, not globally
        # This prevents non-demand effects from being incorrectly treated as demands

        # Execute the plan using ActionScheduler.execute_plan()
        scheduler = ActionScheduler(trace_recorder=trace_recorder)
        result = scheduler.execute_plan(plan, context)

        # Store trace if tracing was enabled
        # Handle interaction suspension
        if result.requires_interaction:
            logger.info(
                f"CONSOLIDATED: Execution suspended at action {result.suspended_at_action + 1} for interaction"
            )
            # Update context with current position for resumption
            updated_context = result.context.with_variable(
                "current_effect_index", result.suspended_at_action
            )

            # Always set resume_primitive_index from scheduler result for interaction suspension.
            # resume_action_index=0 is valid (re-execute from beginning, primitive is idempotent).
            if result.resume_action_index is not None:
                logger.info(
                    f"CONSOLIDATED EXECUTION: Interaction suspension at primitive {result.resume_action_index}, "
                    f"will resume there on response"
                )
                updated_context = updated_context.with_variable(
                    "resume_primitive_index", result.resume_action_index
                )

            return PhaseResult.interaction_required(
                result.interaction,
                ConsolidatedInteractionPhase(),
                updated_context,
            )

        # Handle demand routing
        if result.routes_to_demand:
            logger.info(
                f"CONSOLIDATED: Execution suspended at action {result.suspended_at_action} for demand routing"
            )
            updated_context = result.context.with_variable(
                "demand_config", result.demand_config
            )
            updated_context = updated_context.with_variable(
                "demand_invoked_from_phase", "execution"
            )
            updated_context = updated_context.with_variable(
                "current_effect_index", result.suspended_at_action
            )

            # Preserve mid-primitive resume index for demand routing too
            if result.resume_action_index is not None:
                logger.info(
                    f"CONSOLIDATED EXECUTION: Suspension at primitive {result.resume_action_index} before demand"
                )
                updated_context = updated_context.with_variable(
                    "resume_primitive_index", result.resume_action_index
                )

            return PhaseResult.success(ConsolidatedDemandPhase(), updated_context)

        # Handle failure
        if not result.success:
            error = f"Execution failed: {result.error}"
            logger.error(f"CONSOLIDATED: {error}")
            return PhaseResult.error(error, result.context)

        # All effects completed successfully
        logger.info(
            f"CONSOLIDATED EXECUTION: Finished processing effects. Processed {len(result.all_results)} results"
        )

        current_context = result.context
        current_context = current_context.with_variable("in_execution_phase", False)
        current_context = current_context.with_variable(
            "execution_results_count", len(result.all_results)
        )

        # All effects processed - follow 8-phase pipeline to InteractionPhase
        logger.info(
            "CONSOLIDATED: All effects processed, proceeding to InteractionPhase per 8-phase pipeline"
        )
        return PhaseResult.success(ConsolidatedInteractionPhase(), current_context)


class ConsolidatedInteractionPhase(ConsolidatedPhase):
    """
    Phase 4: Player Interaction Handling

    Consolidates:
    - Original InteractionPhase
    - CardSelectionInteraction
    - ChoiceInteraction
    - All interaction types

    Responsibilities:
    1. Handle all player interaction types (card selection, choices, etc.)
    2. Manage interaction timeouts and cancellation
    3. Validate interaction responses
    4. Route to resolution phase

    This phase serves as a critical suspension point for multiplayer gameplay.
    """

    def __init__(self):
        super().__init__(ConsolidatedPhaseType.INTERACTION)

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Handle player interactions - this phase serves as a routing hub in the 8-phase pipeline"""
        return PhaseExecutor.execute_phase(self, context, self._execute_impl)

    def _execute_impl(self, context: DogmaContext) -> PhaseResult:
        """Domain logic for interaction phase - routing hub for player interactions"""
        # Check if we have a pending interaction that needs to be processed
        interaction_response = context.get_variable("interaction_response")

        if interaction_response:
            # We have an interaction response to process - route to ResolutionPhase
            logger.info(
                "CONSOLIDATED: Interaction response found, routing to ResolutionPhase"
            )
            return PhaseResult.success(ConsolidatedResolutionPhase(), context)

        # Check if we're resuming from a suspended interaction
        if context.get_variable("resuming_from_interaction", False):
            logger.info(
                "CONSOLIDATED: Resuming from interaction, routing to ResolutionPhase"
            )
            return PhaseResult.success(ConsolidatedResolutionPhase(), context)

        # No interactions to process - continue to ResolutionPhase per 8-phase pipeline
        logger.info(
            "CONSOLIDATED: No pending interactions, proceeding to ResolutionPhase per 8-phase pipeline"
        )

        # Follow the documented 8-phase pipeline: InteractionPhase → ResolutionPhase
        return PhaseResult.success(ConsolidatedResolutionPhase(), context)


class ConsolidatedResolutionPhase(ConsolidatedPhase):
    """
    Phase 5: Interaction Resolution and Effect Application

    Consolidates:
    - Original ResolutionPhase
    - Interaction response processing
    - Effect result application
    - Context state updates

    Responsibilities:
    1. Process interaction responses from players
    2. Apply interaction results to game state
    3. Continue effect execution after interactions
    4. Validate interaction outcomes
    5. Route to completion phase
    """

    def __init__(self):
        super().__init__(ConsolidatedPhaseType.RESOLUTION)

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Process interaction responses and apply results"""
        return PhaseExecutor.execute_phase(self, context, self._execute_impl)

    def _execute_impl(self, context: DogmaContext) -> PhaseResult:
        """Domain logic for resolution phase - process interaction results"""
        # Check if we have interaction response to process
        interaction_response = context.get_variable("interaction_response")
        if not interaction_response:
            logger.debug(
                "CONSOLIDATED: No interaction response found, proceeding to completion"
            )
            return PhaseResult.success(ConsolidatedCompletionPhase(), context)

        logger.info(
            f"CONSOLIDATED RESOLUTION: *** Processing interaction response: {interaction_response.get('interaction_id', 'unknown')}"
        )

        # Process the interaction response
        context = self._process_interaction_response(context, interaction_response)

        # CRITICAL: Check if we're in sharing mode - affects index incrementing logic
        # In sharing mode, multiple players execute the same effect sequentially
        # We need to increment player_index, not effect_index, until all players complete
        sharing_players = context.sharing.sharing_players if context.sharing else []
        in_sharing_mode = len(sharing_players) > 0

        current_effect_index = context.get_variable("current_effect_index", 0)
        current_player_in_effect = context.get_variable("current_player_in_effect", 0)
        effects = context.get_variable("effects", [])

        if in_sharing_mode:
            # Calculate total players for this effect (sharing players + activating player)
            total_players_for_effect = len(sharing_players) + 1

            # Check if the current player still has primitives to finish.
            # resume_primitive_index being set means the current player suspended mid-effect
            # (e.g., SelectLowest tie-break) and now needs to re-execute the interactive
            # primitive (idempotent) and then continue with subsequent primitives
            # (e.g., MeldCard, DrawCards).  Do NOT advance to the next player yet.
            resume_prim_for_current = context.get_variable("resume_primitive_index", None)

            # Check if all players have completed this effect
            next_player_index = current_player_in_effect + 1

            if resume_prim_for_current is not None and next_player_index < total_players_for_effect:
                # Current player responded to interaction but still has remaining primitives.
                # Route back to SharingPhase WITHOUT advancing the player index so the
                # scheduler resumes from resume_primitive_index for the same player.
                logger.info(
                    f"CONSOLIDATED RESOLUTION: Player {current_player_in_effect} responded to interaction, "
                    f"resume_primitive_index={resume_prim_for_current} - routing back to SharingPhase "
                    f"to execute remaining primitives for same player (NOT advancing to next player)"
                )
                # Keep resumed_action_index pointing at the current player's action.
                # SharingPhase will apply resume_primitive_index so the scheduler picks up
                # where it left off (SelectLowest will be idempotent, then MeldCard etc. run).
                # Only clear interaction_response so the re-entry doesn't look like a new response.
                context = context.without_variable("interaction_response")
                context = context.without_variable("final_interaction_request")

            elif next_player_index < total_players_for_effect:
                # More players need to execute this effect - increment player index
                context = context.with_variable(
                    "current_player_in_effect", next_player_index
                )

                # CRITICAL FIX: Advance resumed_action_index so SharingPhase resumes at the
                # next player's action in the plan, not the previous player's action.
                current_resumed = context.get_variable("resumed_action_index", 0)
                context = context.with_variable(
                    "resumed_action_index", current_resumed + 1
                )

                # Clear resume_primitive_index - next player starts fresh from primitive 0
                context = context.without_variable("resume_primitive_index")

                # Clear ALL non-system variables to prevent cross-contamination
                system_vars = {
                    "phase_sequence", "start_timestamp", "card_name", "activating_player_id",
                    "game_id", "sharing_players_count", "vulnerable_player_ids",
                    "effects", "effect_metadata", "effects_count",
                    "current_effect_index", "current_effect_context",
                    "in_sharing_phase", "in_execution_phase",
                    "is_sharing_execution", "demanding_player",
                    "resumed_action_index", "current_player_in_effect",
                    "_last_executing_player_id", "_last_responding_player_id",
                    "_demand_transfer_count_accumulator",
                }
                for var_name in list(context.variables.keys()):
                    if var_name not in system_vars:
                        context = context.without_variable(var_name)

                logger.info(
                    f"CONSOLIDATED RESOLUTION: Moving to next player "
                    f"(player {current_player_in_effect} → {next_player_index}, "
                    f"resumed_action_index {current_resumed} → {current_resumed + 1})"
                )
            else:
                # All players have had their interaction for this effect.
                # Check if there are remaining primitives to execute. resume_primitive_index
                # being set (even =0) means the scheduler was suspended mid-effect.
                # The interactive primitive is idempotent - it'll find its result and continue
                # to subsequent primitives (e.g., ConditionalAction after SelectCards).
                resume_prim = context.get_variable("resume_primitive_index", None)

                if resume_prim is not None:
                    # Remaining primitives to execute - route back to SharingPhase to let
                    # the scheduler finish (e.g., ConditionalAction after SelectCards/SelectAchievement).
                    logger.info(
                        f"CONSOLIDATED RESOLUTION: Last player responded, resume_primitive_index={resume_prim}, "
                        f"routing back to SharingPhase to execute remaining primitives"
                    )
                    # Don't advance effect or player - SharingPhase will apply the resume index
                else:
                    # All primitives in effect completed - move to next effect
                    next_effect_index = current_effect_index + 1
                    context = context.with_variable(
                        "current_effect_index", next_effect_index
                    )
                    context = context.with_variable(
                        "current_player_in_effect", 0
                    )  # Reset player index

                    # CRITICAL FIX: Also clear resume_primitive_index when moving to next effect
                    logger.info(
                        f"CONSOLIDATED RESOLUTION: Clearing resume_primitive_index for next effect "
                        f"(moving from effect {current_effect_index} to {next_effect_index})"
                    )
                    context = context.without_variable("resume_primitive_index")

                    logger.info(
                        f"CONSOLIDATED RESOLUTION: Effect {current_effect_index + 1} completed for all {total_players_for_effect} players, "
                        f"advancing to effect {next_effect_index + 1} (total effects: {len(effects)})"
                    )
                    current_effect_index = (
                        next_effect_index  # Update for routing logic below
                    )
        else:
            # No sharing - DON'T increment effect_index here!
            # The scheduler will handle effect advancement naturally when the entire effect completes.
            # This fixes the Pottery bug where we were advancing to effect 1 after SelectCards
            # but before ConditionalAction, causing the card return to never execute.

            # CRITICAL: DO NOT clear resume_primitive_index in non-sharing mode!
            # ExecutionPhase NEEDS this variable to resume at the correct primitive when
            # an effect has multiple primitives (like Archery Effect 2: SelectAchievement + ConditionalAction).
            # ExecutionPhase will clear it itself after using it (line 1373).
            # Clearing it here breaks mid-primitive resumption and causes primitives to re-execute from start.
            logger.info(
                "CONSOLIDATED RESOLUTION: NOT clearing resume_primitive_index (non-sharing) - "
                "ExecutionPhase needs it for mid-primitive resumption"
            )

            logger.info(
                f"CONSOLIDATED RESOLUTION: Interaction completed for effect {current_effect_index + 1}, "
                f"continuing with same effect (total effects: {len(effects)})"
            )
            # DON'T update current_effect_index - let ExecutionPhase handle advancement

        # Check if there are more effects to process
        # Use current_effect_index which has been updated above
        if current_effect_index < len(effects):
            # More effects to process - check if we're in sharing mode
            # If sharing_players exist, we need to route back to SharingPhase to continue
            # interleaved execution, not ExecutionPhase which is only for the activating player
            sharing_players = context.sharing.sharing_players if context.sharing else []

            if sharing_players:
                # We're in sharing mode - route back to SharingPhase for interleaved execution
                logger.info(
                    f"CONSOLIDATED: Continuing with effect {current_effect_index + 1}/{len(effects)} in SharingPhase (interleaved mode)"
                )
                return PhaseResult.success(ConsolidatedSharingPhase(), context)
            else:
                # No sharing - return to ExecutionPhase for activating player only
                logger.info(
                    f"CONSOLIDATED: Continuing with effect {current_effect_index + 1}/{len(effects)} in ExecutionPhase (no sharing)"
                )
                return PhaseResult.success(ConsolidatedExecutionPhase(), context)
        else:
            # All effects processed - move to completion
            logger.info("CONSOLIDATED: All effects processed, proceeding to completion")
            return PhaseResult.success(ConsolidatedCompletionPhase(), context)

    def _process_interaction_response(
        self, context: DogmaContext, response: dict
    ) -> DogmaContext:
        """Process and apply interaction response to context"""
        logger.info(f"CONSOLIDATED: Processing interaction response: {response}")

        # DON'T clear interaction_response here - the Scheduler needs it to prevent
        # clearing selected_cards when executing nested actions (e.g., ConditionalAction)
        # The Scheduler will clear it after checking the flag

        # CRITICAL FIX: Get the store_result variable name from the original interaction
        # If SelectCards used a custom store_result (e.g., "card_to_meld"), we need to
        # store the response to that variable, not just "selected_cards"
        store_result_var = "selected_cards"  # Default
        final_request = context.get_variable("final_interaction_request")
        if final_request:
            # Check if it's a dict or object
            if isinstance(final_request, dict):
                data = final_request.get("data", {})
                if "store_result" in data:
                    store_result_var = data["store_result"]
                    logger.info(
                        f"CONSOLIDATED: Using custom store_result variable: {store_result_var}"
                    )
            elif hasattr(final_request, "data"):
                data = final_request.data
                if isinstance(data, dict) and "store_result" in data:
                    store_result_var = data["store_result"]
                    logger.info(
                        f"CONSOLIDATED: Using custom store_result variable: {store_result_var}"
                    )

        # Apply response data to context variables
        if "selected_cards" in response:
            # CRITICAL FIX: Don't overwrite Card objects with string confirmations
            # The response contains card IDs/names as strings for confirmation,
            # but the actual Card objects are already in context from SelectCards
            existing_cards = context.get_variable("selected_cards")

            # Only update if we don't already have Card objects
            if not existing_cards or not (
                isinstance(existing_cards, list)
                and existing_cards
                and hasattr(existing_cards[0], "color")
            ):
                # No existing Card objects, use response data
                context = context.with_variable(
                    "selected_cards", response["selected_cards"]
                )
                # CRITICAL FIX: Also store to custom variable if specified
                if store_result_var != "selected_cards":
                    context = context.with_variable(
                        store_result_var, response["selected_cards"]
                    )
                    logger.info(
                        f"CONSOLIDATED: Copied selected_cards to {store_result_var}: {response['selected_cards']}"
                    )
                logger.debug(
                    f"CONSOLIDATED: Applied selected_cards from response: {response['selected_cards']}"
                )
            else:
                # Already have Card objects, keep them (response is just confirmation)
                # CRITICAL FIX: Copy to custom variable if it doesn't exist
                if store_result_var != "selected_cards":
                    existing_in_custom = context.get_variable(store_result_var)
                    if not existing_in_custom:
                        context = context.with_variable(
                            store_result_var, existing_cards
                        )
                        logger.info(
                            f"CONSOLIDATED: Copied existing Card objects to {store_result_var}: {[c.name for c in existing_cards]}"
                        )
                logger.debug(
                    f"CONSOLIDATED: Preserving existing Card objects in selected_cards: {[c.name for c in existing_cards]}"
                )

        if "chosen_option" in response:
            context = context.with_variable("chosen_option", response["chosen_option"])
            logger.debug(
                f"CONSOLIDATED: Applied chosen_option: {response['chosen_option']}"
            )

        if "cancelled" in response:
            context = context.with_variable(
                "interaction_cancelled", response["cancelled"]
            )
            logger.debug(f"CONSOLIDATED: Applied cancellation: {response['cancelled']}")

        return context


class ConsolidatedCompletionPhase(ConsolidatedPhase):
    """
    Phase 6: Effect Completion and State Finalization

    Consolidates:
    - Original CompletionPhase
    - Effect result collection
    - Game state finalization
    - Victory condition checks

    Responsibilities:
    1. Collect all effect results
    2. Apply final state changes
    3. Check victory conditions
    4. Prepare logging context
    5. Route to logging phase
    """

    def __init__(self):
        super().__init__(ConsolidatedPhaseType.COMPLETION)

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Finalize dogma execution and prepare for logging"""
        return PhaseExecutor.execute_phase(self, context, self._execute_impl)

    def _execute_impl(self, context: DogmaContext) -> PhaseResult:
        """Domain logic for completion phase - finalize execution"""
        # Collect final results
        final_results = list(context.results)
        logger.info(f"CONSOLIDATED: Collected {len(final_results)} final results")

        # Apply sharing bonus if applicable (The Singularity rules Section 2.6)
        # If anyone shared and board state changed, activating player draws 1 card
        context = self._apply_sharing_bonus(context)

        # Check for victory conditions
        victory_context = self._check_victory_conditions(context)
        if victory_context != context:
            logger.info("CONSOLIDATED: Victory condition detected during completion")
            context = victory_context

        # Set completion metadata
        context = context.with_variable("completion_timestamp", time.time())
        context = context.with_variable(
            "total_effects_processed", len(context.get_variable("effects", []))
        )
        context = context.with_variable("final_results_count", len(final_results))

        return PhaseResult.success(ConsolidatedLoggingPhase(), context)

    def _apply_sharing_bonus(self, context: DogmaContext) -> DogmaContext:
        """Apply sharing bonus: activating player draws if opponents shared and state changed"""
        try:
            # CRITICAL FIX: Check if anyone ACTUALLY shared by looking at state changes
            # Don't just check SharingContext.anyone_shared() which tracks per-effect state
            # but doesn't indicate whether the player actually performed card operations
            # Per The Singularity rules: sharing bonus ONLY if opponent "did something with a card"

            # Get sharing player IDs
            sharing_player_ids = (
                context.sharing.sharing_players if context.sharing else []
            )
            if not sharing_player_ids:
                logger.debug("CONSOLIDATED: No sharing players, no bonus")
                return context

            # Check if ANY sharing player performed qualifying state changes
            # Look at state_tracker for actual card operations (draw, meld, score, tuck, etc.)
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

            # Build set of sharing player names for quick lookup
            sharing_player_names = {
                p.name for p in context.game.players if p.id in sharing_player_ids
            }

            # Check all state changes for sharing players
            anyone_actually_shared = False
            for change in context.state_tracker.changes:
                # Skip non-qualifying change types
                if change.change_type not in sharing_change_types:
                    continue

                # Check if this change was made by a sharing player
                player_name = change.data.get("player")
                from_player = change.data.get("from_player")
                to_player = change.data.get("to_player")

                if (
                    player_name in sharing_player_names
                    or from_player in sharing_player_names
                    or to_player in sharing_player_names
                ):
                    anyone_actually_shared = True
                    logger.debug(
                        f"CONSOLIDATED: Sharing player performed {change.change_type}, "
                        f"qualifies for sharing bonus"
                    )
                    break

            if not anyone_actually_shared:
                logger.debug(
                    "CONSOLIDATED: No sharing players performed card operations, no bonus"
                )
                return context

            logger.info(
                "CONSOLIDATED: Awarding sharing bonus - activating player draws a card"
            )

            # Draw card for activating player
            game = context.game
            activating_player = context.activating_player

            # Determine draw age (highest age on board or 1)
            draw_age = activating_player.board.get_highest_age() or 1

            # Draw from age deck
            drawn_card = game.draw_card(draw_age)
            if drawn_card:
                activating_player.add_to_hand(drawn_card)

                # Record state change for sharing bonus draw
                context.state_tracker.record_draw(
                    player_name=activating_player.name,
                    card_name=drawn_card.name,
                    age=draw_age,
                    revealed=False,
                    context="sharing_bonus",
                )

                # Activity: Log sharing bonus draw event
                try:
                    from logging_config import activity_logger

                    if activity_logger:
                        activity_logger.log_dogma_card_action(
                            game_id=game.game_id,
                            player_id=activating_player.id,
                            card_name=context.card.name,
                            action_type="drawn",
                            cards=[drawn_card],
                            location_from=f"age {draw_age} deck",
                            location_to="hand",
                            reason="sharing_bonus",
                            is_sharing=False,
                        )
                except Exception:
                    pass

                context = context.with_result(
                    f"{activating_player.name} researched an era {draw_age} card as a sharing bonus"
                )
                logger.info(
                    f"CONSOLIDATED: Sharing bonus awarded - {activating_player.name} drew {drawn_card.name}"
                )
            else:
                logger.warning(
                    f"CONSOLIDATED: Could not draw card for sharing bonus - age {draw_age} deck empty"
                )

            return context

        except Exception as e:
            logger.error(
                f"CONSOLIDATED: Exception applying sharing bonus: {e}",
                exc_info=True,
            )
            return context

    def _check_victory_conditions(self, context: DogmaContext) -> DogmaContext:
        """Placeholder for victory condition checks.

        Note: Actual victory checking happens at the AsyncGameManager layer after
        dogma execution completes (achievement claims, age exhaustion, special
        achievements, etc.). The dogma execution layer doesn't need to check
        victory conditions - it just executes effects and returns the modified
        game state to AsyncGameManager, which then checks for victory.

        This placeholder exists for potential future use cases where dogma
        effects might need to trigger immediate victory checks, but currently
        the architecture correctly delegates this responsibility upward.
        """
        try:
            logger.debug("CONSOLIDATED: Victory checking delegated to AsyncGameManager")
            return context
        except Exception as e:
            logger.warning(f"CONSOLIDATED: Victory check placeholder failed: {e}")
            return context



class ConsolidatedLoggingPhase(ConsolidatedPhase):
    """
    Phase 7: Activity Logging and Event Recording

    Consolidates:
    - Original LoggingPhase
    - Activity event generation
    - Performance metrics recording
    - Debug trace generation

    Responsibilities:
    1. Generate activity events
    2. Record performance metrics
    3. Create debug traces
    4. Log execution summary
    5. Route to transaction phase
    """

    def __init__(self):
        super().__init__(ConsolidatedPhaseType.LOGGING)

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Generate logs and activity events"""
        return PhaseExecutor.execute_phase(self, context, self._execute_impl)

    def _execute_impl(self, context: DogmaContext) -> PhaseResult:
        """Domain logic for logging phase - record activity and metrics"""
        # Generate activity events
        self._generate_activity_events(context)

        # Record performance metrics
        self._record_performance_metrics(context)

        # Create debug traces
        self._create_debug_traces(context)

        return PhaseResult.success(ConsolidatedTransactionPhase(), context)

    def _generate_activity_events(self, context: DogmaContext):
        """Generate activity events for the game manager"""
        try:
            # This should integrate with the activity logging system
            card_name = context.card.name if context.card else "Unknown"
            player_name = (
                context.activating_player.name
                if context.activating_player
                else "Unknown"
            )
            results_count = len(context.results)

            logger.info(
                f"CONSOLIDATED: Activity - {player_name} executed {card_name} with {results_count} results"
            )
        except Exception as e:
            logger.warning(f"CONSOLIDATED: Activity event generation failed: {e}")

    def _record_performance_metrics(self, context: DogmaContext):
        """Record performance metrics"""
        try:
            phase_sequence = context.get_variable("phase_sequence", [])
            total_phases = len(phase_sequence)
            execution_time = context.get_variable(
                "completion_timestamp", time.time()
            ) - context.get_variable("start_timestamp", time.time())

            logger.debug(
                f"CONSOLIDATED METRICS: {total_phases} phases, {execution_time:.3f}s total"
            )
        except Exception as e:
            logger.warning(f"CONSOLIDATED: Performance metrics recording failed: {e}")

    def _create_debug_traces(self, context: DogmaContext):
        """Create debug traces for troubleshooting"""
        try:
            if logger.isEnabledFor(logging.DEBUG):
                phase_sequence = context.get_variable("phase_sequence", [])
                logger.debug(
                    f"CONSOLIDATED DEBUG: Phase sequence: {' -> '.join(phase_sequence)}"
                )
        except Exception as e:
            logger.warning(f"CONSOLIDATED: Debug trace creation failed: {e}")


class ConsolidatedDemandPhase(ConsolidatedPhase):
    """
    Consolidated Demand Phase: Handle demand effects like Archery

    Consolidates:
    - Original DemandPhase
    - DemandTargetPhase logic
    - Demand state management
    - Compliance tracking

    Responsibilities:
    1. Process demand effects for all eligible players
    2. Handle compliance checking and state management
    3. Execute demand actions
    4. Return to execution phase for remaining effects
    """

    def __init__(self):
        super().__init__(ConsolidatedPhaseType.DEMAND)

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Execute demand phase logic"""
        return PhaseExecutor.execute_phase(self, context, self._execute_impl)

    def _execute_impl(self, context: DogmaContext) -> PhaseResult:
        """Domain logic for demand phase - process demand effects"""
        # Get demand configuration from context
        demand_config = context.get_variable("demand_config")
        if not demand_config:
            return PhaseResult.error(
                "Demand phase invoked without demand_config", context
            )

        # Execute demand logic using existing demand system
        result = self._execute_demand_effect(context, demand_config)

        if result.requires_interaction:
            # Demand effect requires interaction - suspend
            logger.info("CONSOLIDATED: Demand effect requires interaction - suspending")
            return PhaseResult.interaction_required(
                result.interaction, self, result.context
            )

        if not result.success:
            error = f"Demand execution failed: {result.error}"
            logger.error(f"CONSOLIDATED DEMAND: {error}")
            return PhaseResult.error(error, context)

        # Demand completed successfully - return to execution phase
        # to continue with remaining effects
        updated_context = result.context
        # CRITICAL FIX: Don't duplicate results - just add new ones
        for new_result in result.results:
            updated_context = updated_context.with_result(new_result)

        # Get routing context
        current_effect_index = updated_context.get_variable("current_effect_index", 0)
        effects = updated_context.get_variable("effects", [])
        demand_invoked_from = updated_context.get_variable(
            "demand_invoked_from_phase", "execution"
        )

        if demand_invoked_from == "sharing":
            # CRITICAL FIX: When returning to SharingPhase, we need to continue with
            # the SAME effect for the NEXT player, not move to the next effect.
            # Increment player index, not effect index.
            current_player_in_effect = updated_context.get_variable(
                "current_player_in_effect", 0
            )
            logger.info(
                f"CONSOLIDATED DEMAND: Continuing interleaved execution - "
                f"incrementing player index from {current_player_in_effect} to {current_player_in_effect + 1} "
                f"for effect {current_effect_index + 1}"
            )
            # Move to next player in the sharing loop
            updated_context = updated_context.with_variable(
                "current_player_in_effect", current_player_in_effect + 1
            )
        else:
            # When returning to ExecutionPhase, increment effect index as before
            logger.info(
                f"CONSOLIDATED DEMAND: Incrementing effect index from {current_effect_index} to {current_effect_index + 1} (total effects: {len(effects)})"
            )
            # CRITICAL FIX: Make sure the incremented index is actually stored
            new_index = current_effect_index + 1
            updated_context = updated_context.with_variable(
                "current_effect_index", new_index
            )

        # CRITICAL DEBUG: Verify indices are set correctly
        verify_effect_index = updated_context.get_variable("current_effect_index", -999)
        verify_player_index = updated_context.get_variable(
            "current_player_in_effect", -999
        )
        logger.info(
            f"CONSOLIDATED DEMAND: Verified indices - "
            f"effect_index={verify_effect_index}, player_index={verify_player_index}"
        )

        # CRITICAL DEBUG: Log all effects to see what we have
        all_effects = updated_context.get_variable("effects", [])
        logger.info(
            f"CONSOLIDATED DEMAND: Total effects in context: {len(all_effects)}"
        )
        for i, effect in enumerate(all_effects):
            if isinstance(effect, list) and effect:
                first_action = effect[0] if effect else {}
                logger.info(
                    f"  Effect {i}: {first_action.get('type', 'unknown')} (list of {len(effect)} actions)"
                )
            elif isinstance(effect, dict):
                logger.info(
                    f"  Effect {i}: {effect.get('type', 'unknown')} (single action)"
                )
            else:
                logger.info(f"  Effect {i}: {type(effect).__name__}")

        # CRITICAL FIX: Clear resume_primitive_index after demand completes
        # DemandPhase routes directly to ExecutionPhase/SharingPhase, bypassing ResolutionPhase
        # which normally clears this variable (line 1588). Without clearing, stale resume indices
        # cause infinite loops where ExecutionPhase keeps trying to resume at invalid primitives.
        # This bug was discovered after implementing mid-primitive resumption for Archery Effect 2.
        logger.info(
            "CONSOLIDATED DEMAND: Clearing resume_primitive_index after demand completion"
        )
        updated_context = updated_context.without_variable("resume_primitive_index")

        updated_context = updated_context.without_variable("demand_config")
        # Clear the marker variable now that we've used it
        updated_context = updated_context.without_variable("demand_invoked_from_phase")

        # After demand completes, route back to the appropriate execution phase
        # The effect_index has already been incremented, so execution will continue with the next effect
        verify_effect_index = updated_context.get_variable("current_effect_index", 0)
        verify_player_index = updated_context.get_variable(
            "current_player_in_effect", 0
        )

        logger.info(
            f"CONSOLIDATED: Demand phase completed - routing back to execution "
            f"(effect_index={verify_effect_index}, player_index={verify_player_index}, invoked_from={demand_invoked_from})"
        )

        # Route back to the phase that invoked demand
        # The phase will create a new plan and reset to the current effect_index
        if demand_invoked_from == "sharing":
            return PhaseResult.success(ConsolidatedSharingPhase(), updated_context)
        else:
            return PhaseResult.success(ConsolidatedExecutionPhase(), updated_context)

    def _execute_demand_effect(
        self, context: DogmaContext, demand_config: dict
    ) -> "DemandExecutionResult":
        """Execute demand effect by running the DemandPhase pipeline to completion.

        DemandPhase uses a phase-pipeline architecture where each phase returns
        the next phase to execute. We need to loop through the pipeline until
        we get INTERACTION (suspend) or completion.

        CRITICAL: This method must preserve demand loop state when suspending and
        restore it when resuming. Without this, the demand loop restarts from scratch
        and loses the DemandTargetPhase's current_action_index, causing TransferBetweenPlayers
        to never execute.
        """
        # Tracer already started at dogma execution level - available at module level
        try:
            # Check if we're resuming from a suspended demand
            suspended_phase = context.get_variable("_demand_suspended_phase")
            suspended_iteration = context.get_variable("_demand_suspended_iteration")

            # Initialize dummy_return_phase to None - it will be created in fresh execution
            dummy_return_phase = None

            if suspended_phase is not None:
                # Resuming from suspension - continue with saved phase
                logger.info(
                    f"CONSOLIDATED: Resuming demand from suspended phase {type(suspended_phase).__name__} "
                    f"at iteration {suspended_iteration}"
                )
                current_phase = suspended_phase
                current_context = context
                start_iteration = suspended_iteration

                # Clear the resume markers so we don't resume again
                current_context = current_context.without_variable(
                    "_demand_suspended_phase"
                )
                current_context = current_context.without_variable(
                    "_demand_suspended_iteration"
                )
            else:
                # Starting fresh - create initial phases
                logger.info("CONSOLIDATED: Starting fresh demand execution")

                # Create a dummy return phase - we'll detect completion when we return to it
                dummy_return_phase = EffectExecutionPhase([], 0)

                # Start with the demand phase
                current_phase = DemandPhase(demand_config, dummy_return_phase)
                current_context = context
                start_iteration = 0

            max_iterations = 100  # Safety limit to prevent infinite loops

            for iteration in range(start_iteration, max_iterations):
                logger.debug(
                    f"DEMAND LOOP: iteration {iteration}, phase={type(current_phase).__name__}"
                )

                # Execute current phase
                phase_result = current_phase.execute(current_context)
                logger.debug(
                    f"DEMAND LOOP: result type={phase_result.type}, next_phase={type(phase_result.next_phase).__name__ if phase_result.next_phase else None}"
                )

                # Check result type
                if phase_result.type == ResultType.INTERACTION:
                    # Need user interaction - suspend and return
                    # CRITICAL FIX: Store current phase state for resumption
                    logger.info(
                        f"CONSOLIDATED: Demand requires interaction - suspending at iteration {iteration} "
                        f"with phase {type(phase_result.next_phase).__name__}"
                    )

                    # Store the NEXT phase (the one that will resume) and current iteration
                    resumed_context = phase_result.context.with_variable(
                        "_demand_suspended_phase", phase_result.next_phase
                    )
                    resumed_context = resumed_context.with_variable(
                        "_demand_suspended_iteration", iteration
                    )

                    return DemandExecutionResult(
                        success=True,
                        context=resumed_context,
                        results=list(resumed_context.results),
                        requires_interaction=True,
                        interaction=phase_result.interaction,
                    )
                elif phase_result.type == ResultType.ERROR:
                    # Error occurred
                    logger.error(
                        f"CONSOLIDATED: Demand phase error: {phase_result.error}"
                    )
                    return DemandExecutionResult(
                        success=False,
                        context=phase_result.context,
                        results=[],
                        error=phase_result.error,
                    )
                elif phase_result.type == ResultType.SUCCESS:
                    # Get next phase
                    next_phase = phase_result.next_phase

                    # Check if we're back to the dummy return phase (completion)
                    if next_phase is dummy_return_phase or next_phase is None:
                        logger.info("CONSOLIDATED: Demand pipeline completed")
                        return DemandExecutionResult(
                            success=True,
                            context=phase_result.context,
                            results=list(phase_result.context.results),
                        )

                    # Continue with next phase
                    current_phase = next_phase
                    current_context = phase_result.context
                    continue  # Continue to next iteration of the loop
                elif phase_result.type == ResultType.COMPLETE:
                    # Phase indicates completion (e.g., game won during demand)
                    logger.info(
                        "CONSOLIDATED: Demand pipeline completed via COMPLETE result"
                    )
                    return DemandExecutionResult(
                        success=True,
                        context=phase_result.context,
                        results=list(phase_result.context.results),
                    )
                else:
                    # Unknown result type
                    logger.error(
                        f"CONSOLIDATED: Unknown phase result type: {phase_result.type}"
                    )
                    return DemandExecutionResult(
                        success=False,
                        context=current_context,
                        results=[],
                        error=f"Unknown phase result type: {phase_result.type}",
                    )

            # Hit iteration limit - safety check
            logger.error(
                f"CONSOLIDATED: Demand pipeline exceeded {max_iterations} iterations"
            )
            return DemandExecutionResult(
                success=False,
                context=current_context,
                results=[],
                error="Demand pipeline exceeded maximum iterations",
            )

        except Exception as e:
            logger.error(
                f"CONSOLIDATED: Exception in demand effect execution: {e}",
                exc_info=True,
            )
            return DemandExecutionResult(
                success=False,
                context=context,
                results=[],
                error=f"Demand effect execution failed: {e}",
            )
        finally:
            pass  # Tracer cleanup handled at dogma execution level


class ConsolidatedTransactionPhase(ConsolidatedPhase):
    """
    Phase 8: Transaction Management and Cleanup

    Consolidates:
    - Transaction finalization
    - State persistence
    - Resource cleanup
    - Metrics recording

    Responsibilities:
    1. Finalize transaction state
    2. Persist results if needed
    3. Clean up resources
    4. Record performance metrics
    """

    def __init__(self):
        super().__init__(ConsolidatedPhaseType.TRANSACTION)

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Finalize transaction and cleanup"""
        return PhaseExecutor.execute_phase(self, context, self._execute_impl)

    def _execute_impl(self, context: DogmaContext) -> PhaseResult:
        """Domain logic for transaction phase - finalize and cleanup"""
        # Mark transaction as ready for completion
        context = context.with_variable("transaction_ready_for_completion", True)

        # Record final metrics
        context = self._record_final_metrics(context)

        logger.info("CONSOLIDATED: Transaction phase completed - execution finished")

        # This is the final phase - no next phase
        return PhaseResult.success(None, context)

    def _record_final_metrics(self, context: DogmaContext):
        """Record final performance metrics"""

        phase_sequence = context.get_variable("phase_sequence", [])
        total_results = context.get_variable("total_results_count", 0)

        metrics = {
            "phases_executed": len(phase_sequence),
            "phase_sequence": phase_sequence,
            "total_results": total_results,
            "consolidation_used": True,  # Flag to indicate consolidated system was used
        }

        context = context.with_variable("final_performance_metrics", metrics)
        logger.debug(f"CONSOLIDATED: Recorded final metrics: {metrics}")

        return context


# Factory function for creating the initial phase
def create_consolidated_execution_pipeline() -> ConsolidatedPhase:
    """Create the initial phase for consolidated execution pipeline"""
    return ConsolidatedInitializationPhase()


# Performance monitoring utilities
class ConsolidatedPhaseMetrics:
    """Utility class for monitoring consolidated phase performance"""

    def __init__(self):
        self._phase_metrics = {}

    def record_phase_execution(
        self, phase_name: str, duration_ms: float, suspended: bool = False
    ):
        """Record metrics for a phase execution"""
        if phase_name not in self._phase_metrics:
            self._phase_metrics[phase_name] = {
                "execution_count": 0,
                "total_duration_ms": 0.0,
                "suspension_count": 0,
                "average_duration_ms": 0.0,
            }

        metrics = self._phase_metrics[phase_name]
        metrics["execution_count"] += 1
        metrics["total_duration_ms"] += duration_ms
        if suspended:
            metrics["suspension_count"] += 1

        metrics["average_duration_ms"] = (
            metrics["total_duration_ms"] / metrics["execution_count"]
        )

    def get_performance_report(self) -> dict[str, Any]:
        """Get comprehensive performance report"""
        return {
            "total_phases": len(self._phase_metrics),
            "phase_metrics": self._phase_metrics.copy(),
            "total_executions": sum(
                m["execution_count"] for m in self._phase_metrics.values()
            ),
            "total_suspensions": sum(
                m["suspension_count"] for m in self._phase_metrics.values()
            ),
            "average_phase_duration": sum(
                m["average_duration_ms"] for m in self._phase_metrics.values()
            )
            / max(1, len(self._phase_metrics)),
        }
