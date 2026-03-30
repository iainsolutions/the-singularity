"""StandardInteractionBuilder - Single source of truth for dogma interaction requests.

This module eliminates field name inconsistencies by providing a canonical way
to create all interaction requests. All action primitives must use this builder
instead of creating their own interaction request formats.

UPDATED: Now uses Pydantic models for type safety and validation.
"""

import logging
from typing import TYPE_CHECKING, Any, Optional, Union

from models.card import Card
from schemas.interaction_data import (
    AchievementSelectionData,
    CardSelectionData,
    CardSource,
    OptionSelectionData,
    validate_model_no_cards_field,
)
from schemas.websocket_messages import DogmaInteractionRequest, InteractionType

# Avoid circular import - only import for type checking
if TYPE_CHECKING:
    from dogma_v2.context import ActionContext

logger = logging.getLogger(__name__)


class StandardInteractionBuilder:
    """Single source of truth for creating standardized dogma interaction requests.

    This builder ensures:
    1. Consistent field naming (always 'eligible_cards', never 'cards')
    2. Standardized message structure
    3. Proper data validation
    4. Single place to change interaction format if needed
    """

    @staticmethod
    def create_card_selection_request(
        eligible_cards: list[Card],
        min_count: int,
        max_count: int,
        message: str,
        is_optional: bool = False,
        source: str | None = None,
        source_player: str | None = None,
        execution_results: list[str] | None = None,
        context: "ActionContext | None" = None,  # NEW: For Phase 1A eligibility metadata
    ) -> DogmaInteractionRequest:
        """Create a type-safe standardized card selection interaction request.

        This is the ONLY way action primitives should create card selection interactions.
        Uses Pydantic models for validation and type safety.

        Phase 1A: Removed legacy store_result and selection_type parameters.
        Now requires context for clickable metadata generation.

        Args:
            eligible_cards: List of cards that can be selected
            min_count: Minimum number of cards to select
            max_count: Maximum number of cards to select
            message: Message to display to the player
            is_optional: Whether the selection can be declined
            source: Source of the cards (e.g., "hand", "board")
            source_player: Player whose cards are being selected from
            execution_results: Recent execution context to show player what just happened
            context: ActionContext for Phase 1A metadata (eligible_card_ids, clickable_locations)

        Returns:
            Type-safe DogmaInteractionRequest ready for WebSocket transmission

        Raises:
            ValidationError: If the request data is invalid
            ValueError: If input parameters are invalid or context is missing
        """
        # Validate inputs early
        if min_count < 0:
            raise ValueError(f"min_count cannot be negative: {min_count}")

        if max_count < min_count:
            raise ValueError(
                f"max_count ({max_count}) cannot be less than min_count ({min_count})"
            )

        # Determine location from source parameter
        # PHASE 1A: Extract card IDs from Card objects (no more full CardReference objects)
        eligible_card_ids = []
        eligible_cards_dicts = []  # For AI player prompts
        for card in eligible_cards:
            if card is None:
                logger.warning("Skipping None card in eligible_cards list")
                continue
            # Use card_id if available, fallback to name
            card_id = card.card_id if card.card_id is not None else card.name
            eligible_card_ids.append(card_id)
            # Add card dict for AI prompts (needs name, age, color)
            eligible_cards_dicts.append(
                {
                    "name": card.name,
                    "age": card.age,
                    "color": card.color.value
                    if hasattr(card.color, "value")
                    else str(card.color),
                    "card_id": card_id,
                }
            )

        # Convert source string to CardSource enum
        card_source = CardSource.HAND  # Default
        if source:
            source_mapping = {
                "hand": CardSource.HAND,
                "board": CardSource.BOARD,
                "board_top": CardSource.BOARD,  # board_top selections are from board
                "score_pile": CardSource.SCORE_PILE,
                "all": CardSource.ALL_CARDS,
            }
            card_source = source_mapping.get(source.lower(), CardSource.HAND)

        # PHASE 1A: Require context for Phase 1A metadata (clickable hints)
        if context is None:
            raise ValueError(
                "Phase 1A: context is required for card selection requests. "
                "StandardInteractionBuilder needs ActionContext to generate clickable_locations and clickable_player_ids."
            )

        # Validate context has required attributes
        if not hasattr(context, "player") or not hasattr(context, "game"):
            raise ValueError(
                "Phase 1A: Invalid context provided - missing 'player' or 'game' attribute. "
                "ActionContext must have both player and game references."
            )

        # Create CardSelectionData with Phase 1A fields
        selection_data = CardSelectionData(
            type="select_cards",
            message=message,
            source_player=source_player or "current_player",
            eligible_card_ids=eligible_card_ids,  # PHASE 1A: Just IDs, not full objects
            min_count=min_count,
            max_count=min(max_count, len(eligible_card_ids)),  # Cap at available cards
            source=card_source,
            is_optional=is_optional,
        )

        # Validate that we don't have the field name bug
        validate_model_no_cards_field(selection_data)

        # Convert to dict for JSON serialization
        data_dict = selection_data.model_dump()

        # Add eligible_cards as dicts for AI player prompts
        # AI prompt builder expects eligible_cards to be a list of dicts with name, age, color
        data_dict["eligible_cards"] = eligible_cards_dicts

        # PHASE 1A: Add clickable metadata for frontend UI hints
        # Add clickable_locations (which card sources are clickable)
        data_dict[
            "clickable_locations"
        ] = StandardInteractionBuilder._get_clickable_locations(
            eligible_cards, source_player or "current_player", context
        )

        # Add clickable_player_ids (which player boards are clickable)
        data_dict[
            "clickable_player_ids"
        ] = StandardInteractionBuilder._get_clickable_players(
            source_player or "current_player", context
        )

        # Create the complete DogmaInteractionRequest
        request = DogmaInteractionRequest(
            type="dogma_interaction",
            game_id="",  # Will be set by caller
            player_id="",  # Will be set by caller
            interaction_type=InteractionType.SELECT_CARDS,
            data=data_dict,  # Use enhanced dict with Phase 1A fields
            can_cancel=is_optional,
            execution_results=execution_results,  # Attach execution context
        )

        logger.debug(
            f"Phase 1A: Created card selection request: {len(eligible_card_ids)} eligible card IDs, "
            f"range: {min_count}-{max_count}, optional: {is_optional}, "
            f"clickable_locations: {data_dict['clickable_locations']}, "
            f"clickable_players: {len(data_dict['clickable_player_ids'])}"
        )

        return request

    @staticmethod
    def create_choice_selection_request(
        choices: list[str],
        message: str,
        is_optional: bool = False,
        source_player: str | None = None,
        default_option: str | None = None,
        execution_results: list[str] | None = None,
    ) -> DogmaInteractionRequest:
        """Create a type-safe standardized choice selection interaction request.

        Args:
            choices: List of choice strings to present to the player
            message: Message to display to the player
            is_optional: Whether the choice can be declined
            source_player: Player who triggered the interaction
            default_option: Default option if any
            execution_results: Recent execution context to show player what just happened

        Returns:
            Type-safe DogmaInteractionRequest ready for WebSocket transmission

        Raises:
            ValidationError: If the request data is invalid
            ValueError: If input parameters are invalid
        """
        if not choices:
            raise ValueError("choices cannot be empty")

        # Create OptionSelectionData with type safety
        option_data = OptionSelectionData(
            type="choose_option",
            message=message,
            source_player=source_player or "current_player",
            options=choices,  # Pydantic model handles simple string list
            allow_cancel=is_optional,
            default_option=default_option,
        )

        # Create the complete DogmaInteractionRequest
        request = DogmaInteractionRequest(
            type="dogma_interaction",
            game_id="",  # Will be set by caller
            player_id="",  # Will be set by caller
            interaction_type=InteractionType.CHOOSE_OPTION,
            data=option_data.model_dump(),  # Convert to dict for JSON serialization
            can_cancel=is_optional,
            execution_results=execution_results,  # Attach execution context
        )

        logger.debug(
            f"Created TYPE-SAFE choice selection request: {len(choices)} choices, optional: {is_optional}"
        )

        return request

    @staticmethod
    def create_choice_selection_request_with_options(
        options: list[dict[str, Any]],
        message: str,
        is_optional: bool = False,
        source_player: str | None = None,
        execution_results: list[str] | None = None,
    ) -> DogmaInteractionRequest:
        """Create a type-safe standardized choice selection interaction request with full option objects.

        Args:
            options: List of option objects with description and value fields
            message: Message to display to the player
            is_optional: Whether the choice can be declined
            source_player: Player who triggered the interaction
            execution_results: Recent execution context to show player what just happened

        Returns:
            Type-safe DogmaInteractionRequest ready for WebSocket transmission

        Raises:
            ValidationError: If the request data is invalid
            ValueError: If input parameters are invalid
        """
        if not options:
            raise ValueError("options cannot be empty")

        # Validate that each option has required fields
        for i, option in enumerate(options):
            if not isinstance(option, dict):
                raise ValueError(f"Option {i} must be a dictionary")
            if "description" not in option:
                raise ValueError(f"Option {i} missing required 'description' field")
            if "value" not in option:
                raise ValueError(f"Option {i} missing required 'value' field")

        # Convert to structured option format {label, value} for frontend
        structured_options = [
            {"label": option["description"], "value": option["value"]} for option in options
        ]

        # Create OptionSelectionData with type safety
        option_data = OptionSelectionData(
            type="choose_option",
            message=message,
            source_player=source_player or "current_player",
            options=structured_options,  # Structured objects with label/value
            allow_cancel=is_optional,
            default_option=None,  # Could be enhanced later
        )

        # Create the complete DogmaInteractionRequest
        request = DogmaInteractionRequest(
            type="dogma_interaction",
            game_id="",  # Will be set by caller
            player_id="",  # Will be set by caller
            interaction_type=InteractionType.CHOOSE_OPTION,
            data=option_data.model_dump(),  # Convert to dict for JSON serialization
            can_cancel=is_optional,
            execution_results=execution_results,  # Attach execution context
        )

        logger.debug(
            f"Created TYPE-SAFE choice selection request with full options: {len(options)} choices, optional: {is_optional}"
        )

        return request

    @staticmethod
    def create_achievement_selection_request(
        eligible_achievements: list[dict[str, Any]],
        message: str,
        is_optional: bool = False,
        store_result: str = "selected_achievements",
        execution_results: list[str] | None = None,
    ) -> DogmaInteractionRequest:
        """Create a type-safe standardized achievement selection interaction request.

        Args:
            eligible_achievements: List of achievement data that can be selected
            message: Message to display to the player
            is_optional: Whether the selection can be declined
            store_result: Variable name to store the selected achievements in
            execution_results: Recent execution context to show player what just happened

        Returns:
            Type-safe DogmaInteractionRequest ready for WebSocket transmission

        Raises:
            ValidationError: If the request data is invalid
            ValueError: If input parameters are invalid
        """
        if not eligible_achievements:
            raise ValueError("eligible_achievements cannot be empty")

        # Create AchievementSelectionData with type safety
        achievement_data = AchievementSelectionData(
            type="select_achievement",
            message=message,
            source_player="current_player",
            eligible_achievements=eligible_achievements,
            is_optional=is_optional,
            store_result=store_result,
        )

        # Create the complete DogmaInteractionRequest
        request = DogmaInteractionRequest(
            type="dogma_interaction",
            game_id="",  # Will be set by caller
            player_id="",  # Will be set by caller
            interaction_type=InteractionType.SELECT_ACHIEVEMENT,
            data=achievement_data.model_dump(),  # Convert to dict for JSON serialization
            can_cancel=is_optional,
            execution_results=execution_results,  # Attach execution context
        )

        logger.info(
            f"🎯 Created achievement selection request: {len(eligible_achievements)} eligible achievements, store_result={store_result}"
        )
        logger.info(
            f"🎯 Request data keys: {list(achievement_data.model_dump().keys())}"
        )
        logger.info(f"🎯 Full request data: {achievement_data.model_dump()}")

        return request

    @staticmethod
    def create_color_selection_request(
        available_colors: list[str],
        message: str = "Select a color",
        is_optional: bool = False,
        source_player: str = "current_player",
        execution_results: Optional[list[str]] = None,
        context: Optional["ActionContext"] = None,
    ) -> DogmaInteractionRequest:
        """
        Create a color selection interaction request.

        Args:
            available_colors: List of available colors to select from
            message: Message to display to the player
            is_optional: Whether the selection is optional
            source_player: Player who triggered the interaction
            execution_results: Recent execution results for context
            context: Action context for eligibility metadata (Phase 1A)

        Returns:
            DogmaInteractionRequest with ColorSelectionData
        """
        from schemas.interaction_data import ColorSelectionData

        # Create color selection data
        color_data = ColorSelectionData(
            type="select_color",
            available_colors=available_colors,
            is_optional=is_optional,
            message=message,
            source_player=source_player,
            execution_results=execution_results or [],
        )

        # Create interaction request using DogmaInteractionRequest pattern
        request = DogmaInteractionRequest(
            type="dogma_interaction",
            game_id="",  # Will be set by caller
            player_id="",  # Will be set by caller
            interaction_type=InteractionType.SELECT_COLOR,
            data=color_data.model_dump(),  # Convert Pydantic model to dict
            can_cancel=is_optional,
            execution_results=execution_results,
        )

        return request

    @staticmethod
    def create_card_ordering_request(
        cards_to_order: list[Card],
        message: str,
        instruction: str,
        source_player: str = "current_player",
        execution_results: Optional[list[str]] = None,
    ) -> DogmaInteractionRequest:
        """
        Create a card ordering interaction request (Cities expansion: Search icon).

        Args:
            cards_to_order: List of cards that need to be ordered
            message: Message to display to the player
            instruction: Specific instruction (e.g., "Order cards to return to deck bottom")
            source_player: Player who triggered the interaction
            execution_results: Recent execution results for context

        Returns:
            DogmaInteractionRequest with CardOrderingData
        """
        from schemas.interaction_data import CardOrderingData

        # Convert Card objects to dicts with required fields
        cards_data = []
        for card in cards_to_order:
            card_dict = {
                "card_id": card.card_id if card.card_id is not None else card.name,
                "name": card.name,
                "age": card.age,
                "color": card.color.value if hasattr(card.color, "value") else str(card.color),
            }
            cards_data.append(card_dict)

        # Create card ordering data
        ordering_data = CardOrderingData(
            type="order_cards",
            cards_to_order=cards_data,
            instruction=instruction,
            message=message,
            source_player=source_player,
        )

        # Create interaction request
        request = DogmaInteractionRequest(
            type="dogma_interaction",
            game_id="",  # Will be set by caller
            player_id="",  # Will be set by caller
            interaction_type=InteractionType.ORDER_CARDS,
            data=ordering_data.model_dump(),  # Convert Pydantic model to dict
            can_cancel=False,  # Card ordering is mandatory for Search icon
            execution_results=execution_results,
        )

        logger.info(
            f"Created card ordering request: {len(cards_to_order)} cards to order"
        )

        return request

    @staticmethod
    def validate_interaction_request(
        request: Union[DogmaInteractionRequest, dict[str, Any]],
    ) -> tuple[bool, Optional[str]]:
        """Validate that a DogmaInteractionRequest is properly structured.

        This method handles both Pydantic DogmaInteractionRequest objects and their
        dictionary representations for backward compatibility.

        Args:
            request: Either a DogmaInteractionRequest object or its dictionary representation

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Handle both Pydantic objects and dictionaries
            if isinstance(request, DogmaInteractionRequest):
                # Convert to dict for uniform processing
                request_dict = request.model_dump()
            elif isinstance(request, dict):
                request_dict = request
            else:
                return (
                    False,
                    f"request must be a DogmaInteractionRequest or dictionary, got {type(request)}",
                )

            # Validate required top-level fields
            if "type" not in request_dict:
                return False, "request missing 'type' field"

            if "data" not in request_dict:
                return False, "request missing 'data' field"

            # Validate the data field contains expected structure
            if not isinstance(request_dict["data"], dict):
                return False, "request.data must be a dictionary"

            # Validate based on interaction type
            data = request_dict["data"]
            interaction_type = data.get("type")

            if interaction_type == "select_cards":
                if "eligible_cards" not in data:
                    return (
                        False,
                        "Card selection request missing 'eligible_cards' field",
                    )
                if not isinstance(data["eligible_cards"], list):
                    return False, "eligible_cards must be a list"
                if "min_count" not in data or "max_count" not in data:
                    return (
                        False,
                        "Card selection request missing min_count or max_count",
                    )

            elif interaction_type == "choose_option":
                if "options" not in data:
                    return False, "Choice selection request missing 'options' field"
                if not isinstance(data["options"], list):
                    return False, "options must be a list"

            elif interaction_type == "select_achievement":
                if "eligible_achievements" not in data:
                    return (
                        False,
                        "Achievement selection request missing 'eligible_achievements' field",
                    )
                if not isinstance(data["eligible_achievements"], list):
                    return False, "eligible_achievements must be a list"

            elif interaction_type == "order_cards":
                if "cards_to_order" not in data:
                    return (
                        False,
                        "Card ordering request missing 'cards_to_order' field",
                    )
                if not isinstance(data["cards_to_order"], list):
                    return False, "cards_to_order must be a list"
                if len(data["cards_to_order"]) == 0:
                    return False, "cards_to_order cannot be empty"

            else:
                return False, f"Unknown interaction type: {interaction_type}"

            return True, None

        except Exception as e:
            return False, f"Validation error: {e!s}"

    @staticmethod
    def _get_clickable_locations(
        eligible_cards: list[Card], source_player: str, context: "ActionContext"
    ) -> list[str]:
        """Calculate which card locations should be clickable.

        Phase 1A: This provides explicit UI hints to the frontend about which
        card locations contain eligible cards, eliminating the need for frontend
        to iterate and check each location.

        Args:
            eligible_cards: List of eligible cards to check locations for
            source_player: Which player's cards to check. Valid values:
                - "current_player" or "self": Current player's locations
                - "opponent": Opponent's locations (2-player assumption, see TODO below)
                - "all": Current player's locations (limitation - should check all players)
                - <player_id>: Specific player's locations
            context: ActionContext with game state and player references

        Returns:
            List of clickable locations like ["hand", "board.blue_cards", "score_pile"].
            Returns empty list in these edge cases:
            - eligible_cards is empty (no cards to check)
            - source_player is a player ID that doesn't exist in the game
            - source_player is "opponent" but no opponents exist
            - No eligible cards are found in any location (all cards filtered out)

            For source_player="all", currently only checks current player's cards.
            This is a known limitation - see implementation for details.

        Performance:
            O(n+m) where n is total cards across all locations and m is eligible_cards.
            Uses card_id mapping for O(1) lookups instead of O(n*m) nested loops.

        Edge Cases:
            - If source_player="opponent" with 3+ opponents, uses first opponent only
              and logs a warning. In practice, demand effects should set context.player
              to the specific opponent, so this should rarely occur.
            - If source_player="all", only current player's locations are returned.
              This is a known limitation that should be addressed for multi-player effects.
        """
        locations = set()

        # Determine which player we're checking
        if source_player in ["self", "current_player"]:
            player = context.player
        elif source_player == "opponent":
            # TODO: "opponent" is ambiguous in 3+ player games
            # In practice, demand effects should set context.player to the specific opponent,
            # so source_player should be a specific player ID by the time we get here.
            # This fallback handles 2-player games correctly but may be wrong for 3+ players.
            opponents = [p for p in context.game.players if p.id != context.player.id]
            if not opponents:
                return []
            if len(opponents) > 1:
                logger.warning(
                    f"Phase 1A: source_player='opponent' is ambiguous with {len(opponents)} opponents. "
                    f"Using first opponent. Consider passing specific player ID instead."
                )
            player = opponents[0]  # Take first opponent (2-player assumption)
        elif source_player == "all":
            # For "all", we'd need to check all players - for now just use current
            player = context.player
        else:
            # Specific player ID
            player_obj = next(
                (p for p in context.game.players if p.id == source_player), None
            )
            if not player_obj:
                return []
            player = player_obj

        # Build O(n) card_id → location mapping for efficient lookups
        # This avoids O(n*m) nested loops when checking eligible cards
        card_locations = {}

        # Map hand cards
        for card in player.hand:
            card_locations[card.card_id] = "hand"

        # Map board cards
        for color in ["blue", "red", "green", "purple", "yellow"]:
            stack = getattr(player.board, f"{color}_cards", [])
            for card in stack:
                card_locations[card.card_id] = f"board.{color}_cards"

        # Map score pile cards
        for card in player.score_pile:
            card_locations[card.card_id] = "score_pile"

        # O(1) lookups for eligible cards
        for card in eligible_cards:
            if card.card_id in card_locations:
                locations.add(card_locations[card.card_id])

        return sorted(locations)

    @staticmethod
    def _get_clickable_players(
        source_player: str, context: "ActionContext"
    ) -> list[str]:
        """Calculate which player boards should be clickable.

        Phase 1A: This provides explicit UI hints about which player boards
        should show clickable cards, eliminating complex frontend logic.

        Args:
            source_player: Which player's boards to make clickable. Valid values:
                - "current_player" or "self": Current player only
                - "opponent": All opponents (proper multi-player support)
                - "all": All players in the game
                - <player_id>: Specific player by ID
            context: ActionContext with game state and player references

        Returns:
            List of player IDs (UUIDs) whose boards should be clickable.
            Returns empty list in these edge cases:
            - source_player is "opponent" but game has no opponents (single player)
            - source_player is "all" but game has no players (should never happen)

            For source_player="opponent", returns ALL opponents, not just the first.
            This properly handles 3+ player games unlike _get_clickable_locations.

        Examples:
            - source_player="current_player" → ["player-uuid-123"]
            - source_player="opponent" → ["player-uuid-456", "player-uuid-789"]
            - source_player="all" → ["player-uuid-123", "player-uuid-456", "player-uuid-789"]
            - source_player="player-uuid-456" → ["player-uuid-456"]
        """
        if source_player in ["self", "current_player"]:
            return [context.player.id]
        elif source_player == "opponent":
            # Return all opponents
            return [p.id for p in context.game.players if p.id != context.player.id]
        elif source_player == "all":
            return [p.id for p in context.game.players]
        else:
            # Specific player ID
            return [source_player]

    @staticmethod
    def create_auto_resume_interaction(
        player_id: str,
        message: str
    ):
        """
        Create a dummy interaction request for auto-resume (UI refresh without user input).
        
        This is used by RepeatAction to suspend execution after each revealed draw,
        allowing the UI to refresh and show the newly drawn card, then automatically
        resuming to continue with the next iteration.
        
        Args:
            player_id: The player ID (for routing)
            message: Progress message to display
            
        Returns:
            InteractionRequest with auto_resume flag set
        """
        from models.interaction_request import InteractionRequest
        
        return InteractionRequest(
            interaction_type="auto_resume",
            player_id=player_id,
            data={
                "message": message,
                "auto_resume": True
            },
            message=message
        )
