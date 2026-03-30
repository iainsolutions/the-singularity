"""ActionPrimitiveAdapter - Wraps action primitives with the Effect interface.

This adapter implements the pattern specified in DOGMA_TECHNICAL_SPECIFICATION.md Section 6.2.
It provides clean abstraction between phases and primitives, ensuring:
1. No internal signals leak from primitives to phases
2. Phases never directly interact with ActionContext or ActionResult
3. Special routing (like demands) is handled transparently
"""

import logging
from typing import Any

from action_primitives import ActionResult, create_action_primitive
from action_primitives.base import ActionContext


def safe_get(obj, attr, default=None):
    """Safely get attribute from Pydantic object or dictionary."""
    if hasattr(obj, attr):  # Pydantic object
        return getattr(obj, attr, default)
    elif isinstance(obj, dict):  # Dictionary
        return obj.get(attr, default)
    else:
        return default


from ..core.context import DogmaContext
from .base import Effect, EffectResult

logger = logging.getLogger(__name__)


class ActionPrimitiveAdapter(Effect):
    """Adapter that wraps action primitives with the Effect interface.

    This is the core implementation of the ActionPrimitiveAdapter pattern,
    providing complete isolation between phases and primitives.
    """

    def __init__(self, config: dict[str, Any]):
        """Initialize the adapter with effect configuration.

        Args:
            config: Effect configuration from card JSON
        """
        super().__init__(config)
        self.primitive = None
        self._init_error = None
        self._init_primitive()

    def _init_primitive(self):
        """Initialize the wrapped primitive."""
        try:
            self.primitive = create_action_primitive(self.config)
        except Exception as e:
            logger.error(f"Failed to create primitive for config {self.config}: {e}")
            self.primitive = None
            # Store the error for better error reporting
            self._init_error = str(e)

    def execute(self, context: DogmaContext) -> EffectResult:
        """Execute the wrapped primitive and translate its result.

        This method:
        1. Converts DogmaContext to ActionContext
        2. Executes the primitive
        3. Translates internal signals to clean EffectResult
        4. Hides all primitive implementation details

        Args:
            context: The dogma execution context

        Returns:
            Clean EffectResult with no internal signals
        """
        if not self.primitive:
            error_msg = "Failed to initialize action primitive"
            if hasattr(self, "_init_error"):
                error_msg += f": {self._init_error}"
            return EffectResult(success=False, error=error_msg)

        # Create ActionContext from DogmaContext
        action_context = self._create_action_context(context)

        try:
            # Execute the primitive
            result = self.primitive.execute(action_context)

            # Translate the result, handling all internal signals
            return self._translate_result(result, action_context, context)

        except Exception as e:
            logger.error(f"Error executing primitive: {e}", exc_info=True)
            return EffectResult(success=False, error=f"Primitive execution failed: {e}")

    def _create_action_context(self, context: DogmaContext) -> ActionContext:
        """Create ActionContext from DogmaContext.

        Args:
            context: The dogma context

        Returns:
            ActionContext for primitive execution
        """
        logger.error(
            f"🔥 ADAPTER DEBUG: Creating ActionContext with player={context.current_player.name if context.current_player else 'None'} (ID: {context.current_player.id if context.current_player else 'None'})"
        )
        return ActionContext(
            game=context.game,
            player=context.current_player,
            card=context.card,
            variables=dict(context.variables),
            results=[],
            state_tracker=context.state_tracker,
            sharing=context.sharing,  # Pass sharing context through
        )

    def _translate_result(
        self,
        primitive_result: ActionResult,
        action_context: ActionContext,
        dogma_context: DogmaContext,
    ) -> EffectResult:
        """Translate primitive result to clean EffectResult.

        This is the key method that:
        1. Checks for internal signals like pending_demand_config
        2. Translates them to clean interface properties
        3. Removes internal variables from the result

        Args:
            primitive_result: The raw result from the primitive
            action_context: The action context after execution
            dogma_context: The original dogma context

        Returns:
            Clean EffectResult with internal signals translated
        """
        # Failure path: surface meaningful error details
        if primitive_result == ActionResult.FAILURE:
            error_msg = (
                action_context.variables.get("error")
                or action_context.variables.get("error_message")
                or f"Primitive '{safe_get(self.config, 'type', 'unknown')}' failed"
            )
            return EffectResult(
                success=False,
                error=str(error_msg),
                variables=dict(action_context.variables),
                results=list(action_context.results),
            )

        # Start with basic result translation for non-failure results
        effect_result = EffectResult(
            success=(primitive_result == ActionResult.SUCCESS),
            requires_interaction=(
                primitive_result == ActionResult.REQUIRES_INTERACTION
            ),
            variables=dict(action_context.variables),
            results=list(action_context.results),
        )

        # Check for demand routing signal
        if "pending_demand_config" in action_context.variables:
            demand_config = action_context.variables["pending_demand_config"]
            if (
                demand_config
                and isinstance(demand_config, dict)
                and safe_get(demand_config, "type") == "DemandEffect"
            ):
                # This is a demand that needs special routing
                effect_result.routes_to_demand = True
                effect_result.demand_config = demand_config
                # Override interaction flag for demands
                effect_result.requires_interaction = False

                logger.debug(
                    "Detected demand routing signal, translating to clean interface"
                )

        # Check for interaction request and set accordingly
        if (
            effect_result.requires_interaction
            and "final_interaction_request" in action_context.variables
        ):
            interaction_request = action_context.variables.get(
                "final_interaction_request"
            )
            if interaction_request:
                effect_result.interaction_request = interaction_request
                logger.debug(
                    f"Set interaction_request for effect requiring interaction: {safe_get(interaction_request, 'type', 'unknown')}"
                )

        # Remove internal signals but preserve final_interaction_request for phase layer
        self._clean_internal_variables(effect_result.variables)

        return effect_result

    def _clean_internal_variables(self, variables: dict[str, Any]):
        """Remove internal signals from variables.

        This ensures phases never see internal implementation details.
        IMPORTANT: final_interaction_request is preserved as it's needed by the phase layer.

        Args:
            variables: Variables dictionary to clean (modified in place)
        """
        # Whitelist specific internal keys to remove (safer than removing ALL underscore keys)
        # NOTE: final_interaction_request is NOT removed - it's needed by execution phase
        internal_keys_to_remove = [
            "pending_demand_config",
            "_route_to_demand",
            "_internal_state",
            "_primitive_signal",
            "_temp_variables",
            "_execution_context",
            "_debug_info",
        ]

        keys_to_remove = set(internal_keys_to_remove)

        for key in keys_to_remove:
            variables.pop(key, None)

    def validate(self) -> tuple[bool, str | None]:
        """Validate the effect configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not safe_get(self.config, "type"):
            return False, "Effect configuration missing 'type' field"

        if not self.primitive:
            return False, "Failed to create action primitive"

        # Delegate validation to the primitive if it has the method
        if hasattr(self.primitive, "validate_config"):
            try:
                is_valid = self.primitive.validate_config()
                if not is_valid:
                    return False, "Primitive configuration validation failed"
            except Exception as e:
                return False, f"Validation error: {e}"

        return True, None
