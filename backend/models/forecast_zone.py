"""
Forecast Zone model for Echoes of the Past expansion
"""

from pydantic import BaseModel, Field

from .card import Card


class ForecastZone(BaseModel):
    """
    Forecast zone for Echoes expansion

    Stores face-down cards that can be promoted during Meld actions.
    Limit is calculated based on player's best splay direction:
    - No splay: 5 cards
    - Left splay: 4 cards
    - Right splay: 3 cards
    - Up splay: 2 cards
    - Aslant splay: 1 card
    """

    player_id: str = Field(
        ..., description="ID of the player who owns this forecast zone"
    )
    cards: list[Card] = Field(
        default_factory=list, description="Cards in forecast zone (face-down)"
    )

    def add_card(self, card: Card) -> None:
        """Add a card to the forecast zone (foreshadow action)"""
        self.cards.append(card)

    def remove_card(self, card: Card) -> Card | None:
        """Remove and return a card from forecast zone (promotion or effect)"""
        if card in self.cards:
            self.cards.remove(card)
            return card
        return None

    def remove_card_by_index(self, index: int) -> Card | None:
        """Remove and return a card by index"""
        if 0 <= index < len(self.cards):
            return self.cards.pop(index)
        return None

    def get_cards_by_age(self, max_age: int) -> list[Card]:
        """Get all cards with age <= max_age (for promotion eligibility)"""
        return [card for card in self.cards if card.age <= max_age]

    def count(self) -> int:
        """Get number of cards in forecast zone"""
        return len(self.cards)

    def is_empty(self) -> bool:
        """Check if forecast zone is empty"""
        return len(self.cards) == 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "player_id": self.player_id,
            "cards": [card.to_dict() for card in self.cards],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ForecastZone":
        """Create from dictionary"""
        if not data:
            return None

        return cls(
            player_id=data.get("player_id", ""),
            cards=[Card.model_validate(c) for c in data.get("cards", [])],
        )
