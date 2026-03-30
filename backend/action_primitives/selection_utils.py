"""
Shared utilities for selection-based action primitives.

Provides common resume logic for SelectSymbol, SelectColor, and ChooseOption.
"""

import logging
from collections.abc import Callable
from typing import Any, Optional

from .base import ActionContext, ActionResult

logger = logging.getLogger(__name__)


def handle_selection_resume(
    context: ActionContext,
    *,
    resume_var_name: str,
    result_var_name: str,
    available_options: list[Any],
    primitive_name: str,
    value_extractor: Optional[Callable[[Any, int], tuple[str, str]]] = None,
    on_success: Optional[Callable[[Any, str, str], ActionResult]] = None,
    result_message_prefix: str = "Selected",
) -> Optional[ActionResult]:
    """
    Handle resume logic for selection primitives.

    This eliminates code duplication across SelectSymbol, SelectColor, and ChooseOption
    by providing a standardized resume pattern.

    Args:
        context: Action execution context
        resume_var_name: Name of resume variable (e.g., "selected_symbol_choice")
        result_var_name: Name of result variable (e.g., "selected_symbol")
        available_options: List of available options to choose from
        primitive_name: Name of primitive for logging (e.g., "SelectSymbol")
        value_extractor: Optional function to extract (value, description) from option
                        Signature: (option, index) -> (value, description)
                        Defaults to treating options as simple values
        on_success: Optional callback for additional processing after successful selection
                   Signature: (option, value, description) -> ActionResult
                   Defaults to no additional processing
        result_message_prefix: Prefix for result message (default: "Selected")

    Returns:
        ActionResult.SUCCESS if resume was successful
        None if resume should fall through to new interaction request
    """
    # Check if we're resuming with a choice already made
    if not (
        context.has_variable(resume_var_name) or context.has_variable(result_var_name)
    ):
        return None  # Not resuming

    # Get resume value (prefer resume variable, fall back to result for idempotent resume)
    selected = context.get_variable(resume_var_name)
    if selected is None:
        selected = context.get_variable(result_var_name)

    # Default value extractor: treat options as simple values
    if value_extractor is None:

        def default_extractor(option: Any, _index: int) -> tuple[str, str]:
            return (str(option), str(option).capitalize())

        value_extractor = default_extractor

    # Match selected value to available options (by index, value, or description)
    chosen_option = None
    chosen_index = None

    if isinstance(selected, int):
        # Index-based selection
        if 0 <= selected < len(available_options):
            chosen_index = selected
            chosen_option = available_options[selected]
    elif isinstance(selected, str):
        # Value or description-based selection (case-insensitive)
        selected_lower = selected.lower()
        for i, option in enumerate(available_options):
            value, desc = value_extractor(option, i)
            if value.lower() == selected_lower or desc.lower() == selected_lower:
                chosen_index = i
                chosen_option = option
                break

    logger.debug(
        f"{primitive_name} resume: selected={selected}, chosen_option={chosen_option}, available_count={len(available_options)}"
    )

    # Validate choice
    if chosen_option is None or chosen_index is None:
        # CRITICAL FIX (Badge Guard): Invalid resume values might be stale from other primitives
        logger.warning(
            f"{primitive_name}: Invalid selection (possibly stale): selected={selected}, available_count={len(available_options)}"
        )
        logger.debug(
            f"{primitive_name}: Ignoring invalid resume value and continuing to request interaction"
        )
        return None  # Fall through to new interaction request

    # Extract value and description
    choice_value, choice_desc = value_extractor(chosen_option, chosen_index)

    # Store result variable
    context.set_variable(result_var_name, choice_value)
    context.add_result(f"{result_message_prefix}: {choice_desc}")
    logger.info(
        f"{primitive_name}: Successfully set {result_var_name} to {choice_value}"
    )

    # Execute success callback if provided
    if on_success is not None:
        result = on_success(chosen_option, choice_value, choice_desc)
        if result != ActionResult.SUCCESS:
            return result

    # CRITICAL FIX: Clear the final_interaction_request to prevent re-suspension loop
    if context.has_variable("final_interaction_request"):
        context.remove_variable("final_interaction_request")
        logger.debug(
            f"{primitive_name}: Cleared final_interaction_request to prevent re-suspension"
        )

    # CRITICAL FIX: Clear consumed choice variable to prevent re-execution
    context.remove_variable(resume_var_name)
    logger.debug(f"{primitive_name}: Cleared {resume_var_name} after successful resume")

    return ActionResult.SUCCESS
