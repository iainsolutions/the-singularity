"""
BoardManipulationAdapter - Specialized adapter for board manipulation effects.

This adapter handles effects that change the visual arrangement or
accessibility of cards on the game board:
- Splaying cards (SplayCards) - changes visual arrangement and symbol visibility
- Filtering cards (FilterCards) - creates subsets of cards
- Reveal and process (RevealAndProcess) - temporarily reveals cards

These effects require special handling for visual state synchronization
and proper card accessibility calculations.
"""

import logging
from typing import Any, ClassVar

from action_primitives import ActionResult, create_action_primitive
from action_primitives.base import ActionContext

from ..core.context import DogmaContext
from .base import Effect, EffectResult, EffectType

logger = logging.getLogger(__name__)


class BoardManipulationAdapter(Effect):
    """
    Specialized adapter for board manipulation effects.

    This adapter:
    1. Tracks board state changes
    2. Validates splay operations
    3. Handles visual state synchronization
    4. Manages card accessibility updates
    """

    # Effects that this adapter handles
    BOARD_EFFECTS: ClassVar[set[str]] = {
        "SplayCards",
        "FilterCards",
        "RevealAndProcess",
    }

    # Splay directions for validation
    VALID_SPLAY_DIRECTIONS: ClassVar[set[str]] = {"left", "right", "up", "none", "aslant"}

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the board manipulation adapter.

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
            logger.error(f"Failed to create board manipulation primitive: {e}")
            self.primitive = None

    def execute(self, context: DogmaContext) -> EffectResult:
        """
        Execute the board manipulation effect.

        This handles:
        1. Pre-manipulation validation
        2. Effect execution
        3. Board state synchronization
        4. Visual update notifications

        Args:
            context: The dogma execution context

        Returns:
            EffectResult with board changes
        """
        if not self.primitive:
            return EffectResult(
                success=False, error="Failed to initialize board manipulation primitive"
            )

        effect_type = self.config.get("type", "")
        logger.debug(f"Executing board manipulation effect: {effect_type}")

        # Pre-execution validation
        validation_result = self._pre_manipulation_validation(context)
        if not validation_result.success:
            return validation_result

        # Store pre-execution state for comparison
        pre_state = self._capture_board_state(context)

        # Create action context
        action_context = self._create_action_context(context)

        try:
            # Execute the primitive
            result = self.primitive.execute(action_context)

            # Translate result with board-specific enhancements
            effect_result = self._translate_result(result, action_context, context)

            # Post-manipulation processing
            self._post_manipulation_processing(effect_result, context, pre_state)

            return effect_result

        except Exception as e:
            logger.error(
                f"Error executing board manipulation effect: {e}", exc_info=True
            )
            return EffectResult(success=False, error=f"Board manipulation failed: {e}")

    def _pre_manipulation_validation(self, context: DogmaContext) -> EffectResult:
        """
        Validate conditions before board manipulation.

        Args:
            context: The dogma context

        Returns:
            EffectResult indicating if manipulation can proceed
        """
        effect_type = self.config.get("type", "")

        if effect_type == "SplayCards":
            # Validate splay direction
            direction = self.config.get("direction", "").lower()
            if direction not in self.VALID_SPLAY_DIRECTIONS:
                return EffectResult(
                    success=False,
                    error=f"Invalid splay direction: {direction}. Must be one of {self.VALID_SPLAY_DIRECTIONS}",
                )

            # Validate color specification
            color = self.config.get("color")
            if not color:
                return EffectResult(
                    success=False, error="SplayCards requires 'color' specification"
                )

            # Check if player has cards of the specified color
            player = context.current_player
            color_stack = getattr(player.board, f"{color}_stack", None)
            if not color_stack or len(color_stack) < 2:
                logger.debug(
                    f"Player has insufficient {color} cards to splay ({len(color_stack) if color_stack else 0} cards)"
                )
                # This is not an error - splaying fewer than 2 cards is a no-op

        elif effect_type == "FilterCards":
            # Validate filter criteria - supports 'criteria', 'filter', or 'filters'
            if "criteria" not in self.config and "filter" not in self.config and "filters" not in self.config:
                return EffectResult(
                    success=False, error="FilterCards requires filter criteria"
                )

        elif effect_type == "RevealAndProcess":
            # Validate reveal source - can be either 'source' (draw-based) or 'selection' (selection-based)
            source = self.config.get("source")
            selection = self.config.get("selection")
            if not source and not selection:
                return EffectResult(
                    success=False, error="RevealAndProcess requires 'source' or 'selection'"
                )

        return EffectResult(success=True)

    def _capture_board_state(self, context: DogmaContext) -> dict[str, Any]:
        """
        Capture current board state for change tracking.

        Args:
            context: The dogma context

        Returns:
            Dictionary representing current board state
        """
        player = context.current_player
        board_state = {}

        # Capture splay states
        colors = ["red", "blue", "green", "yellow", "purple"]
        for color in colors:
            stack = getattr(player.board, f"{color}_stack", None)
            if stack:
                splay_direction = getattr(stack, "splay_direction", "none")
                board_state[f"{color}_splay"] = splay_direction
                board_state[f"{color}_count"] = len(stack)

        return board_state

    def _create_action_context(self, context: DogmaContext) -> ActionContext:
        """Create ActionContext from DogmaContext."""
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
        Translate primitive result with board-specific enhancements.

        Args:
            primitive_result: Raw result from primitive
            action_context: Context after execution
            dogma_context: Original dogma context

        Returns:
            Enhanced EffectResult
        """
        success = primitive_result == ActionResult.SUCCESS

        # Failure path: surface error message
        if primitive_result == ActionResult.FAILURE:
            error_msg = (
                action_context.variables.get("error")
                or action_context.variables.get("error_message")
                or f"Board effect '{self.config.get('type', 'unknown')}' failed"
            )
            return EffectResult(
                success=False,
                error=str(error_msg),
                variables=dict(action_context.variables),
                results=list(action_context.results),
            )

        # Extract board changes
        board_changes = self._extract_board_changes(action_context)

        # Build enhanced result
        effect_result = EffectResult(
            success=success,
            variables=dict(action_context.variables),
            results=list(action_context.results),
        )

        # Add board change metadata
        if board_changes:
            effect_result.variables.update(board_changes)

        return effect_result

    def _extract_board_changes(self, action_context: ActionContext) -> dict[str, Any]:
        """
        Extract board changes from action context.

        Args:
            action_context: The action context after execution

        Returns:
            Dictionary of board changes
        """
        changes = {}
        effect_type = self.config.get("type", "")

        if effect_type == "SplayCards":
            # Track splay changes
            color = self.config.get("color", "")
            direction = self.config.get("direction", "")
            if color and direction:
                changes[f"{color}_splayed"] = direction
                changes["splay_changed"] = True

        elif effect_type == "FilterCards":
            # Track filtered card count
            filtered_cards = []
            for result in action_context.results:
                if "filtered" in result.lower():
                    # Extract card information if available
                    filtered_cards.append(result)
            if filtered_cards:
                changes["filtered_results"] = filtered_cards
                changes["filtered_count"] = len(filtered_cards)

        elif effect_type == "RevealAndProcess":
            # Track revealed cards
            revealed_cards = []
            for result in action_context.results:
                if "revealed" in result.lower():
                    revealed_cards.append(result)
            if revealed_cards:
                changes["revealed_results"] = revealed_cards
                changes["revealed_count"] = len(revealed_cards)

        return changes

    def _post_manipulation_processing(
        self,
        effect_result: EffectResult,
        context: DogmaContext,
        pre_state: dict[str, Any],
    ):
        """
        Handle post-manipulation processing.

        Args:
            effect_result: The effect result
            context: The dogma context
            pre_state: Board state before manipulation
        """
        if not effect_result.success:
            return

        effect_type = self.config.get("type", "")

        # Update context with board changes
        if effect_type == "SplayCards":
            color = self.config.get("color", "")
            direction = self.config.get("direction", "")

            # Track splay state change
            old_splay = pre_state.get(f"{color}_splay", "none")
            if old_splay != direction:
                # Store splay state changes in effect_result.variables (mutable dict)
                effect_result.variables[f"{color}_splay_changed"] = True
                effect_result.variables[f"{color}_old_splay"] = old_splay
                effect_result.variables[f"{color}_new_splay"] = direction

                # Log significant splay changes
                player_name = context.current_player.name
                logger.info(
                    f"{player_name} splayed {color} {direction} (was {old_splay})"
                )

                # Add visual update notification
                effect_result.variables["visual_update_required"] = True
                effect_result.variables["updated_color"] = color

        elif effect_type in {"FilterCards", "RevealAndProcess"}:
            # These effects may require UI updates to show/hide cards
            effect_result.variables["board_visibility_changed"] = True

        # Log board manipulation results
        if effect_result.results:
            logger.debug(
                f"Board manipulation completed: {'; '.join(effect_result.results)}"
            )

    def validate(self) -> tuple[bool, str | None]:
        """
        Validate board manipulation effect configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        effect_type = self.config.get("type", "")

        # Check if this is a board effect
        if effect_type not in self.BOARD_EFFECTS:
            return False, f"Not a board manipulation effect: {effect_type}"

        # Validate based on effect type
        if effect_type == "SplayCards":
            # Requires color and direction
            if "color" not in self.config:
                return False, "SplayCards missing 'color'"
            if "direction" not in self.config:
                return False, "SplayCards missing 'direction'"

            direction = self.config.get("direction", "").lower()
            if direction not in self.VALID_SPLAY_DIRECTIONS:
                return False, f"SplayCards invalid direction: {direction}"

        elif effect_type == "FilterCards":
            # Requires filter criteria
            if "criteria" not in self.config and "filter" not in self.config:
                return False, "FilterCards missing filter criteria"

        elif effect_type == "RevealAndProcess":
            # Requires source and actions
            if "source" not in self.config:
                return False, "RevealAndProcess missing 'source'"
            if "actions" not in self.config:
                return False, "RevealAndProcess missing 'actions'"

        # Check primitive initialization
        if not self.primitive:
            return False, "Failed to create board manipulation primitive"

        return True, None

    def get_description(self) -> str:
        """Get human-readable description of the board manipulation."""
        if "description" in self.config:
            return self.config["description"]

        effect_type = self.config.get("type", "board manipulation")

        # Generate meaningful descriptions
        if effect_type == "SplayCards":
            color = self.config.get("color", "cards")
            direction = self.config.get("direction", "unknown")
            return f"Splay {color} cards {direction}"

        elif effect_type == "FilterCards":
            criteria = self.config.get(
                "criteria", self.config.get("filter", "criteria")
            )
            source = self.config.get("source", "cards")
            return f"Filter {source} by {criteria}"

        elif effect_type == "RevealAndProcess":
            source = self.config.get("source", "cards")
            count = self.config.get("count", 1)
            return f"Reveal {count} card(s) from {source} and process"

        return f"{effect_type} effect"
