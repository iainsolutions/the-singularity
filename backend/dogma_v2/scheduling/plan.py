"""
Action Planning - Declarative execution order specification.

This module will be populated in Phase 3.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlannedAction:
    """
    Immutable descriptor for a single effect execution.

    This encapsulates all the parameters needed to execute one effect
    for one player, enabling declarative action planning and testability.
    """

    effect: tuple[dict, ...]  # Immutable sequence of action primitives
    effect_index: int  # Which effect number (0, 1, 2...)
    player: "Player"  # type: ignore  # Player to execute for
    is_sharing: bool  # Is this a sharing execution?
    resume_action_index: int = 0  # For mid-effect resumption

    # Optional behavior flags
    clear_variables_after: bool = False  # Clear context variables after execution
    update_sharing_context: bool = False  # Update sharing-specific variables
    is_demand: bool = False  # Is this a demand execution?

    @property
    def is_resuming(self) -> bool:
        """Check if this action is resuming from a previous suspension."""
        return self.resume_action_index > 0

    def with_resume_index(self, index: int) -> "PlannedAction":
        """Create a copy with updated resume index."""
        return PlannedAction(
            effect=self.effect,
            effect_index=self.effect_index,
            player=self.player,
            is_sharing=self.is_sharing,
            resume_action_index=index,
            clear_variables_after=self.clear_variables_after,
            update_sharing_context=self.update_sharing_context,
            is_demand=self.is_demand,
        )

    def to_dict(self) -> dict:
        """
        Serialize PlannedAction to dictionary.

        Player object is serialized as player_id string for persistence.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "effect": list(self.effect),  # Convert tuple to list for JSON
            "effect_index": self.effect_index,
            "player_id": self.player.id,  # Serialize Player as ID
            "is_sharing": self.is_sharing,
            "resume_action_index": self.resume_action_index,
            "clear_variables_after": self.clear_variables_after,
            "update_sharing_context": self.update_sharing_context,
            "is_demand": self.is_demand,
        }

    @staticmethod
    def from_dict(data: dict, game: "Game") -> "PlannedAction":  # type: ignore
        """
        Deserialize PlannedAction from dictionary.

        Args:
            data: Dictionary representation from to_dict()
            game: Game object to lookup player by ID

        Returns:
            PlannedAction with restored state

        Raises:
            ValueError: If player_id not found in game
        """
        player_id = data["player_id"]
        player = next((p for p in game.players if p.id == player_id), None)

        if player is None:
            raise ValueError(f"Player {player_id} not found in game")

        return PlannedAction(
            effect=tuple(data["effect"]),  # Convert list back to tuple
            effect_index=data["effect_index"],
            player=player,
            is_sharing=data["is_sharing"],
            resume_action_index=data.get("resume_action_index", 0),
            clear_variables_after=data.get("clear_variables_after", False),
            update_sharing_context=data.get("update_sharing_context", False),
            is_demand=data.get("is_demand", False),
        )


