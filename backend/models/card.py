from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .special_icon import SpecialIcon


# Forward declaration to avoid circular import
# Actual import happens in methods that need it
TYPE_CHECKING = False
if TYPE_CHECKING:
    from .figures.karma import KarmaEffect, KarmaType


class Symbol(str, Enum):
    CASTLE = "castle"
    LEAF = "leaf"
    LIGHTBULB = "lightbulb"
    CROWN = "crown"
    FACTORY = "factory"
    CLOCK = "clock"
    HEX = "hex"  # Figures expansion - hex icon for Auspice mechanic


class CardColor(str, Enum):
    BLUE = "blue"
    RED = "red"
    GREEN = "green"
    YELLOW = "yellow"
    PURPLE = "purple"


class CardImageLocation(str, Enum):
    """Position of hexagonal card image on card (for Artifacts dig event matching)"""

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    CENTER_LEFT = "center_left"
    CENTER = "center"
    CENTER_RIGHT = "center_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


class DogmaEffect(BaseModel):
    text: str
    is_demand: bool = False
    is_optional: bool = False
    symbol_count: int = 1  # Number of symbols needed to activate
    actions: list[dict[str, Any]] = Field(default_factory=list)
    selection_condition: dict[str, Any] | None = None  # For multi-effect cards

    def is_compel(self) -> bool:
        """Check if this is a Compel effect (Artifacts expansion)"""
        # Compel effects are demand effects with "I COMPEL" in text
        # Check both the action metadata and the text
        if not self.is_demand:
            return False

        # Check text for "I COMPEL" indicator
        if "I COMPEL" in self.text.upper():
            return True

        # Also check action metadata for is_compel flag (future-proofing)
        if self.actions and self.actions[0].get("is_compel", False):
            return True

        return False


class EchoEffect(BaseModel):
    """Echo effect for Echoes expansion cards.

    Echo effects execute before dogma effects and are always shared (non-demand).
    They appear in icon spaces and execute bottom-to-top when multiple are visible.
    """
    description: str
    actions: list[dict[str, Any]] = Field(default_factory=list)


