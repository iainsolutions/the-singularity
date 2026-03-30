"""Special icon model for Cities of Destiny expansion.

Special icons are unique to city cards and provide either immediate effects
(triggered when the city is melded) or constant effects (active while visible).
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SpecialIconType(str, Enum):
    """Types of special icons on city cards.

    Immediate effects trigger when the city is melded (in position order).
    Constant effects are active while the city is visible on the board.
    """

    # Immediate effects (trigger on meld)
    SEARCH = "search"  # Reveal X cards of Age X, take matching icons
    PLUS = "plus"  # Draw card of age+1
    ARROW = "arrow"  # Splay city's color in direction
    JUNK = "junk"  # Junk available achievement = city age
    UPLIFT = "uplift"  # Junk deck age+1, draw age+2
    UNSPLAY = "unsplay"  # Unsplay city's color on all opponents

    # Constant effects (active while visible)
    FLAG = "flag"  # Achievement if >= visible cards of color than opponents
    FOUNTAIN = "fountain"  # Unconditional achievement


class SpecialIconCategory(str, Enum):
    """Categories of special icons for execution logic."""

    IMMEDIATE = "immediate"  # Triggers on meld
    CONSTANT = "constant"  # Active while visible


class SpecialIcon(BaseModel):
    """Represents a special icon on a city card.

    Each city card can have up to 2 special icons. If both are immediate effects,
    they execute in position order (top icon first, then bottom).

    Attributes:
        type: The type of special icon (search, plus, arrow, etc.)
        position: Icon position on card (0=top slot, 1=bottom slot)
        parameters: Icon-specific parameters (e.g., target_icon for search)
    """

    type: SpecialIconType
    position: int = Field(ge=0, le=1, description="Icon position: 0=top, 1=bottom")
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, v: dict[str, Any], info) -> dict[str, Any]:
        """Validate that required parameters are present for each icon type."""
        if not info.data:
            return v

        icon_type = info.data.get("type")
        if not icon_type:
            return v

        # Search icon requires target_icon
        if icon_type == SpecialIconType.SEARCH:
            if "target_icon" not in v:
                raise ValueError("Search icon requires 'target_icon' parameter")
            valid_icons = {"crown", "leaf", "castle", "lightbulb", "factory", "clock"}
            if v["target_icon"] not in valid_icons:
                raise ValueError(
                    f"Invalid target_icon '{v['target_icon']}', must be one of {valid_icons}"
                )

        # Arrow icon requires direction
        elif icon_type == SpecialIconType.ARROW:
            if "direction" not in v:
                raise ValueError("Arrow icon requires 'direction' parameter")
            if v["direction"] not in {"left", "right", "up"}:
                raise ValueError(
                    f"Invalid direction '{v['direction']}', must be 'left', 'right', or 'up'"
                )

        # Flag icon requires target_color
        elif icon_type == SpecialIconType.FLAG:
            if "target_color" not in v:
                raise ValueError("Flag icon requires 'target_color' parameter")
            valid_colors = {"purple", "blue", "green", "red", "yellow"}
            if v["target_color"] not in valid_colors:
                raise ValueError(
                    f"Invalid target_color '{v['target_color']}', must be one of {valid_colors}"
                )

        return v

    def get_category(self) -> SpecialIconCategory:
        """Determine if this is an immediate or constant effect icon."""
        immediate_types = {
            SpecialIconType.SEARCH,
            SpecialIconType.PLUS,
            SpecialIconType.ARROW,
            SpecialIconType.JUNK,
            SpecialIconType.UPLIFT,
            SpecialIconType.UNSPLAY,
        }
        if self.type in immediate_types:
            return SpecialIconCategory.IMMEDIATE
        return SpecialIconCategory.CONSTANT

    def is_immediate(self) -> bool:
        """Check if this is an immediate effect icon (triggers on meld)."""
        return self.get_category() == SpecialIconCategory.IMMEDIATE

    def is_constant(self) -> bool:
        """Check if this is a constant effect icon (active while visible)."""
        return self.get_category() == SpecialIconCategory.CONSTANT

    def get_target_icon(self) -> str | None:
        """For Search icons, get the target icon type to search for."""
        if self.type == SpecialIconType.SEARCH:
            return self.parameters.get("target_icon")
        return None

    def get_target_color(self) -> str | None:
        """For Flag icons, get the target color to count."""
        if self.type == SpecialIconType.FLAG:
            return self.parameters.get("target_color")
        return None

    def get_arrow_direction(self) -> str | None:
        """For Arrow icons, get the splay direction."""
        if self.type == SpecialIconType.ARROW:
            return self.parameters.get("direction")
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON/API responses."""
        return {
            "type": self.type.value,
            "position": self.position,
            "parameters": self.parameters,
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        if self.type == SpecialIconType.SEARCH:
            return f"Search({self.get_target_icon()})"
        elif self.type == SpecialIconType.ARROW:
            return f"Arrow({self.get_arrow_direction()})"
        elif self.type == SpecialIconType.FLAG:
            return f"Flag({self.get_target_color()})"
        else:
            return f"{self.type.value.capitalize()}"
