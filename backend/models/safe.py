"""
Safe model for The Unseen expansion.

The Safe stores Unseen cards face-down. Per official rules (Innovation Ultimate v4.1, page 31):
"These cards in your Safe (called secrets) are tucked face-down under the bottom edge of your
Reference Card. Other players cannot look at their fronts, and neither can you! You may keep
track of the order cards come into a Safe, which can prove useful."

KEY SECURITY REQUIREMENT:
- Card fronts are hidden from ALL players (including owner)
- Owner can track: order, count, and age of each secret
- Owner CANNOT see: specific card identity, effects, icons, color
- Opponents can see: count only
"""

from typing import Optional

from pydantic import BaseModel, Field

from .card import Card


class Safe(BaseModel):
    """
    Represents a player's Safe (hidden card storage with age tracking).

    Security: Card fronts are hidden from ALL players (including owner).
    Age tracking: Owner knows age of each secret (for achievement validation).
    Order tracking: Owner knows which secret was added first, second, third, etc.
    """

    player_id: str
    cards: list[Card] = Field(default_factory=list)
    secret_ages: list[int] = Field(default_factory=list)  # Age of each secret

    def add_card(self, card: Card) -> bool:
        """
        Tuck a card into the Safe.

        Args:
            card: The Unseen card to add

        Returns:
            True if card was added successfully

        Raises:
            ValueError: If card is not an Unseen card
        """
        if card.expansion != "unseen":
            raise ValueError("Only Unseen cards can be tucked into Safe")

        self.cards.append(card)
        self.secret_ages.append(card.age)  # Track age for achievement
        return True

    def remove_card(self, card_index: int) -> Card:
        """
        Remove a card from Safe (e.g., for achieving or melding).

        Args:
            card_index: Position in the Safe (0-based)

        Returns:
            The removed card

        Raises:
            ValueError: If index is invalid
        """
        if card_index < 0 or card_index >= len(self.cards):
            raise ValueError(f"Invalid Safe index: {card_index}")

        self.secret_ages.pop(card_index)
        return self.cards.pop(card_index)

    def get_card_count(self) -> int:
        """Get number of cards in Safe (visible to all players)"""
        return len(self.cards)

    def get_secret_ages(self) -> list[int]:
        """Get ages of all secrets (owner can know this for tracking)"""
        return self.secret_ages.copy()

    def get_card_at_index(self, index: int) -> Optional[Card]:
        """
        Get card at specific index (server-side only, for game logic).

        This should NEVER be exposed to clients. Used only for server-side
        operations like validation.
        """
        if index < 0 or index >= len(self.cards):
            return None
        return self.cards[index]

    def to_dict_for_owner(self) -> dict:
        """
        Serialize for Safe owner (ages visible, card details hidden).

        Owner can see:
        - Card count
        - Ages of each secret (for achievement validation)
        - Order of secrets

        Owner CANNOT see:
        - Specific card identities
        - Card effects
        - Icons or colors
        """
        return {
            "player_id": self.player_id,
            "card_count": len(self.cards),
            "secret_ages": self.secret_ages,  # Owner sees ages
            "cards": [],  # Card identities hidden (empty list for Pydantic)
        }

    def to_dict_for_opponent(self) -> dict:
        """
        Serialize for opponents (only count visible).

        Opponents can see:
        - Card count only

        Opponents CANNOT see:
        - Ages of secrets
        - Card identities
        - Any other information
        """
        return {
            "player_id": self.player_id,
            "card_count": len(self.cards),
            "secret_ages": [],  # Hidden (empty list for Pydantic)
            "cards": [],  # Hidden (empty list for Pydantic)
        }

    def calculate_safe_limit(self, splay_directions: dict[str, str]) -> int:
        """
        Calculate Safe limit based on best splay state.

        Per official rules: Better splays INCREASE Safe capacity.
        Formula: 5 + (number of icon positions revealed by best splay)

        Splay State -> Safe Limit:
        - None: 5 (base)
        - Left: 6 (5 + 1 position revealed)
        - Right: 7 (5 + 2 positions revealed)
        - Up: 8 (5 + 3 positions revealed)
        - Aslant: 9 (5 + 4 positions revealed)

        Args:
            splay_directions: Dictionary of color -> splay direction

        Returns:
            Maximum number of cards allowed in Safe
        """
        if not splay_directions:
            return 5  # No splays (base limit)

        # Check for best splay (most generous first - better splays increase capacity)
        if "aslant" in splay_directions.values():
            return 9  # 5 + 4 positions (all icons revealed)
        elif "up" in splay_directions.values():
            return 8  # 5 + 3 positions (bottom row revealed)
        elif "right" in splay_directions.values():
            return 7  # 5 + 2 positions (left edge revealed)
        elif "left" in splay_directions.values():
            return 6  # 5 + 1 position (right edge revealed)
        else:
            return 5  # No splays (base limit)

    def is_at_or_over_limit(self, splay_directions: dict[str, str]) -> bool:
        """
        Check if Safe is at or over its current limit.

        Note: Safe can go over limit temporarily (limit changes with splay).
        Cards are NOT automatically removed when limit decreases.

        Args:
            splay_directions: Dictionary of color -> splay direction

        Returns:
            True if at or over limit
        """
        limit = self.calculate_safe_limit(splay_directions)
        return len(self.cards) >= limit
