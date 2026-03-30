from enum import Enum
from typing import Set

from pydantic import BaseModel, Field


class Expansion(str, Enum):
    """Available expansions for Innovation Ultimate"""

    CITIES = "cities"
    ARTIFACTS = "artifacts"
    ECHOES = "echoes"
    FIGURES = "figures"
    UNSEEN = "unseen"


class ExpansionConfig(BaseModel):
    """Configuration for which expansions are enabled in a game"""

    enabled_expansions: Set[Expansion] = Field(default_factory=set)

    def is_enabled(self, expansion: Expansion | str) -> bool:
        """Check if an expansion is enabled"""
        if isinstance(expansion, str):
            try:
                expansion = Expansion(expansion)
            except ValueError:
                return False
        return expansion in self.enabled_expansions

    def enable(self, expansion: Expansion | str):
        """Enable an expansion"""
        if isinstance(expansion, str):
            expansion = Expansion(expansion)
        self.enabled_expansions.add(expansion)

    def disable(self, expansion: Expansion | str):
        """Disable an expansion"""
        if isinstance(expansion, str):
            try:
                expansion = Expansion(expansion)
            except ValueError:
                return
        self.enabled_expansions.discard(expansion)

    def get_expansion_count(self) -> int:
        """Get the number of enabled expansions (used for victory condition)"""
        return len(self.enabled_expansions)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {"enabled_expansions": [exp.value for exp in self.enabled_expansions]}

    @classmethod
    def from_dict(cls, data: dict) -> "ExpansionConfig":
        """Create from dictionary"""
        if not data:
            return cls()
        expansions = data.get("enabled_expansions", [])
        return cls(enabled_expansions={Expansion(exp) for exp in expansions})
