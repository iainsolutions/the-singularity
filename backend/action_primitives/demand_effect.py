"""
DemandEffect Action Primitive

Executes demand effects that affect other players based on symbol requirements.
"""

import logging
from typing import Any

from .base import ActionContext, ActionPrimitive, ActionResult

logger = logging.getLogger(__name__)


class DemandEffect(ActionPrimitive):
    """
    Marker primitive for demand effects - NO-OP during execution.

    This primitive is a structural wrapper in BaseCards.json that:
    1. Marks an effect as is_demand=true (checked during initialization)
    2. Contains demand_actions which are extracted and executed by vulnerable players

    The actual demand routing is handled by:
    - ConsolidatedInitializationPhase: Identifies vulnerable players
    - ActionPlan.create_sharing_plan: Routes effects to correct participants
    - ConsolidatedSharingPhase: Executes the plan

    This primitive should NEVER be executed as an action primitive - the
    demand_actions are extracted during effect loading and replace this wrapper.

    Parameters:
    - required_symbol: Symbol for vulnerability check (used during initialization)
    - demand_actions: Actions vulnerable players execute (extracted during loading)
    - repeat_on_compliance: Whether to repeat (deprecated, not currently used)
    - fallback_actions: Fallback actions (deprecated, not currently used)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.required_symbol = config.get("required_symbol")
        self.demand_actions = config.get("demand_actions", [])
        self.repeat_on_compliance = config.get("repeat_on_compliance", False)
        self.fallback_actions = config.get("fallback_actions", [])

    def execute(self, context: ActionContext) -> ActionResult:
        """
        No-op execution - demand routing handled by DemandEffectAdapter.

        DemandEffect primitives should NEVER execute directly. They should be
        routed through EffectFactory which creates DemandEffectAdapter instances
        that properly handle demand routing with routes_to_demand signal.

        If this executes, it means the Effect abstraction layer is being bypassed.
        """
        logger.error(
            "DemandEffect.execute() called - this should NEVER happen! "
            "DemandEffect primitives must be routed through EffectFactory.create() "
            f"which creates DemandEffectAdapter. Effect has {len(self.demand_actions)} demand_actions, "
            f"repeat_on_compliance={self.repeat_on_compliance}."
        )

        # Return SUCCESS to not break execution, but this indicates a serious bug
        return ActionResult.SUCCESS

    def _can_player_comply(self, player) -> bool:
        """Check if a player can potentially comply with the demand"""
        logger.info(f"_can_player_comply: Checking {player.name}")
        logger.info(f"  Current hand: {[c.name for c in player.hand]}")
        # Check if player has cards in the required source location
        for action in self.demand_actions:
            action_type = action.get("type")
            if action_type in ["SelectCards", "SelectHighest", "SelectLowest"]:
                source = action.get("source", "hand")
                filter_config = action.get("filter", {})

                # Get cards from the source location
                cards = []
                if source == "hand":
                    cards = getattr(player, "hand", [])
                elif source == "score_pile":
                    cards = getattr(player, "score_pile", [])
                elif source == "board":
                    board = getattr(player, "board", None)
                    if board:
                        cards = board.get_all_cards()

                # If there's a filter, check if any cards match
                if filter_config:
                    # Support filtering by symbol name or enum value
                    has_symbol = filter_config.get("has_symbol")
                    if has_symbol:
                        try:
                            from models.card import Symbol
                            from utils.symbol_mapping import string_to_symbol

                            required_symbol = (
                                string_to_symbol(has_symbol)
                                if isinstance(has_symbol, str)
                                else has_symbol
                            )
                        except Exception:
                            required_symbol = has_symbol

                        # Check if any card has the required symbol
                        for card in cards:
                            syms = getattr(card, "symbols", [])
                            if isinstance(required_symbol, Symbol):
                                if required_symbol in syms:
                                    return True
                            else:
                                # Fallback string compare
                                if any(
                                    getattr(s, "value", s) == required_symbol
                                    for s in syms
                                ):
                                    return True
                        # No cards match the filter
                        continue
                    # Add other filter checks here as needed

                # No filter or filter type not implemented - just check if cards exist
                if len(cards) > 0:
                    return True
            elif action_type == "TransferBetweenPlayers":
                # For transfers, check the from_location
                from_location = action.get("from_location", "hand")
                if (
                    from_location == "hand" and len(getattr(player, "hand", [])) > 0
                ) or (
                    from_location == "score_pile"
                    and len(getattr(player, "score_pile", [])) > 0
                ):
                    return True
                elif from_location == "board":
                    board = getattr(player, "board", None)
                    if board and len(board.get_all_cards()) > 0:
                        return True
            else:
                # For other action types, assume they can comply
                return True

        return False
