"""
AchievementEffectAdapter - Specialized adapter for achievement-related effects.

This adapter handles effects that interact with achievements:
- Claiming achievements (ClaimAchievement) - validates requirements and executes claims
- Making achievements available (MakeAvailable) - controls achievement availability
- Achievement conditions (HasAchievement, CanClaim) - checks achievement states

These effects require special handling for:
- Achievement eligibility validation
- Victory condition checking
- Achievement state synchronization
- Proper rule compliance for achievement requirements
"""

import logging
from typing import Any, ClassVar

from action_primitives import ActionResult, create_action_primitive
from action_primitives.base import ActionContext

from ..core.context import DogmaContext
from .base import Effect, EffectResult, EffectType

logger = logging.getLogger(__name__)


class AchievementEffectAdapter(Effect):
    """
    Specialized adapter for achievement-related effects.

    This adapter:
    1. Validates achievement requirements before claims
    2. Checks victory conditions after achievement changes
    3. Synchronizes achievement state across players
    4. Ensures compliance with Innovation achievement rules
    """

    # Effects that this adapter handles
    ACHIEVEMENT_EFFECTS: ClassVar[set[str]] = {"ClaimAchievement", "MakeAvailable"}

    # Achievement condition effects for validation
    ACHIEVEMENT_CONDITIONS: ClassVar[set[str]] = {
        "HasAchievement",
        "CanClaim",
        "AchievementCount",
    }

    # All achievement-related effects
    ALL_ACHIEVEMENT_EFFECTS = ACHIEVEMENT_EFFECTS | ACHIEVEMENT_CONDITIONS

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the achievement effect adapter.

        Args:
            config: Effect configuration from card JSON
        """
        super().__init__(config)
        self.type = EffectType.ACHIEVEMENT
        self.primitive = None
        self._init_primitive()

    def _init_primitive(self):
        """Initialize the wrapped primitive."""
        try:
            self.primitive = create_action_primitive(self.config)
        except Exception as e:
            logger.error(f"Failed to create achievement primitive: {e}")
            self.primitive = None

    def execute(self, context: DogmaContext) -> EffectResult:
        """
        Execute the achievement effect.

        This handles:
        1. Pre-claim validation for achievement requirements
        2. Achievement execution with proper state tracking
        3. Post-claim victory condition checking
        4. Achievement state synchronization

        Args:
            context: The dogma execution context

        Returns:
            EffectResult with achievement changes and victory status
        """
        if not self.primitive:
            return EffectResult(
                success=False, error="Failed to initialize achievement primitive"
            )

        effect_type = self.config.get("type", "")
        logger.debug(f"Executing achievement effect: {effect_type}")

        # Pre-execution validation
        validation_result = self._pre_achievement_validation(context)
        if not validation_result.success:
            return validation_result

        # Store pre-execution achievement state
        pre_state = self._capture_achievement_state(context)

        # Create action context
        action_context = self._create_action_context(context)

        try:
            # Execute the primitive
            result = self.primitive.execute(action_context)

            # Translate result with achievement-specific enhancements
            effect_result = self._translate_result(result, action_context, context)

            # Post-achievement processing
            self._post_achievement_processing(effect_result, context, pre_state)

            return effect_result

        except Exception as e:
            logger.error(f"Error executing achievement effect: {e}", exc_info=True)
            return EffectResult(success=False, error=f"Achievement effect failed: {e}")

    def _pre_achievement_validation(self, context: DogmaContext) -> EffectResult:
        """
        Validate conditions before achievement operations.

        Args:
            context: The dogma context

        Returns:
            EffectResult indicating if operation can proceed
        """
        effect_type = self.config.get("type", "")

        if effect_type == "ClaimAchievement":
            # Validate achievement specification
            achievement_spec = self.config.get("achievement")
            if not achievement_spec:
                return EffectResult(
                    success=False,
                    error="ClaimAchievement requires 'achievement' specification",
                )

            # Check if achievement exists and is available
            if isinstance(achievement_spec, dict):
                max_age = achievement_spec.get("max_age")
                if max_age is not None and not isinstance(max_age, int):
                    return EffectResult(
                        success=False, error="Achievement max_age must be an integer"
                    )

        elif effect_type == "MakeAvailable":
            # Validate achievement to make available
            achievement_name = self.config.get("achievement_name")
            if not achievement_name:
                return EffectResult(
                    success=False, error="MakeAvailable requires 'achievement_name'"
                )

        return EffectResult(success=True)

    def _capture_achievement_state(self, context: DogmaContext) -> dict[str, Any]:
        """
        Capture current achievement state for change tracking.

        Args:
            context: The dogma context

        Returns:
            Dictionary representing current achievement state
        """
        player = context.current_player
        state = {
            "player_achievements": len(player.achievements)
            if hasattr(player, "achievements")
            else 0,
            "available_achievements": [],
        }

        # Capture available achievements if game has them
        if hasattr(context.game, "achievements"):
            for age, achievement in context.game.achievements.items():
                if achievement and not achievement.claimed:
                    state["available_achievements"].append(age)

        return state

    def _create_action_context(self, context: DogmaContext) -> ActionContext:
        """Create ActionContext from DogmaContext."""
        return ActionContext(
            game=context.game,
            player=context.current_player,
            card=context.card,
            variables=dict(context.variables),
            results=[],
            state_tracker=context.state_tracker,
            sharing=context.sharing,  # Pass sharing context through
        )

    def _translate_result(
        self,
        primitive_result: ActionResult,
        action_context: ActionContext,
        dogma_context: DogmaContext,
    ) -> EffectResult:
        """
        Translate primitive result with achievement-specific enhancements.

        Args:
            primitive_result: Raw result from primitive
            action_context: Context after execution
            dogma_context: Original dogma context

        Returns:
            Enhanced EffectResult
        """
        success = primitive_result == ActionResult.SUCCESS

        # Extract achievement changes
        achievement_changes = self._extract_achievement_changes(action_context)

        # Check for interaction requirements
        requires_interaction = primitive_result == ActionResult.REQUIRES_INTERACTION
        interaction_request = None
        if requires_interaction:
            interaction_request = action_context.variables.get(
                "final_interaction_request"
            )

        # Build enhanced result
        effect_result = EffectResult(
            success=success,
            requires_interaction=requires_interaction,
            interaction_request=interaction_request,
            variables=dict(action_context.variables),
            results=list(action_context.results),
        )

        # Add achievement change metadata
        if achievement_changes:
            effect_result.variables.update(achievement_changes)

        return effect_result

    def _extract_achievement_changes(
        self, action_context: ActionContext
    ) -> dict[str, Any]:
        """
        Extract achievement changes from action context.

        Args:
            action_context: The action context after execution

        Returns:
            Dictionary of achievement changes
        """
        changes = {}
        effect_type = self.config.get("type", "")

        if effect_type == "ClaimAchievement":
            # Track claimed achievements
            for result in action_context.results:
                if "claimed" in result.lower() or "achievement" in result.lower():
                    changes["achievement_claimed"] = True
                    # Try to extract achievement details from result
                    if "age" in result.lower():
                        # Extract age if mentioned in result
                        words = result.split()
                        for i, word in enumerate(words):
                            if word.lower() == "age" and i + 1 < len(words):
                                try:
                                    age = int(words[i + 1])
                                    changes["claimed_achievement_age"] = age
                                    break
                                except ValueError:
                                    pass
                    break

        elif effect_type == "MakeAvailable":
            # Track achievements made available
            achievement_name = self.config.get("achievement_name", "unknown")
            changes["achievement_made_available"] = achievement_name
            changes["availability_changed"] = True

        return changes

    def _post_achievement_processing(
        self,
        effect_result: EffectResult,
        context: DogmaContext,
        pre_state: dict[str, Any],
    ):
        """
        Handle post-achievement processing.

        Args:
            effect_result: The effect result
            context: The dogma context
            pre_state: Achievement state before execution
        """
        if not effect_result.success:
            return

        effect_type = self.config.get("type", "")
        player = context.current_player

        # Check for victory conditions after achievement changes
        if effect_type == "ClaimAchievement" and effect_result.variables.get(
            "achievement_claimed"
        ):
            # Count player achievements
            achievement_count = (
                len(player.achievements) if hasattr(player, "achievements") else 0
            )
            old_count = pre_state.get("player_achievements", 0)

            if achievement_count > old_count:
                context.variables["achievement_count_changed"] = True
                context.variables["new_achievement_count"] = achievement_count

                # Check victory condition (6 achievements)
                if achievement_count >= 6:
                    effect_result.variables["victory_condition_met"] = True
                    effect_result.variables["victory_type"] = "achievement"
                    logger.info(
                        f"{player.name} achieved victory with {achievement_count} achievements!"
                    )

                # Log significant achievement milestones
                if achievement_count in [3, 4, 5]:
                    logger.info(
                        f"{player.name} now has {achievement_count} achievements"
                    )

        # Update achievement tracking variables
        if effect_type == "MakeAvailable":
            achievement_name = self.config.get("achievement_name", "unknown")
            available_achievements = context.variables.get("available_achievements", [])
            if achievement_name not in available_achievements:
                available_achievements.append(achievement_name)
                context.variables["available_achievements"] = available_achievements

        # Log achievement results
        if effect_result.results:
            logger.info(
                f"Achievement effect completed: {'; '.join(effect_result.results)}"
            )

    def validate(self) -> tuple[bool, str | None]:
        """
        Validate achievement effect configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        effect_type = self.config.get("type", "")

        # Check if this is an achievement effect
        if effect_type not in self.ALL_ACHIEVEMENT_EFFECTS:
            return False, f"Not an achievement effect: {effect_type}"

        # Validate based on effect type
        if effect_type == "ClaimAchievement":
            # Requires achievement specification
            if "achievement" not in self.config:
                return False, "ClaimAchievement missing 'achievement' specification"

            achievement = self.config.get("achievement")
            if isinstance(achievement, dict):
                # Validate achievement criteria
                if "max_age" in achievement:
                    max_age = achievement["max_age"]
                    if not isinstance(max_age, int) or max_age < 1 or max_age > 10:
                        return False, f"Invalid max_age for achievement: {max_age}"

        elif effect_type == "MakeAvailable":
            # Requires achievement name
            if "achievement_name" not in self.config:
                return False, "MakeAvailable missing 'achievement_name'"

        elif effect_type in self.ACHIEVEMENT_CONDITIONS:
            # Achievement conditions may have different requirements
            if effect_type == "HasAchievement" and (
                "achievement_name" not in self.config
                and "achievement_age" not in self.config
            ):
                return (
                    False,
                    "HasAchievement requires 'achievement_name' or 'achievement_age'",
                )

        # Check primitive initialization
        if not self.primitive:
            return False, "Failed to create achievement primitive"

        return True, None

    def get_description(self) -> str:
        """Get human-readable description of the achievement effect."""
        if "description" in self.config:
            return self.config["description"]

        effect_type = self.config.get("type", "achievement")

        # Generate meaningful descriptions
        if effect_type == "ClaimAchievement":
            achievement = self.config.get("achievement", {})
            if isinstance(achievement, dict):
                max_age = achievement.get("max_age")
                if max_age:
                    return f"Claim achievement (max age {max_age})"
                criteria = achievement.get("criteria", "achievement")
                return f"Claim achievement: {criteria}"
            return f"Claim achievement: {achievement}"

        elif effect_type == "MakeAvailable":
            achievement_name = self.config.get("achievement_name", "achievement")
            return f"Make {achievement_name} achievement available"

        elif effect_type == "HasAchievement":
            achievement_name = self.config.get("achievement_name")
            achievement_age = self.config.get("achievement_age")
            if achievement_name:
                return f"Check if has {achievement_name} achievement"
            elif achievement_age:
                return f"Check if has age {achievement_age} achievement"
            return "Check achievement ownership"

        elif effect_type == "CanClaim":
            achievement = self.config.get("achievement", "achievement")
            return f"Check if can claim {achievement}"

        elif effect_type == "AchievementCount":
            min_count = self.config.get("min_count", 1)
            return f"Check achievement count (min {min_count})"

        return f"{effect_type} effect"
