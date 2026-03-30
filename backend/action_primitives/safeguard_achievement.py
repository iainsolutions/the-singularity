"""
SafeguardAchievement Action Primitive

Actively safeguard one or more achievements via dogma effect.
Part of the Unseen expansion mechanics.

This is different from the passive Safeguard keyword on cards:
- Safeguard keyword: Automatically safeguards when card is in Safe or visible on board
- SafeguardAchievement: Active dogma effect that safeguards achievements
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class SafeguardAchievement(ActionPrimitive):
    """
    Actively safeguard one or more achievements via dogma effect.

    This primitive adds the current player to the safeguard owners for
    specified achievement(s), preventing opponents from claiming them.

    Parameters:
    - achievement_type: Type of achievement to safeguard ("age", "score", "special")
    - value: The specific value (e.g., 4 for age 4, 15 for 15 points, "world" for World)
    - achievement_variable: Variable name containing achievement ID (alternative to type+value)
    - count: Optional number of achievements to safeguard (default: 1)
              For "all", use count=-1
    - store_result: Variable name to store safeguarded achievement IDs (default: "safeguarded_achievements")
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.achievement_type = config.get("achievement_type")
        self.value = config.get("value")
        self.achievement_variable = config.get("achievement_variable")
        self.count = config.get("count", 1)
        self.store_result = config.get("store_result", "safeguarded_achievements")

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the safeguard achievement action"""
        logger.debug(
            f"SafeguardAchievement.execute: type={self.achievement_type}, "
            f"value={self.value}, variable={self.achievement_variable}"
        )

        # Check if we're safeguarding by variable reference
        if self.achievement_variable:
            # Get achievement ID from variable
            achievement_id = context.get_variable(self.achievement_variable)
            if not achievement_id:
                context.add_result(f"No achievement found in variable: {self.achievement_variable}")
                return ActionResult.CONDITION_NOT_MET

            achievement_ids = [achievement_id] if isinstance(achievement_id, str) else list(achievement_id)

        else:
            # Validate parameters for type+value mode
            if not self.achievement_type:
                context.add_result("Error: achievement_type or achievement_variable required")
                return ActionResult.FAILURE

            if self.value is None:
                context.add_result("Error: value required when using achievement_type")
                return ActionResult.FAILURE

            # Get achievement IDs to safeguard
            achievement_ids = self._get_achievement_ids()

        if not achievement_ids:
            context.add_result(
                f"No achievements found for type={self.achievement_type}, value={self.value}"
            )
            return ActionResult.FAILURE

        # Limit by count if specified
        if self.count > 0 and len(achievement_ids) > self.count:
            achievement_ids = achievement_ids[: self.count]

        # Safeguard each achievement
        safeguarded_count = 0
        for achievement_id in achievement_ids:
            success = self._safeguard_achievement(context, achievement_id)
            if success:
                safeguarded_count += 1

        # Store result
        context.set_variable(self.store_result, achievement_ids)

        # Log result
        activity_logger.info(
            f"{context.player.name} safeguarded {safeguarded_count} achievement(s)"
        )
        context.add_result(f"Safeguarded {safeguarded_count} achievement(s)")

        logger.debug(
            f"SafeguardAchievement: Safeguarded {achievement_ids}"
        )
        return ActionResult.SUCCESS

    def _get_achievement_ids(self) -> list[str]:
        """
        Get achievement IDs based on type and value.

        Returns:
            List of achievement IDs (e.g., ["age_4"], ["score_15"], ["special_world"])
        """
        achievement_ids = []

        if self.achievement_type == "age":
            # Age-based achievement
            try:
                age = int(self.value)
                if 1 <= age <= 11:
                    achievement_ids.append(f"age_{age}")
            except (ValueError, TypeError):
                logger.error(f"Invalid age value: {self.value}")

        elif self.achievement_type == "score":
            # Score-based achievement
            try:
                score = int(self.value)
                achievement_ids.append(f"score_{score}")
            except (ValueError, TypeError):
                logger.error(f"Invalid score value: {self.value}")

        elif self.achievement_type == "special":
            # Special achievement (e.g., "world", "empire", "monument")
            achievement_ids.append(f"special_{self.value}")

        elif self.achievement_type == "all_age":
            # All age achievements
            achievement_ids = [f"age_{age}" for age in range(1, 12)]

        elif self.achievement_type == "all_score":
            # All score achievements (standard: 5, 10, 15, 20, 25, 30, 35, 40, 45, 50)
            achievement_ids = [f"score_{score}" for score in [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]]

        elif self.achievement_type == "all_special":
            # All special achievements (Monument, Empire, World, Wonder)
            achievement_ids = [
                "special_monument",
                "special_empire",
                "special_world",
                "special_wonder",
            ]

        elif self.achievement_type == "all":
            # All achievements
            achievement_ids = [f"age_{age}" for age in range(1, 12)]
            achievement_ids.extend([f"score_{score}" for score in [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]])
            achievement_ids.extend([
                "special_monument",
                "special_empire",
                "special_world",
                "special_wonder",
            ])

        return achievement_ids

    def _safeguard_achievement(
        self, context: ActionContext, achievement_id: str
    ) -> bool:
        """
        Safeguard a specific achievement for the current player.

        Args:
            context: Action context
            achievement_id: ID of achievement to safeguard

        Returns:
            True if safeguarded successfully
        """
        # Initialize active_safeguards if not present
        if not hasattr(context.game, "active_safeguards"):
            context.game.active_safeguards = {}

        # Get current safeguard owners for this achievement
        if achievement_id not in context.game.active_safeguards:
            context.game.active_safeguards[achievement_id] = set()

        # Add current player to safeguard owners
        context.game.active_safeguards[achievement_id].add(context.player.id)

        # Check if this creates a deadlock (multiple owners)
        owners = context.game.active_safeguards[achievement_id]
        is_deadlock = len(owners) > 1

        # Log safeguard activation
        logger.debug(
            f"Safeguarded {achievement_id} by {context.player.name} "
            f"(owners: {owners}, deadlock: {is_deadlock})"
        )

        # Activity log
        if is_deadlock:
            activity_logger.info(
                f"⚠️ Deadlock: {achievement_id} safeguarded by multiple players!"
            )
        else:
            activity_logger.info(
                f"🛡️ {context.player.name} safeguarded {achievement_id}"
            )

        return True

    def get_required_fields(self) -> list[str]:
        return []  # Either achievement_variable OR (achievement_type + value) required

    def get_optional_fields(self) -> list[str]:
        return ["achievement_type", "value", "achievement_variable", "count", "store_result"]
