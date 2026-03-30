"""
AchieveSecret Action Primitive

Achieves a secret card from the player's safe as an achievement.
Part of the Unseen expansion mechanics.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class AchieveSecret(ActionPrimitive):
    """
    Achieves a secret from the player's safe.

    Parameters:
    - secret_index: Index of secret in safe to achieve (0-based)
    - secret_age: Age of secret to achieve (alternative to index)
    - bypass_eligibility: If True, achieve regardless of eligibility (default: False)
    - store_result: Variable name to store the achieved card
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.secret_index = config.get("secret_index")
        self.secret_age = config.get("secret_age")
        self.bypass_eligibility = config.get("bypass_eligibility", False)
        self.store_result = config.get("store_result", "achieved_secret")

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the achieve secret action"""
        logger.debug(
            f"AchieveSecret.execute: index={self.secret_index}, "
            f"age={self.secret_age}, bypass={self.bypass_eligibility}"
        )

        # Check if player has a safe
        if not hasattr(context.player, "safe"):
            context.add_result("Player has no safe")
            return ActionResult.FAILURE

        safe = context.player.safe
        if not safe or len(safe) == 0:
            context.add_result("Player's safe is empty")
            return ActionResult.FAILURE

        # Find the secret to achieve
        secret_card = None
        secret_idx = None

        if self.secret_index is not None:
            # Resolve index from variable if needed
            idx = self.secret_index
            if isinstance(idx, str) and context.has_variable(idx):
                idx = context.get_variable(idx)

            try:
                idx = int(idx)
                if 0 <= idx < len(safe):
                    secret_card = safe[idx]
                    secret_idx = idx
                else:
                    context.add_result(f"Secret index {idx} out of range")
                    return ActionResult.FAILURE
            except (ValueError, TypeError):
                context.add_result(f"Invalid secret index: {idx}")
                return ActionResult.FAILURE

        elif self.secret_age is not None:
            # Find secret by age
            age = self.secret_age
            if isinstance(age, str) and context.has_variable(age):
                age = context.get_variable(age)

            try:
                age = int(age)
                for idx, card in enumerate(safe):
                    if card.age == age:
                        secret_card = card
                        secret_idx = idx
                        break

                if secret_card is None:
                    context.add_result(f"No secret of age {age} found in safe")
                    return ActionResult.FAILURE
            except (ValueError, TypeError):
                context.add_result(f"Invalid secret age: {age}")
                return ActionResult.FAILURE
        else:
            context.add_result("Must specify either secret_index or secret_age")
            return ActionResult.FAILURE

        # Check eligibility unless bypassed
        if not self.bypass_eligibility:
            # Check if the secret's age matches an available achievement
            if not self._is_achievement_available(context, secret_card.age):
                context.add_result(
                    f"Achievement age {secret_card.age} is not available"
                )
                return ActionResult.CONDITION_NOT_MET

        # Remove secret from safe
        safe.pop(secret_idx)

        # Add to player's achievements
        if not hasattr(context.player, "achievements"):
            context.player.achievements = []

        context.player.achievements.append(secret_card)

        # Store result
        context.set_variable(self.store_result, secret_card)

        # Log the achievement
        activity_logger.info(
            f"{context.player.name} achieves secret {secret_card.name} (age {secret_card.age})"
        )
        context.add_result(
            f"Achieved secret: {secret_card.name} (age {secret_card.age})"
        )

        # Check victory condition
        self._check_victory(context)

        logger.debug(f"AchieveSecret: Successfully achieved {secret_card.name}")
        return ActionResult.SUCCESS

    def _is_achievement_available(self, context: ActionContext, age: int) -> bool:
        """Check if an achievement of the given age is available"""
        if not hasattr(context.game, "achievement_cards"):
            return False

        # Check if there's an achievement card for this age
        if age in context.game.deck_manager.achievement_cards:
            achievements = context.game.deck_manager.achievement_cards[age]
            return len(achievements) > 0

        return False

    def _check_victory(self, context: ActionContext):
        """Check if achieving this secret triggers victory"""
        if not hasattr(context.player, "achievements"):
            return

        achievement_count = len(context.player.achievements)

        # Standard victory: 6 or more achievements
        if achievement_count >= 6:
            from models.game import GamePhase

            context.game.winner = context.player
            context.game.phase = GamePhase.FINISHED

            activity_logger.info(
                f"🏆 {context.player.name} wins by achieving 6+ achievements!"
            )
            context.add_result(f"{context.player.name} wins the game!")
            logger.info(
                f"Victory triggered for {context.player.name} with {achievement_count} achievements"
            )

    def get_required_fields(self) -> list[str]:
        return []

    def get_optional_fields(self) -> list[str]:
        return ["secret_index", "secret_age", "bypass_eligibility", "store_result"]
