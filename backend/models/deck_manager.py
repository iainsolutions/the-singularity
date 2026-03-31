import copy
import logging
import random

from pydantic import BaseModel, Field

from .card import Card


logger = logging.getLogger(__name__)


class DeckManager(BaseModel):
    """Manages the game decks (age decks, achievements, junk pile)."""

    age_decks: dict[int, list[Card]] = Field(default_factory=dict)
    achievement_cards: dict[int, list[Card]] = Field(default_factory=dict)
    special_achievements: dict[str, Card] = Field(default_factory=dict)
    special_achievements_available: list[str] = Field(default_factory=list)
    special_achievements_junk: list[str] = Field(default_factory=list)
    junk_pile: list[Card] = Field(default_factory=list)

    def setup_decks(self):
        """Load all cards, separate into age decks, pick achievements, shuffle."""
        from data.cards import load_cards_from_json

        # Only load cards if we haven't already
        if self.age_decks and any(self.age_decks.values()):
            logger.warning("Decks already set up, skipping duplicate initialization")
            return

        all_cards = load_cards_from_json()
        logger.info("Loaded %d cards from JSON", len(all_cards))

        self.age_decks = {}
        self.achievement_cards = {}

        # Process cards ages 1-10: shuffle, pick one as achievement, rest in deck
        for age in range(1, 11):
            age_cards = [
                copy.deepcopy(card)
                for card in all_cards
                if card.age == age and not card.is_achievement
            ]
            random.shuffle(age_cards)

            if age_cards:
                achievement_card = age_cards.pop()
                self.achievement_cards[age] = [achievement_card]
                logger.info("Age %d achievement: %s", age, achievement_card.name)

            self.age_decks[age] = age_cards

        # Age 11 has no achievement card
        age_11_cards = [
            copy.deepcopy(card)
            for card in all_cards
            if card.age == 11 and not card.is_achievement
        ]
        random.shuffle(age_11_cards)
        self.age_decks[11] = age_11_cards

        # Load special achievements
        from data.cards import load_achievement_cards_from_json

        _standard, special_list = load_achievement_cards_from_json()
        self.special_achievements = {}

        for achievement in special_list:
            self.special_achievements[achievement.name] = achievement
            logger.debug("Loaded special achievement: %s", achievement.name)

        self.special_achievements_available = list(self.special_achievements.keys())
        self.special_achievements_junk = []

        logger.info(
            "Setup complete: %d age achievements, %d special achievements",
            len(self.achievement_cards),
            len(self.special_achievements),
        )

    def draw_card(self, age: int) -> Card | None:
        """Draw a card from the specified age deck, skipping to higher ages if empty"""
        # Skip empty decks and go to the next available age
        for current_age in range(age, 12):  # Try ages up to 11
            if self.age_decks.get(current_age):
                # Pop the card from the deck
                card = self.age_decks[current_age].pop()
                # Return the card (already deep copied during setup)
                return card

        return None

    def return_card(self, card: Card, age: int):
        """Return a card to the bottom of its age deck"""
        # Initialize deck if it doesn't exist (happens in tests)
        if age not in self.age_decks:
            self.age_decks[age] = []
        self.age_decks[age].insert(0, card)
