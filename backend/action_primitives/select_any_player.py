"""
SelectAnyPlayer Action Primitive

Select any player in the game (not limited to opponent/self).
Part of the Unseen expansion mechanics.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult
from .standard_interaction_builder import StandardInteractionBuilder

logger = logging.getLogger(__name__)


class SelectAnyPlayer(ActionPrimitive):
    """
    Select any player in the game.

    Creates an interaction for the current player to choose from all players
    (including themselves and all opponents).

    Parameters:
    - store_result: Variable name to store selected player ID (default: "selected_player")
    - prompt: Custom prompt text for the selection (default: "Choose a player")
    - filter: Optional filter condition to limit eligible players
              - has_card_age: Player must have card of specific age
              - has_achievement: Player must have at least one achievement
              - has_color: Player must have cards of specific color
              - min_score: Player must have minimum score
    - exclude_self: If True, exclude current player from selection (default: False)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.store_result = config.get("store_result", "selected_player")
        self.prompt = config.get("prompt", "Choose a player")
        self.filter = config.get("filter")
        self.exclude_self = config.get("exclude_self", False)

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the select any player action"""
        logger.debug(
            f"SelectAnyPlayer.execute: prompt='{self.prompt}', exclude_self={self.exclude_self}"
        )

        # Get all players
        all_players = context.game.players.copy()

        # Filter players
        eligible_players = self._filter_players(context, all_players)

        if not eligible_players:
            context.add_result("No eligible players to select")
            return ActionResult.CONDITION_NOT_MET

        # If only one eligible player, auto-select
        if len(eligible_players) == 1:
            selected_player = eligible_players[0]
            context.set_variable(self.store_result, selected_player.id)

            logger.info(
                f"{context.player.name} auto-selected {selected_player.name} (only eligible player)"
            )
            context.add_result(f"Auto-selected: {selected_player.name}")

            logger.debug(f"SelectAnyPlayer: Auto-selected {selected_player.name}")
            return ActionResult.SUCCESS

        # Create player selection interaction
        self._create_player_selection_interaction(context, eligible_players)

        logger.debug(f"SelectAnyPlayer: Requested interaction for {len(eligible_players)} players")
        return ActionResult.SUCCESS

    def _filter_players(self, context: ActionContext, players: list) -> list:
        """Filter players by eligibility criteria"""
        eligible = []

        for player in players:
            # Exclude self if requested
            if self.exclude_self and player.id == context.player.id:
                continue

            # Apply filter conditions if specified
            if self.filter:
                if not self._check_filter(context, player):
                    continue

            eligible.append(player)

        return eligible

    def _check_filter(self, context: ActionContext, player) -> bool:
        """Check if player meets filter criteria"""
        filter_type = self.filter.get("type") if isinstance(self.filter, dict) else None
        filter_value = self.filter.get("value") if isinstance(self.filter, dict) else None

        if filter_type == "has_card_age":
            # Player must have card of specific age
            age = int(filter_value) if filter_value else None
            if age:
                # Check hand
                for card in player.hand:
                    if card.age == age:
                        return True
                # Check board
                for color_stack in player.board.get_all_cards().values():
                    for card in color_stack:
                        if card.age == age:
                            return True
                return False

        elif filter_type == "has_achievement":
            # Player must have at least one achievement
            return len(player.achievements) > 0

        elif filter_type == "has_color":
            # Player must have cards of specific color on board
            color = str(filter_value) if filter_value else None
            if color:
                stack = player.board.get_cards_by_color(color)
                return len(stack) > 0
            return False

        elif filter_type == "min_score":
            # Player must have minimum score
            min_score = int(filter_value) if filter_value else 0
            current_score = player.get_score()
            return current_score >= min_score

        elif filter_type == "has_secret":
            # Player must have at least one secret in Safe (Unseen expansion)
            if hasattr(player, "safe") and player.safe:
                return player.safe.get_card_count() > 0
            return False

        # Unknown filter type or no filter - allow player
        return True

    def _create_player_selection_interaction(self, context: ActionContext, players: list):
        """Create player selection interaction using StandardInteractionBuilder"""
        # Build player options
        options = []
        for player in players:
            option = {
                "id": player.id,
                "label": player.name,
                "description": self._get_player_description(player)
            }
            options.append(option)

        # Create interaction using StandardInteractionBuilder
        interaction = StandardInteractionBuilder.select_from_options(
            player=context.player,
            prompt=self.prompt,
            options=options,
            min_selections=1,
            max_selections=1,
            store_result=self.store_result
        )

        # Set the interaction
        context.set_interaction(interaction)

        logger.debug(f"Created player selection interaction with {len(options)} options")

    def _get_player_description(self, player) -> str:
        """Get description for player option"""
        parts = []

        # Score
        score = player.get_score()
        parts.append(f"Score: {score}")

        # Achievements
        achievement_count = len(player.achievements)
        parts.append(f"Achievements: {achievement_count}")

        # Secrets (Unseen expansion)
        if hasattr(player, "safe") and player.safe:
            secret_count = player.safe.get_card_count()
            if secret_count > 0:
                parts.append(f"Secrets: {secret_count}")

        return " | ".join(parts)

    def get_required_fields(self) -> list[str]:
        return []

    def get_optional_fields(self) -> list[str]:
        return ["store_result", "prompt", "filter", "exclude_self"]
