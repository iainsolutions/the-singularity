"""
InteractionEffectAdapter - Specialized adapter for user interaction effects.

This adapter handles all effects that require user input:
- Card selection (SelectCards, SelectHighest, SelectLowest)
- Color/Symbol selection (SelectColor, SelectSymbol)
- Achievement selection (SelectAchievement)
- Choice selection (ChooseOption)

It ensures consistent interaction request formatting and proper
response handling across all interaction types.
"""

import logging
from typing import Any, ClassVar

from action_primitives import ActionResult, create_action_primitive
from action_primitives.base import ActionContext
from schemas.websocket_messages import DogmaInteractionRequest

from ..core.context import DogmaContext
from .base import Effect, EffectResult, EffectType

logger = logging.getLogger(__name__)


class InteractionEffectAdapter(Effect):
    """
    Specialized adapter for effects requiring user interaction.

    This adapter:
    1. Validates interaction requirements
    2. Formats interaction requests consistently
    3. Handles interaction responses properly
    4. Provides fallback behavior for auto-selection
    """

    # Effects that this adapter handles
    INTERACTION_EFFECTS: ClassVar[set[str]] = {
        "SelectCards",
        "SelectHighest",
        "SelectLowest",
        "SelectColor",
        "SelectSymbol",
        "SelectAchievement",
        "ChooseOption",
    }

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the interaction effect adapter.

        Args:
            config: Effect configuration from card JSON
        """
        super().__init__(config)
        self.type = EffectType.INTERACTION
        self.primitive = None
        self._init_error = None
        self._init_primitive()

    def _init_primitive(self):
        """Initialize the wrapped primitive."""
        try:
            logger.debug(
                f"Initializing interaction primitive with config: {self.config}"
            )
            effect_type = self.config.get("type", "unknown")

            # Validate config before primitive creation
            if not isinstance(self.config, dict):
                raise ValueError(
                    f"Primitive config must be a dictionary, got: {type(self.config)}"
                )

            if "type" not in self.config:
                raise ValueError(
                    f"Primitive config missing required 'type' field: {self.config}"
                )

            if effect_type not in self.INTERACTION_EFFECTS:
                raise ValueError(
                    f"Effect type '{effect_type}' is not supported by InteractionEffectAdapter"
                )

            self.primitive = create_action_primitive(self.config)
            if not self.primitive:
                raise ValueError(
                    f"create_action_primitive returned None for config: {self.config}"
                )

            logger.debug(
                f"Successfully created interaction primitive for type '{effect_type}'"
            )

        except Exception as e:
            error_msg = f"Failed to create interaction primitive for type '{self.config.get('type', 'unknown')}': {type(e).__name__}: {e}"
            logger.error(error_msg)
            logger.error(f"Problematic config: {self.config}")
            self.primitive = None
            self._init_error = error_msg

    def execute(self, context: DogmaContext) -> EffectResult:
        """
        Execute the interaction effect.

        This handles:
        1. Auto-selection when possible
        2. Interaction request creation
        3. Response validation
        4. Result translation

        Args:
            context: The dogma execution context

        Returns:
            EffectResult with interaction requirements
        """
        if not self.primitive:
            error_msg = "Failed to initialize interaction primitive"
            if hasattr(self, "_init_error") and self._init_error:
                error_msg += f": {self._init_error}"
            return EffectResult(success=False, error=error_msg)

        # Create action context
        action_context = self._create_action_context(context)

        try:
            # Execute the primitive
            result = self.primitive.execute(action_context)

            # Translate to effect result
            effect_result = self._translate_result(result, action_context)

            # Enhance interaction request if needed
            if effect_result.requires_interaction:
                self._enhance_interaction_request(effect_result, context)

            return effect_result

        except Exception as e:
            logger.error(f"Error executing interaction effect: {e}", exc_info=True)
            return EffectResult(success=False, error=f"Interaction effect failed: {e}")

    def _create_action_context(self, context: DogmaContext) -> ActionContext:
        """Create ActionContext from DogmaContext."""
        action_ctx = ActionContext(
            game=context.game,
            player=context.current_player,
            card=context.card,
            variables=dict(context.variables),
            results=[],
            state_tracker=context.state_tracker,
            sharing=context.sharing,  # Pass sharing context through
        )
        # CRITICAL: Copy demanding_player for demand effects (needed for demanding_player_hand source)
        # Only set if we're actually in a demand context (check variables)
        if context.has_variable("demanding_player"):
            action_ctx.demanding_player = context.get_variable("demanding_player")
        elif hasattr(context, "is_demand") and context.is_demand:
            # Fallback: if context explicitly marks this as demand, use activating_player
            action_ctx.demanding_player = context.activating_player
        return action_ctx

    def _translate_result(
        self, primitive_result: ActionResult, action_context: ActionContext
    ) -> EffectResult:
        """
        Translate primitive result to EffectResult.

        Args:
            primitive_result: Raw result from primitive
            action_context: Context after execution

        Returns:
            Clean EffectResult
        """
        # Failure path: provide clear error details
        if primitive_result == ActionResult.FAILURE:
            error_msg = (
                action_context.variables.get("error")
                or action_context.variables.get("error_message")
                or f"Interaction effect '{self.config.get('type', 'unknown')}' failed"
            )
            return EffectResult(
                success=False,
                error=str(error_msg),
                variables=dict(action_context.variables),
                results=list(action_context.results),
            )

        # Check if interaction is required
        requires_interaction = primitive_result == ActionResult.REQUIRES_INTERACTION

        # Get interaction request if present
        interaction_request = None
        if requires_interaction:
            # Check for StandardInteractionBuilder request
            interaction_request = action_context.variables.get(
                "final_interaction_request"
            )

        # Defensive: if the primitive prepared a final_interaction_request but
        # mistakenly returned SUCCESS, still raise interaction to avoid silent no-ops.
        if (not requires_interaction) and action_context.variables.get(
            "final_interaction_request"
        ):
            requires_interaction = True
            interaction_request = action_context.variables.get(
                "final_interaction_request"
            )
            logger.debug(
                "InteractionEffectAdapter: forcing interaction due to presence of final_interaction_request"
            )

        return EffectResult(
            success=(primitive_result == ActionResult.SUCCESS),
            requires_interaction=requires_interaction,
            interaction_request=interaction_request,
            variables=dict(action_context.variables),
            results=list(action_context.results),
        )

    def _enhance_interaction_request(
        self, effect_result: EffectResult, context: DogmaContext
    ):
        """
        Enhance interaction request with additional metadata.

        This adds:
        - Clearer messages for the user
        - Context about why the interaction is needed
        - Validation hints

        Args:
            effect_result: The effect result to enhance
            context: The dogma context
        """
        if not effect_result.interaction_request:
            return

        request = effect_result.interaction_request
        effect_type = self.config.get("type", "")

        # Check if request is a Pydantic model (DogmaInteractionRequest)
        if isinstance(request, DogmaInteractionRequest):
            # Handle Pydantic model - need to modify the data dict and create new model
            data_updates = {}

            # Add effect-specific enhancements
            if effect_type == "ChooseOption":
                # Enhance choice messages
                if "message" not in request.data or not request.data.get("message"):
                    data_updates["message"] = "Choose an option to continue"

            elif effect_type in {"SelectCards", "SelectHighest", "SelectLowest"}:
                # Enhance card selection messages
                if "message" in request.data:
                    # Add context about the effect
                    card_name = context.card.name if context.card else "effect"
                    data_updates["message"] = f"{card_name}: {request.data['message']}"

            elif effect_type == "SelectColor":
                # Enhance color selection
                if "message" not in request.data:
                    data_updates["message"] = "Select a color for the effect"

            elif effect_type == "SelectSymbol":
                # Enhance symbol selection
                if "message" not in request.data:
                    data_updates["message"] = "Select a symbol for the effect"

            elif effect_type == "SelectAchievement":
                # Enhance achievement selection
                if "message" not in request.data:
                    data_updates["message"] = "Select an achievement to claim"

            # If we have updates, create a new request with updated data
            if data_updates:
                updated_data = {**request.data, **data_updates}
                effect_result.interaction_request = request.model_copy(
                    update={"data": updated_data}
                )

        else:
            # Handle legacy dict format (fallback)
            # Add effect-specific enhancements
            if effect_type == "ChooseOption":
                # Enhance choice messages
                if "message" not in request or not request["message"]:
                    request["message"] = "Choose an option to continue"

            elif effect_type in {"SelectCards", "SelectHighest", "SelectLowest"}:
                # Enhance card selection messages
                if "message" in request:
                    # Add context about the effect
                    card_name = context.card.name if context.card else "effect"
                    request["message"] = f"{card_name}: {request['message']}"

            elif effect_type == "SelectColor":
                # Enhance color selection
                if "message" not in request:
                    request["message"] = "Select a color for the effect"

            elif effect_type == "SelectSymbol":
                # Enhance symbol selection
                if "message" not in request:
                    request["message"] = "Select a symbol for the effect"

            elif effect_type == "SelectAchievement":
                # Enhance achievement selection
                if "message" not in request:
                    request["message"] = "Select an achievement to claim"

    def validate(self) -> tuple[bool, str | None]:
        """
        Validate interaction effect configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        effect_type = self.config.get("type", "")

        # Check if this is an interaction effect
        if effect_type not in self.INTERACTION_EFFECTS:
            return False, f"Not an interaction effect: {effect_type}"

        # Validate based on effect type
        if effect_type == "SelectCards":
            # Requires source and counts
            if "source" not in self.config:
                return False, "SelectCards missing 'source'"
            if "min_count" not in self.config and "max_count" not in self.config:
                return False, "SelectCards missing count specification"

        elif effect_type == "ChooseOption":
            # Requires options list
            if "options" not in self.config:
                return False, "ChooseOption missing 'options'"
            if not isinstance(self.config["options"], list):
                return False, "ChooseOption 'options' must be a list"

        elif effect_type in {"SelectHighest", "SelectLowest"}:
            # Requires source
            if "source" not in self.config:
                return False, f"{effect_type} missing 'source'"

        elif effect_type == "SelectAchievement":
            # Optional max_age parameter
            pass  # No required fields

        elif effect_type in {"SelectColor", "SelectSymbol"}:
            # Optional parameters for available choices
            pass  # No required fields

        # Check primitive initialization
        if not self.primitive:
            return False, "Failed to create interaction primitive"

        return True, None

    def get_description(self) -> str:
        """Get human-readable description of the interaction."""
        if "description" in self.config:
            return self.config["description"]

        effect_type = self.config.get("type", "interaction")

        # Generate meaningful descriptions
        if effect_type == "SelectCards":
            source = self.config.get("source", "cards")
            min_count = self.config.get("min_count", 1)
            max_count = self.config.get("max_count", min_count)

            if min_count == max_count:
                count_str = str(min_count)
            else:
                count_str = f"{min_count}-{max_count}"

            return f"Select {count_str} card(s) from {source}"

        elif effect_type == "ChooseOption":
            num_options = len(self.config.get("options", []))
            return f"Choose from {num_options} options"

        elif effect_type == "SelectHighest":
            source = self.config.get("source", "cards")
            return f"Select highest card from {source}"

        elif effect_type == "SelectLowest":
            source = self.config.get("source", "cards")
            return f"Select lowest card from {source}"

        elif effect_type == "SelectColor":
            return "Select a color"

        elif effect_type == "SelectSymbol":
            return "Select a symbol"

        elif effect_type == "SelectAchievement":
            max_age = self.config.get("max_age", "")
            if max_age:
                return f"Select achievement (max age {max_age})"
            return "Select an achievement"

        return f"{effect_type} interaction"
