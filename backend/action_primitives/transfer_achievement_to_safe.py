"""
TransferAchievementToSafe Action Primitive

Transfer an achievement card from a player's achievements to another player's Safe.
Part of the Unseen expansion mechanics.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class TransferAchievementToSafe(ActionPrimitive):
    """
    Transfer an achievement from source player to target player's Safe.

    This primitive removes an achievement from a player's claimed achievements
    and adds it to another player's Safe as a secret.

    Parameters:
    - achievement_id: ID of achievement to transfer (e.g., "age_5")
    - achievement_variable: Variable containing achievement ID
    - source_player: Which player loses the achievement ("opponent", "self", "selected_player")
    - target_player: Which player's Safe gets the achievement ("self", "opponent", "selected_player")
    - store_result: Variable name to store transferred achievement
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.achievement_id = config.get("achievement_id")
        self.achievement_variable = config.get("achievement_variable")
        self.source_player = config.get("source_player", "opponent")
        self.target_player = config.get("target_player", "self")
        self.store_result = config.get("store_result", "transferred_achievement")

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the transfer achievement to safe action"""
        logger.debug(
            f"TransferAchievementToSafe.execute: source={self.source_player}, "
            f"target={self.target_player}"
        )

        # Get achievement ID
        if self.achievement_variable:
            achievement_id = context.get_variable(self.achievement_variable)
        elif self.achievement_id:
            achievement_id = self.achievement_id
        else:
            context.add_result("Error: No achievement specified")
            return ActionResult.FAILURE

        if not achievement_id:
            context.add_result("Error: Achievement ID is empty")
            return ActionResult.FAILURE

        # Get source player
        if self.source_player == "opponent":
            source_player = context.target_player or context.get_opponent()
        elif self.source_player == "selected_player":
            selected_id = context.get_variable("selected_player")
            source_player = context.game.get_player_by_id(selected_id) if selected_id else None
        else:
            source_player = context.player

        # Get target player
        if self.target_player == "opponent":
            target_player = context.target_player or context.get_opponent()
        elif self.target_player == "selected_player":
            selected_id = context.get_variable("selected_player")
            target_player = context.game.get_player_by_id(selected_id) if selected_id else None
        else:
            target_player = context.player

        if not source_player or not target_player:
            context.add_result("Error: Invalid source or target player")
            return ActionResult.FAILURE

        # Check source has the achievement
        if not hasattr(source_player, "achievements"):
            context.add_result(f"{source_player.name} has no achievements")
            return ActionResult.CONDITION_NOT_MET

        achievement_card = None
        for ach in source_player.achievements:
            if getattr(ach, 'card_id', None) == achievement_id or getattr(ach, 'name', None) == achievement_id:
                achievement_card = ach
                break

        if not achievement_card:
            context.add_result(f"{source_player.name} does not have achievement {achievement_id}")
            return ActionResult.CONDITION_NOT_MET

        # Ensure target has Safe
        if not hasattr(target_player, "safe") or not target_player.safe:
            context.add_result(f"{target_player.name} has no Safe (Unseen expansion required)")
            return ActionResult.FAILURE

        # Remove from source achievements
        source_player.achievements.remove(achievement_card)

        # Add to target Safe
        target_player.safe.add_secret(achievement_card)

        # Store result
        context.set_variable(self.store_result, achievement_card)

        activity_logger.info(
            f"🔄 {source_player.name}'s achievement {achievement_card.name} "
            f"transferred to {target_player.name}'s Safe"
        )

        context.add_result(
            f"Transferred {achievement_card.name} from {source_player.name}'s achievements "
            f"to {target_player.name}'s Safe"
        )

        return ActionResult.SUCCESS

    def get_required_fields(self) -> list[str]:
        """Either achievement_id or achievement_variable is required"""
        return []

    def get_optional_fields(self) -> list[str]:
        return ["achievement_id", "achievement_variable", "source_player", "target_player", "store_result"]