@dataclass(frozen=True)
class ActionPlan:
    """
    Immutable ordered sequence of PlannedActions.

    This provides declarative specification of execution order,
    supporting iteration, resumption, and factory methods for
    common planning patterns.
    """

    actions: tuple[PlannedAction, ...]  # Immutable sequence
    resumption_index: int = 0  # Which action to execute next

    @property
    def is_complete(self) -> bool:
        """Check if all actions have been executed."""
        return self.resumption_index >= len(self.actions)

    @property
    def remaining_actions(self) -> tuple[PlannedAction, ...]:
        """Get the actions that haven't been executed yet."""
        return self.actions[self.resumption_index :]

    def get_next_action(self) -> PlannedAction | None:
        """Get the next action to execute, or None if complete."""
        if self.is_complete:
            return None
        return self.actions[self.resumption_index]

    def reset_to(self, index: int) -> "ActionPlan":
        """Create a copy with updated resumption index."""
        return ActionPlan(
            actions=self.actions,
            resumption_index=index,
        )

    def mark_complete(self, action_index: int) -> "ActionPlan":
        """Mark an action as complete and advance to the next."""
        return self.reset_to(action_index + 1)

    def to_dict(self) -> dict:
        """
        Serialize ActionPlan to dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "actions": [action.to_dict() for action in self.actions],
            "resumption_index": self.resumption_index,
        }

    @staticmethod
    def from_dict(data: dict, game: "Game") -> "ActionPlan":  # type: ignore
        """
        Deserialize ActionPlan from dictionary.

        Args:
            data: Dictionary representation from to_dict()
            game: Game object to lookup players by ID

        Returns:
            ActionPlan with restored state
        """
        actions = tuple(
            PlannedAction.from_dict(action_data, game)
            for action_data in data["actions"]
        )
        return ActionPlan(
            actions=actions,
            resumption_index=data.get("resumption_index", 0),
        )

    # Class-level cache instance (shared across all plans)
    _cache: "PlanCache | None" = None  # type: ignore

    @classmethod
    def set_cache(cls, cache: "PlanCache") -> None:  # type: ignore
        """
        Set class-level cache for plan caching.

        Args:
            cache: PlanCache instance to use for caching
        """
        cls._cache = cache

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the plan cache if enabled."""
        if cls._cache:
            cls._cache.clear()

    @classmethod
    def create_sharing_plan(
        cls,
        effects: list[list[dict]],
        sharing_players: list["Player"],  # type: ignore
        effect_start_index: int = 0,
        use_cache: bool = True,
        activating_player: Optional["Player"] = None,  # type: ignore
        vulnerable_players: Optional[list["Player"]] = None,  # NEW
        effect_metadata: Optional[list[dict]] = None,  # NEW
        endorsed: bool = False,  # Cities: Double demands for endorsed dogmas
    ) -> "ActionPlan":
        """
        Factory: Create plan for dogma execution with proper participant routing.

        For each effect:
        - If demand: Only vulnerable opponents execute (twice if endorsed)
        - If non-demand: Sharing players execute first, then activating player

        Args:
            effects: List of effects (each effect is list of action primitives)
            sharing_players: Players who share (in clockwise order)
            effect_start_index: Effect index offset (default: 0)
            use_cache: Whether to use plan cache if available (default: True)
            activating_player: Player who activated dogma (added after sharing players)
            vulnerable_players: Players vulnerable to demands (fewer symbols than active)
            effect_metadata: Metadata for each effect (e.g., {"is_demand": True})
            endorsed: Whether this is an endorsed dogma (Cities expansion)

        Returns:
            ActionPlan with correct routing based on effect type
        """
        # Try cache if enabled
        if use_cache and cls._cache is not None:
            from dogma_v2.scheduling.cache import PlanCache

            player_ids = [p.id for p in sharing_players]
            if activating_player:
                player_ids.append(activating_player.id)
            cache_key = PlanCache.generate_cache_key(
                plan_type="sharing",
                effects=effects,
                player_ids=player_ids,
            )

            cached_plan_dict = cls._cache.get(cache_key)
            if cached_plan_dict is not None:
                # Cache hit - deserialize using the players we have
                # Build player lookup from the players passed to this method
                player_lookup = {p.id: p for p in sharing_players}
                if activating_player:
                    player_lookup[activating_player.id] = activating_player

                # Deserialize actions using our player lookup
                actions = []
                for action_data in cached_plan_dict["actions"]:
                    player_id = action_data["player_id"]
                    player = player_lookup.get(player_id)
                    if player is None:
                        # Player not found - cache is stale, rebuild
                        logger.debug(
                            f"PLAN_CACHE: Cache miss - player {player_id} not found"
                        )
                        break
                    actions.append(
                        PlannedAction(
                            effect=tuple(action_data["effect"]),
                            effect_index=action_data["effect_index"],
                            player=player,
                            is_sharing=action_data["is_sharing"],
                            resume_action_index=action_data.get(
                                "resume_action_index", 0
                            ),
                            clear_variables_after=action_data.get(
                                "clear_variables_after", False
                            ),
                            update_sharing_context=action_data.get(
                                "update_sharing_context", False
                            ),
                            is_demand=action_data.get("is_demand", False),
                        )
                    )
                else:
                    # All actions deserialized successfully
                    logger.info(
                        f"🎯 PLAN_CACHE HIT: Using cached plan with {len(actions)} actions"
                    )
                    # Log cached plan details
                    for i, action in enumerate(actions):
                        logger.info(
                            f"🎯   Cached Action {i}: Effect {action.effect_index}, Player={action.player.name}, "
                            f"is_sharing={action.is_sharing}, is_demand={action.is_demand}"
                        )
                    return cls(
                        actions=tuple(actions),
                        resumption_index=cached_plan_dict.get("resumption_index", 0),
                    )

        # Initialize defaults
        vulnerable_players = vulnerable_players or []
        effect_metadata = effect_metadata or [{"is_demand": False}] * len(effects)

        # Build plan from scratch with proper routing
        actions = []
        for effect_idx, effect in enumerate(effects):
            # Get metadata for this effect
            metadata = (
                effect_metadata[effect_idx]
                if effect_idx < len(effect_metadata)
                else {"is_demand": False}
            )
            is_demand = metadata.get("is_demand", False)

            if is_demand:
                # DEMAND EFFECT: Only vulnerable opponents execute (NOT activating player!)
                # Cities expansion: If endorsed, affect each opponent twice (two passes)
                num_passes = 2 if endorsed else 1

                logger.debug(
                    f"PLAN: Effect {effect_idx} is DEMAND - routing to {len(vulnerable_players)} vulnerable players"
                    f"{' (ENDORSED - 2 passes)' if endorsed else ''}"
                )

                if len(vulnerable_players) > 0:
                    # Normal case: route to vulnerable players
                    for pass_num in range(num_passes):
                        for player in vulnerable_players:
                            actions.append(
                                PlannedAction(
                                    effect=tuple(effect),
                                    effect_index=effect_start_index + effect_idx,
                                    player=player,
                                    is_sharing=False,  # Demands don't count as sharing
                                    update_sharing_context=False,
                                    is_demand=True,
                                )
                            )
                # else: No vulnerable players - skip entirely
            else:
                # NON-DEMAND EFFECT: Sharing players + activating player
                logger.debug(
                    f"PLAN: Effect {effect_idx} is NON-DEMAND - routing to {len(sharing_players)} sharing players + activating player"
                )
                # Add actions for sharing players (marked as sharing)
                for player in sharing_players:
                    actions.append(
                        PlannedAction(
                            effect=tuple(effect),
                            effect_index=effect_start_index + effect_idx,
                            player=player,
                            is_sharing=True,
                            update_sharing_context=True,
                            clear_variables_after=True,  # CRITICAL: Clear variables to prevent cross-contamination
                        )
                    )

                # Add action for activating player (NOT sharing, goes last)
                if activating_player:
                    actions.append(
                        PlannedAction(
                            effect=tuple(effect),
                            effect_index=effect_start_index + effect_idx,
                            player=activating_player,
                            is_sharing=False,  # Activating player is NOT sharing
                            update_sharing_context=False,
                        )
                    )

        plan = cls(actions=tuple(actions))

        # DEBUG: Log created plan structure
        logger.info(
            f"🎯 PLAN CREATED: {len(actions)} actions for {len(effects)} effects"
        )
        for i, action in enumerate(actions):
            logger.info(
                f"🎯   Action {i}: Effect {action.effect_index}, Player={action.player.name}, "
                f"is_sharing={action.is_sharing}, is_demand={action.is_demand}, "
                f"primitives={len(action.effect)}"
            )

        # Store in cache if enabled
        if use_cache and cls._cache is not None:
            from dogma_v2.scheduling.cache import PlanCache

            player_ids = [p.id for p in sharing_players]
            if activating_player:
                player_ids.append(activating_player.id)
            cache_key = PlanCache.generate_cache_key(
                plan_type="sharing",
                effects=effects,
                player_ids=player_ids,
            )
            cls._cache.put(cache_key, plan.to_dict())

        return plan

    @classmethod
    def create_execution_plan(
        cls,
        effects: list[list[dict]],
        activating_player: "Player",  # type: ignore
        use_cache: bool = True,
    ) -> "ActionPlan":
        """
        Factory: Create plan for normal (non-sharing) execution.

        Execute all effects for the activating player.

        Args:
            effects: List of effects (each effect is list of action primitives)
            activating_player: Player who activated dogma
            use_cache: Whether to use plan cache if available (default: True)

        Returns:
            ActionPlan with sequential execution order
        """
        # Try cache if enabled
        if use_cache and cls._cache is not None:
            from dogma_v2.scheduling.cache import PlanCache

            cache_key = PlanCache.generate_cache_key(
                plan_type="execution",
                effects=effects,
                player_ids=[activating_player.id],
            )

            cached_plan_dict = cls._cache.get(cache_key)
            if cached_plan_dict is not None:
                # Cache hit - deserialize using the activating_player we have
                actions = []
                for action_data in cached_plan_dict["actions"]:
                    player_id = action_data["player_id"]
                    if player_id != activating_player.id:
                        # Player mismatch - cache is stale, rebuild
                        logger.debug("PLAN_CACHE: Cache miss - player mismatch")
                        break
                    actions.append(
                        PlannedAction(
                            effect=tuple(action_data["effect"]),
                            effect_index=action_data["effect_index"],
                            player=activating_player,
                            is_sharing=action_data["is_sharing"],
                            resume_action_index=action_data.get(
                                "resume_action_index", 0
                            ),
                            clear_variables_after=action_data.get(
                                "clear_variables_after", False
                            ),
                            update_sharing_context=action_data.get(
                                "update_sharing_context", False
                            ),
                            is_demand=action_data.get("is_demand", False),
                        )
                    )
                else:
                    # All actions deserialized successfully
                    logger.debug(
                        f"PLAN_CACHE: Cache hit for execution plan ({len(actions)} actions)"
                    )
                    return cls(
                        actions=tuple(actions),
                        resumption_index=cached_plan_dict.get("resumption_index", 0),
                    )

        # Build plan from scratch
        actions = []
        for effect_idx, effect in enumerate(effects):
            actions.append(
                PlannedAction(
                    effect=tuple(effect),
                    effect_index=effect_idx,
                    player=activating_player,
                    is_sharing=False,
                )
            )

        plan = cls(actions=tuple(actions))

        # Store in cache if enabled
        if use_cache and cls._cache is not None:
            from dogma_v2.scheduling.cache import PlanCache

            cache_key = PlanCache.generate_cache_key(
                plan_type="execution",
                effects=effects,
                player_ids=[activating_player.id],
            )
            cls._cache.put(cache_key, plan.to_dict())

        return plan
