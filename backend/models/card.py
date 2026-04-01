from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Symbol(str, Enum):
    CIRCUIT = "circuit"
    NEURAL_NET = "neural_net"
    DATA = "data"
    ALGORITHM = "algorithm"
    HUMAN_MIND = "human_mind"
    ROBOT = "robot"


class CardColor(str, Enum):
    BLUE = "blue"
    RED = "red"
    GREEN = "green"
    YELLOW = "yellow"
    PURPLE = "purple"


class DogmaEffect(BaseModel):
    text: str
    is_demand: bool = False
    is_optional: bool = False
    symbol_count: int = 1
    actions: list[dict[str, Any]] = Field(default_factory=list)
    selection_condition: dict[str, Any] | None = None


class Card(BaseModel):
    name: str
    age: int
    color: CardColor
    card_id: str | None = None
    dogma_resource: Symbol | None = None
    symbols: list[Symbol | str]

    dogma_effects: list[DogmaEffect] = Field(default_factory=list)

    # Positional symbol data for splay visibility
    # [top_left, bottom_left, bottom_right, top_right]
    symbol_positions: list[Symbol | str | None] = Field(
        default_factory=lambda: [None, None, None, None]
    )

    is_achievement: bool = False
    achievement_requirement: str | None = None
    expansion: str = "base"
    is_revealed: bool = False
    flavour_text: str | None = None

    def __str__(self):
        return f"{self.name} (Age {self.age})"

    def get_symbol_count(self, symbol: Symbol) -> int:
        """Count symbols, preferring symbol_positions over symbols field."""
        if hasattr(self, "symbol_positions") and any(self.symbol_positions):
            return sum(
                1 for pos_symbol in self.symbol_positions if pos_symbol == symbol
            )
        return self.symbols.count(symbol)

    def has_symbol(self, symbol: Symbol) -> bool:
        return symbol in self.symbols

    def has_dogma(self) -> bool:
        return len(self.dogma_effects) > 0

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
            "flavour_text": self.flavour_text,
        }
