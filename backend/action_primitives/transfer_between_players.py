"""
TransferBetweenPlayers Action Primitive

Transfers cards between different players.
"""

import logging
from typing import Any

from models.board_utils import BoardColorIterator

from .base import ActionContext, ActionPrimitive, ActionResult


logger = logging.getLogger(__name__)


class TransferBetweenPlayers(ActionPrimitive):
    """
    Transfers cards between different players.

    Parameters:
    - cards: Variable name containing cards to transfer
    - source_player: "current", "demanding_player", "target_player"
    - target_player: "current", "demanding_player", "target_player"
    - target_location: "hand", "score_pile", "board"
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        # Support both parameter name styles
        self.cards_var = config.get("cards") or config.get(
            "selection", "selected_cards"
        )
        self.source_player_type = config.get("source_player") or config.get(
            "from_player", "current"
        )
        self.target_player_type = config.get("target_player") or config.get(
            "to_player", "demanding_player"
        )
        self.source_location = config.get("source_location") or config.get(
            "from_location", "hand"
        )
        self.target_location = config.get("target_location") or config.get(
            "to_location", "score_pile"
        )
        # NEW: Support filters and from_all_opponents for Classification-style effects
        self.filters = config.get("filters", [])
        self.from_all_opponents = config.get("from_all_opponents", False)

    def execute(self, context: ActionContext) -> ActionResult:
        """Transfer cards between players"""
        # NEW: Handle from_all_opponents with filters (for Classification-style effects)
        logger.debug(
            f"TransferBetweenPlayers: from_all_opponents={self.from_all_opponents}, filters={self.filters}"
        )
        if self.from_all_opponents:
            card_source_tuples = self._gather_filtered_cards_from_opponents(context)
            logger.debug(
                f"TransferBetweenPlayers: Gathered {len(card_source_tuples)} filtered cards from all opponents"
            )
            if not card_source_tuples:
                logger.debug(
                    "TransferBetweenPlayers: NO MATCHING CARDS - returning success"
                )
                context.add_result("No matching cards to transfer from opponents")
                return ActionResult.SUCCESS

            # Handle transfers from multiple sources
            target_player = context.player  # Active player receives the cards
            transferred_count = 0
            actually_transferred = []

            for card, source_player in card_source_tuples:
                if self._transfer_card_between_players(
                    context, card, source_player, target_player
                ):
                    transferred_count += 1
                    actually_transferred.append(card)

            if transferred_count > 0:
                context.set_variable("transferred_cards", actually_transferred)
                card_names = [c.name for c in actually_transferred]
                context.add_result(
                    f"Transferred {transferred_count} cards from opponents to {target_player.name}'s {self.target_location}: {', '.join(card_names)}"
                )
                # Sync all modified players back to game
                for _, source_player in card_source_tuples:
                    self._sync_players_to_game(context, source_player, target_player)

            return ActionResult.SUCCESS
        else:
            # Get cards to transfer from variable
            cards_to_transfer = context.get_variable(self.cards_var, [])
            if (not cards_to_transfer) and (self.cards_var != "selected_cards"):
                # Fallback to common key used by selection primitives
                fallback = context.get_variable("selected_cards", [])
                if fallback:
                    logger.debug(
                        f"TransferBetweenPlayers: Falling back to 'selected_cards' variable with {len(fallback)} card(s)"
                    )
                    cards_to_transfer = fallback

        def safe_card_name(c):
            if c is None:
                return "None"
            elif hasattr(c, "name"):
                return c.name
            elif isinstance(c, dict) and "name" in c:
                return c["name"]
            else:
                return f"<{type(c).__name__}>"

        logger.info(
            f"TransferBetweenPlayers: STARTING TRANSFER - cards_var={self.cards_var}, cards found={[safe_card_name(c) for c in cards_to_transfer]}"
        )
        logger.info(
            f"Transfer config: from_player={self.source_player_type}, to_player={self.target_player_type}, from_location={self.source_location}, to_location={self.target_location}"
        )
        logger.debug(f"All context variables: {context.variables}")
        if not cards_to_transfer:
            logger.info(
                "TransferBetweenPlayers: NO CARDS TO TRANSFER - returning success"
            )
            context.add_result("No cards to transfer between players")
            return ActionResult.SUCCESS

        # Ensure cards is a list
        if not isinstance(cards_to_transfer, list):
            cards_to_transfer = [cards_to_transfer]

        # Normalize non-Card entries (dicts/IDs) to actual Card objects from the source player's location
        def resolve_identifiers_to_cards(items, source_player):
            resolved = []
            # Build search pool based on source_location
            pool = []
            if self.source_location == "hand" and hasattr(source_player, "hand"):
                pool = list(source_player.hand)
            elif self.source_location == "score_pile" and hasattr(
                source_player, "score_pile"
            ):
                pool = list(source_player.score_pile)
            # For board transfers, we'll resolve during removal
            for it in items:
                if hasattr(it, "age") and hasattr(it, "name"):
                    resolved.append(it)
                    continue
                ident = None
                if isinstance(it, str):
                    ident = it
                elif isinstance(it, dict):
                    ident = it.get("card_id") or it.get("id") or it.get("name")
                if ident and pool:
                    found = None
                    for c in pool:
                        cid = getattr(c, "card_id", None)
                        if (cid and cid == ident) or getattr(c, "name", None) == ident:
                            found = c
                            break
                    resolved.append(found or it)
                else:
                    resolved.append(it)
            return resolved

        source_for_norm = self._get_player(context, self.source_player_type) or getattr(
            context, "player", None
        )
        cards_to_transfer = resolve_identifiers_to_cards(
            cards_to_transfer, source_for_norm
        )

        # Determine source and target players
        source_player = self._get_player(context, self.source_player_type)
        target_player = self._get_player(context, self.target_player_type)

        logger.info(
            f"TransferBetweenPlayers: RESOLVED PLAYERS - Source player ({self.source_player_type}): {source_player.name if source_player else 'None'}"
        )
        logger.info(
            f"TransferBetweenPlayers: RESOLVED PLAYERS - Target player ({self.target_player_type}): {target_player.name if target_player else 'None'}"
        )
        logger.debug(
            f"TRANSFER: Source player_obj_id={id(source_player) if source_player else None}, hand_id={id(source_player.hand) if source_player and hasattr(source_player, 'hand') else None}"
        )
        logger.debug(
            f"TRANSFER: Target player_obj_id={id(target_player) if target_player else None}, score_pile_id={id(target_player.score_pile) if target_player and hasattr(target_player, 'score_pile') else None}"
        )

        if not source_player or not target_player:
            context.add_result("Could not identify source or target player")
            return ActionResult.FAILURE

        if source_player.id == target_player.id:
            context.add_result("Source and target player are the same")
            return ActionResult.FAILURE

        transferred_count = 0
        actually_transferred = []
        for card in cards_to_transfer:
            logger.info(
                f"TransferBetweenPlayers: ATTEMPTING TO TRANSFER CARD: {card.name if card else 'None'}"
            )
            if self._transfer_card_between_players(
                context, card, source_player, target_player
            ):
                transferred_count += 1
                actually_transferred.append(card)
                logger.info(
                    f"TransferBetweenPlayers: SUCCESSFULLY TRANSFERRED: {card.name}"
                )
            else:
                logger.info(
                    f"TransferBetweenPlayers: FAILED TO TRANSFER: {card.name if card else 'None'}"
                )

        if transferred_count > 0:
            # Set the transferred_cards variable for compliance detection
            context.set_variable("transferred_cards", actually_transferred)

            # CRITICAL: Also set iteration-specific variable for demand compliance detection
            # This prevents false positives in repeating demands like Oars
            if context.get_variable("is_demand_target", False):
                context.set_variable(
                    "demand_iteration_transferred", actually_transferred
                )
                logger.info(
                    "TransferBetweenPlayers: Set demand_iteration_transferred for compliance detection"
                )

            source_name = getattr(source_player, "name", "Player")
            target_name = getattr(target_player, "name", "Player")
            card_names = [c.name for c in actually_transferred]
            context.add_result(
                f"Transferred {transferred_count} cards from {source_name} to {target_name}'s {self.target_location}: {', '.join(card_names)}"
            )

            # Log the transfer with details
            logger.info(
                f"TransferBetweenPlayers: TRANSFER COMPLETE - {transferred_count} cards transferred: {card_names}"
            )

            # CRITICAL FIX: Sync modified player objects back to game.players list
            # This ensures that when context is recreated during demand repeat cycles,
            # the game.players list contains the updated player state
            self._sync_players_to_game(context, source_player, target_player)

            # Add activity logging for each transferred card
            from logging_config import activity_logger

            if (
                activity_logger
                and hasattr(context, "game")
                and hasattr(context.game, "game_id")
            ):
                for card in actually_transferred:
                    try:
                        activity_logger.log_dogma_card_action(
                            game_id=context.game.game_id,
                            player_id=source_player.id,
                            card_name=card.name,
                            action_type="transferred",
                            cards=[card],
                            source_location=self.source_location,
                            target_location=self.target_location,
                            target_player_id=target_player.id,
                            target_player_name=target_name,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log card transfer activity: {e}")
        else:
            logger.info("TransferBetweenPlayers: NO CARDS WERE TRANSFERRED")
            context.add_result("No cards were transferred")

        return ActionResult.SUCCESS

    def _get_player(self, context: ActionContext, player_type: str):
        """Get a player based on the player type specification"""
        if player_type == "current":
            return context.player
        elif player_type == "opponent":
            # In a demand context, opponent means the current player (who is responding to the demand)
            return context.player
        elif player_type in ("active", "demanding_player"):
            # Active player is the one who initiated the action
            # In demand contexts: this is the demanding player
            # In regular dogma effects: this is the current player executing the dogma

            # First check if demanding_player is directly set in context
            demanding_player = context.get_variable("demanding_player")
            if demanding_player:
                return demanding_player

            # NEW: Check for activating_player_id in context variables (set by ConsolidatedSharingPhase)
            # This is critical for sharing phases where "active" means the player whose dogma is being shared,
            # not the current sharing player.
            activating_player_id = context.get_variable("activating_player_id")
            if activating_player_id:
                # Find player by ID
                if hasattr(context.game, "players"):
                    for p in context.game.players:
                        if p.id == activating_player_id:
                            return p

            # Also check if it's set as an attribute
            if hasattr(context, "demanding_player") and context.demanding_player:
                return context.demanding_player
            # Otherwise, get from pending action context
            if hasattr(context.game, "state") and hasattr(
                context.game.state, "pending_dogma_action"
            ):
                pending_action = context.game.state.pending_dogma_action
                if pending_action and hasattr(pending_action, "original_player_id"):
                    demanding_id = pending_action.original_player_id
                    player = next(
                        (p for p in context.game.players if p.id == demanding_id), None
                    )
                    if player:
                        return player

            # FALLBACK: If not in a demand context, "active" means the current player
            # This is needed for regular dogma effects like Optics that use "active"
            return context.player

        elif player_type == "target_player":
            # Get from pending action context
            if hasattr(context.game, "state") and hasattr(
                context.game.state, "pending_dogma_action"
            ):
                pending_action = context.game.state.pending_dogma_action
                if pending_action and hasattr(pending_action, "target_player_id"):
                    target_id = pending_action.target_player_id
                    return next(
                        (p for p in context.game.players if p.id == target_id), None
                    )
        elif player_type == "opponent_any":
            # TODO: Should trigger SelectOpponent interaction for proper implementation
            # For now: auto-select if only one opponent, otherwise require selection

            # Check if opponent was already selected via interaction
            selected_opponent_id = context.get_variable("selected_opponent_id")
            if selected_opponent_id:
                if hasattr(context.game, "players"):
                    return next(
                        (
                            p
                            for p in context.game.players
                            if p.id == selected_opponent_id
                        ),
                        None,
                    )

            # Auto-select opponent in 2-player games
            active_player = context.player
            if active_player and hasattr(context.game, "players"):
                opponents = [
                    p for p in context.game.players if p.id != active_player.id
                ]
                if len(opponents) == 1:
                    # Only one opponent - auto-select
                    return opponents[0]
                elif len(opponents) > 1:
                    # Multiple opponents - need SelectOpponent interaction
                    logger.warning(
                        f"TransferBetweenPlayers: Multiple opponents ({len(opponents)}) - "
                        "SelectOpponent interaction not yet implemented. Using first opponent."
                    )
                    # TEMPORARY: Return first opponent until SelectOpponent is implemented
                    return opponents[0]
            return None
        else:
            # Try to find player by ID
            if hasattr(context.game, "players"):
                for player in context.game.players:
                    if player.id == player_type:
                        return player
            # Try get_player_by_id method if available
            if hasattr(context.game, "get_player_by_id") and callable(
                context.game.get_player_by_id
            ):
                try:
                    return context.game.get_player_by_id(player_type)
                except Exception:
                    pass
        return None

    def _sync_players_to_game(
        self, context: ActionContext, source_player, target_player
    ):
        """
        Sync modified player objects back to context.game.players list.

        CRITICAL: This ensures that when context is recreated during demand repeat cycles,
        the game.players list contains references to the modified player objects, not stale copies.

        Without this, modifications to player.hand and player.score_pile are lost when
        a new context is created from context.game during suspension/resume.
        """
        if not hasattr(context.game, "players"):
            logger.warning("Game object has no players list to sync to")
            return

        # Update source player in game.players list
        for i, p in enumerate(context.game.players):
            if p.id == source_player.id:
                context.game.players[i] = source_player
                logger.debug(
                    f"SYNC: Updated source player {source_player.name} in game.players[{i}] "
                    f"(obj_id={id(source_player)}, hand_size={len(source_player.hand)})"
                )
                break

        # Update target player in game.players list
        for i, p in enumerate(context.game.players):
            if p.id == target_player.id:
                context.game.players[i] = target_player
                logger.debug(
                    f"SYNC: Updated target player {target_player.name} in game.players[{i}] "
                    f"(obj_id={id(target_player)}, score_pile_size={len(target_player.score_pile)})"
                )
                break

    def _transfer_card_between_players(
        self, context: ActionContext, card, source_player, target_player
    ) -> bool:
        """Transfer a single card between players"""
        # Remove from source player based on source location
        card_removed = False
        original_card = card

        # COMPREHENSIVE DEBUG LOGGING
        logger.debug("DEBUG: Starting transfer")
        logger.info(f"Card to transfer: {card} (type: {type(card)})")
        logger.info(
            f"Card attributes: card_id={getattr(card, 'card_id', 'N/A')}, name={getattr(card, 'name', 'N/A')}"
        )
        logger.info(
            f"Source player: {source_player.name}, Source location: {self.source_location}"
        )
        logger.info(
            f"Target player: {target_player.name}, Target location: {self.target_location}"
        )

        if self.source_location == "hand":
            logger.info(f"Source player hand BEFORE: {len(source_player.hand)} cards")
            for i, c in enumerate(source_player.hand):
                logger.info(
                    f"[{i}] {getattr(c, 'name', 'unknown')} (card_id={getattr(c, 'card_id', 'N/A')}, id={id(c)})"
                )

        # Helper to resolve a matching card object from a player's location
        def resolve_from_list(cards_list):
            logger.info(f"RESOLVE: Looking for card in list of {len(cards_list)} cards")
            logger.info(
                f"RESOLVE: original_card id={id(original_card)}, card_id={getattr(original_card, 'card_id', 'N/A')}, name={getattr(original_card, 'name', 'N/A')}"
            )

            # Fast path: exact object match
            if original_card in cards_list:
                logger.debug("RESOLVE: Found exact object match!")
                return original_card

            logger.debug("RESOLVE: No exact match, trying card_id/name match")

            # Match by card_id or name
            ident = getattr(original_card, "card_id", None) or getattr(
                original_card, "name", None
            )
            logger.debug(f"RESOLVE: Using identifier: {ident}")

            if ident:
                for i, c in enumerate(cards_list):
                    cid = getattr(c, "card_id", None)
                    cname = getattr(c, "name", None)
                    logger.info(f"RESOLVE: Checking [{i}] card_id={cid}, name={cname}")

                    if (cid and cid == ident) or cname == ident:
                        logger.debug(f"RESOLVE: FOUND MATCH at index {i}!")
                        return c

            logger.debug("RESOLVE: NO MATCH FOUND!")
            return None

        if self.source_location == "hand":
            if hasattr(source_player, "hand"):
                to_remove = resolve_from_list(source_player.hand)
                if to_remove is not None:
                    logger.info(
                        f"REMOVING card from hand: {getattr(to_remove, 'name', 'unknown')}"
                    )
                    source_player.hand.remove(to_remove)
                    card = to_remove
                    card_removed = True
                    logger.info(
                        f"Source player hand AFTER: {len(source_player.hand)} cards"
                    )
                else:
                    logger.error("FAILED to find card to remove!")
        elif self.source_location == "score_pile":
            if hasattr(source_player, "score_pile"):
                to_remove = resolve_from_list(source_player.score_pile)
                if to_remove is not None:
                    source_player.score_pile.remove(to_remove)
                    card = to_remove
                    card_removed = True
        elif self.source_location == "board":
            if hasattr(source_player, "board"):
                # Try to remove by name since object equality might fail
                board = source_player.board
                card_name = getattr(original_card, "card_id", None) or (
                    original_card.name
                    if hasattr(original_card, "name")
                    else str(original_card)
                )

                # Check each color stack using BoardColorIterator
                for color, color_cards in BoardColorIterator.iterate_color_stacks(
                    board
                ):
                    for i, board_card in enumerate(color_cards):
                        # Check card_id first (preferred stable identifier), then fall back to name
                        if (
                            hasattr(board_card, "card_id")
                            and board_card.card_id
                            and board_card.card_id == card_name
                        ) or (
                            hasattr(board_card, "name") and board_card.name == card_name
                        ):
                            # Found the card, remove it
                            color_cards.pop(i)
                            card_removed = True
                            logger.debug(
                                f"Removed {card_name} from {source_player.name}'s {color} stack"
                            )
                            break
                    if card_removed:
                        break

                # If not found by name matching, try the remove_card method
                if not card_removed and hasattr(board, "remove_card"):
                    try:
                        board.remove_card(card)
                        card_removed = True
                    except Exception:
                        pass
        else:
            # Fallback: try to find the card anywhere
            if hasattr(source_player, "hand") and card in source_player.hand:
                source_player.hand.remove(card)
                card_removed = True
            elif (
                hasattr(source_player, "score_pile")
                and card in source_player.score_pile
            ):
                source_player.score_pile.remove(card)
                card_removed = True

        if not card_removed:
            logger.error(
                f"TRANSFER FAILED: Card not found in source player's {self.source_location}"
            )
            logger.error(
                f"This means the card was NOT removed from {source_player.name}'s {self.source_location}"
            )
            return False

        logger.debug(
            "TRANSFER: Card successfully removed from source, now adding to target"
        )

        # Add to target player
        if self.target_location == "hand":
            # Ensure target player has a hand attribute
            if not hasattr(target_player, "hand"):
                target_player.hand = []

            # For Mock objects, prioritize direct append over method calls
            if hasattr(target_player.hand, "append"):
                target_player.hand.append(card)
            elif hasattr(target_player, "add_to_hand") and callable(
                target_player.add_to_hand
            ):
                # Only use add_to_hand if direct append failed
                try:
                    target_player.add_to_hand(card)
                except Exception:
                    # Fallback to creating new list
                    target_player.hand = [card]
            else:
                # If hand doesn't have append, make it a list
                target_player.hand = [card]

        elif self.target_location in ["score_pile", "score"]:
            if not hasattr(target_player, "score_pile"):
                target_player.score_pile = []
            target_player.score_pile.append(card)

        elif self.target_location == "board":
            # Check if player has a real meld_card method (not just a Mock auto-attribute)
            has_real_meld_card = (
                hasattr(target_player, "meld_card")
                and callable(target_player.meld_card)
                and not getattr(target_player.meld_card, "_mock_name", None)
            )

            if has_real_meld_card:
                target_player.meld_card(card)
            elif hasattr(target_player, "board") and hasattr(
                target_player.board, "add_card"
            ):
                target_player.board.add_card(card)
            else:
                logger.error("Target player has no board attribute or add_card method")
                return False
        else:
            logger.error(f"Unknown target location: {self.target_location}")
            return False

        logger.debug(
            f"TRANSFER SUCCESS: Card transferred from {source_player.name} to {target_player.name}"
        )
        return True

    def _gather_filtered_cards_from_opponents(self, context: ActionContext) -> list:
        """
        Gather cards from all opponents matching the filters.
        Returns a list of (card, source_player) tuples.

        Performance: O(n*m*f) where n=opponents, m=cards per opponent, f=filters.
        This is acceptable for Innovation's typical game scale (2-4 players, small card pools).
        """
        from .filter_cards import FilterCards

        matching_cards = []
        active_player = context.player

        if not active_player or not hasattr(context.game, "players"):
            return []

        # Iterate through all opponents
        opponents = [p for p in context.game.players if p.id != active_player.id]

        for opponent in opponents:
            # Get cards from source location
            if self.source_location == "hand" and hasattr(opponent, "hand"):
                cards_pool = list(opponent.hand)
            elif self.source_location == "score_pile" and hasattr(
                opponent, "score_pile"
            ):
                cards_pool = list(opponent.score_pile)
            elif self.source_location == "board" and hasattr(opponent, "board"):
                # Get all board cards
                from models.board_utils import BoardColorIterator

                cards_pool = []
                for _, color_cards in BoardColorIterator.iterate_color_stacks(
                    opponent.board
                ):
                    cards_pool.extend(color_cards)
            else:
                continue

            # Apply filters to each card
            for card in cards_pool:
                matches = True
                for filter_config in self.filters:
                    if not FilterCards.evaluate_filter(card, filter_config, context):
                        matches = False
                        break

                if matches:
                    # Store card with its source player for transfer
                    matching_cards.append((card, opponent))
                    logger.debug(
                        f"Found matching card: {card.name} from {opponent.name}"
                    )

        return matching_cards
