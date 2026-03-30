"""
ExecuteDogma primitive - Executes the dogma effect of a specified card.
"""

from typing import Any

from data.cards import load_cards_from_json

# Import at module level to avoid repeated imports in hot path
from action_primitives import create_action_primitive

from .base import ActionContext, ActionPrimitive, ActionResult

# Cache loaded cards to avoid repeated file I/O
_cards_cache = None


class ExecuteDogma(ActionPrimitive):
    """
    Executes the dogma effect of a specified card without actually activating it as an action.
    This is used for cards that trigger other cards' dogma effects.

    Supports three execution modes:
    - normal: Standard execution (all effects, sharing applies)
    - self: Self-execute (non-demand only, no sharing)
    - super: Super-execute (all effects including demands, no sharing, all vulnerable)

    Config:
        - card: Variable containing the card or card name whose dogma to execute
        - source: Where to find the card ('board_top', 'variable', 'specific')
        - color: If source is 'board_top', which color stack
        - player: Which player's card ('active', 'opponent', or player_id)
        - effect_index: Which effect to execute (default: all effects)
        - execution_mode: 'normal', 'self', or 'super' (default: 'normal')
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.card_source = config.get("card")
        self.source = config.get("source", "variable")
        self.color = config.get("color")
        self.player = config.get("player", "active")
        self.effect_index = config.get("effect_index")
        self.execution_mode = config.get("execution_mode", "normal")

    def execute(self, context: ActionContext) -> ActionResult:
        """Execute the dogma of the specified card"""
        # Get the target player
        target_player = self._get_target_player(context)
        if not target_player:
            return ActionResult.FAILURE

        # Get the card whose dogma to execute
        card = self._get_card_to_execute(context, target_player)
        if not card:
            context.add_result("No card found to execute dogma from")
            return ActionResult.FAILURE

        # Execute the card's dogma effects
        if not hasattr(card, "dogma_effects") or not card.dogma_effects:
            context.add_result(f"{card.name} has no dogma effects")
            return ActionResult.SUCCESS

        # Execute specified effect or all effects
        effects_to_execute = self._get_effects_to_execute(card)

        # Filter effects based on execution mode
        effects_to_execute = self._filter_effects_by_mode(effects_to_execute)

        # Add execution mode context
        mode_suffix = ""
        if self.execution_mode == "self":
            mode_suffix = " (self-execute)"
        elif self.execution_mode == "super":
            mode_suffix = " (super-execute)"

        # Execute each effect
        for effect in effects_to_execute:
            # Get actions from effect (handle both dict and DogmaEffect object)
            actions = effect.get("actions") if isinstance(effect, dict) else getattr(effect, "actions", None)
            if not actions:
                continue
            
            # Execute all actions in the effect
            for action_config in actions:
                result = self._execute_single_action(context, action_config, card.name)
                if result != ActionResult.SUCCESS:
                    return result

        context.add_result(f"Executed {card.name} dogma effects{mode_suffix}")
        return ActionResult.SUCCESS

    def _filter_effects_by_mode(self, effects: list) -> list:
        """Filter effects based on execution mode"""
        if self.execution_mode == "normal":
            # Normal mode: execute all effects
            return effects
        elif self.execution_mode == "self":
            # Self-execute: only non-demand effects
            filtered = []
            for e in effects:
                # Handle both dict and DogmaEffect object
                is_demand = e.get("is_demand", False) if isinstance(e, dict) else getattr(e, "is_demand", False)
                if not is_demand:
                    filtered.append(e)
            return filtered
        elif self.execution_mode == "super":
            # Super-execute: all effects (demands + non-demands), skip compels
            # Note: Compel filtering would need card type checking
            return effects
        return effects

    def _get_target_player(self, context: ActionContext):
        """Get the target player for dogma execution"""
        if self.player == "active":
            return context.player
        elif self.player == "opponent":
            # Get first opponent
            opponents = [p for p in context.game.players if p.id != context.player.id]
            if not opponents:
                context.add_result("No opponents to execute dogma from")
                return None
            return opponents[0]
        else:
            target_player = context.game.get_player_by_id(self.player)
            if not target_player:
                context.add_result(f"Player {self.player} not found")
                return None
            return target_player

    def _get_card_to_execute(self, context: ActionContext, target_player):
        """Get the card whose dogma to execute"""
        if self.source == "variable":
            # Get card from variable
            card = context.get_variable(self.card_source)
            if isinstance(card, list) and card:
                return card[0]
            return card

        elif self.source == "board_top":
            # Get top card of specified color
            if self.color:
                color_cards = getattr(target_player.board, f"{self.color}_cards", [])
                if color_cards:
                    return color_cards[-1]
            else:
                # Get any top card
                top_cards = target_player.board.get_top_cards()
                if top_cards:
                    return top_cards[0]
            return None

        elif self.source == "specific":
            # Card name specified directly - search game state first, then fallback to cache
            card = self._find_card_in_game_state(context, self.card_source)
            if card:
                return card

            # Fallback to cached cards for edge cases
            global _cards_cache
            if _cards_cache is None:
                # load_cards_from_json returns a single list of all cards
                _cards_cache = load_cards_from_json()

            for c in _cards_cache:
                # Check card_id first, then fall back to name for backwards compatibility
                if (hasattr(c, 'card_id') and c.card_id == self.card_source) or c.name == self.card_source:
                    return c
            return None

        return None

    def _get_effects_to_execute(self, card):
        """Get the list of effects to execute"""
        if self.effect_index is not None:
            if 0 <= self.effect_index < len(card.dogma_effects):
                return [card.dogma_effects[self.effect_index]]
            return []
        return card.dogma_effects

    def _find_card_in_game_state(self, context: ActionContext, card_identifier: str):
        """
        Efficiently find a card by ID or name in the current game state.
        This avoids expensive JSON loading by using already-loaded game data.
        Checks card_id first, then falls back to name for backwards compatibility.
        """
        def _matches_card(card, identifier):
            """Helper function to check if card matches identifier"""
            # Check card_id first (preferred stable identifier)
            if hasattr(card, 'card_id') and card.card_id and card.card_id == identifier:
                return True
            # Fall back to name for backwards compatibility
            return card.name == identifier

        # Search in age decks (most common case for ExecuteDogma)
        for _age, cards in context.game.deck_manager.age_decks.items():
            for card in cards:
                if _matches_card(card, card_identifier):
                    return card

        # Search in achievement cards
        for _age, cards in context.game.deck_manager.achievement_cards.items():
            for card in cards:
                if _matches_card(card, card_identifier):
                    return card

        # Search in all players' cards (hand, board, score pile, achievements)
        for player in context.game.players:
            # Check hand
            for card in player.hand:
                if _matches_card(card, card_identifier):
                    return card

            # Check board (all color stacks)
            board_cards = player.board.get_all_cards()
            for card in board_cards:
                if _matches_card(card, card_identifier):
                    return card

            # Check score pile
            for card in player.score_pile:
                if _matches_card(card, card_identifier):
                    return card

            # Check achievements
            for card in player.achievements:
                if _matches_card(card, card_identifier):
                    return card

        # Search in junk pile
        for card in context.game.junk_pile:
            if _matches_card(card, card_identifier):
                return card

        return None

    def _execute_single_action(
        self, context: ActionContext, action_config: dict, card_name: str
    ) -> ActionResult:
        """Execute a single action and handle its result"""
        try:
            primitive = create_action_primitive(action_config)
            result = primitive.execute(context)

            if result == ActionResult.FAILURE:
                context.add_result(f"Failed to execute {card_name} dogma")
                return ActionResult.FAILURE
            elif result == ActionResult.REQUIRES_INTERACTION:
                # Pass through interaction requirements
                return ActionResult.REQUIRES_INTERACTION

            return ActionResult.SUCCESS
        except (KeyError, AttributeError) as e:
            # Specific errors for missing fields or attributes
            context.add_result(f"Invalid action configuration in {card_name}: {e!s}")
            return ActionResult.FAILURE
        except ValueError as e:
            # Value errors in action execution
            context.add_result(f"Value error executing {card_name} dogma: {e!s}")
            return ActionResult.FAILURE
