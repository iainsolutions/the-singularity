"""
Initialization phase for dogma execution.

This phase is responsible for setting up the dogma execution environment
according to DOGMA_SPECIFICATION.md Section 1. It validates activation rules,
calculates sharing players, and initializes all required variables.
"""

import logging

from utils.symbol_mapping import string_to_symbol

from ..core.context import DogmaContext
from ..core.phases import DogmaPhase, PhaseResult, ValidationResult
from .execution import EffectExecutionPhase

logger = logging.getLogger(__name__)


class InitializationPhase(DogmaPhase):
    """
    Phase 1: Set up dogma execution environment.

    This phase implements DOGMA_SPECIFICATION.md Section 1.2:
    1. Validate activation rules
    2. Calculate sharing players immediately
    3. Initialize all required variables
    4. Create effect execution sequence
    """

    def validate(self, context: DogmaContext) -> ValidationResult:
        """Validate dogma can be activated (Spec 1.1)"""

        # Check player is active player
        # Prefer game.get_current_player() if available (tests use this),
        # otherwise fall back to game.current_player
        if hasattr(context.game, "get_current_player") and callable(
            context.game.get_current_player
        ):
            current_player = context.game.get_current_player()
        else:
            current_player = getattr(context.game, "current_player", None)
        if current_player.id != context.activating_player.id:
            return ValidationResult.invalid(
                f"Only current player can activate dogma (current: {current_player.name}, "
                f"activating: {context.activating_player.name})"
            )

        # Check card is top of color stack
        card_color = (
            context.card.color.value
            if hasattr(context.card.color, "value")
            else str(context.card.color)
        )
        color_stack = getattr(context.activating_player.board, f"{card_color}_cards")

        if not color_stack:
            return ValidationResult.invalid(f"No {card_color} cards on board")

        top_card = color_stack[-1]
        if (
            top_card.card_id != context.card.card_id
            and top_card.name != context.card.name
        ):
            return ValidationResult.invalid(
                f"Card {context.card.name} is not top of {card_color} stack "
                f"(top card: {top_card.name})"
            )

        # Check player has action available
        # Use actions_remaining if present; otherwise derive from actions_taken
        actions_remaining = getattr(context.game.state, "actions_remaining", None)
        if actions_remaining is None:
            actions_taken = getattr(context.game.state, "actions_taken", 0)
            try:
                actions_remaining = max(0, 2 - int(actions_taken))
            except Exception:
                actions_remaining = 0
        if actions_remaining <= 0:
            return ValidationResult.invalid("Player has no actions remaining")

        return ValidationResult.valid()

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Execute initialization phase"""
        self.log_phase_start(context)

        # 1. Validate activation rules (Spec 1.1)
        validation = self.validate(context)
        if not validation.is_valid:
            logger.error(f"Dogma activation validation failed: {validation.message}")
            return PhaseResult.error(validation.message, context)

        # 2. Calculate sharing players (Spec 2.2)
        sharing_players = self._calculate_sharing_players(context)

        # 3. Initialize SharingContext with eligible players
        sharing_player_ids = [player.id for player in sharing_players]
        updated_context = context.initialize_sharing(sharing_player_ids)

        # 4. Initialize all required variables (Spec 1.2)
        # CRITICAL: Always initialize demand_transferred_count to 0
        initial_variables = {
            "featured_symbol": context.card.dogma_resource,
            "demand_transferred_count": 0,  # Always initialize!
            "effect_index": 0,
            "dogma_card": context.card,
            "transaction_id": context.transaction_id,
            # Expose eligible sharing players in variables for downstream consumers
            # (e.g., CompletionPhase summaries, Interaction routing, and result reporting)
            "sharing_players": sharing_player_ids,
        }

        # Update context with all variables
        updated_context = updated_context.with_variables(initial_variables)
        updated_context = updated_context.with_phase_entered("InitializationPhase")

        logger.info(f"Dogma initialization complete for {context.card.name}")
        logger.info(f"Sharing players: {[p.name for p in sharing_players]}")
        logger.info(f"Featured symbol: {context.card.dogma_resource}")
        logger.info(f"Variables initialized: {list(initial_variables.keys())}")
        logger.info(
            f"Sharing context initialized: {updated_context.sharing.get_sharing_stats()}"
        )

        # 4. Create effect execution sequence and transition
        effects = self._parse_card_effects(context.card)

        # Check if sharing should happen first
        if sharing_player_ids:
            # Sharing players execute first
            logger.info(f"Transitioning to SharingPhase for {len(sharing_player_ids)} sharing player(s)")
            from .sharing import SharingPhase
            next_phase = SharingPhase(effects)
        else:
            # No sharing - activating player executes directly
            logger.info("No sharing players - activating player executes directly")
            next_phase = EffectExecutionPhase(effects, 0)

        result = PhaseResult.success(next_phase, updated_context)
        self.log_phase_complete(updated_context, result)

        return result

    def _calculate_sharing_players(self, context: DogmaContext) -> list:
        """
        Calculate sharing players according to Spec 2.2.

        A player can share if:
        - They are NOT the activating player
        - They have >= the same number of featured symbols
        - The first effect is NOT a demand effect (demands cannot be shared)
        """

        sharing_players = []

        # Get featured symbol and activating player's count
        featured_symbol_str = context.card.dogma_resource
        featured_symbol = string_to_symbol(featured_symbol_str)

        if not featured_symbol:
            logger.warning(f"Invalid dogma resource symbol: {featured_symbol_str}")
            return sharing_players

        activating_count = context.activating_player.count_symbol(featured_symbol)

        # Check if first effect is a demand (demands cannot be shared)
        is_first_effect_demand = self._is_first_effect_demand(context.card)

        if is_first_effect_demand:
            logger.debug("First effect is demand - no sharing allowed")
            return sharing_players

        # Find eligible sharing players
        for player in context.game.players:
            if player.id != context.activating_player.id:
                player_count = player.count_symbol(featured_symbol)

                if player_count >= activating_count:
                    sharing_players.append(player)
                    logger.debug(
                        f"{player.name} can share ({player_count} >= {activating_count} {featured_symbol_str})"
                    )
                else:
                    logger.debug(
                        f"{player.name} cannot share ({player_count} < {activating_count} {featured_symbol_str})"
                    )

        return sharing_players

    def _is_first_effect_demand(self, card) -> bool:
        """Check if the first dogma effect is a demand"""
        if not hasattr(card, "dogma_effects") or not card.dogma_effects:
            return False

        first_effect = card.dogma_effects[0]

        # Handle both dict format (from JSON) and object format
        if isinstance(first_effect, dict):
            # Check is_demand field (correct way for JSON format)
            is_demand = first_effect.get("is_demand", False)
            if is_demand:
                return True
            # Fallback: check if first action is DemandEffect
            actions = first_effect.get("actions", [])
            if actions and isinstance(actions[0], dict):
                return actions[0].get("type") == "DemandEffect"
            return False
        else:
            # Object format - check is_demand attribute first
            is_demand = getattr(first_effect, "is_demand", False)
            if is_demand:
                return True
            # Fallback: check actions
            actions = getattr(first_effect, "actions", [])
            if actions and hasattr(actions[0], "type"):
                return actions[0].type == "DemandEffect"
            return False

    def _parse_card_effects(self, card) -> list:
        """
        Parse card effects into executable format.

        Extract individual actions from DogmaEffect objects for execution.
        """
        actions = []

        if hasattr(card, "dogma_effects"):
            for dogma_effect in card.dogma_effects or []:
                if hasattr(dogma_effect, "actions"):
                    # Extract actions from DogmaEffect
                    actions.extend(dogma_effect.actions)
                elif isinstance(dogma_effect, dict):
                    # Already in dict format
                    actions.append(dogma_effect)
                else:
                    logger.warning(f"Unknown dogma effect format: {dogma_effect}")
        else:
            logger.warning(f"Card {card.name} has no dogma_effects")

        logger.debug(f"Parsed {len(actions)} actions from {card.name}: {actions}")
        return actions

    def estimate_remaining_phases(self) -> int:
        """Estimate phases remaining after initialization"""
        # Initialization + Effect execution + possible sharing/demand + completion
        return 4
