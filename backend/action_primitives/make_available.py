"""
MakeAvailable primitive - Makes cards available for other players to take.
"""

from typing import Any

from models.board_utils import BoardColorIterator

from .base import ActionContext, ActionPrimitive, ActionResult


class MakeAvailable(ActionPrimitive):
    """
    Makes cards available in a shared pool for other players to take.
    This is used for effects where cards are placed in a common area.

    Special handling for special achievements: moves them from junk to available.

    Config:
        - selection: Which cards to make available ('selected_cards', variable name)
        - cards: Legacy alias for selection
        - source: Where cards come from ('hand', 'board', 'score_pile', 'deck')
        - age: If source is 'deck', which age to draw from
        - count: Number of cards to make available
        - pool_name: Name of the available pool (default: 'available_cards')
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        # Support both 'selection' (new) and 'cards' (legacy) parameters
        self.cards = config.get("selection", config.get("cards", "selected_cards"))
        self.source = config.get("source", "hand")
        self.age = config.get("age")
        self.count = config.get("count", 1)
        self.pool_name = config.get("pool_name", "available_cards")

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the make available action"""
        try:
            # Get cards to make available
            cards_to_make_available = []

            if self.source == "deck" and self.age is not None:
                # Draw cards from deck to make available
                for _ in range(self.count):
                    if (
                        context.game.deck_manager.age_decks.get(self.age)
                    ):
                        card = context.game.deck_manager.age_decks[self.age].pop()
                        cards_to_make_available.append(card)

            else:
                # Get cards from player's areas
                if self.cards == "selected_cards":
                    cards_to_make_available = context.get_variable("selected_cards", [])
                elif self.cards == "last_drawn":
                    cards_to_make_available = context.get_variable("last_drawn", [])
                else:
                    # Variable name
                    cards_to_make_available = context.get_variable(self.cards, [])

                # Ensure we have a list
                if not isinstance(cards_to_make_available, list):
                    cards_to_make_available = (
                        [cards_to_make_available] if cards_to_make_available else []
                    )

                # Remove cards from their current location
                for card in cards_to_make_available:
                    removed = False

                    # Try to remove from hand
                    if self.source == "hand":
                        if card in context.player.hand:
                            context.player.hand.remove(card)
                            removed = True

                    # Try to remove from score pile
                    elif self.source == "score_pile":
                        if card in context.player.score_pile:
                            context.player.score_pile.remove(card)
                            removed = True

                    # Try to remove from board
                    elif self.source == "board":
                        for (
                            _color,
                            color_cards,
                        ) in BoardColorIterator.iterate_color_stacks(
                            context.player.board
                        ):
                            if card in color_cards:
                                color_cards.remove(card)
                                removed = True
                                break

                    if not removed and self.source != "deck":
                        # Card wasn't in expected location, skip it
                        cards_to_make_available.remove(card)

            # Check if these are special achievements and handle them specially
            made_available = 0
            for card in cards_to_make_available:
                # Check if this is a special achievement
                if hasattr(card, 'is_achievement') and card.is_achievement and card.name in context.game.deck_manager.special_achievements:
                    # Move from junk to available
                    if card.name in context.game.deck_manager.special_achievements_junk:
                        context.game.deck_manager.special_achievements_junk.remove(card.name)
                    if card.name not in context.game.deck_manager.special_achievements_available:
                        context.game.deck_manager.special_achievements_available.append(card.name)
                    made_available += 1
                    context.add_result(f"Made special achievement '{card.name}' available")
                else:
                    # Regular card - add to available pool
                    if not hasattr(context.game, "available_pools"):
                        context.game.available_pools = {}
                    if self.pool_name not in context.game.available_pools:
                        context.game.available_pools[self.pool_name] = []
                    context.game.available_pools[self.pool_name].append(card)
                    made_available += 1

            # Store reference to available cards
            context.set_variable("made_available", cards_to_make_available)

            # Log the action
            if made_available == 0:
                context.add_result("No cards made available")

            return ActionResult.SUCCESS

        except Exception as e:
            context.add_result(f"Error making cards available: {e!s}")
            return ActionResult.FAILURE
