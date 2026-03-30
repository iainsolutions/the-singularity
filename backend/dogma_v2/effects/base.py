"""
Effect abstraction layer for Dogma v2.

This module provides the clean interface between phases and action primitives,
implementing the ActionPrimitiveAdapter pattern specified in DOGMA_TECHNICAL_SPECIFICATION.md.

The Effect abstraction ensures:
1. Phases never directly import or know about action primitives
2. Internal signals from primitives never leak into phase logic
3. All primitive interactions go through a clean, well-defined interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..core.context import DogmaContext


class EffectType(Enum):
    """Types of effects that require special handling"""

    STANDARD = "standard"
    DEMAND = "demand"
    INTERACTION = "interaction"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    TRANSFER = "transfer"
    BOARD = "board"
    CALCULATION = "calculation"
    ACHIEVEMENT = "achievement"


@dataclass
class EffectResult:
    """
    Clean result interface for effects.

    This is what phases see - no internal signals or primitive details.
    """

    success: bool
    requires_interaction: bool = False
    interaction_request: dict[str, Any] | None = None
    routes_to_demand: bool = False
    demand_config: dict[str, Any] | None = None
    variables: dict[str, Any] = None
    results: list[str] = None
    error: str | None = None

    def __post_init__(self):
        if self.variables is None:
            self.variables = {}
        if self.results is None:
            self.results = []

        # Validate routing flags are mutually exclusive
        if self.requires_interaction and self.routes_to_demand:
            raise ValueError(
                "EffectResult cannot have both requires_interaction=True and routes_to_demand=True. "
                "Effects must route to either interaction or demand, not both."
            )


class Effect(ABC):
    """
    Abstract base class for all effects.

    This is the only interface that phases should interact with.
    All action primitive details are hidden behind this abstraction.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the effect.

        Args:
            config: Effect configuration from card JSON
        """
        self.config = config
        self.type = self._determine_type()

    def _determine_type(self) -> EffectType:
        """Determine the effect type from configuration"""
        effect_type_str = self.config.get("type", "")

        if effect_type_str == "DemandEffect":
            return EffectType.DEMAND
        elif effect_type_str in ["SelectCards", "SelectAchievement", "ChooseOption"]:
            return EffectType.INTERACTION
        elif effect_type_str == "ConditionalAction":
            return EffectType.CONDITIONAL
        elif effect_type_str in ["LoopAction", "RepeatAction"]:
            return EffectType.LOOP
        else:
            return EffectType.STANDARD

    @abstractmethod
    def execute(self, context: DogmaContext) -> EffectResult:
        """
        Execute the effect.

        Args:
            context: The dogma execution context

        Returns:
            EffectResult with clean interface (no internal signals)
        """
        pass

    @abstractmethod
    def validate(self) -> tuple[bool, str | None]:
        """
        Validate the effect configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        pass

    def get_description(self) -> str:
        """Get human-readable description of the effect"""
        if "description" in self.config:
            return self.config["description"]

        # Generate a better fallback based on effect type
        effect_type = self.config.get("type", "action")

        # Create more descriptive fallback messages
        if effect_type == "DemandEffect":
            symbol = self.config.get("symbol_requirement", "symbol")
            return f"Demand effect requiring {symbol}"
        elif effect_type == "SelectCards":
            count = self.config.get("selection_count", 1)
            source = self.config.get("selection_source", "cards")
            return f"Select {count} card{'s' if count != 1 else ''} from {source}"
        elif effect_type == "DrawCards":
            age = self.config.get("age", "?")
            count = self.config.get("count", 1)
            return f"Draw {count} age {age} card{'s' if count != 1 else ''}"
        elif effect_type == "MeldCard":
            return "Meld a card to your board"
        elif effect_type == "ScoreCards":
            return "Score cards to your score pile"
        else:
            return f"{effect_type} effect"
