"""
CalculationEffectAdapter - Specialized adapter for calculation effects.

This adapter handles effects that perform computations and value calculations:
- Counting effects (CountCards, CountSymbols, CountColorsWithSymbol, etc.)
- Value calculations (CalculateValue)
- Card property extraction (GetCardAge, GetCardColor)
- Unique value computations (CountUniqueColors, CountUniqueValues)

These effects require special handling for:
- Type safety and numeric validation
- Variable storage and retrieval
- Mathematical operations
- Result caching and optimization
"""

import logging
from typing import Any, ClassVar

from action_primitives import ActionResult, create_action_primitive
from action_primitives.base import ActionContext

from ..core.context import DogmaContext
from .base import Effect, EffectResult, EffectType

logger = logging.getLogger(__name__)


class CalculationEffectAdapter(Effect):
    """
    Specialized adapter for calculation effects.

    This adapter:
    1. Validates numeric operations and types
    2. Handles variable storage for calculated values
    3. Provides result caching for expensive computations
    4. Ensures type safety in mathematical operations
    """

    # Effects that this adapter handles
    CALCULATION_EFFECTS: ClassVar[set[str]] = {
        "CountCards",
        "CountSymbols",
        "CountColorsWithSymbol",
        "CountColorsWithSplay",
        "CountUniqueColors",
        "CountUniqueValues",
        "CalculateValue",
        "GetCardAge",
        "GetCardColor",
    }

    # Counting effects that return integers
    COUNTING_EFFECTS: ClassVar[set[str]] = {
        "CountCards",
        "CountSymbols",
        "CountColorsWithSymbol",
        "CountColorsWithSplay",
        "CountUniqueColors",
        "CountUniqueValues",
    }

    # Property extraction effects that return specific types
    PROPERTY_EFFECTS: ClassVar[dict[str, type]] = {
        "GetCardAge": int,  # Returns age as integer
        "GetCardColor": str,  # Returns color as string
    }

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the calculation effect adapter.

        Args:
            config: Effect configuration from card JSON
        """
        super().__init__(config)
        self.type = EffectType.STANDARD
        self.primitive = None
        self._init_primitive()

    def _init_primitive(self):
        """Initialize the wrapped primitive."""
        try:
            self.primitive = create_action_primitive(self.config)
        except Exception as e:
            logger.error(f"Failed to create calculation primitive: {e}")
            self.primitive = None

    def execute(self, context: DogmaContext) -> EffectResult:
        """
        Execute the calculation effect.

        This handles:
        1. Input validation and type checking
        2. Calculation execution
        3. Result validation and type conversion
        4. Variable storage with proper naming

        Args:
            context: The dogma execution context

        Returns:
            EffectResult with calculated values
        """
        if not self.primitive:
            return EffectResult(
                success=False, error="Failed to initialize calculation primitive"
            )

        effect_type = self.config.get("type", "")
        logger.debug(f"Executing calculation effect: {effect_type}")

        # Pre-calculation validation
        validation_result = self._pre_calculation_validation(context)
        if not validation_result.success:
            return validation_result

        # Create action context with calculation setup
        action_context = self._create_action_context(context)

        try:
            # Execute the primitive
            result = self.primitive.execute(action_context)

            # Translate result with calculation enhancements
            effect_result = self._translate_result(result, action_context, context)

            # Post-calculation processing
            self._post_calculation_processing(effect_result, context)

            return effect_result

        except Exception as e:
            logger.error(f"Error executing calculation effect: {e}", exc_info=True)
            return EffectResult(success=False, error=f"Calculation failed: {e}")

    def _pre_calculation_validation(self, context: DogmaContext) -> EffectResult:
        """
        Validate inputs before calculation.

        Args:
            context: The dogma context

        Returns:
            EffectResult indicating if calculation can proceed
        """
        effect_type = self.config.get("type", "")

        # Validate CalculateValue operands
        if effect_type == "CalculateValue":
            # Support multiple parameter naming conventions
            operand1 = (
                self.config.get("operand1")
                or self.config.get("value1")
                or self.config.get("left")
            )
            operand2 = (
                self.config.get("operand2")
                or self.config.get("value2")
                or self.config.get("right")
            )
            operation = self.config.get("operation", "add")

            if not operand1 or not operand2:
                return EffectResult(
                    success=False,
                    error="CalculateValue requires operand1/value1 and operand2/value2",
                )

            # Validate operation type
            valid_operations = {"add", "subtract", "multiply", "divide", "min", "max"}
            if operation not in valid_operations:
                return EffectResult(
                    success=False,
                    error=f"Invalid operation: {operation}. Must be one of {valid_operations}",
                )

            # Try to resolve operands to check they exist
            value1 = self._resolve_operand(operand1, context)
            value2 = self._resolve_operand(operand2, context)

            if value1 is None and operand1.get("type") == "variable":
                logger.warning(
                    f"Variable {operand1.get('name')} not found for calculation"
                )
            if value2 is None and operand2.get("type") == "variable":
                logger.warning(
                    f"Variable {operand2.get('name')} not found for calculation"
                )

        # Validate counting targets
        elif effect_type in self.COUNTING_EFFECTS:
            # Check source specification
            self.config.get("source", self.config.get("location", "hand"))
            if effect_type.startswith("CountColorsWithSymbol"):
                symbol = self.config.get("symbol")
                if not symbol:
                    return EffectResult(
                        success=False,
                        error=f"{effect_type} requires 'symbol' parameter",
                    )

        # Validate property extraction targets
        elif effect_type in self.PROPERTY_EFFECTS:
            # Check for selection, card, or source parameter
            selection = self.config.get("selection") or self.config.get("card") or self.config.get("source")
            if not selection:
                return EffectResult(
                    success=False, error=f"{effect_type} requires card selection"
                )

        return EffectResult(success=True)

    def _resolve_operand(self, operand: dict[str, Any], context: DogmaContext) -> Any:
        """
        Resolve an operand value from configuration.

        Args:
            operand: Operand configuration
            context: The dogma context

        Returns:
            Resolved operand value or None
        """
        if not isinstance(operand, dict):
            return operand

        operand_type = operand.get("type", "literal")

        if operand_type == "literal":
            return operand.get("value")
        elif operand_type == "variable":
            var_name = operand.get("name")
            return context.variables.get(var_name)
        elif operand_type == "constant":
            return operand.get("value")
        else:
            logger.warning(f"Unknown operand type: {operand_type}")
            return None

    def _create_action_context(self, context: DogmaContext) -> ActionContext:
        """Create ActionContext for calculation."""
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
        """
        Translate primitive result with calculation enhancements.

        Args:
            primitive_result: Raw result from primitive
            action_context: Context after execution
            dogma_context: Original dogma context

        Returns:
            Enhanced EffectResult with validated calculations
        """
        success = primitive_result == ActionResult.SUCCESS

        # Extract and validate calculated values
        calculated_values = self._extract_calculated_values(action_context)

        # Build enhanced result
        effect_result = EffectResult(
            success=success,
            variables=dict(action_context.variables),
            results=list(action_context.results),
        )

        # Add validated calculated values
        if calculated_values:
            effect_result.variables.update(calculated_values)

        return effect_result

    def _extract_calculated_values(
        self, action_context: ActionContext
    ) -> dict[str, Any]:
        """
        Extract and validate calculated values.

        Args:
            action_context: The action context after execution

        Returns:
            Dictionary of validated calculated values
        """
        values = {}
        effect_type = self.config.get("type", "")

        # Get the storage variable name
        store_result = self.config.get("store_result", "result")

        if effect_type in self.COUNTING_EFFECTS:
            # Extract count values - should be integers >= 0
            result_value = action_context.variables.get(store_result)
            if result_value is not None:
                try:
                    count_value = int(result_value)
                    if count_value >= 0:
                        values[store_result] = count_value
                        values[f"{effect_type.lower()}_result"] = count_value
                    else:
                        logger.warning(f"Negative count result: {count_value}")
                        values[store_result] = 0
                except (ValueError, TypeError):
                    logger.error(f"Invalid count result type: {result_value}")
                    values[store_result] = 0

        elif effect_type == "CalculateValue":
            # Extract calculated value - should be numeric
            result_value = action_context.variables.get(store_result)
            if result_value is not None:
                try:
                    # Try to preserve the original numeric type
                    if isinstance(result_value, int | float):
                        values[store_result] = result_value
                    else:
                        # Try to convert
                        float_value = float(result_value)
                        # Use int if it's a whole number
                        if float_value.is_integer():
                            values[store_result] = int(float_value)
                        else:
                            values[store_result] = float_value
                except (ValueError, TypeError):
                    logger.error(f"Invalid calculation result type: {result_value}")
                    values[store_result] = 0

        elif effect_type in self.PROPERTY_EFFECTS:
            # Extract property values with type validation
            result_value = action_context.variables.get(store_result)
            expected_type = self.PROPERTY_EFFECTS[effect_type]

            if result_value is not None:
                try:
                    if expected_type == int:
                        values[store_result] = int(result_value)
                    elif expected_type == str:
                        values[store_result] = str(result_value)
                    else:
                        values[store_result] = result_value
                except (ValueError, TypeError):
                    logger.error(
                        f"Invalid property result type for {effect_type}: {result_value}"
                    )
                    # Use appropriate default
                    if expected_type == int:
                        values[store_result] = 0
                    elif expected_type == str:
                        values[store_result] = ""
                    else:
                        values[store_result] = None

        return values

    def _post_calculation_processing(
        self, effect_result: EffectResult, context: DogmaContext
    ):
        """
        Handle post-calculation processing.

        Args:
            effect_result: The effect result
            context: The dogma context
        """
        if not effect_result.success:
            return

        effect_type = self.config.get("type", "")
        store_result = self.config.get("store_result", "result")

        # Log significant calculations
        result_value = effect_result.variables.get(store_result)
        if result_value is not None:
            logger.debug(f"{effect_type} calculated: {result_value}")

            # Track calculation statistics using the mutable effect result only.
            previous_count = effect_result.variables.get("calculations_performed", 0)
            try:
                effect_result.variables["calculations_performed"] = (
                    int(previous_count) + 1
                )
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid calculations_performed counter %s; resetting to 1",
                    previous_count,
                )
                effect_result.variables["calculations_performed"] = 1

            # Store calculation history for debugging without mutating the frozen context
            existing_history = effect_result.variables.get("calculation_history", [])
            calc_history = (
                list(existing_history) if isinstance(existing_history, list) else []
            )
            calc_history.append(
                {"type": effect_type, "result": result_value, "variable": store_result}
            )
            # Keep only recent calculations to avoid memory issues
            if len(calc_history) > 10:
                calc_history = calc_history[-10:]
            effect_result.variables["calculation_history"] = calc_history

    def validate(self) -> tuple[bool, str | None]:
        """
        Validate calculation effect configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        effect_type = self.config.get("type", "")

        # Check if this is a calculation effect
        if effect_type not in self.CALCULATION_EFFECTS:
            return False, f"Not a calculation effect: {effect_type}"

        # Validate store_result parameter
        store_result = self.config.get("store_result")
        if not store_result:
            return False, f"{effect_type} missing 'store_result' parameter"

        # Type-specific validation
        if effect_type == "CalculateValue":
            # Requires operands and operation
            if "operand1" not in self.config or "operand2" not in self.config:
                return False, "CalculateValue requires operand1 and operand2"
            if "operation" not in self.config:
                return False, "CalculateValue requires operation"

        elif effect_type.startswith("CountColorsWithSymbol"):
            # Requires symbol parameter
            if "symbol" not in self.config:
                return False, f"{effect_type} requires 'symbol' parameter"

        elif effect_type in self.PROPERTY_EFFECTS:
            # Requires selection or card
            has_selection = "selection" in self.config
            has_card = "card" in self.config
            if not (has_selection or has_card):
                return False, f"{effect_type} requires 'selection' or 'card'"

        # Check primitive initialization
        if not self.primitive:
            return False, "Failed to create calculation primitive"

        return True, None

    def get_description(self) -> str:
        """Get human-readable description of the calculation."""
        if "description" in self.config:
            return self.config["description"]

        effect_type = self.config.get("type", "calculation")
        store_result = self.config.get("store_result", "result")

        # Generate meaningful descriptions
        if effect_type == "CountCards":
            source = self.config.get("source", "cards")
            return f"Count cards in {source} → {store_result}"

        elif effect_type == "CountSymbols":
            symbol = self.config.get("symbol", "symbols")
            source = self.config.get("source", "board")
            return f"Count {symbol} symbols on {source} → {store_result}"

        elif effect_type == "CountColorsWithSymbol":
            symbol = self.config.get("symbol", "symbol")
            return f"Count colors with {symbol} symbol → {store_result}"

        elif effect_type == "CountColorsWithSplay":
            splay = self.config.get("splay_direction", "any")
            return f"Count colors splayed {splay} → {store_result}"

        elif effect_type == "CalculateValue":
            op1 = self.config.get("operand1", {})
            op2 = self.config.get("operand2", {})
            operation = self.config.get("operation", "operation")

            op1_str = op1.get("name", str(op1)) if isinstance(op1, dict) else str(op1)
            op2_str = op2.get("name", str(op2)) if isinstance(op2, dict) else str(op2)

            return f"Calculate {op1_str} {operation} {op2_str} → {store_result}"

        elif effect_type == "GetCardAge":
            selection = self.config.get("selection", "card")
            return f"Get age of {selection} → {store_result}"

        elif effect_type == "GetCardColor":
            selection = self.config.get("selection", "card")
            return f"Get color of {selection} → {store_result}"

        elif effect_type.startswith("CountUnique"):
            what = effect_type.replace("CountUnique", "").lower()
            source = self.config.get("source", "cards")
            return f"Count unique {what} in {source} → {store_result}"

        return f"{effect_type} → {store_result}"
