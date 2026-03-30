from enum import Enum
from typing import Set

from pydantic import BaseModel, Field


class Expansion(str, Enum):
    """Available expansions for Innovation Ultimate (base game only - none)"""
    pass


class ExpansionConfig(BaseModel):
    """Configuration for which expansions are enabled in a game.

    Base-game-only build: no expansions are ever enabled.
    Kept as a stub so existing call-sites don't break.
    """

    enabled_expansions: Set[Expansion] = Field(default_factory=set)

    def is_enabled(self, expansion: "Expansion | str") -> bool:
        """Always returns False - no expansions in base game."""
        return False

    def enable(self, expansion: "Expansion | str"):
        """No-op in base game build."""
        pass

    def disable(self, expansion: "Expansion | str"):
        """No-op in base game build."""
        pass

    def get_expansion_count(self) -> int:
        """Always 0 - no expansions."""
        return 0

    def to_dict(self) -> dict:
        return {"enabled_expansions": []}

    @classmethod
    def from_dict(cls, data: dict) -> "ExpansionConfig":
        return cls()
