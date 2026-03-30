"""SelectAchievement Action Primitive.

Selects available achievement cards.
"""

import logging
from typing import Any

from interaction.builder import StandardInteractionBuilder
from logging_config import EventType, activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult
from .utils import attach_player_to_interaction

logger = logging.getLogger(__name__)


class SelectAchievement(ActionPrimitive):
    """Select achievement cards that are available (not claimed).

    Parameters:
    - max_age: Maximum age of achievements to select (optional)
    - min_age: Minimum age of achievements to select (optional)
    - count: Number of achievements to select (default: 1)
    - is_optional: Whether selection is optional (default: False)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.max_age = config.get("max_age")
        self.min_age = config.get("min_age", 1)
        self.count = config.get("count", 1)
        self.is_optional = config.get("is_optional", False)
        # Support both 'store_as' and 'store_result' naming
        self.store_var = (
            config.get("store_as")
            or config.get("store_result")
            or ("selected_achievements" if self.count != 1 else "selected_achievement")
        )

    def execute(self, context: ActionContext) -> ActionResult:
        """Select available achievements."""

        # COMPREHENSIVE DEBUG LOGGING
        logger.debug("===== SelectAchievement")
        logger.info(f"Context has these variables: {list(context.variables.keys())}")
        logger.info("Checking for resume indicators:")
        logger.info(
            f"- has_variable('chosen_option'): {context.has_variable('chosen_option')}"
        )
        logger.info(
            f"- has_variable('selected_achievements'): {context.has_variable('selected_achievements')}"
        )

        if context.has_variable("chosen_option"):
            logger.info(
                f"- chosen_option value: {context.get_variable('chosen_option')}"
            )
        if context.has_variable("selected_achievements"):
            val = context.get_variable("selected_achievements")
            logger.info(f"- selected_achievements value: {val} (type: {type(val)})")
            if isinstance(val, list):
                logger.info(f"- selected_achievements is list with length: {len(val)}")

        # Check if player explicitly declined (declarative pattern)
        if context.has_variable("decline") and context.get_variable("decline"):
            logger.debug(
                "SelectAchievement: Player explicitly declined (decline=true), returning SUCCESS"
            )
            context.add_result("Player declined achievement selection")
            context.set_variable(self.store_var, None)
            context.set_variable("selected_achievements", [])
            context.set_variable("selected_cards", [])
            return ActionResult.SUCCESS

        # UI/Player sends selected_achievements directly in context
        if context.has_variable("selected_achievements"):
            selected_achievements_response = context.get_variable(
                "selected_achievements"
            )
            # Only process if it's a non-empty list
            if (
                isinstance(selected_achievements_response, list)
                and len(selected_achievements_response) > 0
            ):
                logger.debug(
                    f"SelectAchievement: Resuming from interaction, selected_achievements={selected_achievements_response}"
                )

                # Player selected achievement(s) - get the achievement name/ID
                first_item = selected_achievements_response[0]
                if isinstance(first_item, str):
                    achievement_id = first_item
                elif hasattr(first_item, "name"):
                    # It's already a Card object from prior processing
                    achievement_id = first_item.name
                else:
                    # It's a dict from UI/AI response
                    achievement_id = first_item.get("id") or first_item.get("name")

                # Find the selected achievement in game state
                selected_achievement = None
                for age, achievements in context.game.deck_manager.achievement_cards.items():
                    for achievement in achievements:
                        if achievement.name == achievement_id:
                            selected_achievement = achievement
                            break
                    if selected_achievement:
                        break

                if selected_achievement:
                    selected = [selected_achievement]
                    context.set_variable(
                        self.store_var,
                        selected[0]
                        if self.store_var.endswith("_achievement")
                        else selected,
                    )
                    context.set_variable("selected_achievements", selected)
                    context.set_variable("selected_cards", selected)
                    context.add_result(
                        f"Selected achievement: {selected_achievement.name}"
                    )
                    logger.debug(
                        f"SelectAchievement: Stored selected achievement in {self.store_var}"
                    )
                    return ActionResult.SUCCESS
                else:
                    logger.error(
                        f"SelectAchievement: Could not find selected achievement: {achievement_id}"
                    )
                    return ActionResult.FAILURE

        # IDEMPOTENCY CHECK - Skip if already executed AND not resuming
        # Must check AFTER resume logic to avoid blocking legitimate resume processing
        logger.info(f"🔒 IDEMPOTENCY CHECK: Looking for variable '{self.store_var}'")
        if context.has_variable(self.store_var):
            value = context.get_variable(self.store_var)
            logger.info(
                f"🔒 IDEMPOTENCY CHECK: Found {self.store_var} = {value} - SKIPPING execution"
            )
            return ActionResult.SUCCESS
        else:
            logger.info(
                f"🔒 IDEMPOTENCY CHECK: Variable '{self.store_var}' NOT found - proceeding with execution"
            )

        # Get available achievements
        available = []

        logger.debug(
            f"SelectAchievement: Starting execution - min_age={self.min_age}, max_age={self.max_age}, count={self.count}, is_optional={self.is_optional}"
        )

        for age, achievements in context.game.deck_manager.achievement_cards.items():
            # Check age limits
            if self.min_age and age < self.min_age:
                logger.debug(
                    f"SelectAchievement: Skipping age {age} (below min_age {self.min_age})"
                )
                continue
            if self.max_age and age > self.max_age:
                logger.debug(
                    f"SelectAchievement: Skipping age {age} (above max_age {self.max_age})"
                )
                continue

            logger.debug(
                f"SelectAchievement: Checking age {age} with {len(achievements)} achievement(s)"
            )

            # Add unclaimed achievements
            for achievement in achievements:
                # Check if already claimed by any player
                claimed = False
                for player in context.game.players:
                    if achievement in player.achievements:
                        claimed = True
                        break

                if not claimed:
                    available.append(achievement)
                    logger.debug(
                        f"SelectAchievement: Added available achievement: {achievement.name} (age {age})"
                    )
                else:
                    logger.debug(
                        f"SelectAchievement: Skipping claimed achievement: {achievement.name} (age {age})"
                    )

        logger.debug(
            f"SelectAchievement: Found {len(available)} available achievement(s)"
        )

        if not available:
            if self.is_optional:
                logger.debug(
                    "SelectAchievement: No achievements available, is_optional=True - returning SUCCESS"
                )
                context.add_result("No achievements available to select")
                context.set_variable(
                    self.store_var, None
                )  # Set configured store variable
                context.set_variable("selected_achievements", [])
                context.set_variable("selected_cards", [])  # Also clear selected_cards
                return ActionResult.SUCCESS
            else:
                logger.debug(
                    "SelectAchievement: No achievements available, is_optional=False - returning FAILURE"
                )
                context.add_result("No achievements available")
                return ActionResult.FAILURE

        # If count is 1 and only 1 available, auto-select
        if self.count == 1 and len(available) == 1:
            logger.debug(
                f"SelectAchievement: Auto-selecting single achievement: {available[0].name}"
            )
            selected = [available[0]]
            # Store under configured store variable; if storing a single value, store the single element
            context.set_variable(
                self.store_var,
                selected[0] if self.store_var.endswith("_achievement") else selected,
            )
            # Maintain compatibility
            context.set_variable("selected_achievements", selected)
            context.set_variable("selected_cards", selected)
            context.add_result(f"Selected achievement: {selected[0].name}")
            return ActionResult.SUCCESS

        # If multiple available, need player interaction
        logger.debug(
            f"SelectAchievement: Checking interaction condition: len(available)={len(available)}, count={self.count}, is_optional={self.is_optional}"
        )
        logger.debug(
            f"SelectAchievement: Condition parts: len(available) >= count = {len(available) >= self.count}, len(available) > 1 = {len(available) > 1}, is_optional = {self.is_optional}"
        )
        if len(available) >= self.count and (len(available) > 1 or self.is_optional):
            logger.debug("SelectAchievement: Interaction required - building request")

            eligible_achievements = [
                {"id": a.name, "name": a.name, "age": getattr(a, "age", 0)}
                for a in available
            ]

            # Create message (decline instructions are in AI system prompt)
            if self.is_optional:
                message = f"Select {self.count} achievement(s) or decline"
            else:
                message = f"Select {self.count} achievement(s)"

            interaction_request = (
                StandardInteractionBuilder.create_achievement_selection_request(
                    eligible_achievements=eligible_achievements,
                    message=message,
                    is_optional=self.is_optional,
                    store_result=self.store_var,
                    execution_results=list(context.results)
                    if context.results
                    else None,
                )
            )

            # Use the player from context - phase layer has already set the correct player
            target_player_id = getattr(context.player, "id", None)
            logger.debug(f"SelectAchievement: Targeting player {context.player.name}")

            interaction_request = attach_player_to_interaction(
                interaction_request,
                target_player_id,
                getattr(context.game, "game_id", None),
            )

            context.set_variable("final_interaction_request", interaction_request)

            # Activity log: achievement selection interaction
            try:
                if activity_logger:
                    game_id = getattr(context.game, "game_id", None)
                    player_id = getattr(context.player, "id", None)

                    # Construct human-readable message
                    age_range = (
                        f"ages {self.min_age}-{self.max_age}"
                        if self.max_age
                        else f"age {self.min_age}+"
                    )
                    if self.is_optional:
                        msg = f"Select up to {self.count} achievement(s) ({age_range}, optional)"
                    else:
                        msg = f"Select {self.count} achievement(s) ({age_range})"

                    activity_logger.log_game_event(
                        event_type=EventType.DOGMA_CARD_SELECTION,
                        game_id=str(game_id) if game_id else "test-game",
                        player_id=str(player_id) if player_id else None,
                        data={
                            "interaction": "select_achievement",
                            "eligible_count": len(eligible_achievements),
                            "min_age": self.min_age,
                            "max_age": self.max_age,
                            "count": self.count,
                            "is_optional": bool(self.is_optional),
                        },
                        message=msg,
                    )
            except Exception:
                pass
            return ActionResult.REQUIRES_INTERACTION
        else:
            # Only auto-select if not optional and we have exact count
            if not self.is_optional and len(available) == self.count:
                context.set_variable("selected_achievements", available)
                context.set_variable("selected_cards", available)
                for achievement in available:
                    context.add_result(f"Selected achievement: {achievement.name}")
                return ActionResult.SUCCESS
            else:
                # Still need interaction for optional selections

                logger.debug("SelectAchievement optional selection - building request")
                eligible_achievements = [
                    {"id": a.name, "name": a.name, "age": getattr(a, "age", 0)}
                    for a in available
                ]

                # Create message (decline instructions are in AI system prompt)
                message = f"Select {self.count} achievement(s) or decline"

                interaction_request = (
                    StandardInteractionBuilder.create_achievement_selection_request(
                        eligible_achievements=eligible_achievements,
                        message=message,
                        is_optional=True,
                        store_result=self.store_var,
                        execution_results=list(context.results)
                        if context.results
                        else None,
                    )
                )

                # Use the player from context - phase layer has already set the correct player
                target_player_id = getattr(context.player, "id", None)
                logger.debug(
                    f"SelectAchievement: Targeting player {context.player.name}"
                )

                interaction_request = attach_player_to_interaction(
                    interaction_request,
                    target_player_id,
                    getattr(context.game, "game_id", None),
                )

                context.set_variable("final_interaction_request", interaction_request)
                return ActionResult.REQUIRES_INTERACTION
