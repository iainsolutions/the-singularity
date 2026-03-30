"""
Action Primitives Package

This package contains all action primitive implementations for the Innovation game.
Action primitives are the building blocks for card effects, providing a declarative
way to define game actions without hardcoding card-specific logic.
"""

# Import base classes
from .base import ActionContext, ActionPrimitive, ActionResult

# Import utilities
from .utils import ActionLogger, CardFilterUtils, CardSourceResolver


def create_action_primitive(config):
    """
    Factory function that creates action primitive instances from configuration.

    Args:
        config: Dictionary containing the action primitive configuration,
                must include a 'type' field specifying the primitive type.

    Returns:
        An instance of the appropriate ActionPrimitive subclass.

    Raises:
        ValueError: If the action type is not recognized.
    """
    action_type = config.get("type")

    if not action_type:
        raise ValueError("Action configuration must include a 'type' field")

    # Map of action types to their module implementations
    # Using lazy imports to avoid circular dependencies
    primitive_map = {
        # Core Actions
        "DrawCards": lambda: __import__(
            "action_primitives.draw_cards", fromlist=["DrawCards"]
        ).DrawCards,
        "MeldCard": lambda: __import__(
            "action_primitives.meld_card", fromlist=["MeldCard"]
        ).MeldCard,
        "ScoreCards": lambda: __import__(
            "action_primitives.score_cards", fromlist=["ScoreCards"]
        ).ScoreCards,
        "ReturnCards": lambda: __import__(
            "action_primitives.return_cards", fromlist=["ReturnCards"]
        ).ReturnCards,
        "TransferCards": lambda: __import__(
            "action_primitives.transfer_cards", fromlist=["TransferCards"]
        ).TransferCards,
        "JunkCards": lambda: __import__(
            "action_primitives.junk_cards", fromlist=["JunkCards"]
        ).JunkCards,
        "JunkAllDeck": lambda: __import__(
            "action_primitives.junk_all_deck", fromlist=["JunkAllDeck"]
        ).JunkAllDeck,
        # Selection & Filtering
        "SelectCards": lambda: __import__(
            "action_primitives.select_cards", fromlist=["SelectCards"]
        ).SelectCards,
        "SelectHighest": lambda: __import__(
            "action_primitives.select_highest", fromlist=["SelectHighest"]
        ).SelectHighest,
        "SelectLowest": lambda: __import__(
            "action_primitives.select_lowest", fromlist=["SelectLowest"]
        ).SelectLowest,
        "SelectAchievement": lambda: __import__(
            "action_primitives.select_achievement", fromlist=["SelectAchievement"]
        ).SelectAchievement,
        "SelectColor": lambda: __import__(
            "action_primitives.select_color", fromlist=["SelectColor"]
        ).SelectColor,
        "SelectSymbol": lambda: __import__(
            "action_primitives.select_symbol", fromlist=["SelectSymbol"]
        ).SelectSymbol,
        "FilterCards": lambda: __import__(
            "action_primitives.filter_cards", fromlist=["FilterCards"]
        ).FilterCards,
        # Board Manipulation
        "SplayCards": lambda: __import__(
            "action_primitives.splay_cards", fromlist=["SplayCards"]
        ).SplayCards,
        "TuckCard": lambda: __import__(
            "action_primitives.tuck_card", fromlist=["TuckCard"]
        ).TuckCard,
        "ExchangeCards": lambda: __import__(
            "action_primitives.exchange_cards", fromlist=["ExchangeCards"]
        ).ExchangeCards,
        "TransferBetweenPlayers": lambda: __import__(
            "action_primitives.transfer_between_players",
            fromlist=["TransferBetweenPlayers"],
        ).TransferBetweenPlayers,
        "MakeAvailable": lambda: __import__(
            "action_primitives.make_available", fromlist=["MakeAvailable"]
        ).MakeAvailable,
        # Counting & Analysis
        "CountSymbols": lambda: __import__(
            "action_primitives.count_symbols", fromlist=["CountSymbols"]
        ).CountSymbols,
        "CountUniqueColors": lambda: __import__(
            "action_primitives.count_unique_colors", fromlist=["CountUniqueColors"]
        ).CountUniqueColors,
        "CountUniqueValues": lambda: __import__(
            "action_primitives.count_unique_values", fromlist=["CountUniqueValues"]
        ).CountUniqueValues,
        "CountColorsWithSymbol": lambda: __import__(
            "action_primitives.count_colors_with_symbol",
            fromlist=["CountColorsWithSymbol"],
        ).CountColorsWithSymbol,
        "CountColorsWithSplay": lambda: __import__(
            "action_primitives.count_colors_with_splay",
            fromlist=["CountColorsWithSplay"],
        ).CountColorsWithSplay,
        "CountCards": lambda: __import__(
            "action_primitives.count_cards", fromlist=["CountCards"]
        ).CountCards,
        "GetCardAge": lambda: __import__(
            "action_primitives.get_card_age", fromlist=["GetCardAge"]
        ).GetCardAge,
        "GetCardColor": lambda: __import__(
            "action_primitives.get_card_color", fromlist=["GetCardColor"]
        ).GetCardColor,
        # Control Flow
        "ConditionalAction": lambda: __import__(
            "action_primitives.conditional_action", fromlist=["ConditionalAction"]
        ).ConditionalAction,
        "EvaluateCondition": lambda: __import__(
            "action_primitives.evaluate_condition", fromlist=["EvaluateCondition"]
        ).EvaluateCondition,
        "LoopAction": lambda: __import__(
            "action_primitives.loop_action", fromlist=["LoopAction"]
        ).LoopAction,
        "RepeatAction": lambda: __import__(
            "action_primitives.repeat_action", fromlist=["RepeatAction"]
        ).RepeatAction,
        "RevealAndProcess": lambda: __import__(
            "action_primitives.reveal_and_process", fromlist=["RevealAndProcess"]
        ).RevealAndProcess,
        # Game Mechanics
        "ClaimAchievement": lambda: __import__(
            "action_primitives.claim_achievement", fromlist=["ClaimAchievement"]
        ).ClaimAchievement,
        "DemandEffect": lambda: __import__(
            "action_primitives.demand_effect", fromlist=["DemandEffect"]
        ).DemandEffect,
        "ExecuteDogma": lambda: __import__(
            "action_primitives.execute_dogma", fromlist=["ExecuteDogma"]
        ).ExecuteDogma,
        "ChooseOption": lambda: __import__(
            "action_primitives.choose_option", fromlist=["ChooseOption"]
        ).ChooseOption,
        "CalculateValue": lambda: __import__(
            "action_primitives.calculate_value", fromlist=["CalculateValue"]
        ).CalculateValue,
        # Echoes Expansion
        "Foreshadow": lambda: __import__(
            "action_primitives.foreshadow", fromlist=["Foreshadow"]
        ).Foreshadow,
        "PromoteForecast": lambda: __import__(
            "action_primitives.promote_forecast", fromlist=["PromoteForecast"]
        ).PromoteForecast,
        # Unseen Expansion Mechanics
        "FlipCoin": lambda: __import__(
            "action_primitives.flip_coin", fromlist=["FlipCoin"]
        ).FlipCoin,
        "WinGame": lambda: __import__(
            "action_primitives.win_game", fromlist=["WinGame"]
        ).WinGame,
        "LoseGame": lambda: __import__(
            "action_primitives.win_game", fromlist=["LoseGame"]
        ).LoseGame,
        "AchieveSecret": lambda: __import__(
            "action_primitives.achieve_secret", fromlist=["AchieveSecret"]
        ).AchieveSecret,
        "RepeatEffect": lambda: __import__(
            "action_primitives.repeat_effect", fromlist=["RepeatEffect"]
        ).RepeatEffect,
        "SafeguardAchievement": lambda: __import__(
            "action_primitives.safeguard_achievement", fromlist=["SafeguardAchievement"]
        ).SafeguardAchievement,
        "SafeguardCard": lambda: __import__(
            "action_primitives.safeguard_card", fromlist=["SafeguardCard"]
        ).SafeguardCard,
        "UnsplayCards": lambda: __import__(
            "action_primitives.unsplay_cards", fromlist=["UnsplayCards"]
        ).UnsplayCards,
        "SelectAnyPlayer": lambda: __import__(
            "action_primitives.select_any_player", fromlist=["SelectAnyPlayer"]
        ).SelectAnyPlayer,
        "SelfExecute": lambda: __import__(
            "action_primitives.self_execute", fromlist=["SelfExecute"]
        ).SelfExecute,
        "TransferSecret": lambda: __import__(
            "action_primitives.transfer_secret", fromlist=["TransferSecret"]
        ).TransferSecret,
        "RevealAndChoose": lambda: __import__(
            "action_primitives.reveal_and_choose", fromlist=["RevealAndChoose"]
        ).RevealAndChoose,
        "NoOp": lambda: __import__(
            "action_primitives.no_op", fromlist=["NoOp"]
        ).NoOp,
        "AddToSafe": lambda: __import__(
            "action_primitives.add_to_safe", fromlist=["AddToSafe"]
        ).AddToSafe,
        "TransferAchievementToSafe": lambda: __import__(
            "action_primitives.transfer_achievement_to_safe", fromlist=["TransferAchievementToSafe"]
        ).TransferAchievementToSafe,
        # Advanced Unseen Primitives
        "RevealTopCard": lambda: __import__(
            "action_primitives.reveal_top_card", fromlist=["RevealTopCard"]
        ).RevealTopCard,
        "SelfExecute": lambda: __import__(
            "action_primitives.self_execute", fromlist=["SelfExecute"]
        ).SelfExecute,
        "ScoreExcess": lambda: __import__(
            "action_primitives.score_excess", fromlist=["ScoreExcess"]
        ).ScoreExcess,
        # Utility Primitives
        "SetVariable": lambda: __import__(
            "action_primitives.set_variable", fromlist=["SetVariable"]
        ).SetVariable,
        "IncrementVariable": lambda: __import__(
            "action_primitives.increment_variable", fromlist=["IncrementVariable"]
        ).IncrementVariable,
        "AppendToList": lambda: __import__(
            "action_primitives.append_to_list", fromlist=["AppendToList"]
        ).AppendToList,
        "ConvertToInt": lambda: __import__(
            "action_primitives.convert_to_int", fromlist=["ConvertToInt"]
        ).ConvertToInt,
        # Card Information Primitives
        "GetCardColors": lambda: __import__(
            "action_primitives.get_card_colors", fromlist=["GetCardColors"]
        ).GetCardColors,
        "GetCardSymbols": lambda: __import__(
            "action_primitives.get_card_symbols", fromlist=["GetCardSymbols"]
        ).GetCardSymbols,
        "GetSplayDirection": lambda: __import__(
            "action_primitives.get_splay_direction", fromlist=["GetSplayDirection"]
        ).GetSplayDirection,
        "GetLowestValue": lambda: __import__(
            "action_primitives.get_lowest_value", fromlist=["GetLowestValue"]
        ).GetLowestValue,
        "CountUniqueSymbols": lambda: __import__(
            "action_primitives.count_unique_symbols", fromlist=["CountUniqueSymbols"]
        ).CountUniqueSymbols,
        # Check/Verify Primitives
        "CheckHandNotEmpty": lambda: __import__(
            "action_primitives.check_hand_not_empty", fromlist=["CheckHandNotEmpty"]
        ).CheckHandNotEmpty,
        "CheckIsMyTurn": lambda: __import__(
            "action_primitives.check_is_my_turn", fromlist=["CheckIsMyTurn"]
        ).CheckIsMyTurn,
        # Reveal Primitives
        "RevealHand": lambda: __import__(
            "action_primitives.reveal_hand", fromlist=["RevealHand"]
        ).RevealHand,
        "RevealCard": lambda: __import__(
            "action_primitives.reveal_card", fromlist=["RevealCard"]
        ).RevealCard,
    }

    if action_type not in primitive_map:
        raise ValueError(
            f"Invalid action type: {action_type}. Available types: {', '.join(sorted(primitive_map.keys()))}"
        )

    try:
        # Get the class using lazy import
        primitive_class = primitive_map[action_type]()
        # Create and return an instance
        return primitive_class(config)
    except ImportError as e:
        raise ImportError(
            f"Failed to import action primitive '{action_type}': {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to create action primitive '{action_type}': {e}"
        ) from e


# Export key classes and functions
__all__ = [
    # Base classes
    "ActionContext",
    "ActionLogger",
    "ActionPrimitive",
    "ActionResult",
    "CardFilterUtils",
    # Utilities
    "CardSourceResolver",
    # Factory
    "create_action_primitive",
]
