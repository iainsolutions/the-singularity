import copy
import logging
import random

from pydantic import BaseModel, Field

from .card import Card
from .expansion import ExpansionConfig


logger = logging.getLogger(__name__)


class DeckManager(BaseModel):
    """
    Manages the game decks (Age decks, Cities decks, Unseen decks, etc.).
    Handles initialization, drawing, and returning cards.
    """

    age_decks: dict[int, list[Card]] = Field(default_factory=dict)
    cities_decks: dict[int, list[Card]] = Field(default_factory=dict)
    echoes_decks: dict[int, list[Card]] = Field(default_factory=dict)
    unseen_decks: dict[int, list[Card]] = Field(default_factory=dict)
    achievement_cards: dict[int, list[Card]] = Field(default_factory=dict)
    special_achievements: dict[str, Card] = Field(default_factory=dict)
    special_achievements_available: list[str] = Field(default_factory=list)  # Names of available special achievements
    special_achievements_junk: list[str] = Field(default_factory=list)  # Names of junked special achievements
    junk_pile: list[Card] = Field(default_factory=list)

    # We need expansion_config for setup, but it's stored in Game.
    # We can pass it to setup_decks.

    def setup_decks(self, expansion_config: ExpansionConfig):
        """Set up the age decks for the game"""
        from data.cards import load_cards_from_json

        # Only load cards if we haven't already (check both existence AND non-empty)
        if self.age_decks and any(self.age_decks.values()):
            logger.warning(
                "Decks already set up, skipping duplicate initialization"
            )  # pylint: disable=line-too-long
            return

        # Get enabled expansions list
        enabled_expansions = []
        if expansion_config.is_enabled("cities"):
            enabled_expansions.append("cities")
        if expansion_config.is_enabled("artifacts"):
            enabled_expansions.append("artifacts")
        if expansion_config.is_enabled("echoes"):
            enabled_expansions.append("echoes")
        if expansion_config.is_enabled("unseen"):
            enabled_expansions.append("unseen")

        all_cards = load_cards_from_json(enabled_expansions=enabled_expansions)
        logger.info("Loaded %d cards from JSON", len(all_cards))

        # Separate cards by expansion and age
        self.age_decks = {}
        self.cities_decks = {}
        self.echoes_decks = {}
        self.achievement_cards = {}

        # Separate cards by expansion for age decks
        # Age decks include: Base + Figures (mixed in)
        # Excluded from Age decks: Cities (separate), Echoes (separate), Artifacts (separate), Unseen (separate)
        age_deck_expansions = {"base", "figures"}
        base_cards = [
            card for card in all_cards if card.expansion in age_deck_expansions
        ]

        cities_cards = [card for card in all_cards if card.expansion == "cities"]
        echoes_cards = [card for card in all_cards if card.expansion == "echoes"]
        unseen_cards = [card for card in all_cards if card.expansion == "unseen"]

        # Debug: Log card counts by expansion
        logger.info(f"Base cards for age decks: {len(base_cards)}")
        if echoes_cards:
            logger.info(f"Echoes cards (separate decks): {len(echoes_cards)}")
        if unseen_cards:
            logger.info(f"Unseen cards (separate decks): {len(unseen_cards)}")

        if cities_cards:
            logger.info(
                "Found %d Cities expansion cards across ages", len(cities_cards)
            )

        # Process base game cards (ages 1-10)
        for age in range(1, 11):  # Ages 1-10 for base game
            # Deep copy each card to ensure unique instances
            age_cards = [
                copy.deepcopy(card)
                for card in base_cards
                if card.age == age and not card.is_achievement
            ]
            random.shuffle(age_cards)

            # Take one card from each age (1-10) as achievement
            if age <= 10 and age_cards:
                achievement_card = age_cards.pop()
                self.achievement_cards[age] = [achievement_card]
                logger.info("Age %d achievement: %s", age, achievement_card.name)

            # Rest go in the age deck
            self.age_decks[age] = age_cards

        # Age 11 has no achievement card
        age_11_cards = [
            copy.deepcopy(card)
            for card in base_cards
            if card.age == 11 and not card.is_achievement
        ]
        random.shuffle(age_11_cards)
        self.age_decks[11] = age_11_cards

        # Process Cities expansion cards (ages 1-11) - separate decks
        if expansion_config.is_enabled("cities") and cities_cards:
            for age in range(1, 12):  # Cities can be age 1-11
                cities_age_cards = [
                    copy.deepcopy(card) for card in cities_cards if card.age == age
                ]
                if cities_age_cards:
                    random.shuffle(cities_age_cards)
                    self.cities_decks[age] = cities_age_cards
                    logger.info(f"Cities deck age {age}: {len(cities_age_cards)} cards")

        # Process Echoes expansion cards (ages 1-11) - separate decks
        if expansion_config.is_enabled("echoes") and echoes_cards:
            for age in range(1, 12):  # Echoes can be age 1-11
                echoes_age_cards = [
                    copy.deepcopy(card) for card in echoes_cards if card.age == age
                ]
                if echoes_age_cards:
                    random.shuffle(echoes_age_cards)
                    self.echoes_decks[age] = echoes_age_cards
                    logger.info(f"Echoes deck age {age}: {len(echoes_age_cards)} cards")

        # Load special achievements (Monument, Empire, etc. + Fountains if Cities enabled)
        from data.cards import load_achievement_cards_from_json

        all_achievements = load_achievement_cards_from_json()
        self.special_achievements = {}

        for achievement in all_achievements:
            # Skip age-based achievements (1-9) - those are handled above
            if achievement.name.startswith("Age "):
                continue

            # Filter Cities achievements if expansion is not enabled
            if (
                "Fountain" in achievement.name or "Flag" in achievement.name
            ) and not expansion_config.is_enabled("cities"):
                continue

            # Store by name for easy lookup
            self.special_achievements[achievement.name] = achievement
            logger.debug("Loaded special achievement: %s", achievement.name)

        # Initialize all special achievements as available
        self.special_achievements_available = list(self.special_achievements.keys())
        self.special_achievements_junk = []

        logger.info(
            "Setup complete: %d age achievements, %d special achievements",
            len(self.achievement_cards),
            len(self.special_achievements),
        )

        # Setup Unseen expansion decks if enabled
        if expansion_config.is_enabled("unseen"):
            self._setup_unseen_decks()

    def _setup_unseen_decks(self):
        """Setup Unseen expansion decks (age-segregated, separate from base decks)"""
        from data.cards import load_unseen_cards

        logger.info("Setting up Unseen expansion decks")

        try:
            all_unseen_cards = load_unseen_cards()
            logger.info("Loaded %d Unseen cards", len(all_unseen_cards))

            # Create age-segregated Unseen decks (separate from base decks)
            self.unseen_decks = {}
            for age in range(1, 11):  # Ages 1-10
                age_cards = [
                    copy.deepcopy(card) for card in all_unseen_cards if card.age == age
                ]
                random.shuffle(age_cards)
                self.unseen_decks[age] = age_cards
                logger.debug("Unseen Age %d: %d cards", age, len(age_cards))

            logger.info("Unseen decks setup complete")

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to setup Unseen decks: %s", e)
            # Set empty decks as fallback
            self.unseen_decks = {age: [] for age in range(1, 11)}

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
