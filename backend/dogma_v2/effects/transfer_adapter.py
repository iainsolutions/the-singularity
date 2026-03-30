"""
TransferEffectAdapter - Specialized adapter for card transfer effects.

This adapter handles all effects that move cards between locations:
- Drawing cards (DrawCards)
- Melding cards (MeldCard)
- Scoring cards (ScoreCards)
- Tucking cards (TuckCard)
- Junking cards (JunkCard, JunkCards)
- Transferring cards (TransferCards, TransferBetweenPlayers)
- Exchanging cards (ExchangeCards)
- Returning cards (ReturnCards)

It provides consistent validation, state tracking, and error handling
for all card movement operations.
"""

import logging
from typing import Any, ClassVar

from action_primitives import ActionResult, create_action_primitive
from action_primitives.base import ActionContext

from ..core.context import DogmaContext
from .base import Effect, EffectResult, EffectType

logger = logging.getLogger(__name__)


class TransferEffectAdapter(Effect):
    """
    Specialized adapter for card transfer effects.

    This adapter:
    1. Validates card availability before transfer
    2. Tracks card state changes
    3. Handles transfer failures gracefully
    4. Provides detailed transfer results
    """

    # Effects that this adapter handles
    TRANSFER_EFFECTS: ClassVar[set[str]] = {
        "DrawCards",
        "MeldCard",
        "ScoreCards",
        "TuckCard",
        "JunkCard",
        "JunkCards",
        "TransferCards",
        "TransferBetweenPlayers",
        "ExchangeCards",
        "ReturnCards",
    }

    # Effect categories for specialized handling
    DRAW_EFFECTS: ClassVar[set[str]] = {"DrawCards"}
    MELD_EFFECTS: ClassVar[set[str]] = {"MeldCard"}
    SCORE_EFFECTS: ClassVar[set[str]] = {"ScoreCards"}
    TUCK_EFFECTS: ClassVar[set[str]] = {"TuckCard"}
    JUNK_EFFECTS: ClassVar[set[str]] = {"JunkCard", "JunkCards"}
    TRANSFER_EFFECTS_STRICT: ClassVar[set[str]] = {
        "TransferCards",
        "TransferBetweenPlayers",
    }
    EXCHANGE_EFFECTS: ClassVar[set[str]] = {"ExchangeCards"}
    RETURN_EFFECTS: ClassVar[set[str]] = {"ReturnCards"}

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the transfer effect adapter.

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
            logger.error(f"Failed to create transfer primitive: {e}")
            self.primitive = None

    def execute(self, context: DogmaContext) -> EffectResult:
        """
        Execute the transfer effect.

        This handles:
        1. Pre-transfer validation
        2. Transfer execution
        3. Post-transfer verification
        4. Result tracking

        Args:
            context: The dogma execution context

        Returns:
            EffectResult with transfer details
        """
        if not self.primitive:
            return EffectResult(
                success=False, error="Failed to initialize transfer primitive"
            )

        effect_type = self.config.get("type", "")
        logger.debug(f"Executing transfer effect: {effect_type}")

        # Pre-execution validation
        validation_result = self._pre_transfer_validation(context)
        if not validation_result.success:
            return validation_result

        # Create action context
        action_context = self._create_action_context(context)

        try:
            # Execute the primitive
            result = self.primitive.execute(action_context)

            # Translate result with transfer-specific enhancements
            effect_result = self._translate_result(result, action_context, context)

            # Post-transfer processing
            self._post_transfer_processing(effect_result, context)

            return effect_result

        except Exception as e:
            logger.error(f"Error executing transfer effect: {e}", exc_info=True)
            return EffectResult(success=False, error=f"Transfer effect failed: {e}")

    def _pre_transfer_validation(self, context: DogmaContext) -> EffectResult:
        """
        Validate conditions before attempting transfer.

        Args:
            context: The dogma context

        Returns:
            EffectResult indicating if transfer can proceed
        """
        effect_type = self.config.get("type", "")

        # Draw effects: check if deck has cards
        if effect_type in self.DRAW_EFFECTS:
            age = self.config.get("age", 1)
            deck_name = f"age_{age}_deck"
            if hasattr(context.game, deck_name):
                deck = getattr(context.game, deck_name)
                if not deck:
                    logger.warning(f"Attempted to draw from empty age {age} deck")
                    # This is not necessarily a failure - some draws are optional

        # Meld effects: check if player has cards to meld
        elif effect_type in self.MELD_EFFECTS:
            player = context.current_player
            if not player.hand:
                logger.debug("Player has no cards in hand to meld")

        # Transfer between players: validate players exist
        elif effect_type in self.TRANSFER_EFFECTS_STRICT:
            from_player_id = self.config.get("from_player")
            self.config.get("to_player")

            if from_player_id == "opponent" and len(context.game.players) < 2:
                return EffectResult(
                    success=False,
                    error="Transfer requires opponent but only one player in game",
                )

        return EffectResult(success=True)

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
        self,
        primitive_result: ActionResult,
        action_context: ActionContext,
        dogma_context: DogmaContext,
    ) -> EffectResult:
        """
        Translate primitive result with transfer-specific enhancements.

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
                or f"Transfer effect '{self.config.get('type', 'unknown')}' failed"
            )
            return EffectResult(
                success=False,
                error=str(error_msg),
                variables=dict(action_context.variables),
                results=list(action_context.results),
            )

        # Extract transfer statistics
        transfer_stats = self._extract_transfer_stats(action_context)

        # Build enhanced result
        effect_result = EffectResult(
            success=success,
            variables=dict(action_context.variables),
            results=list(action_context.results),
        )

        # Add transfer statistics to variables
        if transfer_stats:
            effect_result.variables.update(transfer_stats)

        return effect_result

    def _extract_transfer_stats(self, action_context: ActionContext) -> dict[str, Any]:
        """
        Extract transfer statistics from action context.

        Args:
            action_context: The action context after execution

        Returns:
            Dictionary of transfer statistics
        """
        stats = {}
        effect_type = self.config.get("type", "")

        # Count cards that were moved
        if effect_type == "DrawCards":
            # Count cards added to hand
            drawn_count = 0
            for result in action_context.results:
                if "drew" in result.lower() or "drawn" in result.lower():
                    drawn_count += 1
            if drawn_count > 0:
                stats["cards_drawn"] = drawn_count

        elif effect_type == "ScoreCards":
            # Count cards added to score pile
            scored_count = 0
            for result in action_context.results:
                if "scored" in result.lower():
                    scored_count += 1
            if scored_count > 0:
                stats["cards_scored"] = scored_count

        elif effect_type in self.JUNK_EFFECTS:
            # Count cards junked
            junked_count = 0
            for result in action_context.results:
                if "junked" in result.lower():
                    junked_count += 1
            if junked_count > 0:
                stats["cards_junked"] = junked_count

        elif effect_type in self.TRANSFER_EFFECTS_STRICT:
            # Count cards transferred
            transferred_count = 0
            for result in action_context.results:
                if "transferred" in result.lower():
                    transferred_count += 1
            if transferred_count > 0:
                stats["cards_transferred"] = transferred_count

        return stats

    def _post_transfer_processing(
        self, effect_result: EffectResult, context: DogmaContext
    ):
        """
        Handle post-transfer processing.

        Args:
            effect_result: The effect result
            context: The dogma context
        """
        if not effect_result.success:
            return

        effect_type = self.config.get("type", "")

        # Update game state tracking
        if effect_type == "DrawCards":
            # Track cards drawn this turn via effect_result variables (context is immutable)
            turn_draws = context.variables.get("cards_drawn_this_turn", 0)
            new_draws = effect_result.variables.get("cards_drawn", 0)
            if new_draws:
                effect_result.variables["cards_drawn_this_turn"] = (
                    turn_draws + new_draws
                )

        elif effect_type == "ScoreCards":
            # Track score changes via effect_result variables (context is immutable)
            turn_scored = context.variables.get("cards_scored_this_turn", 0)
            new_scored = effect_result.variables.get("cards_scored", 0)
            if new_scored:
                effect_result.variables["cards_scored_this_turn"] = (
                    turn_scored + new_scored
                )

        # Log significant transfers
        if effect_result.results:
            logger.info(f"Transfer completed: {'; '.join(effect_result.results)}")

    def validate(self) -> tuple[bool, str | None]:
        """
        Validate transfer effect configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        effect_type = self.config.get("type", "")

        # Check if this is a transfer effect
        if effect_type not in self.TRANSFER_EFFECTS:
            return False, f"Not a transfer effect: {effect_type}"

        # Validate based on effect type
        if effect_type == "DrawCards":
            # Requires age and count
            if "age" not in self.config:
                return False, "DrawCards missing 'age'"
            if "count" not in self.config:
                return False, "DrawCards missing 'count'"
            age = self.config.get("age", 0)
            if not (1 <= age <= 10):
                return False, f"DrawCards age must be 1-10, got {age}"

        elif effect_type == "MeldCard":
            # May require selection or use variables
            pass  # Optional validation

        elif effect_type == "ScoreCards":
            # May require selection or source
            if "selection" in self.config and "source" in self.config:
                return False, "ScoreCards cannot have both 'selection' and 'source'"

        elif effect_type in self.TRANSFER_EFFECTS_STRICT:
            # Requires from/to locations
            if "from_location" not in self.config:
                return False, f"{effect_type} missing 'from_location'"
            if "to_location" not in self.config:
                return False, f"{effect_type} missing 'to_location'"

        elif effect_type == "ExchangeCards":
            # Requires locations and counts
            if "location1" not in self.config or "location2" not in self.config:
                return False, "ExchangeCards missing location specifications"

        # Check primitive initialization
        if not self.primitive:
            return False, "Failed to create transfer primitive"

        return True, None

    def get_description(self) -> str:
        """Get human-readable description of the transfer."""
        if "description" in self.config:
            return self.config["description"]

        effect_type = self.config.get("type", "transfer")

        # Generate meaningful descriptions
        if effect_type == "DrawCards":
            age = self.config.get("age", "?")
            count = self.config.get("count", 1)
            location = self.config.get("location", "hand")
            return f"Draw {count} age {age} card(s) to {location}"

        elif effect_type == "MeldCard":
            selection = self.config.get("selection", "card")
            return f"Meld {selection} from hand to board"

        elif effect_type == "ScoreCards":
            selection = self.config.get("selection", "cards")
            source = self.config.get("source", "selection")
            return f"Score {selection} from {source}"

        elif effect_type == "TuckCard":
            return "Tuck card under another card"

        elif effect_type in self.JUNK_EFFECTS:
            selection = self.config.get("selection", "card")
            return f"Junk {selection}"

        elif effect_type == "TransferCards":
            from_loc = self.config.get("from_location", "source")
            to_loc = self.config.get("to_location", "target")
            return f"Transfer cards from {from_loc} to {to_loc}"

        elif effect_type == "TransferBetweenPlayers":
            from_player = self.config.get("from_player", "source")
            to_player = self.config.get("to_player", "target")
            return f"Transfer cards from {from_player} to {to_player}"

        elif effect_type == "ExchangeCards":
            loc1 = self.config.get("location1", "location1")
            loc2 = self.config.get("location2", "location2")
            return f"Exchange cards between {loc1} and {loc2}"

        elif effect_type == "ReturnCards":
            selection = self.config.get("selection", "cards")
            to_location = self.config.get("to_location", "deck")
            return f"Return {selection} to {to_location}"

        return f"{effect_type} transfer"
