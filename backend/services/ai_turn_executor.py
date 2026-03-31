"""
AI Turn Executor

Executes AI player turns by integrating with AsyncGameManager and AIPlayerAgent.
"""

import asyncio
import json

import httpx

from app_config import get_server_config
from async_game_manager import AsyncGameManager
from logging_config import get_logger
from models.game import GamePhase
from services.ai_evaluation import track_decision
from services.ai_service import ai_service


logger = get_logger(__name__)


class AITurnExecutor:
    """Executes AI player turns"""

    def __init__(self, game_manager: AsyncGameManager):
        self.game_manager = game_manager

    async def execute_ai_turn(self, game_id: str, player_id: str) -> dict:
        """
        Execute complete AI turn.

        Returns summary of turn execution.
        """
        agent = ai_service.get_agent(player_id)
        if not agent:
            logger.error(f"No AI agent found for player {player_id}")
            return {"success": False, "error": "AI agent not found"}

        game = self.game_manager.get_game(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        logger.info(f"AI turn starting: game={game_id}, player={player_id}")

        turn_summary = {
            "actions_taken": [],
            "total_cost": 0.0,
            "total_latency_ms": 0.0,
        }

        try:
            # Execute actions until turn ends
            max_actions = 10  # Safety limit
            action_count = 0

            # Track interactions we've already handled to prevent duplicate processing
            handled_interactions = set()
            stale_skip_count = 0
            waiting_logged = False

            # Get initial player state
            player = game.get_player_by_id(player_id)

            while action_count < max_actions:
                # Check if game ended
                if game.phase == GamePhase.FINISHED:
                    break

                # Get current state - MUST reload from Redis to get fresh state
                # The HTTP endpoints update Redis, not the in-memory cache
                game = await self.game_manager.load_game_from_storage(game_id)
                if not game:
                    logger.error(f"Game {game_id} not found in storage")
                    break
                player = game.get_player_by_id(player_id)

                # Check for pending interaction targeting this AI player FIRST
                if game.state.pending_dogma_action:
                    pending = game.state.pending_dogma_action

                    # Build a unique ID that distinguishes multiple interactions within
                    # the same dogma transaction (e.g., Pottery triggers select then score)
                    tx_id = (
                        getattr(pending, "transaction_id", None)
                        or (pending.get("transaction_id") if isinstance(pending, dict) else None)
                        or ""
                    )
                    ctx = getattr(pending, "context", {}) or {}
                    idata = ctx.get("interaction_data", {}) if isinstance(ctx, dict) else {}
                    itype = idata.get("interaction_type", "")
                    msg = idata.get("data", {}).get("message", "") if isinstance(idata.get("data"), dict) else ""
                    interaction_id = f"{tx_id}:{itype}:{msg[:50]}"
                    if interaction_id in handled_interactions:
                        stale_skip_count += 1
                        if stale_skip_count > 5:
                            logger.error(f"Interaction stuck after response was sent, giving up")
                            break
                        await asyncio.sleep(1)
                        continue

                    if (
                        hasattr(pending, "target_player_id")
                        and pending.target_player_id == player_id
                    ):
                        handled_interactions.add(interaction_id)
                        logger.info(
                            f"✅ Handling targeted interaction: {interaction_id}"
                        )

                        result = await self._handle_interaction(
                            game_id, player_id, game, agent
                        )
                        if result:
                            turn_summary["actions_taken"].append(result["action"])
                            turn_summary["total_cost"] += result.get("api_cost", 0)
                            turn_summary["total_latency_ms"] += result.get(
                                "latency_ms", 0
                            )
                        continue

                # Check for pending interaction targeting OTHER players (human players)
                # CRITICAL: This must come BEFORE the "still our turn" check!
                # If AI's dogma triggered an interaction for a human, we must wait
                # for the human to respond - we should NOT exit the loop.
                #
                # IMPORTANT: Reload from Redis to see changes made by other HTTP requests
                # (cached copy may be stale if dogma-response was processed)
                fresh_game = await self.game_manager.load_game_from_storage(game_id)
                if fresh_game and fresh_game.state.pending_dogma_action:
                    pending = fresh_game.state.pending_dogma_action
                    target_player_id = getattr(pending, "target_player_id", None)

                    if target_player_id and target_player_id != player_id:
                        if not waiting_logged:
                            logger.info(f"Waiting for human player {target_player_id[:8]} interaction")
                            waiting_logged = True
                        await asyncio.sleep(0.5)
                        continue  # Loop back to check if interaction is complete
                    # Update our game reference with fresh data
                    waiting_logged = False
                    game = fresh_game

                # Check if still our turn (AFTER checking for pending interactions)
                # This prevents AI from exiting when waiting for human response
                current_player = game.players[game.state.current_player_index]
                if current_player.id != player_id:
                    logger.info(
                        f"No longer AI player's turn (now {current_player.name})"
                    )
                    break

                # Check if actions remaining
                if (
                    game.phase == GamePhase.PLAYING
                    and game.state.actions_remaining <= 0
                ):
                    logger.info("No actions remaining, ending turn")
                    result = await self._execute_action(
                        game_id, player_id, "end_turn", {}
                    )
                    if result.get("success"):
                        turn_summary["actions_taken"].append(
                            {"action_type": "end_turn"}
                        )
                    break

                # Get available actions
                available_actions = await self._get_available_actions(
                    game_id, player_id
                )

                logger.info(
                    f"AI available actions: {available_actions} "
                    f"(actions_remaining={game.state.actions_remaining})"
                )

                if not available_actions:
                    logger.info("No available actions, ending turn")
                    result = await self._execute_action(
                        game_id, player_id, "end_turn", {}
                    )
                    if result.get("success"):
                        turn_summary["actions_taken"].append(
                            {"action_type": "end_turn"}
                        )
                    break

                # Filter out provably useless dogma actions
                available_actions = self._filter_useless_actions(
                    available_actions, game, player
                )

                if not available_actions:
                    # Should not happen: draw/meld/achieve are never filtered.
                    # Defensive fallback only.
                    logger.warning(
                        "All actions filtered - unexpected. Ending turn."
                    )
                    result = await self._execute_action(
                        game_id, player_id, "end_turn", {}
                    )
                    if result.get("success"):
                        turn_summary["actions_taken"].append(
                            {"action_type": "end_turn"}
                        )
                    break

                # Get AI decision with retry logic for invalid choices
                game_state = self._build_game_state(game, player)
                decision = None
                retry_count = 0
                max_retries = 2
                previous_error = None

                while retry_count <= max_retries:
                    try:
                        if previous_error:
                            game_state["_previous_error"] = previous_error
                            # Clear so it doesn't overwrite _diagnose_invalid_decision
                            # context set by the validation-failure path (line ~327)
                            previous_error = None
                        try_decision = await agent.make_decision(
                            game_state, available_actions
                        )
                    except ValueError as e:
                        # AI agent raised ValueError for invalid action - retry with error context
                        retry_count += 1
                        error_msg = str(e)
                        logger.warning(
                            f"❌ AI agent ValueError (attempt {retry_count}/{max_retries + 1}): {error_msg}"
                        )
                        if retry_count <= max_retries:
                            previous_error = (
                                f"PREVIOUS ERROR: {error_msg} "
                                f"VALID OPTIONS: {available_actions[:20]}"
                            )
                            # Rebuild game_state fresh to avoid stale mutation
                            game_state = self._build_game_state(game, player)
                            continue
                        else:
                            logger.error(
                                f"❌ AI exhausted retries after ValueError: {error_msg}"
                            )
                            break

                    # Extract metadata
                    metadata = try_decision.pop("_metadata", {})
                    turn_summary["total_cost"] += metadata.get("api_cost", 0)
                    turn_summary["total_latency_ms"] += metadata.get("latency_ms", 0)

                    # Normalize malformed action_type (Ollama models sometimes copy available_actions format)
                    # Example: action_type="meld:The Wheel" should be action_type="meld", card_name="The Wheel"
                    action_type = try_decision.get("action_type", "")
                    if ":" in action_type:
                        parts = action_type.split(":", 1)
                        base_action = parts[0].strip()
                        action_value = parts[1].strip()

                        if base_action in ("meld", "dogma"):
                            try_decision["action_type"] = base_action
                            if not try_decision.get("card_name"):
                                try_decision["card_name"] = action_value
                            logger.info(
                                f"Normalized action_type '{action_type}' to '{base_action}'"
                            )
                            action_type = base_action
                        elif base_action == "draw" or base_action == "achieve":
                            try_decision["action_type"] = base_action
                            if not try_decision.get("age"):
                                try:
                                    age = int(action_value)
                                    try_decision["age"] = age
                                except ValueError:
                                    logger.warning(
                                        f"Could not parse age from malformed action_type '{action_type}'"
                                    )
                            logger.info(
                                f"Normalized action_type '{action_type}' to '{base_action}'"
                            )
                            action_type = base_action

                    # Validate decision matches available actions
                    action_type = try_decision.get("action_type")
                    is_valid = self._validate_decision(
                        try_decision, available_actions, game_state
                    )

                    if is_valid:
                        decision = try_decision
                        logger.debug(
                            f"✅ Valid decision on attempt {retry_count + 1}: {action_type}"
                        )
                        break
                    else:
                        retry_count += 1
                        if retry_count <= max_retries:
                            logger.warning(
                                f"❌ Invalid decision (attempt {retry_count}/{max_retries + 1}): "
                                f"{action_type} with {try_decision.get('card_name')} not in available_actions. "
                                f"Retrying with stricter prompt..."
                            )
                            # Add diagnostic error context for retry
                            card_name = try_decision.get('card_name', 'N/A')
                            diag = self._diagnose_invalid_decision(
                                action_type, card_name, game_state, available_actions
                            )
                            game_state["_previous_error"] = diag
                        else:
                            logger.error(
                                f"❌ AI failed validation after {max_retries + 1} attempts. "
                                f"Last attempt: {action_type} with {try_decision.get('card_name')}. "
                                f"Available: {available_actions}"
                            )

                if not decision:
                    # Fallback: end turn after max retries
                    logger.error("AI exhausted retries, ending turn as fallback")
                    result = await self._execute_action(
                        game_id, player_id, "end_turn", {}
                    )
                    if result.get("success"):
                        turn_summary["actions_taken"].append(
                            {"action_type": "end_turn"}
                        )
                    break

                # Track decision for evaluation
                try:
                    track_decision(
                        game_id=game_id,
                        player_id=player_id,
                        difficulty=agent.difficulty,
                        turn_number=game.state.turn_number,
                        decision=decision,
                        metadata=metadata,
                    )
                except Exception as e:
                    logger.debug(f"Failed to track decision: {e}")

                action_type = decision.get("action_type")
                reasoning = decision.get("reasoning", "No reasoning provided")

                logger.info(
                    f"AI decision: {action_type} | Reasoning: {reasoning} | "
                    f"Cost: ${metadata.get('api_cost', 0):.4f}"
                )

                if action_type == "end_turn":
                    logger.info("AI chose to end turn")
                    break

                # Execute action
                result = await self._execute_action(
                    game_id, player_id, action_type, decision
                )

                if result.get("success"):
                    turn_summary["actions_taken"].append(
                        {"action_type": action_type, **decision}
                    )
                else:
                    # Log error but continue (validation should have caught this)
                    logger.error(
                        f"Action failed despite validation: {result.get('error')}"
                    )
                    # End turn on unexpected failure
                    result = await self._execute_action(
                        game_id, player_id, "end_turn", {}
                    )
                    if result.get("success"):
                        turn_summary["actions_taken"].append(
                            {"action_type": "end_turn"}
                        )
                    break

                action_count += 1
                await asyncio.sleep(0.5)

            logger.info(
                f"AI turn complete: {len(turn_summary['actions_taken'])} actions, "
                f"${turn_summary['total_cost']:.4f} cost"
            )

            return {
                "success": True,
                **turn_summary,
            }

        except Exception as e:
            logger.error(f"AI turn execution failed: {e}", exc_info=True)
            raise

    async def _handle_interaction(
        self, game_id: str, player_id: str, game, agent
    ) -> dict | None:
        """Handle pending interaction"""

        try:
            pending_interaction = game.state.pending_dogma_action

            # PendingDogmaAction is a Pydantic model, access fields directly
            logger.debug(f"AI handling interaction: {pending_interaction.action_type}")

            # Build game state for interaction
            player = game.get_player_by_id(player_id)
            game_state = self._build_game_state(game, player)

            # Extract demand context if present (for AI prompt to understand it's losing cards)
            if hasattr(pending_interaction, "context") and pending_interaction.context:
                is_demand_target = pending_interaction.context.get(
                    "is_demand_target", False
                )
                if is_demand_target:
                    game_state["is_demand_target"] = True
                    logger.debug(
                        "AI is responding to demand effect (will lose cards to opponent)"
                    )

            # Extract the actual interaction data from pending action context
            # PendingDogmaAction.context contains "interaction_data" with StandardInteractionBuilder format
            pending_dict = pending_interaction.to_serializable_dict()
            interaction_data = pending_dict.get("context", {}).get(
                "interaction_data", {}
            )

            # If no interaction_data, fallback to the pending_dict itself (legacy format)
            if not interaction_data:
                logger.warning(
                    "No interaction_data found in pending action context, using pending_dict"
                )
                interaction_data = pending_dict

            # DEBUG: Log the structure we received
            logger.info("🔍 AI Interaction Data Structure:")
            logger.info(f"   - Top level keys: {list(interaction_data.keys())}")
            if "data" in interaction_data:
                logger.info(
                    f"   - Data field keys: {list(interaction_data['data'].keys())}"
                )
                if "eligible_cards" in interaction_data["data"]:
                    logger.info(
                        "   - Found eligible_cards in data field (correct location)"
                    )
            if "eligible_cards" in interaction_data:
                logger.info(
                    "   - Found eligible_cards at top level (unexpected location)"
                )

            # Get AI response
            response = await agent.make_interaction_response(
                game_state=game_state, interaction=interaction_data
            )

            # Extract metadata
            metadata = response.pop("_metadata", {})

            # Convert card names to card IDs
            # AI uses card names for semantic understanding, but game expects card IDs

            # StandardInteractionBuilder creates structure: {"type": "dogma_interaction", "data": {"eligible_cards": [...]}}
            # So we need to check in the nested data field first, then fallback to top level
            eligible_cards = None
            if (
                isinstance(interaction_data.get("data"), dict)
                and "eligible_cards" in interaction_data["data"]
            ):
                eligible_cards = interaction_data["data"]["eligible_cards"]
                logger.debug(
                    "✅ Found eligible_cards in data field (StandardInteractionBuilder format)"
                )
            elif "eligible_cards" in interaction_data:
                eligible_cards = interaction_data["eligible_cards"]
                logger.debug("✅ Found eligible_cards at top level (legacy format)")
            else:
                logger.warning("⚠️ No eligible_cards found in interaction_data")
                logger.debug(f"   Full structure: {interaction_data}")

            # DEBUG: Check if eligible cards have card_id fields
            if eligible_cards:
                logger.info("📋 Eligible cards structure check:")
                for idx, card in enumerate(eligible_cards):
                    if isinstance(card, dict):
                        logger.info(
                            f"   Card {idx}: name={card.get('name')}, has card_id={('card_id' in card)}, keys={list(card.keys())}"
                        )
                    else:
                        logger.info(f"   Card {idx}: type={type(card)}")

            # The AI is explicitly told to use card NAMES, not IDs
            # The backend should handle names directly since many cards don't have IDs
            if "selected_cards" in response:
                card_names = response["selected_cards"]
                logger.info(f"🎯 AI selected cards (names): {card_names}")

                # Verify the selected cards are in the eligible list
                if eligible_cards:
                    eligible_names = [card["name"] for card in eligible_cards]
                    for name in card_names:
                        if name not in eligible_names:
                            logger.warning(
                                f"⚠️ Card '{name}' not in eligible cards: {eligible_names}"
                            )
                        else:
                            logger.debug(f"✅ Card '{name}' is valid selection")

                # Keep the card names as-is since that's what the backend expects
                logger.info(f"📝 Passing card names directly: {card_names}")
            else:
                logger.warning("⚠️ No selected_cards in response")

            # Execute response directly via game_manager (not HTTP self-call)
            # Direct call avoids race conditions with Redis save timing
            reasoning = response.pop("reasoning", None)
            if reasoning:
                logger.debug(f"AI reasoning: {reasoning}")

            action_data = {
                "action_type": "dogma_response",
                "player_id": player_id,
                **response,
            }
            logger.info(f"📤 AI dogma response: {list(response.keys())}")

            try:
                result = await self.game_manager.perform_action(game_id, action_data)
                logger.info(
                    f"📥 Dogma response: success={result.get('success')}, error={result.get('error')}"
                )

                # Broadcast state update so frontend refreshes
                # (direct call bypasses the router broadcast that HTTP path did)
                if result.get("success") and "interaction_request" not in result:
                    from services.broadcast_service import get_broadcast_service
                    fresh_game = self.game_manager.get_game(game_id)
                    if fresh_game:
                        try:
                            await get_broadcast_service().broadcast_game_update(
                                game_id=game_id,
                                message_type="game_state_updated",
                                data={"game_state": fresh_game.to_dict()},
                            )
                        except RuntimeError as e:
                            logger.debug(f"Broadcast skipped: {e}")
            except Exception as e:
                logger.error(f"❌ Dogma response failed: {e}", exc_info=True)
                return {
                    "action": {"action_type": "dogma_response", **response},
                    "success": False,
                    "api_cost": metadata.get("api_cost", 0),
                    "latency_ms": metadata.get("latency_ms", 0),
                }

            return {
                "action": {"action_type": "dogma_response", **response},
                "success": result.get("success"),
                "api_cost": metadata.get("api_cost", 0),
                "latency_ms": metadata.get("latency_ms", 0),
            }

        except Exception as e:
            logger.error(f"AI interaction response failed: {e}", exc_info=True)
            return None

    def _filter_useless_actions(
        self, available_actions: list[str], game, player
    ) -> list[str]:
        """
        Remove provably useless dogma actions before passing to AI.

        Uses AIPromptBuilder's card viability analysis to detect actions like
        dogma:Tools when hand has 0 cards. Only removes actions marked USELESS,
        keeps LOW VALUE warnings (still playable).
        Falls back to unfiltered list on any error.
        """
        try:
            if not hasattr(self, "_prompt_builder"):
                from services.ai_prompt_builder import AIPromptBuilder
                # "expert" is arbitrary - viability checks don't use difficulty
                self._prompt_builder = AIPromptBuilder(difficulty="expert")

            from services.ai_prompt_builder import VIABILITY_USELESS

            game_state = self._build_game_state(game, player)

            filtered = []
            for action in available_actions:
                if action.startswith("dogma:"):
                    card_name = action.split(":", 1)[1]
                    warning = self._prompt_builder.check_dogma_viability(
                        card_name, game_state
                    )
                    if warning and VIABILITY_USELESS in warning:
                        logger.info(f"Filtered action '{action}': {warning}")
                        continue
                filtered.append(action)

            if len(filtered) < len(available_actions):
                removed = len(available_actions) - len(filtered)
                logger.info(
                    f"Filtered {removed} useless dogma actions. "
                    f"Remaining: {filtered}"
                )

            return filtered

        except Exception as e:
            logger.error(
                f"Error in _filter_useless_actions, returning unfiltered list: {e}",
                exc_info=True,
            )
            return available_actions

    async def _get_available_actions(self, game_id: str, player_id: str) -> list[str]:
        """Get list of available actions for player using game manager's logic"""
        result = await self.game_manager.get_available_actions(game_id, player_id)
        if result.get("success"):
            return result.get("actions", [])
        return []

    def _validate_decision(
        self, decision: dict, available_actions: list[str], game_state: dict | None = None
    ) -> bool:
        """Validate that AI decision matches available actions.

        Args:
            decision: AI's decision dict with action_type and optional card_name/age
            available_actions: List of available actions like ["draw:1", "meld:Pottery", "dogma:Oars"]
            game_state: Optional game state for resource requirement checks

        Returns:
            True if decision is valid, False otherwise
        """
        action_type = decision.get("action_type")

        if action_type == "end_turn":
            # end_turn is always valid
            return True

        # available_actions is already a list
        actions_list = available_actions

        # For actions that need a card name
        if action_type in ("meld", "dogma"):
            card_name = decision.get("card_name")
            if not card_name:
                logger.warning(f"Decision missing card_name for {action_type}")
                return False

            # Check if "action_type:card_name" is in available actions
            expected = f"{action_type}:{card_name}"
            if expected not in actions_list:
                logger.warning(
                    f"Invalid decision: '{expected}' not in available actions: {actions_list}"
                )
                return False

            # Note: viability guardrails are now handled data-driven by
            # _filter_useless_actions() before the AI sees the action list

        # For draw action
        elif action_type == "draw":
            age = decision.get("age")
            if age is None:
                logger.warning("Decision missing age for draw")
                return False

            expected = f"draw:{age}"
            if expected not in actions_list:
                logger.warning(
                    f"Invalid decision: '{expected}' not in available actions: {actions_list}"
                )
                return False

        # For achieve action
        elif action_type == "achieve":
            age = decision.get("age")
            if age is None:
                logger.warning("Decision missing age for achieve")
                return False

            expected = f"achieve:{age}"
            if expected not in actions_list:
                logger.warning(
                    f"Invalid decision: '{expected}' not in available actions: {actions_list}"
                )
                return False
        else:
            logger.warning(f"Unknown action type: {action_type}")
            return False

        return True

    def _diagnose_invalid_decision(
        self,
        action_type: str,
        card_name: str,
        game_state: dict,
        available_actions: list[str],
    ) -> str:
        """
        Create diagnostic error message for invalid AI decisions.

        Helps AI understand WHY choice was wrong and WHERE to look.
        """
        parts = [f"INVALID: '{action_type}:{card_name}' rejected."]

        player = game_state.get("current_player_state", {})
        hand = player.get("hand", [])
        board = player.get("board", {})

        hand_names = [c.get("name") for c in hand] if hand else []
        board_names = []
        for color in ["red", "blue", "green", "yellow", "purple"]:
            cards = board.get(f"{color}_cards", [])
            if cards:
                board_names.append(cards[0].get("name"))

        # Diagnose by action type
        if action_type == "meld":
            if card_name not in hand_names:
                parts.append(f"PROBLEM: '{card_name}' NOT in hand.")
                parts.append(f"Your hand: {hand_names}")
            else:
                parts.append("Card in hand but action invalid - check format.")
        elif action_type == "dogma":
            if card_name not in board_names:
                parts.append(f"PROBLEM: '{card_name}' NOT on board top.")
                parts.append(f"Your board tops: {board_names}")
            else:
                parts.append("Card on board but action invalid - check format.")

        # Show valid options (max 10)
        valid = available_actions[:10]
        parts.append(f"VALID OPTIONS: {valid}")

        return " ".join(parts)

    async def _execute_action(
        self, game_id: str, player_id: str, action_type: str, decision: dict
    ) -> dict:
        """Execute action directly via game_manager + broadcast."""
        try:
            action_data = {
                "action_type": action_type,
                "player_id": player_id,
            }

            if action_type == "draw":
                action_data["age"] = decision.get("age", 1)
            elif action_type in ("meld", "dogma"):
                action_data["card_name"] = decision.get("card_name")
            elif action_type == "achieve":
                action_data["age"] = decision.get("age")

            result = await self.game_manager.perform_action(game_id, action_data)

            # Broadcast state update so frontend refreshes
            if result.get("success"):
                from services.broadcast_service import get_broadcast_service
                fresh_game = self.game_manager.get_game(game_id)
                if fresh_game:
                    svc = get_broadcast_service()
                    if svc:
                        await svc.broadcast_game_update(
                            game_id=game_id,
                            message_type="game_state_updated",
                            data={"game_state": fresh_game.to_dict()},
                        )

            return result

        except Exception as e:
            logger.error(f"Action execution failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _build_game_state(self, game, player) -> dict:
        """Build game state for AI prompt"""

        # Get recent actions from action log (last 10 actions)
        recent_actions = []
        if hasattr(game, "action_log") and game.action_log:
            # Take last 10 actions, format for AI context
            for entry in game.action_log[-10:]:
                recent_actions.append(
                    {
                        "player_name": entry.player_name,
                        "action_type": entry.action_type,
                        "description": entry.description,
                    }
                )

        # Build opponent information (critical for strategic play)
        opponents = []
        for opponent in game.players:
            if opponent.id != player.id:
                # Calculate symbol counts for sharing determination
                from models.card import Symbol

                opponent_symbols = {
                    "circuit": opponent.board.count_symbol(Symbol.CIRCUIT),
                    "neural_net": opponent.board.count_symbol(Symbol.NEURAL_NET),
                    "data": opponent.board.count_symbol(Symbol.DATA),
                    "algorithm": opponent.board.count_symbol(Symbol.ALGORITHM),
                    "robot": opponent.board.count_symbol(Symbol.ROBOT),
                    "human_mind": opponent.board.count_symbol(Symbol.HUMAN_MIND),
                }

                opponents.append(
                    {
                        "id": opponent.id,
                        "name": opponent.name,
                        "hand_count": len(opponent.hand),  # Count only, not contents
                        "board": (
                            opponent.board.model_dump()
                            if hasattr(opponent.board, "model_dump")
                            else {}
                        ),
                        "symbol_counts": opponent_symbols,  # Critical for sharing analysis
                        "score_total": opponent.score,
                        "achievements": [
                            card.to_dict() for card in opponent.achievements
                        ],
                    }
                )

        # Calculate AI player's symbol counts for sharing analysis
        from models.card import Symbol

        player_symbols = {
            "circuit": player.board.count_symbol(Symbol.CIRCUIT),
            "neural_net": player.board.count_symbol(Symbol.NEURAL_NET),
            "data": player.board.count_symbol(Symbol.DATA),
            "algorithm": player.board.count_symbol(Symbol.ALGORITHM),
            "robot": player.board.count_symbol(Symbol.ROBOT),
            "human_mind": player.board.count_symbol(Symbol.HUMAN_MIND),
        }

        game_state = {
            "game_id": game.game_id,
            "turn_number": game.state.turn_number,
            "actions_taken": game.state.actions_taken,
            "phase": (
                game.phase.value if hasattr(game.phase, "value") else str(game.phase)
            ),
            "current_player_state": {
                "id": player.id,
                "name": player.name,
                "hand": [card.to_dict() for card in player.hand],
                "board": (
                    player.board.model_dump()
                    if hasattr(player.board, "model_dump")
                    else {}
                ),
                "symbol_counts": player_symbols,  # Critical for sharing analysis
                "score_total": player.score,
                "achievements": [card.to_dict() for card in player.achievements],
                "actions_remaining": game.state.actions_remaining,
            },
            "opponents": opponents,  # Critical for strategic decision-making
            "recent_actions": recent_actions,
        }

        # Add available achievements (ages where standard achievements still exist)
        if hasattr(game, "achievement_cards") and game.achievement_cards:
            available_ages = [
                age for age, cards in game.achievement_cards.items() if cards
            ]
            game_state["available_achievement_ages"] = sorted(available_ages)

        # Add deck status (empty/low ages for strategic decisions)
        if hasattr(game, "deck_manager") and game.deck_manager.age_decks:
            empty_ages = []
            low_ages = []
            for age, cards in game.deck_manager.age_decks.items():
                count = len(cards) if cards else 0
                if count == 0:
                    empty_ages.append(age)
                elif count <= 3:
                    low_ages.append(age)
            game_state["deck_status"] = {
                "empty": sorted(empty_ages),
                "low": sorted(low_ages),
            }

        # Add sharing context if present
        if hasattr(game.state, "sharing_context") and game.state.sharing_context:
            game_state["sharing_context"] = {
                "active": game.state.sharing_context.active,
                "initiator_id": game.state.sharing_context.initiator_id,
                "card_name": game.state.sharing_context.card_name,
            }

        return game_state


# Global instance
ai_turn_executor = None


def get_ai_turn_executor(game_manager: AsyncGameManager) -> AITurnExecutor:
    """Get or create AI turn executor"""
    global ai_turn_executor
    if ai_turn_executor is None:
        ai_turn_executor = AITurnExecutor(game_manager)
    return ai_turn_executor
