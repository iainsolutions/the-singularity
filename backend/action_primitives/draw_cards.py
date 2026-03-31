"""
DrawCards Action Primitive

Draws cards from age decks and places them in specified locations.
"""

import logging
from typing import Any

from logging_config import activity_logger

from .base import ActionContext, ActionPrimitive, ActionResult


logger = logging.getLogger(__name__)


class DrawCards(ActionPrimitive):
    """
    Draws cards from age decks.

    Parameters:
    - age: Age of cards to draw (can be a number or variable name)
    - count: Number of cards to draw (default 1)
    - location: Where to place drawn cards ('hand' or 'score_pile')
    - store_result: Variable name to store drawn cards
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.age = config.get("age")
        self.count = config.get("count", 1)
        self.location = config.get("location", "hand")
        self.store_result = config.get("store_result", "last_drawn")

    def execute(self, context: ActionContext) -> ActionResult:
        """Draw cards from the specified age deck"""
        logger.debug(
            f"DrawCards.execute: age={self.age}, count={self.count}, location={self.location}"
        )
        logger.debug(
            f"DrawCards: Current context variables: {list(context.variables.keys())}"
        )

        # CRITICAL: Clear store_result variable at the START to ensure each DrawCards
        # execution draws fresh cards. This allows:
        # 1. Sequential DrawCards primitives to execute independently
        # 2. Loop iterations to draw new cards each time (LoopAction also clears these)
        # 3. Proper isolation between different draw operations
        # NOTE: DrawCards executes atomically (never suspends mid-execution), so
        # idempotency protection within DrawCards itself is not needed.
        if context.has_variable(self.store_result):
            logger.debug(
                f"DrawCards: Clearing previous {self.store_result} for fresh draw"
            )
            context.remove_variable(self.store_result)

        # RUNTIME ASSERTION: Validate variable was actually cleared
        # This catches bugs where variable clearing fails silently
        if context.has_variable(self.store_result):
            error_msg = f"VARIABLE LIFECYCLE ERROR: {self.store_result} still exists after clearing"
            logger.error(error_msg)
            context.add_result(error_msg)
            return ActionResult.FAILURE

        # Check for required parameters
        if self.age is None:
            context.add_result("Missing required parameter: age")
            return ActionResult.FAILURE

        # Resolve age value
        if isinstance(self.age, str) and context.has_variable(self.age):
            age = context.get_variable(self.age)
        else:
            age = self.age

        # Convert to int
        logger.debug(
            f"DrawCards: Attempting to convert age value: {age} (type: {type(age)})"
        )
        try:
            age = int(age) if age is not None else 1
            logger.debug(f"DrawCards: Successfully converted to age: {age}")
        except (ValueError, TypeError) as e:
            logger.error(
                f"DrawCards: Failed to convert age value: {age} (type: {type(age)}) - Error: {e}"
            )
            context.add_result(f"Invalid era value: {age}")
            return ActionResult.FAILURE

        # Resolve count value
        if isinstance(self.count, str) and context.has_variable(self.count):
            count = context.get_variable(self.count)
        else:
            count = self.count

        # Convert to int
        logger.debug(
            f"DrawCards: Attempting to convert count value: {count} (type: {type(count)})"
        )
        try:
            count = int(count) if count is not None else 1
            logger.debug(f"DrawCards: Successfully converted to count: {count}")
        except (ValueError, TypeError) as e:
            logger.error(
                f"DrawCards: Failed to convert count value: {count} (type: {type(count)}) - Error: {e}"
            )
            context.add_result(f"Invalid count value: {count}")
            return ActionResult.FAILURE

        # Draw cards
        drawn_cards = []
        for i in range(count):
            card = self._draw_card_from_deck(context.game, age, context)
            if card:
                # Place card in specified location
                if self.location == "hand":
                    drawn_cards.append(card)
                    context.player.hand.append(card)
                    # Record state change
                    context.state_tracker.record_draw(
                        player_name=context.player.name,
                        card_name=card.name,
                        age=age,
                        revealed=False,
                        context=context.get_variable("current_effect_context", "draw"),
                    )
                    # Use private card name for hand draws (unless revealed)
                    card_name = context.get_card_name_for_log(card, is_owner=True)
                    context.add_result(f"Researched {card_name} to hand")
                    # Activity: card drawn to hand
                    try:
                        if activity_logger:
                            activity_logger.log_dogma_card_action(
                                game_id=getattr(context.game, "game_id", "test-game"),
                                player_id=getattr(context.player, "id", None)
                                or "player",
                                card_name=getattr(context.card, "name", "Card"),
                                action_type="drawn",
                                cards=[{"name": getattr(card, "name", str(card))}],
                                location_from=f"age {age} deck",
                                location_to="hand",
                                is_sharing=bool(
                                    context.get_variable("is_sharing_phase", False)
                                ),
                            )
                    except Exception:
                        pass
                elif self.location == "score_pile" or self.location == "score":
                    drawn_cards.append(card)
                    if not hasattr(context.player, "score_pile"):
                        context.player.score_pile = []
                    context.player.score_pile.append(card)
                    # Record state change
                    context.state_tracker.record_draw(
                        player_name=context.player.name,
                        card_name=card.name,
                        age=age,
                        revealed=True,
                        context=context.get_variable("current_effect_context", "draw"),
                    )
                    # Score pile is public
                    context.add_result(
                        f"Drew {card.name} (age {card.age}) to score pile"
                    )
                    # Activity: card drawn to score pile
                    try:
                        if activity_logger:
                            activity_logger.log_dogma_card_action(
                                game_id=getattr(context.game, "game_id", "test-game"),
                                player_id=getattr(context.player, "id", None)
                                or "player",
                                card_name=getattr(context.card, "name", "Card"),
                                action_type="drawn",
                                cards=[{"name": getattr(card, "name", str(card))}],
                                location_from=f"age {age} deck",
                                location_to="score_pile",
                                is_sharing=bool(
                                    context.get_variable("is_sharing_phase", False)
                                ),
                            )
                    except Exception:
                        pass
                elif self.location == "reveal" or self.location == "revealed":
                    # According to official rules: "'Draw and reveal' effects place the card in your hand"
                    # The card is shown to all players but goes to hand
                    drawn_cards.append(card)
                    # Mark card as revealed (visible to all players)
                    card.is_revealed = True
                    # Place in hand (per official rules)
                    context.player.hand.append(card)
                    # Record state change
                    context.state_tracker.record_draw(
                        player_name=context.player.name,
                        card_name=card.name,
                        age=age,
                        revealed=True,
                        context=context.get_variable("current_effect_context", "draw"),
                    )
                    context.add_result(
                        f"Drew and revealed {card.name} (age {card.age})"
                    )
                    # Activity: card drawn and revealed to hand
                    try:
                        if activity_logger:
                            activity_logger.log_dogma_card_action(
                                game_id=getattr(context.game, "game_id", "test-game"),
                                player_id=getattr(context.player, "id", None)
                                or "player",
                                card_name=getattr(context.card, "name", "Card"),
                                action_type="drawn",
                                cards=[{"name": getattr(card, "name", str(card))}],
                                location_from=f"age {age} deck",
                                location_to="hand",
                                revealed=True,
                                is_sharing=bool(
                                    context.get_variable("is_sharing_phase", False)
                                ),
                            )
                    except Exception:
                        pass
                    # Store the color for condition checking (CardColor is str enum)
                    if hasattr(card, "color"):
                        context.set_variable("revealed_color", str(card.color))
            else:
                # Handle age skipping
                higher_age = self._find_next_available_age(context.game, age)
                if higher_age:
                    card = self._draw_card_from_deck(context.game, higher_age)
                    if card:
                        if self.location == "hand":
                            drawn_cards.append(card)
                            context.player.hand.append(card)
                            # Use private card name for hand draws (unless revealed)
                            card_name = context.get_card_name_for_log(
                                card, is_owner=True
                            )
                            context.add_result(
                                f"Age {age} empty, drew {card_name} to hand"
                            )
                            try:
                                if activity_logger:
                                    activity_logger.log_dogma_card_action(
                                        game_id=getattr(
                                            context.game, "game_id", "test-game"
                                        ),
                                        player_id=getattr(context.player, "id", None)
                                        or "player",
                                        card_name=getattr(context.card, "name", "Card"),
                                        action_type="drawn",
                                        cards=[
                                            {"name": getattr(card, "name", str(card))}
                                        ],
                                        location_from=f"age {higher_age} deck",
                                        location_to="hand",
                                        age_skipped=age,
                                        is_sharing=bool(
                                            context.get_variable(
                                                "is_sharing_phase", False
                                            )
                                        ),
                                    )
                            except Exception:
                                pass
                        elif self.location == "score_pile" or self.location == "score":
                            drawn_cards.append(card)
                            if not hasattr(context.player, "score_pile"):
                                context.player.score_pile = []
                            context.player.score_pile.append(card)
                            # Score pile is public
                            context.add_result(
                                f"Age {age} empty, drew {card.name} (age {card.age}) to score pile"
                            )
                            try:
                                if activity_logger:
                                    activity_logger.log_dogma_card_action(
                                        game_id=getattr(
                                            context.game, "game_id", "test-game"
                                        ),
                                        player_id=getattr(context.player, "id", None)
                                        or "player",
                                        card_name=getattr(context.card, "name", "Card"),
                                        action_type="drawn",
                                        cards=[
                                            {"name": getattr(card, "name", str(card))}
                                        ],
                                        location_from=f"age {higher_age} deck",
                                        location_to="score_pile",
                                        age_skipped=age,
                                        is_sharing=bool(
                                            context.get_variable(
                                                "is_sharing_phase", False
                                            )
                                        ),
                                    )
                            except Exception:
                                pass
                        elif self.location == "reveal" or self.location == "revealed":
                            # According to official rules: "'Draw and reveal' effects place the card in your hand"
                            # The card is shown to all players but goes to hand
                            drawn_cards.append(card)
                            # Mark card as revealed (visible to all players)
                            card.is_revealed = True
                            # Place in hand (per official rules)
                            context.player.hand.append(card)
                            context.add_result(
                                f"Era {age} empty, researched and revealed {card.name} (era {card.age})"
                            )
                            try:
                                if activity_logger:
                                    activity_logger.log_dogma_card_action(
                                        game_id=getattr(
                                            context.game, "game_id", "test-game"
                                        ),
                                        player_id=getattr(context.player, "id", None)
                                        or "player",
                                        card_name=getattr(context.card, "name", "Card"),
                                        action_type="drawn",
                                        cards=[
                                            {"name": getattr(card, "name", str(card))}
                                        ],
                                        location_from=f"age {higher_age} deck",
                                        location_to="hand",
                                        revealed=True,
                                        age_skipped=age,
                                        is_sharing=bool(
                                            context.get_variable(
                                                "is_sharing_phase", False
                                            )
                                        ),
                                    )
                            except Exception:
                                pass
                            if hasattr(card, "color"):
                                # CardColor is str enum, can use directly
                                context.set_variable("revealed_color", str(card.color))
                else:
                    context.add_result(f"No cards available from era {age} or higher")

        # Store drawn cards in variable
        if drawn_cards:
            # For single card draws, store just the card, not a list
            if self.count == 1 and len(drawn_cards) == 1:
                context.set_variable(self.store_result, drawn_cards[0])
            else:
                context.set_variable(self.store_result, drawn_cards)

            # Also store indexed versions for multi-card draws
            if len(drawn_cards) >= 1:
                context.set_variable("first_drawn", drawn_cards[0])
            if len(drawn_cards) >= 2:
                context.set_variable("second_drawn", drawn_cards[1])
            if len(drawn_cards) >= 3:
                context.set_variable("third_drawn", drawn_cards[2])

            # Track count for downstream adapters (e.g., sharing detection, logging)
            try:
                prev = context.get_variable("cards_drawn", 0)
                context.set_variable("cards_drawn", int(prev) + len(drawn_cards))
            except Exception:
                pass

            # RUNTIME ASSERTION: Validate stored result matches what we drew
            stored = context.get_variable(self.store_result)
            expected = (
                drawn_cards[0]
                if (self.count == 1 and len(drawn_cards) == 1)
                else drawn_cards
            )
            if stored != expected:
                error_msg = f"VARIABLE LIFECYCLE ERROR: {self.store_result} mismatch after storage"
                logger.error(f"{error_msg} - stored: {stored}, expected: {expected}")
                context.add_result(error_msg)
                return ActionResult.FAILURE

        return ActionResult.SUCCESS

    def _draw_card_from_deck(self, game, age: int, context: ActionContext = None):
        """Draw a card from the specified age deck

        Echoes Expansion Rule:
        Game.draw_card() now handles Echoes logic automatically based on player's
        board state (unique highest top card rule).
        """
        # Game.draw_card() handles card drawing
        return game.draw_card(age)

    def _find_next_available_age(self, game, start_age: int) -> int | None:
        """Find the next age with available cards"""
        if not hasattr(game, "deck_manager") or not hasattr(
            game.deck_manager, "age_decks"
        ):
            return None

        for age in range(start_age + 1, 11):  # Check up to age 10
            if game.deck_manager.age_decks.get(age):
                return age
        return None

