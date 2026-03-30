"""
TransferSecret Action Primitive

Transfer a secret from one player's Safe to another location.
Part of the Unseen expansion mechanics.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class TransferSecret(ActionPrimitive):
    """
    Transfer a secret from one player's Safe to another location.

    This primitive removes a secret from a player's Safe and moves it to
    a specified target location (achievements, opponent's safe, score pile, etc.).

    Parameters:
    - source_player: Which player's Safe to transfer from ("self", "opponent", "selected_player")
    - secret_index: Position in Safe (0-based, or "highest", "lowest", "random")
    - secret_age: Alternative to index - find secret by age
    - target: Where to transfer the secret ("achievements", "opponent_safe", "score_pile", "hand", "junk")
    - target_player: Which player gets the secret (for target="opponent_safe", "score_pile", etc.)
    - reveal: If True, reveal card identity when transferring (default: False keeps it hidden)
    - store_result: Variable name to store transferred card
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.source_player = config.get("source_player", "opponent")
        self.secret_index = config.get("secret_index", 0)
        self.secret_age = config.get("secret_age")
        self.target = config.get("target", "achievements")
        self.target_player = config.get("target_player", "self")
        self.reveal = config.get("reveal", False)
        self.store_result = config.get("store_result", "transferred_secret")

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the transfer secret action"""
        logger.debug(
            f"TransferSecret.execute: source={self.source_player}, "
            f"target={self.target}, reveal={self.reveal}"
        )

        # Get source player
        if self.source_player == "opponent":
            source_player = context.target_player or context.get_opponent()
        elif self.source_player == "selected_player":
            selected_id = context.get_variable("selected_player")
            source_player = context.game.get_player_by_id(selected_id) if selected_id else None
        else:
            source_player = context.player

        if not source_player:
            context.add_result("Error: No source player found")
            return ActionResult.FAILURE

        # Check if source player has Safe with secrets
        if not hasattr(source_player, "safe") or not source_player.safe:
            context.add_result(f"{source_player.name} has no Safe")
            return ActionResult.CONDITION_NOT_MET

        if source_player.safe.get_card_count() == 0:
            context.add_result(f"{source_player.name}'s Safe is empty")
            return ActionResult.CONDITION_NOT_MET

        # Determine secret index
        index = self._resolve_secret_index(context, source_player)

        if index is None or index < 0 or index >= source_player.safe.get_card_count():
            context.add_result(f"Invalid secret index: {index}")
            return ActionResult.FAILURE

        # Remove secret from source Safe
        try:
            from game_logic.unseen.safe_manager import SafeManager
            safe_manager = SafeManager(context.game)
            secret_card = safe_manager.remove_card_from_safe(source_player.id, index)
        except Exception as e:
            logger.error(f"Failed to remove secret from Safe: {e}")
            context.add_result(f"Error removing secret from Safe")
            return ActionResult.FAILURE

        # Get target player
        if self.target_player == "opponent":
            target_player = context.target_player or context.get_opponent()
        elif self.target_player == "selected_player":
            selected_id = context.get_variable("selected_player")
            target_player = context.game.get_player_by_id(selected_id) if selected_id else None
        else:
            target_player = context.player

        if not target_player:
            context.add_result("Error: No target player found")
            # Put card back in Safe
            source_player.safe.add_card(secret_card)
            return ActionResult.FAILURE

        # Transfer to target location
        success = self._transfer_to_target(
            context, secret_card, target_player
        )

        if not success:
            # Put card back in Safe
            source_player.safe.add_card(secret_card)
            return ActionResult.FAILURE

        # Store result
        context.set_variable(self.store_result, secret_card)

        # Log result
        if self.reveal:
            activity_logger.info(
                f"{context.player.name} transferred {secret_card.name} "
                f"from {source_player.name}'s Safe to {self.target}"
            )
            context.add_result(
                f"Transferred {secret_card.name} to {self.target}"
            )
        else:
            activity_logger.info(
                f"{context.player.name} transferred a secret (age {secret_card.age}) "
                f"from {source_player.name}'s Safe to {self.target}"
            )
            context.add_result(
                f"Transferred secret (age {secret_card.age}) to {self.target}"
            )

        # Update Safeguards (card removed from Safe)
        if context.game.expansion_config.is_enabled("unseen"):
            try:
                from game_logic.unseen.safeguard_tracker import SafeguardTracker
                tracker = SafeguardTracker(context.game)
                tracker.rebuild_all_safeguards()
            except ImportError:
                pass

        logger.debug(f"TransferSecret: Transferred {secret_card.name}")
        return ActionResult.SUCCESS

    def _resolve_secret_index(self, context: ActionContext, source_player) -> int | None:
        """Resolve secret index from various formats"""
        # If secret_age specified, find by age
        if self.secret_age is not None:
            age = self.secret_age
            if isinstance(age, str) and context.has_variable(age):
                age = context.get_variable(age)

            try:
                age = int(age)
                secret_ages = source_player.safe.get_secret_ages()
                for idx, secret_age in enumerate(secret_ages):
                    if secret_age == age:
                        return idx
                # Age not found
                return None
            except (ValueError, TypeError):
                return None

        # Resolve index
        index = self.secret_index

        if isinstance(index, str):
            if index == "highest":
                # Highest age secret
                secret_ages = source_player.safe.get_secret_ages()
                if secret_ages:
                    max_age = max(secret_ages)
                    return secret_ages.index(max_age)
                return None
            elif index == "lowest":
                # Lowest age secret
                secret_ages = source_player.safe.get_secret_ages()
                if secret_ages:
                    min_age = min(secret_ages)
                    return secret_ages.index(min_age)
                return None
            elif index == "random":
                # Random secret
                import random
                count = source_player.safe.get_card_count()
                return random.randint(0, count - 1) if count > 0 else None
            elif context.has_variable(index):
                # Variable reference
                index = context.get_variable(index)

        try:
            return int(index)
        except (ValueError, TypeError):
            return None

    def _transfer_to_target(
        self, context: ActionContext, card, target_player
    ) -> bool:
        """Transfer card to target location"""
        if self.target == "achievements":
            # Add to achievements
            if not hasattr(target_player, "achievements"):
                target_player.achievements = []
            target_player.achievements.append(card.age)

            # Check victory condition
            if len(target_player.achievements) >= 6:
                from models.game import GamePhase
                context.game.winner = target_player
                context.game.phase = GamePhase.FINISHED
                activity_logger.info(
                    f"🏆 {target_player.name} wins by achieving 6+ achievements!"
                )

            return True

        elif self.target == "opponent_safe" or self.target == "safe":
            # Add to target player's Safe
            if not hasattr(target_player, "safe") or not target_player.safe:
                from models.safe import Safe
                target_player.safe = Safe(player_id=target_player.id)

            try:
                target_player.safe.add_card(card)
                return True
            except Exception as e:
                logger.error(f"Failed to add to Safe: {e}")
                return False

        elif self.target == "score_pile":
            # Add to score pile
            target_player.score_pile.append(card)
            return True

        elif self.target == "hand":
            # Add to hand
            target_player.hand.append(card)
            return True

        elif self.target == "junk":
            # Junk the card (remove from game)
            # Card is simply not added anywhere
            return True

        else:
            context.add_result(f"Unknown target: {self.target}")
            return False

    def get_required_fields(self) -> list[str]:
        return ["target"]

    def get_optional_fields(self) -> list[str]:
        return [
            "source_player",
            "secret_index",
            "secret_age",
            "target_player",
            "reveal",
            "store_result"
        ]
