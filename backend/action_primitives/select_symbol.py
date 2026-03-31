"""
SelectSymbol primitive - Allows player to select a symbol type.
"""

import logging
from typing import Any, ClassVar

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class SelectSymbol(ActionPrimitive):
    """
    Allows a player to select a symbol type interactively.

    Config:
        - available_symbols: List of symbols to choose from (optional, defaults to all)
        - exclude_symbols: List of symbols to exclude from selection
        - symbols: Alias for available_symbols (from BaseCards.json)
        - prompt: Message to show the player
        - description: Alias for prompt
        - store_result: Variable name to store the selected symbol
        - is_optional: Whether selection is optional (default: False)
    """

    VALID_SYMBOLS: ClassVar[list[str]] = [
        "circuit",
        "data",
        "algorithm",
        "neural_net",
        "robot",
        "human_mind",
    ]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        # Support both 'symbols' (from BaseCards.json) and 'available_symbols'
        self.available_symbols = config.get("symbols") or config.get(
            "available_symbols", self.VALID_SYMBOLS
        )
        self.exclude_symbols = config.get("exclude_symbols", [])
        # Support both 'description' (from BaseCards.json) and 'prompt'
        self.prompt = config.get("description") or config.get(
            "prompt", "Select a symbol"
        )
        self.store_result = config.get("store_result", "selected_symbol")
        self.is_optional = config.get("is_optional", False)

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the select symbol action"""
        # Determine available symbols
        available = []
        for symbol in self.available_symbols:
            # Normalize to lowercase for case-insensitive comparison
            normalized_symbol = symbol.lower() if isinstance(symbol, str) else symbol
            if (
                normalized_symbol in self.VALID_SYMBOLS
                and normalized_symbol not in self.exclude_symbols
            ):
                available.append(normalized_symbol)

        if not available:
            if self.is_optional:
                context.add_result("No symbols available for selection")
                return ActionResult.SUCCESS
            else:
                context.add_result("No symbols available for selection")
                return ActionResult.FAILURE

        # CRITICAL FIX: Check if we already have the symbol stored
        # (could be from previous resumption or cross-effect persistence)
        if context.has_variable(self.store_result):
            selected_symbol = context.get_variable(self.store_result)
            if selected_symbol in available:
                logger.info(f"SelectSymbol: Already have {self.store_result}={selected_symbol}, returning success")
                context.add_result(f"Symbol already selected: {selected_symbol}")
                return ActionResult.SUCCESS

        # CRITICAL FIX: Check for chosen_option FIRST (from interaction response)
        # before checking resume variables. This must happen BEFORE scheduler clears it.
        if context.has_variable("chosen_option"):
            selected_symbol = context.get_variable("chosen_option")
            if selected_symbol in available:
                # Store in the configured variable name
                context.set_variable(self.store_result, selected_symbol)
                # Also ensure "selected_symbol" is always set as fallback
                if self.store_result != "selected_symbol":
                    context.set_variable("selected_symbol", selected_symbol)
                context.add_result(f"Selected symbol: {selected_symbol}")
                logger.info(f"SelectSymbol: Stored chosen_option '{selected_symbol}' to {self.store_result}")
                return ActionResult.SUCCESS
            else:
                logger.warning(f"SelectSymbol: chosen_option '{selected_symbol}' not in available symbols {available}")

        # Check if we're resuming with a choice already made
        from .selection_utils import handle_selection_resume

        def on_success(_chosen_symbol, value, _desc):
            # CRITICAL: Also ensure "selected_symbol" is always set regardless of store_result config
            if self.store_result != "selected_symbol":
                context.set_variable("selected_symbol", value)
                logger.debug(
                    f"SelectSymbol: Set both {self.store_result} and selected_symbol to {value}"
                )
            return ActionResult.SUCCESS

        result = handle_selection_resume(
            context,
            resume_var_name="selected_symbol_choice",
            result_var_name=self.store_result,
            available_options=available,
            primitive_name="SelectSymbol",
            on_success=on_success,
        )
        if result is not None:
            return result
        # Fall through to normal interaction request below

        # If only one symbol available, auto-select it
        if len(available) == 1:
            selected_symbol = available[0]
            context.set_variable(self.store_result, selected_symbol)
            # CRITICAL: Also ensure "selected_symbol" is always set
            if self.store_result != "selected_symbol":
                context.set_variable("selected_symbol", selected_symbol)
            context.add_result(
                f"Auto-selected only available symbol: {selected_symbol}"
            )
            logger.info(f"SelectSymbol: Auto-selected {selected_symbol}")
            return ActionResult.SUCCESS

        # Need player interaction - use StandardInteractionBuilder for type safety
        from interaction.builder import StandardInteractionBuilder

        context.set_variable("pending_symbol_options", available)

        # Convert symbols to option objects with description/value for StandardInteractionBuilder
        option_objs = [
            {"description": symbol.capitalize(), "value": symbol}
            for symbol in available
        ]

        # Use StandardInteractionBuilder to ensure consistent field names and validation
        interaction_request = (
            StandardInteractionBuilder.create_choice_selection_request_with_options(
                options=option_objs,
                message=self.prompt,
                is_optional=bool(self.is_optional),
                source_player=getattr(context.player, "id", None),
                execution_results=list(context.results) if context.results else None,
            )
        )

        # Set game_id and player_id as required by the WebSocket system
        interaction_request.game_id = getattr(context.game, "game_id", "")
        interaction_request.player_id = getattr(context.player, "id", "")
        # Expose to the higher-level adapter which will carry it through
        context.set_variable("final_interaction_request", interaction_request)

        context.add_result(f"Awaiting symbol selection from: {', '.join(available)}")

        logger.info(f"Created pending symbol selection with {len(available)} options")
        return ActionResult.REQUIRES_INTERACTION
