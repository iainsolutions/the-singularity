"""
ControlFlowAdapter - Specialized adapter for control flow effects.

This adapter handles effects that control the execution flow:
- Conditional actions (ConditionalAction) - if-then-else logic
- Loop actions (LoopAction, RepeatAction) - iteration and repetition
- Execute dogma (ExecuteDogma) - nested dogma execution

These effects require special handling for:
- Context preservation across nested executions
- Loop termination conditions
- Conditional evaluation with proper variable scoping
"""

import logging
from typing import Any, ClassVar

from action_primitives import ActionResult, create_action_primitive
from action_primitives.base import ActionContext

from ..core.context import DogmaContext
from .base import Effect, EffectResult, EffectType

logger = logging.getLogger(__name__)


class ControlFlowAdapter(Effect):
    """
    Specialized adapter for control flow effects.

    This adapter:
    1. Manages execution context across nested operations
    2. Handles loop termination and iteration limits
    3. Evaluates conditions with proper variable scoping
    4. Provides detailed execution flow tracking
    """

    # Effects that this adapter handles
    CONTROL_EFFECTS: ClassVar[set[str]] = {
        "ConditionalAction",
        "LoopAction",
        "RepeatAction",
        "ExecuteDogma",
    }

    # Maximum iterations to prevent infinite loops
    MAX_ITERATIONS = 100

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the control flow adapter.

        Args:
            config: Effect configuration from card JSON
        """
        super().__init__(config)
        self.type = (
            EffectType.CONDITIONAL
            if config.get("type") == "ConditionalAction"
            else EffectType.LOOP
        )
        self.primitive = None
        self._init_primitive()

    def _init_primitive(self):
        """Initialize the wrapped primitive."""
        try:
            self.primitive = create_action_primitive(self.config)
        except Exception as e:
            logger.error(f"Failed to create control flow primitive: {e}")
            self.primitive = None

    def execute(self, context: DogmaContext) -> EffectResult:
        """
        Execute the control flow effect.

        This handles:
        1. Execution context setup
        2. Condition evaluation or loop iteration
        3. Nested effect execution with context preservation
        4. Flow control tracking

        Args:
            context: The dogma execution context

        Returns:
            EffectResult with flow control details
        """
        if not self.primitive:
            return EffectResult(
                success=False, error="Failed to initialize control flow primitive"
            )

        effect_type = self.config.get("type", "")
        logger.debug(f"Executing control flow effect: {effect_type}")

        # Set up execution tracking
        execution_context = self._setup_execution_context(context)

        # Create action context with execution tracking
        action_context = self._create_action_context(context, execution_context)

        try:
            # Execute the primitive
            result = self.primitive.execute(action_context)

            # Translate result with control flow enhancements
            effect_result = self._translate_result(
                result, action_context, context, execution_context
            )

            # Post-execution processing
            self._post_execution_processing(effect_result, context, execution_context)

            return effect_result

        except Exception as e:
            logger.error(f"Error executing control flow effect: {e}", exc_info=True)
            return EffectResult(
                success=False, error=f"Control flow execution failed: {e}"
            )

    def _setup_execution_context(self, context: DogmaContext) -> dict[str, Any]:
        """
        Set up execution context for control flow tracking.

        Args:
            context: The dogma context

        Returns:
            Execution context dictionary
        """
        effect_type = self.config.get("type", "")
        execution_context = {
            "effect_type": effect_type,
            "start_time": None,  # Would use time.time() in real implementation
            "iterations": 0,
            "conditions_evaluated": 0,
            "nested_executions": 0,
        }

        # Add safety limits
        if effect_type in {"LoopAction", "RepeatAction"}:
            max_iterations = self.config.get("max_iterations", self.MAX_ITERATIONS)
            execution_context["max_iterations"] = min(
                max_iterations, self.MAX_ITERATIONS
            )
            execution_context["iteration_limit_reached"] = False

        elif effect_type == "ConditionalAction":
            execution_context["condition_result"] = None
            execution_context["branch_taken"] = None

        elif effect_type == "ExecuteDogma":
            execution_context["nested_card"] = self.config.get("card_name", "unknown")
            execution_context["nested_player"] = self.config.get(
                "target_player", "current"
            )

        return execution_context

    def _create_action_context(
        self, context: DogmaContext, execution_context: dict[str, Any]
    ) -> ActionContext:
        """
        Create ActionContext with execution tracking.

        Args:
            context: The dogma context
            execution_context: Execution tracking context

        Returns:
            Enhanced ActionContext
        """
        # Create base context
        action_context = ActionContext(
            game=context.game,
            player=context.current_player,
            card=context.card,
            variables=dict(context.variables),
            results=[],
            state_tracker=context.state_tracker,
            sharing=context.sharing,  # Pass sharing context through
        )

        # Add execution tracking variables
        action_context.update_variables(
            {
                "execution_context": execution_context,
                "control_flow_depth": context.variables.get("control_flow_depth", 0)
                + 1,
            }
        )

        return action_context

    def _translate_result(
        self,
        primitive_result: ActionResult,
        action_context: ActionContext,
        dogma_context: DogmaContext,
        execution_context: dict[str, Any],
    ) -> EffectResult:
        """
        Translate primitive result with control flow enhancements.

        Args:
            primitive_result: Raw result from primitive
            action_context: Context after execution
            dogma_context: Original dogma context
            execution_context: Execution tracking context

        Returns:
            Enhanced EffectResult
        """
        success = primitive_result == ActionResult.SUCCESS

        # Extract control flow statistics
        flow_stats = self._extract_flow_stats(action_context, execution_context)

        # Check for interaction requirements
        requires_interaction = primitive_result == ActionResult.REQUIRES_INTERACTION
        interaction_request = None
        if requires_interaction:
            interaction_request = action_context.variables.get(
                "final_interaction_request"
            )

        # Failure path: return clear error
        if primitive_result == ActionResult.FAILURE:
            error_msg = (
                action_context.variables.get("error")
                or action_context.variables.get("error_message")
                or f"Control flow effect '{execution_context.get('effect_type', 'unknown')}' failed"
            )
            return EffectResult(
                success=False,
                error=str(error_msg),
                variables=dict(action_context.variables),
                results=list(action_context.results),
            )

        # Build enhanced result
        effect_result = EffectResult(
            success=success,
            requires_interaction=requires_interaction,
            interaction_request=interaction_request,
            variables=dict(action_context.variables),
            results=list(action_context.results),
        )

        # Add control flow statistics
        if flow_stats:
            effect_result.variables.update(flow_stats)

        # Clean up internal execution tracking
        effect_result.variables.pop("execution_context", None)

        return effect_result

    def _extract_flow_stats(
        self, action_context: ActionContext, execution_context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Extract control flow statistics.

        Args:
            action_context: The action context after execution
            execution_context: Execution tracking context

        Returns:
            Dictionary of control flow statistics
        """
        stats = {}
        effect_type = execution_context.get("effect_type", "")

        if effect_type == "ConditionalAction":
            # Track condition evaluation
            condition_result = execution_context.get("condition_result")
            branch_taken = execution_context.get("branch_taken")

            if condition_result is not None:
                stats["condition_evaluated"] = True
                stats["condition_result"] = condition_result
            if branch_taken:
                stats["branch_taken"] = branch_taken

        elif effect_type in {"LoopAction", "RepeatAction"}:
            # Track iteration counts
            iterations = execution_context.get("iterations", 0)
            max_iterations = execution_context.get(
                "max_iterations", self.MAX_ITERATIONS
            )
            limit_reached = execution_context.get("iteration_limit_reached", False)

            stats["iterations_executed"] = iterations
            stats["max_iterations"] = max_iterations
            if limit_reached:
                stats["iteration_limit_reached"] = True

        elif effect_type == "ExecuteDogma":
            # Track nested execution
            nested_card = execution_context.get("nested_card", "unknown")
            nested_player = execution_context.get("nested_player", "current")

            stats["nested_dogma_executed"] = True
            stats["nested_card"] = nested_card
            stats["nested_player"] = nested_player

        return stats

    def _post_execution_processing(
        self,
        effect_result: EffectResult,
        context: DogmaContext,
        execution_context: dict[str, Any],
    ):
        """
        Handle post-execution processing.

        Args:
            effect_result: The effect result
            context: The dogma context
            execution_context: Execution tracking context
        """
        effect_type = execution_context.get("effect_type", "")

        # Log execution details
        if effect_type == "ConditionalAction":
            condition_result = effect_result.variables.get("condition_result")
            branch_taken = effect_result.variables.get("branch_taken")
            if condition_result is not None:
                logger.debug(
                    f"Condition evaluated to {condition_result}, took {branch_taken} branch"
                )

        elif effect_type in {"LoopAction", "RepeatAction"}:
            iterations = effect_result.variables.get("iterations_executed", 0)
            limit_reached = effect_result.variables.get(
                "iteration_limit_reached", False
            )
            logger.debug(
                f"Loop executed {iterations} iterations"
                + (" (limit reached)" if limit_reached else "")
            )

            if limit_reached:
                logger.warning(
                    f"Loop iteration limit reached ({iterations} iterations)"
                )

        elif effect_type == "ExecuteDogma":
            nested_card = effect_result.variables.get("nested_card", "unknown")
            logger.debug(f"Executed nested dogma for {nested_card}")

        # Update effect result with flow control state - don't modify immutable context directly
        depth = context.variables.get("control_flow_depth", 0)
        effect_result.variables["control_flow_depth"] = max(0, depth - 1)

        # Track nested executions for debugging
        if effect_type == "ExecuteDogma":
            nested_count = context.variables.get("nested_dogma_count", 0)
            effect_result.variables["nested_dogma_count"] = nested_count + 1

    def validate(self) -> tuple[bool, str | None]:
        """
        Validate control flow effect configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        effect_type = self.config.get("type", "")

        # Check if this is a control flow effect
        if effect_type not in self.CONTROL_EFFECTS:
            return False, f"Not a control flow effect: {effect_type}"

        # Validate based on effect type
        if effect_type == "ConditionalAction":
            # Requires condition and actions
            if "condition" not in self.config:
                return False, "ConditionalAction missing 'condition'"

            # Should have either if_true, if_false, or both
            has_true = "if_true" in self.config
            has_false = "if_false" in self.config
            if not (has_true or has_false):
                return (
                    False,
                    "ConditionalAction requires 'if_true' or 'if_false' actions",
                )

        elif effect_type in {"LoopAction", "RepeatAction"}:
            # Requires loop condition or count
            has_condition = "condition" in self.config
            has_count = "count" in self.config
            has_actions = "actions" in self.config

            if not (has_condition or has_count):
                return False, f"{effect_type} requires 'condition' or 'count'"
            if not has_actions:
                return False, f"{effect_type} missing 'actions'"

            # Validate iteration limits
            if has_count:
                count = self.config.get("count", 0)
                if not isinstance(count, int) or count < 0:
                    return False, f"{effect_type} count must be non-negative integer"
                if count > self.MAX_ITERATIONS:
                    return (
                        False,
                        f"{effect_type} count exceeds maximum ({self.MAX_ITERATIONS})",
                    )

        elif effect_type == "ExecuteDogma":
            # Requires card specification
            if "card_name" not in self.config and "card" not in self.config:
                return False, "ExecuteDogma requires 'card_name' or 'card'"

        # Check primitive initialization
        if not self.primitive:
            return False, "Failed to create control flow primitive"

        return True, None

    def get_description(self) -> str:
        """Get human-readable description of the control flow."""
        if "description" in self.config:
            return self.config["description"]

        effect_type = self.config.get("type", "control flow")

        # Generate meaningful descriptions
        if effect_type == "ConditionalAction":
            condition = self.config.get("condition", {})
            condition_type = (
                condition.get("type", "condition")
                if isinstance(condition, dict)
                else str(condition)
            )
            return f"If {condition_type} then execute actions"

        elif effect_type == "LoopAction":
            condition = self.config.get("condition", {})
            if condition:
                condition_type = (
                    condition.get("type", "condition")
                    if isinstance(condition, dict)
                    else str(condition)
                )
                return f"Loop while {condition_type}"
            else:
                return "Loop with actions"

        elif effect_type == "RepeatAction":
            count = self.config.get("count", "?")
            return f"Repeat actions {count} times"

        elif effect_type == "ExecuteDogma":
            card_name = self.config.get("card_name", self.config.get("card", "card"))
            target = self.config.get("target_player", "current player")
            return f"Execute {card_name} dogma for {target}"

        return f"{effect_type} effect"
