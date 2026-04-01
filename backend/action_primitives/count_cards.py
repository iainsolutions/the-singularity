"""
CountCards primitive - Counts cards in a specified location.
"""

from typing import Any

from models.board_utils import BoardColorIterator

from .base import ActionContext, ActionPrimitive, ActionResult


class CountCards(ActionPrimitive):
    """
    Counts the number of cards in a specified location.

    Config:
        - location: Where to count cards ('hand', 'score_pile', 'board', 'board_top', 'board_<color>')
        - player: Which player ('active', 'opponent', 'all', or player_id)
        - store_result: Variable name to store the count
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        # Support both 'location' and 'source' parameter names
        self.location = config.get("location", config.get("source", "hand"))
        # Map 'score' to 'score_pile' for compatibility
        if self.location == "score":
            self.location = "score_pile"
        self.player = config.get("player", "active")
        # Support both 'store_result' and 'store_as' parameter names
        self.store_result = config.get(
            "store_result", config.get("store_as", "card_count")
        )
        # Add filter support for counting specific types of cards
        self.filter_criteria = config.get("filter", {})

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the count cards action"""
        try:
            count = 0

            # Determine which player(s) to count
            if self.player == "active":
                players = [context.player]
            elif self.player == "all":
                players = (
                    context.game.players if hasattr(context.game, "players") else []
                )
            elif self.player == "opponent":
                # Count all opponents
                players = [p for p in context.game.players if p.id != context.player.id]
            else:
                # Specific player ID
                player = context.game.get_player_by_id(self.player)
                players = [player] if player else []

            # Handle game-level locations first (not player-specific)
            if self.location == "junk" or self.location == "junk_pile":
                # Junk pile is game-level, not player-specific
                cards_to_count = []
                if hasattr(context.game, "junk_pile"):
                    cards_to_count = context.game.junk_pile

                # Apply filters if specified
                if self.filter_criteria and cards_to_count:
                    cards_to_count = self._apply_filters(cards_to_count)

                count = len(cards_to_count)
                context.set_variable(self.store_result, count)
                context.add_result(f"Counted {count} cards in junk pile")
                return ActionResult.SUCCESS

            # Count cards for each player
            for player in players:
                cards_to_count = []

                if self.location == "hand":
                    cards_to_count = player.hand
                elif self.location == "score_pile":
                    cards_to_count = player.score_pile
                elif self.location == "board":
                    # Count all cards on board
                    # NOTE: Only use get_total_cards() optimization when there's no filter
                    # Otherwise we must collect cards to apply the filter
                    if hasattr(player.board, "get_total_cards") and not self.filter_criteria:
                        # Use the optimized method if available AND no filters
                        count += player.board.get_total_cards()
                        continue  # Skip the manual counting for this player
                    else:
                        # Manual collection of board cards (required for filtering)
                        cards_to_count = []
                        for color in ["blue", "red", "green", "yellow", "purple"]:
                            stack = getattr(player.board, f"{color}_cards", [])
                            cards_to_count.extend(stack)
                elif self.location == "board_top":
                    # Count only top cards
                    if hasattr(player.board, "get_top_cards"):
                        cards_to_count = player.board.get_top_cards()
                    else:
                        # Manual collection of top cards
                        cards_to_count = []
                        for color, stack in BoardColorIterator.iterate_non_empty_stacks(
                            player.board
                        ):
                            if stack:
                                cards_to_count.append(stack[-1])  # Top card
                elif self.location.startswith("board_"):
                    # Count cards of specific color on board
                    color = self.location.replace("board_", "")
                    cards_to_count = getattr(player.board, f"{color}_cards", [])
                elif self.location == "achievements":
                    cards_to_count = player.achievements

                # Apply filters if specified
                if self.filter_criteria and cards_to_count:
                    cards_to_count = self._apply_filters(cards_to_count)

                count += len(cards_to_count)

            # Store the result
            context.set_variable(self.store_result, count)

            # Log the action
            context.add_result(f"Counted {count} cards in {self.location}")

            return ActionResult.SUCCESS

        except Exception as e:
            context.add_result(f"Error counting cards: {e!s}")
            return ActionResult.FAILURE

    def _apply_filters(self, cards: list) -> list:
        """Apply filter criteria to cards list"""
        filtered_cards = []

        for card in cards:
            if self._card_matches_filter(card):
                filtered_cards.append(card)

        return filtered_cards

    def _card_matches_filter(self, card) -> bool:
        """Check if a card matches the filter criteria"""
        # Color filter
        if "color" in self.filter_criteria:
            required_color = self.filter_criteria["color"]
            if hasattr(card, "color"):
                # Use .value for enum, fallback to str for other types
                card_color = card.color.value if hasattr(card.color, "value") else card.color.value
                if card_color != required_color:
                    return False

        # Age filter
        if "age" in self.filter_criteria:
            required_age = self.filter_criteria["age"]
            if hasattr(card, "age") and card.age != required_age:
                return False

        # Symbol filter
        if "has_symbol" in self.filter_criteria:
            required_symbol = self.filter_criteria["has_symbol"]
            if hasattr(card, "symbols"):
                # Handle both string and enum symbols
                card_symbols = [
                    s.value if hasattr(s, "value") else str(s) for s in card.symbols
                ]
                if required_symbol not in card_symbols:
                    return False

        return True
