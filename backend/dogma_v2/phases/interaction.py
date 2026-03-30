"""
Interaction phase for dogma processing.

This phase handles player interactions that require suspension
of dogma execution until the player provides a response.
"""

import logging
from typing import Any

from ..core.context import DogmaContext
from ..core.phases import DogmaPhase, PhaseResult

logger = logging.getLogger(__name__)


class InteractionPhase(DogmaPhase):
    """
    Phase for handling player interactions.

    This phase suspends dogma execution and waits for player input.
    It will be resumed when the player provides their response.
    """

    def __init__(
        self,
        interaction_type: str,
        interaction_data: dict[str, Any],
        return_phase: DogmaPhase,
        context_updates: dict[str, Any] | None = None,
    ):
        """
        Initialize interaction phase.

        Args:
            interaction_type: Type of interaction (e.g., 'card_selection', 'choice')
            interaction_data: Data needed for the interaction UI
            return_phase: Phase to return to after interaction completes
            context_updates: Variables to update context with after interaction
        """
        self.interaction_type = interaction_type
        self.interaction_data = interaction_data
        self.return_phase = return_phase
        self.context_updates = context_updates or {}

    def execute(self, context: DogmaContext) -> PhaseResult:
        """Execute interaction phase - this always requires interaction"""
        self.log_phase_start(context)

        logger.info(f"Interaction required: {self.interaction_type}")
        logger.info(
            f"Interaction data keys: {list(self.interaction_data.keys()) if isinstance(self.interaction_data, dict) else 'not a dict'}"
        )

        # CRITICAL: Only check for 'eligible_cards' field (canonical field name)
        # Per dogma-critical.md: Backend sends eligible_cards, Frontend expects eligible_cards
        if (
            isinstance(self.interaction_data, dict)
            and "eligible_cards" in self.interaction_data
        ):
            eligible_cards = self.interaction_data["eligible_cards"]
            logger.info(
                f"eligible_cards field present with {len(eligible_cards)} cards"
            )
            if eligible_cards:
                logger.info(f"First card in eligible_cards field: {eligible_cards[0]}")

        logger.debug(f"Full interaction data: {self.interaction_data}")

        # Create proper InteractionRequest
        import uuid

        from ..interaction_request import InteractionRequest, InteractionType

        # Map string type to enum
        interaction_type_enum = InteractionType.SELECT_CARDS
        if self.interaction_type == "select_cards":
            interaction_type_enum = InteractionType.SELECT_CARDS
        elif self.interaction_type == "choose_option":
            interaction_type_enum = InteractionType.CHOOSE_OPTION
        elif self.interaction_type == "select_achievement":
            interaction_type_enum = InteractionType.SELECT_ACHIEVEMENT
        # Add more mappings as needed

        # Determine the correct target player for this interaction
        target_player_id = self._determine_target_player_id(context)

        interaction_request = InteractionRequest(
            id=str(uuid.uuid4()),
            player_id=target_player_id,
            type=interaction_type_enum,
            data=self.interaction_data,
            message=self.interaction_data.get(
                "message", f"Interaction required: {self.interaction_type}"
            ),
            timeout=None,
        )

        # Update context with interaction information
        interaction_context = context.with_variables(
            {
                "interaction_id": interaction_request.id,
                "interaction_type": self.interaction_type,
                "interaction_data": self.interaction_data,
                **self.context_updates,
            }
        )

        # Return phase result that requires interaction
        return PhaseResult.interaction_required(
            interaction=interaction_request,
            resume_phase=self.return_phase,
            context=interaction_context,
        )

    def get_phase_name(self) -> str:
        """Return phase name with interaction type"""
        return f"InteractionPhase[{self.interaction_type}]"

    def estimate_remaining_phases(self) -> int:
        """Estimate phases remaining after interaction"""
        # This phase plus whatever the return phase estimates
        return 1 + (
            self.return_phase.estimate_remaining_phases() if self.return_phase else 0
        )

    def _determine_target_player_id(self, context: DogmaContext) -> str:
        """
        Determine the correct target player for this interaction.

        For sharing effects (like select_achievement), the interaction should target
        sharing players, not the activating player. For demand effects, this method
        shouldn't be called as DemandTargetPhase handles targeting directly.
        """
        # For sharing effects, always target the current_player in the isolated
        # sharing context. Do not attempt to infer from a list of IDs.
        is_sharing_phase = context.get_variable("is_sharing_phase", False)
        if is_sharing_phase:
            return context.current_player.id

        # Default to the current player (activating player during self-effects)
        return context.current_player.id


class CardSelectionInteraction(InteractionPhase):
    """Specialized interaction for card selection"""

    def __init__(
        self,
        cards: list,
        constraints: dict[str, Any],
        return_phase: DogmaPhase,
        variable_name: str = "selected_cards",
    ):
        """
        Initialize card selection interaction.

        Args:
            cards: List of cards available for selection
            constraints: Selection constraints (min_count, max_count, etc.)
            return_phase: Phase to return to after selection
            variable_name: Context variable name to store selected cards
        """
        interaction_data = {
            "eligible_cards": [
                card.to_dict() if hasattr(card, "to_dict") else card for card in cards
            ],
            "constraints": constraints,
        }

        context_updates = {variable_name: []}  # Will be populated by player response

        super().__init__(
            interaction_type="card_selection",
            interaction_data=interaction_data,
            return_phase=return_phase,
            context_updates=context_updates,
        )

        self.variable_name = variable_name

    def get_phase_name(self) -> str:
        """Return phase name with selection details"""
        card_count = len(self.interaction_data.get("cards", []))
        constraints = self.interaction_data.get("constraints", {})
        min_count = constraints.get("min_count", 0)
        max_count = constraints.get("max_count", card_count)

        return f"CardSelectionInteraction[{card_count} cards, select {min_count}-{max_count}]"


class ChoiceInteraction(InteractionPhase):
    """Specialized interaction for multiple choice"""

    def __init__(
        self,
        choices: list,
        prompt: str,
        return_phase: DogmaPhase,
        variable_name: str = "selected_choice",
    ):
        """
        Initialize choice interaction.

        Args:
            choices: List of choice options
            prompt: Prompt text for the player
            return_phase: Phase to return to after choice
            variable_name: Context variable name to store selected choice
        """
        interaction_data = {"choices": choices, "prompt": prompt}

        context_updates = {variable_name: None}  # Will be populated by player response

        super().__init__(
            interaction_type="choice",
            interaction_data=interaction_data,
            return_phase=return_phase,
            context_updates=context_updates,
        )

        self.variable_name = variable_name

    def get_phase_name(self) -> str:
        """Return phase name with choice details"""
        choice_count = len(self.interaction_data.get("choices", []))
        return f"ChoiceInteraction[{choice_count} options]"