class Card(BaseModel):
    name: str
    age: int
    color: CardColor
    card_id: str | None = None  # Card identifier (e.g., "B 001" for Base card 1)
    dogma_resource: Symbol | None = None
    symbols: list[Symbol | str]  # Symbol enum for base game, strings for expansion hex symbols

    # Base game cards have dogma_effects, city cards have special_icons
    dogma_effects: list[DogmaEffect] = Field(default_factory=list)
    special_icons: list[SpecialIcon] = Field(default_factory=list)

    # Positional symbol data for proper splaying/UI display
    # Supports both Symbol enum (base game) and strings (expansion hex symbols like "hex-city")
    symbol_positions: list[Symbol | str | None] = Field(
        default_factory=lambda: [None, None, None, None]
    )

    # Special properties
    is_achievement: bool = False
    achievement_requirement: str | None = None

    # Expansion tracking - which expansion this card belongs to
    # "base" for base game cards, "cities", "artifacts", "echoes", "figures", "unseen" for expansions
    expansion: str = "base"

    # Visibility tracking - cards are revealed when drawn to reveal location
    # or when explicitly revealed by card effects. Revealed cards are visible
    # to all players in logs and UI
    is_revealed: bool = False

    # Unseen expansion: Safeguard keyword
    # Safeguard reserves achievements for exclusive claiming by the card's owner
    # Format: {"type": "age", "value": 4} for Age 4 achievement
    #         {"type": "score", "value": 15} for 15-point achievement
    #         {"type": "special", "value": "world"} for special achievements
    # Active when card is in Safe OR visible on board
    safeguard: dict[str, Any] | None = None

    # Artifacts expansion fields
    card_image_location: CardImageLocation | None = None  # For dig event matching
    has_compel_effects: bool = False  # Quick lookup for Compel effects
    special_value: int | None = None  # For cards like Battleship Yamato (value 11)

    def __str__(self):
        return f"{self.name} (Age {self.age})"

    def get_symbol_count(self, symbol: Symbol) -> int:
        """Count symbols, preferring symbol_positions over symbols field.

        For Cities expansion cards with Search icons, the search icon also counts
        as its target symbol (dual counting for dogma sharing/demands).
        """
        count = 0

        if hasattr(self, "symbol_positions") and any(self.symbol_positions):
            # Count from symbol_positions (the canonical source for Innovation)
            count = sum(
                1 for pos_symbol in self.symbol_positions if pos_symbol == symbol
            )
        else:
            # Fallback to symbols field for cards without positions
            count = self.symbols.count(symbol)

        # Cities expansion: Search icons count as their target symbol
        # This allows Search-Crown to count as a crown for sharing/demands
        for icon in self.special_icons:
            if icon.type == "search":
                target_icon = icon.parameters.get("target_icon")
                if target_icon == symbol.value:
                    count += 1

        return count

    def has_symbol(self, symbol: Symbol) -> bool:
        """Check if this card has a given symbol.

        For Cities expansion cards with Search icons, the search icon also counts
        as having its target symbol (dual counting for dogma sharing/demands).
        """
        # Check regular symbols
        if symbol in self.symbols:
            return True

        # Cities expansion: Search icons count as their target symbol
        for icon in self.special_icons:
            if icon.type == "search":
                target_icon = icon.parameters.get("target_icon")
                if target_icon == symbol.value:
                    return True

        return False

    def is_city(self) -> bool:
        """Check if this is a city card (Cities expansion).

        City cards are identified by having expansion="cities" and having
        special_icons instead of dogma_effects.
        """
        return self.expansion == "cities" and len(self.special_icons) > 0

    def is_artifact(self) -> bool:
        """Check if this is an artifact card (Artifacts expansion)"""
        return self.expansion == "artifacts"

    def is_compel(self) -> bool:
        """Check if this card has any Compel effects (Artifacts expansion)"""
        return any(eff.is_compel() for eff in self.dogma_effects)

    def get_compel_effects(self) -> list[DogmaEffect]:
        """Get all Compel effects (Artifacts expansion)"""
        return [eff for eff in self.dogma_effects if eff.is_compel()]

    def get_display_age(self) -> int:
        """Get display age (special_value overrides age if present)"""
        return self.special_value if self.special_value else self.age

    def has_dogma(self) -> bool:
        """Check if this card can be selected for Dogma action.

        City cards cannot be dogma'd because they have no dogma effects.
        """
        return not self.is_city() and len(self.dogma_effects) > 0

    def get_immediate_icons(self) -> list[SpecialIcon]:
        """Get immediate effect icons that trigger when this city is melded.

        Returns icons sorted by position (top icon executes first, then bottom).
        """
        immediate = [icon for icon in self.special_icons if icon.is_immediate()]
        return sorted(immediate, key=lambda x: x.position)

    def get_constant_icons(self) -> list[SpecialIcon]:
        """Get constant effect icons that are active while this city is visible.

        Constant icons include Flag (conditional achievement) and Fountain
        (unconditional achievement).
        """
        return [icon for icon in self.special_icons if icon.is_constant()]

    def has_safeguard(self) -> bool:
        """Check if this card has Safeguard keyword (Unseen expansion)"""
        return self.safeguard is not None

    def get_safeguard_achievement_ids(self) -> list[str]:
        """
        Get achievement IDs that this card Safeguards.

        Returns:
            List of achievement IDs (e.g., ["age_4"] for Safeguard 4)
        """
        if not self.safeguard:
            return []

        safeguard_type = self.safeguard.get("type")
        safeguard_value = self.safeguard.get("value")

        if safeguard_type == "age":
            return [f"age_{safeguard_value}"]
        elif safeguard_type == "score":
            return [f"score_{safeguard_value}"]
        elif safeguard_type == "special":
            return [f"special_{safeguard_value}"]

        return []

    def to_dict(self):
        return {
            "card_id": self.card_id,
            "name": self.name,
            "age": self.age,
            "color": self.color.value,
            "dogma_resource": (
                self.dogma_resource.value if self.dogma_resource else None
            ),
            "symbols": [s.value if isinstance(s, Symbol) else s for s in self.symbols],
            "symbol_positions": [
                s.value if isinstance(s, Symbol) else s for s in self.symbol_positions
            ],
            "dogma_effects": [
                {
                    "text": effect.text,
                    "is_demand": effect.is_demand,
                    "is_optional": effect.is_optional,
                    "symbol_count": effect.symbol_count,
                    "actions": effect.actions,
                    "selection_condition": effect.selection_condition,
                }
                for effect in self.dogma_effects
            ],
            "is_achievement": self.is_achievement,
            "achievement_requirement": self.achievement_requirement,
            "expansion": self.expansion,
            "is_revealed": self.is_revealed,
            "special_icons": [icon.to_dict() for icon in self.special_icons],
            "safeguard": self.safeguard,
            # Artifacts expansion fields
            "card_image_location": (
                self.card_image_location.value if self.card_image_location else None
            ),
            "has_compel_effects": self.has_compel_effects,
            "special_value": self.special_value,
        }
