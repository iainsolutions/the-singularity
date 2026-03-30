"""
DogmaExecutionResult - Consolidated result model for dogma execution
"""


from .core.context import DogmaContext
from .core.transaction import DogmaTransaction
from .interaction_request import InteractionRequest


class DogmaExecutionResult:
    """Result of dogma execution with comprehensive execution information.

    This class encapsulates all information about a dogma execution, including
    success status, game state changes, player interactions, and detailed
    activity summaries for logging and display purposes.

    Attributes:
        success: True if the dogma executed successfully.
        context: Final execution context containing game state and variables.
                 May be None in error cases if game/player/card objects unavailable.
        transaction: Transaction record with phase execution history.
        error: Error message if execution failed, None otherwise.
        interaction_required: True if player interaction is needed to continue.
        interaction_request: Unified interaction request for all interaction types.
        interaction_type: Type of interaction ("demand", "sharing", or "player").
        anyone_shared: True if any players participated in sharing effects.
        demand_transferred_count: Number of cards transferred via demand effects.
        sharing_players: List of players who participated in sharing.
        results: List of human-readable action results.

    Example:
        >>> result = executor.execute_dogma(game, player, card)
        >>> if result.success:
        ...     print(f"Success: {result.get_activity_summary()}")
        >>> else:
        ...     print(f"Failed: {result.error}")
    """

    def __init__(
        self,
        success: bool,
        context: DogmaContext | None,
        transaction: DogmaTransaction,
        error: str | None = None,
        interaction_required: bool = False,
        interaction_request: InteractionRequest | None = None,
        interaction_type: str | None = None,  # "demand", "sharing", or "player"
    ):
        self.success = success
        self.context = context
        self.transaction = transaction
        self.error = error
        self.interaction_required = interaction_required

        # Unified interaction fields
        self.interaction_request = interaction_request
        self.interaction_type = interaction_type

        # Summary information extracted from context (handle None context for error cases)
        if context is not None:
            self.anyone_shared = context.get_variable("anyone_shared", False)
            self.demand_transferred_count = context.get_variable(
                "demand_transferred_count", 0
            )
            self.sharing_players = context.get_variable("sharing_players", [])
            self.results = list(context.results)
            self.updated_game = context.game
        else:
            # Context is None - error case with no game/player/card available
            self.anyone_shared = False
            self.demand_transferred_count = 0
            self.sharing_players = []
            self.results = []
            self.updated_game = None

        # Legacy compatibility properties
        self.requires_interaction = interaction_required
        self.is_complete = success and not interaction_required
        self.interaction = interaction_request
        self.transaction_id = transaction.id if transaction else None

    def get_activity_summary(self) -> str:
        """Generate human-readable summary of dogma execution activity.

        Creates a concise summary describing what occurred during dogma execution,
        including sharing participation, demand transfers, and any errors.

        Returns:
            Formatted string summarizing the dogma execution activity.

        Example:
            >>> result.get_activity_summary()
            'Executed Sailing dogma (2 sharing players) (sharing effects applied)'
        """
        parts = []

        if self.success:
            card_name = self.context.card.name if self.context else "unknown card"
            parts.append(f"Executed {card_name} dogma")
            if self.sharing_players:
                parts.append(f"({len(self.sharing_players)} sharing players)")
            if self.anyone_shared:
                parts.append("(sharing effects applied)")
            if self.demand_transferred_count > 0:
                parts.append(
                    f"({self.demand_transferred_count} cards transferred from demands)"
                )
        else:
            card_name = self.context.card.name if self.context else "unknown card"
            parts.append(f"Failed to execute {card_name} dogma")
            if self.error:
                parts.append(f"({self.error})")

        return " ".join(parts)

    @staticmethod
    def success_complete(
        results: list[str], context: DogmaContext, transaction: DogmaTransaction
    ) -> "DogmaExecutionResult":
        """Create a successful completion result"""
        return DogmaExecutionResult(
            success=True,
            context=context,
            transaction=transaction,
        )

    @staticmethod
    def needs_interaction(
        interaction: InteractionRequest,
        context: DogmaContext,
        transaction: DogmaTransaction,
        interaction_type: str = "player",
    ) -> "DogmaExecutionResult":
        """Create a result requiring player interaction"""
        return DogmaExecutionResult(
            success=True,
            context=context,
            transaction=transaction,
            interaction_required=True,
            interaction_request=interaction,
            interaction_type=interaction_type,
        )

    @staticmethod
    def error(
        message: str, context: DogmaContext, transaction: DogmaTransaction
    ) -> "DogmaExecutionResult":
        """Create an error result"""
        return DogmaExecutionResult(
            success=False,
            context=context,
            transaction=transaction,
            error=message,
        )
