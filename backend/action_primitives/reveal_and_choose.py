"""
RevealAndChoose Action Primitive

Reveal cards from multiple sources and choose which to keep.
Part of the Unseen expansion mechanics.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult
from .standard_interaction_builder import StandardInteractionBuilder

logger = logging.getLogger(__name__)


class RevealAndChoose(ActionPrimitive):
    """
    Reveal cards from multiple sources and choose which to keep.

    This primitive reveals cards from different decks/locations, allows the player
    to choose which card(s) to keep, and handles the unchosen cards according to
    the specified return action.

    Example: "Reveal a 7 and a 9. Draw one and return the other."

    Parameters:
    - reveal_sources: List of sources to reveal from
                     [{"type": "age_deck", "age": 7}, {"type": "age_deck", "age": 9}]
    - choose_count: Number of cards to choose (default: 1)
    - keep_action: What to do with chosen card(s) ("draw", "meld", "score", "hand")
    - return_action: What to do with unchosen card(s) ("deck_bottom", "deck_top", "junk")
    - store_result: Variable name to store chosen card(s)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.reveal_sources = config.get("reveal_sources", [])
        self.choose_count = config.get("choose_count", 1)
        self.keep_action = config.get("keep_action", "draw")
        self.return_action = config.get("return_action", "deck_bottom")
        self.store_result = config.get("store_result", "chosen_cards")

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the reveal and choose action"""
        logger.debug(
            f"RevealAndChoose.execute: {len(self.reveal_sources)} sources, "
            f"choose {self.choose_count}, keep={self.keep_action}"
        )

        # Validate reveal sources
        if not self.reveal_sources or len(self.reveal_sources) == 0:
            context.add_result("Error: No reveal sources specified")
            return ActionResult.FAILURE

        # Reveal cards from each source
        revealed_cards = []
        for source_config in self.reveal_sources:
            card = self._reveal_from_source(context, source_config)
            if card:
                revealed_cards.append({
                    "card": card,
                    "source": source_config
                })
            else:
                logger.warning(f"Failed to reveal from source: {source_config}")

        if not revealed_cards:
            context.add_result("No cards could be revealed")
            return ActionResult.CONDITION_NOT_MET

        # If only one card or choose_count equals revealed count, auto-select
        if len(revealed_cards) == 1 or self.choose_count >= len(revealed_cards):
            chosen_cards = [rc["card"] for rc in revealed_cards]
            self._process_choices(context, chosen_cards, [])
            return ActionResult.SUCCESS

        # Create card selection interaction
        self._create_card_selection_interaction(context, revealed_cards)

        logger.debug(f"RevealAndChoose: Created interaction for {len(revealed_cards)} cards")
        return ActionResult.SUCCESS

    def _reveal_from_source(self, context: ActionContext, source_config: dict):
        """Reveal a card from the specified source"""
        source_type = source_config.get("type")

        if source_type == "age_deck":
            # Reveal from age deck
            age = source_config.get("age")
            if age is None:
                logger.error("RevealAndChoose: age required for age_deck source")
                return None

            # Resolve age (may be variable)
            if isinstance(age, str) and context.has_variable(age):
                age = context.get_variable(age)

            try:
                age = int(age)
            except (ValueError, TypeError):
                logger.error(f"RevealAndChoose: Invalid age {age}")
                return None

            # Get deck
            deck = context.game.deck_manager.age_decks.get(age, [])
            if not deck:
                logger.warning(f"Age {age} deck is empty")
                return None

            # Reveal top card (don't remove yet)
            card = deck[0]
            activity_logger.info(f"Revealed {card.name} (Age {age})")
            return card

        elif source_type == "unseen_deck":
            # Reveal from Unseen deck
            age = source_config.get("age")
            if age is None:
                logger.error("RevealAndChoose: age required for unseen_deck source")
                return None

            # Resolve age
            if isinstance(age, str) and context.has_variable(age):
                age = context.get_variable(age)

            try:
                age = int(age)
            except (ValueError, TypeError):
                logger.error(f"RevealAndChoose: Invalid age {age}")
                return None

            # Get Unseen deck
            if hasattr(context.game, "unseen_decks"):
                deck = context.game.deck_manager.unseen_decks.get(age, [])
                if deck:
                    card = deck[0]
                    activity_logger.info(f"Revealed Unseen card (Age {age})")
                    return card

            logger.warning(f"Unseen deck age {age} is empty")
            return None

        elif source_type == "hand":
            # Reveal from hand (specific index or selection)
            index = source_config.get("index", 0)
            if index < len(context.player.hand):
                return context.player.hand[index]
            return None

        elif source_type == "board_top":
            # Reveal top card of color
            color = source_config.get("color")
            if not color:
                return None

            stack = context.player.board.get_cards_by_color(color)
            if stack:
                return stack[-1]
            return None

        else:
            logger.error(f"RevealAndChoose: Unknown source type {source_type}")
            return None

    def _create_card_selection_interaction(self, context: ActionContext, revealed_cards: list):
        """Create card selection interaction"""
        # Build card options
        options = []
        for idx, rc in enumerate(revealed_cards):
            card = rc["card"]
            option = {
                "id": str(idx),
                "label": card.name,
                "description": f"Age {card.age} {card.color}"
            }
            options.append(option)

        # Create interaction
        interaction = StandardInteractionBuilder.select_from_options(
            player=context.player,
            prompt=f"Choose {self.choose_count} card(s) to {self.keep_action}",
            options=options,
            min_selections=self.choose_count,
            max_selections=self.choose_count,
            store_result=self.store_result
        )

        context.set_interaction(interaction)

    def _process_choices(self, context: ActionContext, chosen_cards: list, unchosen_cards: list):
        """Process the chosen and unchosen cards"""
        # Store chosen cards
        context.set_variable(self.store_result, chosen_cards)

        # Process chosen cards based on keep_action
        for card in chosen_cards:
            if self.keep_action == "draw" or self.keep_action == "hand":
                context.player.hand.append(card)
                activity_logger.info(f"{context.player.name} drew {card.name}")

            elif self.keep_action == "meld":
                # Meld the card
                if hasattr(card, "color"):
                    stack = context.player.board.get_cards_by_color(card.color)
                    stack.append(card)
                    activity_logger.info(f"{context.player.name} melded {card.name}")

            elif self.keep_action == "score":
                context.player.score_pile.append(card)
                activity_logger.info(f"{context.player.name} scored {card.name}")

        # Process unchosen cards based on return_action
        for card in unchosen_cards:
            if self.return_action == "deck_bottom":
                # Return to bottom of appropriate deck
                if hasattr(card, "age"):
                    deck = context.game.deck_manager.age_decks.get(card.age, [])
                    deck.append(card)
                    activity_logger.info(f"Returned {card.name} to bottom of deck")

            elif self.return_action == "deck_top":
                # Return to top of appropriate deck
                if hasattr(card, "age"):
                    deck = context.game.deck_manager.age_decks.get(card.age, [])
                    deck.insert(0, card)
                    activity_logger.info(f"Returned {card.name} to top of deck")

            elif self.return_action == "junk":
                # Junk the card (remove from game)
                activity_logger.info(f"Junked {card.name}")

        context.add_result(
            f"Chose {len(chosen_cards)} card(s), returned {len(unchosen_cards)}"
        )

    def get_required_fields(self) -> list[str]:
        return ["reveal_sources"]

    def get_optional_fields(self) -> list[str]:
        return ["choose_count", "keep_action", "return_action", "store_result"]
