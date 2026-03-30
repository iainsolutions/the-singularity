"""
JunkCards primitive - Removes cards from the game entirely (to the "junk" pile).
"""

from typing import Any

from models.board_utils import BoardColorIterator

from .base import ActionContext, ActionPrimitive, ActionResult


class JunkCards(ActionPrimitive):
    """
    Removes cards from the game by moving them to a junk pile (out of play).
    This is different from returning cards to decks - junked cards are removed entirely.

    Config:
        - selection: Which cards to junk ('selected_cards', 'last_drawn', variable name, or 'all')
        - source: Where to junk from ('hand', 'board', 'score_pile', 'board_<color>', 'age_deck')
        - count: Number of cards to junk (if selection is 'all' or not specified)
        - player: Which player's cards ('active', 'opponent', or player_id)
        - age: Age of deck to junk from (when source='age_deck', can be int or variable name)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.selection = config.get("selection", "selected_cards")
        self.source = config.get("source", "hand")
        self.count = config.get("count", 1)
        self.player = config.get("player", "active")
        self.age = config.get("age")  # For age_deck source

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the junk cards action"""
        try:
            # Get the target player
            if self.player == "active":
                target_player = context.player
            elif self.player == "opponent":
                # Get first opponent
                opponents = [
                    p for p in context.game.players if p.id != context.player.id
                ]
                if not opponents:
                    context.add_result("No opponents to junk cards from")
                    return ActionResult.SUCCESS
                target_player = opponents[0]
            else:
                target_player = context.game.get_player_by_id(self.player)
                if not target_player:
                    context.add_result(f"Player {self.player} not found")
                    return ActionResult.FAILURE

            # Initialize junk pile if it doesn't exist
            if not hasattr(context.game.deck_manager, "junk_pile"):
                context.game.deck_manager.junk_pile = []

            # Handle age_deck source (abstracts FilterCards + TransferCards pattern)
            if self.source == "age_deck":
                if not self.age:
                    context.add_result("age_deck source requires age parameter")
                    return ActionResult.FAILURE

                # Resolve age from variable if needed
                age = self.age
                if isinstance(age, str):
                    age = context.get_variable(age)
                    if age is None:
                        context.add_result(f"Age variable '{self.age}' not found")
                        return ActionResult.FAILURE

                # Access age deck directly (don't use CardSourceResolver which returns a copy)
                if (
                    not hasattr(context.game, "deck_manager")
                    or not hasattr(context.game.deck_manager, "age_decks")
                    or age not in context.game.deck_manager.age_decks
                ):
                    context.add_result(f"No age {age} deck found")
                    return ActionResult.SUCCESS

                deck_cards = context.game.deck_manager.age_decks[age]

                if not deck_cards:
                    context.add_result(f"No cards in age {age} deck to junk")
                    return ActionResult.SUCCESS

                # Copy list for iteration, then clear original
                cards_to_junk = list(deck_cards)
                junked_count = len(cards_to_junk)

                # Clear the deck and move to junk pile
                deck_cards.clear()
                context.game.deck_manager.junk_pile.extend(cards_to_junk)

                context.add_result(f"Junked {junked_count} cards from age {age} deck")
                return ActionResult.SUCCESS

            # Determine which cards to junk
            cards_to_junk = []

            if self.selection == "selected_cards":
                cards_to_junk = context.get_variable("selected_cards", [])
            elif self.selection == "last_drawn":
                cards_to_junk = context.get_variable("last_drawn", [])
            elif self.selection == "all":
                # Junk all cards from source
                if self.source == "hand":
                    cards_to_junk = target_player.hand.copy()
                elif self.source == "score_pile":
                    cards_to_junk = target_player.score_pile.copy()
                elif self.source == "board":
                    # All cards from board
                    cards_to_junk = BoardColorIterator.get_all_board_cards(
                        target_player.board
                    )
                elif self.source.startswith("board_"):
                    # Cards from specific color
                    color = self.source.replace("board_", "")
                    cards_to_junk = getattr(
                        target_player.board, f"{color}_cards", []
                    ).copy()
            else:
                # Variable name
                cards_to_junk = context.get_variable(self.selection, [])

            # Ensure we have a list
            if not isinstance(cards_to_junk, list):
                cards_to_junk = [cards_to_junk] if cards_to_junk else []

            # Limit to count if specified
            if self.count and len(cards_to_junk) > self.count:
                cards_to_junk = cards_to_junk[: self.count]

            # Remove cards from their current location and add to junk
            junked_count = 0
            for card in cards_to_junk:
                # Check if this is a special achievement
                if hasattr(card, 'is_achievement') and card.is_achievement and card.name in context.game.deck_manager.special_achievements:
                    # Move from available to junk
                    if card.name in context.game.deck_manager.special_achievements_available:
                        context.game.deck_manager.special_achievements_available.remove(card.name)
                    if card.name not in context.game.deck_manager.special_achievements_junk:
                        context.game.deck_manager.special_achievements_junk.append(card.name)
                    junked_count += 1
                    context.add_result(f"Junked special achievement '{card.name}'")
                    continue

                removed = False

                # Try to remove from hand
                if self.source == "hand" or self.source == "all":
                    if card in target_player.hand:
                        target_player.hand.remove(card)
                        removed = True

                # Try to remove from score pile
                if (
                    not removed
                    and (self.source == "score_pile" or self.source == "all")
                    and card in target_player.score_pile
                ):
                    target_player.score_pile.remove(card)
                    removed = True

                # Try to remove from board
                if not removed and (
                    self.source == "board"
                    or self.source.startswith("board_")
                    or self.source == "all"
                ):
                    if self.source.startswith("board_"):
                        # Only check the specific color
                        specific_color = self.source.replace("board_", "")
                        color_cards = getattr(
                            target_player.board, f"{specific_color}_cards", []
                        )
                        if card in color_cards:
                            color_cards.remove(card)
                            removed = True
                    else:
                        # Check all colors
                        for (
                            _,
                            color_cards,
                        ) in BoardColorIterator.iterate_color_stacks(
                            target_player.board
                        ):
                            if card in color_cards:
                                color_cards.remove(card)
                                removed = True
                                break

                if removed:
                    context.game.deck_manager.junk_pile.append(card)
                    junked_count += 1

            # Log the action
            if junked_count > 0:
                context.add_result(f"Junked {junked_count} cards from {self.source}")
            else:
                context.add_result("No cards to junk")

            # UNSEEN EXPANSION: Rebuild Safeguards when cards are junked
            # Junked cards leave the board, affecting Safeguard status
            if junked_count > 0 and hasattr(context.game, "expansion_config"):
                if context.game.expansion_config.is_enabled("unseen"):
                    try:
                        from game_logic.unseen.safeguard_tracker import SafeguardTracker

                        tracker = SafeguardTracker(context.game)
                        tracker.rebuild_all_safeguards()
                    except Exception:
                        # Log but don't fail the action
                        pass

            return ActionResult.SUCCESS

        except Exception as e:
            context.add_result(f"Error junking cards: {e!s}")
            return ActionResult.FAILURE
