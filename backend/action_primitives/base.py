"""
Base classes for action primitives.
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from models.card import Card
    from models.game import Game
    from models.player import Player

logger = logging.getLogger(__name__)


class ActionResult(Enum):
    """Result of an action primitive execution."""

    SUCCESS = "success"
    FAILURE = "failure"
    REQUIRES_INTERACTION = "requires_interaction"
    CONDITION_NOT_MET = "condition_not_met"
    SKIPPED = "skipped"


class ActionContext:
    """
    Context for executing action primitives.
    Maintains state across action execution.
    """

    def __init__(
        self,
        game: "Game",
        player: "Player",
        card: Optional["Card"] = None,
        variables: dict[str, Any] | None = None,
        results: list[str] | None = None,
        state_tracker: Any = None,
        sharing: Any = None,  # Add sharing context parameter
    ):
        self.game = game
        self.player = player
        self.card = card
        self.variables = variables if variables is not None else {}
        self.results = results if results is not None else []
        self.demanding_player: Player | None = None  # For demand effects
        self.target_player: Player | None = None  # For targeted effects
        self.sharing = sharing  # Store sharing context

        # Use provided state tracker or create dummy for standalone tests
        if state_tracker is not None:
            self.state_tracker = state_tracker
        else:
            # Create dummy tracker for standalone primitive testing
            try:
                from dogma_v2.state_tracker import StateChangeTracker

                self.state_tracker = StateChangeTracker()
            except ImportError:
                # Fallback if state_tracker not available
                class DummyTracker:
                    def __getattr__(self, name):
                        return lambda *args, **kwargs: None

                # Fallback when state_tracker unavailable
                self.state_tracker = DummyTracker()

    def set_variable(self, name: str, value: Any) -> None:
        """Store a variable in the context."""
        self.variables[name] = value
        logger.debug(f"Set variable {name} = {value}")

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Retrieve a variable from the context."""
        return self.variables.get(name, default)

    def has_variable(self, name: str) -> bool:
        """Check if a variable exists in the context."""
        return name in self.variables

    def remove_variable(self, name: str) -> None:
        """Remove a variable from the context if it exists."""
        self.variables.pop(name, None)
        logger.debug(f"Removed variable {name}")

    def update_variables(self, variables: dict[str, Any]) -> None:
        """Update multiple variables in the context at once.

        Validates against reserved variable names to prevent cross-contamination.
        Reserved patterns:
        - *_choice: Primitive-specific resume variables (e.g., chosen_option_choice)
        - final_interaction_request: Interaction system variable
        - pending_*: Pending state variables
        """
        # Define reserved variable patterns
        RESERVED_PATTERNS = [
            ("_choice", "Resume variables should only be set by ResumeManager"),
            (
                "final_interaction_request",
                "Interaction request should be set by primitives directly",
            ),
            ("pending_", "Pending state should be set by primitives directly"),
        ]

        # Validate variables before updating
        warnings = []
        for var_name in variables:
            for pattern, reason in RESERVED_PATTERNS:
                if (pattern.startswith("_") and var_name.endswith(pattern)) or (
                    not pattern.startswith("_") and pattern in var_name
                ):
                    warnings.append(
                        f"Warning: Updating reserved variable '{var_name}' via bulk update. {reason}"
                    )
                    break

        # Log all warnings
        for warning in warnings:
            logger.warning(warning)

        # Proceed with update
        self.variables.update(variables)
        logger.debug(f"Updated {len(variables)} variables")

    def add_result(self, message: str) -> None:
        """Add a result message."""
        self.results.append(message)
        logger.info(f"Action result: {message}")

    def get_results(self) -> list[str]:
        """Get all result messages."""
        return self.results.copy()

    def clear_results(self) -> None:
        """Clear all result messages."""
        self.results.clear()

    def copy(self) -> "ActionContext":
        """Create a copy of this context."""
        return ActionContext(
            game=self.game,
            player=self.player,
            card=self.card,
            variables=self.variables.copy(),
            results=self.results.copy(),
            state_tracker=self.state_tracker,
        )

    def get_private_card_name(self, card: "Card") -> str:
        """Get a private representation of a card (age only unless revealed)."""
        if card:
            # If card is revealed, show full name even in private context
            if getattr(card, "is_revealed", False):
                return f"{card.name} (age {card.age})"
            return f"age {card.age} card"
        return "a card"

    def get_public_card_name(self, card: "Card") -> str:
        """Get a public representation of a card (full name)."""
        if card:
            return f"{card.name} (age {card.age})"
        return "a card"

    def get_card_name_for_log(self, card: "Card", is_owner: bool = False) -> str:
        """
        Get appropriate card name for activity log.

        Args:
            card: The card to describe
            is_owner: True if the current player owns the card

        Returns:
            Card name (full if revealed/public, age-only if private)
        """
        if not card:
            return "a card"

        # Cards on board, in score pile, or revealed are always public
        if getattr(card, "is_revealed", False):
            return f"{card.name} (age {card.age})"

        # If owner is viewing their own card, show full name
        if is_owner:
            return f"{card.name} (age {card.age})"

        # Otherwise show only age
        return f"age {card.age} card"

    def add_detailed_log(self, message: str) -> None:
        """Add a detailed log message (alias for add_result)."""
        self.add_result(message)


class ActionPrimitive(ABC):
    """
    Base class for all action primitives.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the action primitive.

        Args:
            config: Configuration parameters for the action
        """
        self.config = config if config is not None else {}

    @abstractmethod
    def execute(self, context: ActionContext) -> ActionResult:
        """
        Execute the action primitive.

        Args:
            context: Execution context

        Returns:
            Result of the execution
        """
        pass

    def validate_config(self) -> bool:
        """
        Validate the configuration.
        Override in subclasses for specific validation.

        Returns:
            True if configuration is valid
        """
        return True

    def get_required_fields(self) -> list[str]:
        """
        Get list of required configuration fields.
        Override in subclasses.

        Returns:
            List of required field names
        """
        return []

    def get_optional_fields(self) -> list[str]:
        """
        Get list of optional configuration fields.
        Override in subclasses.

        Returns:
            List of optional field names
        """
        return []
