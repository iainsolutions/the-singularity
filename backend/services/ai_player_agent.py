"""
AI Player Agent

Core AI decision-making agent using pluggable AI providers with structured outputs,
prompt caching, and tiered difficulty tuning.
"""

import asyncio
import hashlib
import json
import os
import re
import time

from logging_config import ai_interaction_logger, get_logger

# Track logged template hashes to avoid repeating static content
_logged_template_hashes: dict[str, str] = {}

from services.ai_cost_monitor import CostLimitExceeded, cost_monitor
from services.ai_prompt_builder import AIPromptBuilder
from services.ai_providers.base import (
    AIProviderConnectionError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
)
from services.ai_providers.factory import create_ai_provider
from services.ai_providers.model_config import get_default_model_for_difficulty
from services.ai_providers.tool_definitions import (
    get_action_tools,
    get_interaction_tools,
)
from services.ai_memory import get_memory_store


logger = get_logger(__name__)


def _extract_prompt_parts_for_logging(prompt: str, log_type: str = "decision") -> tuple[str, str, str]:
    """Extract game-specific data and template from prompt for efficient logging.

    Returns:
        tuple: (game_data, template, template_hash)
        - game_data: Only the variable parts (game_state, available_actions, notes)
        - template: The static thinking framework
        - template_hash: Hash of the template for change detection
    """
    # Find where template starts (usually <task> or <thinking> tag)
    task_match = re.search(r'<task>', prompt)
    thinking_match = re.search(r'^<thinking>', prompt, re.MULTILINE)

    # Split at the template boundary
    split_pos = None
    if task_match:
        split_pos = task_match.start()
    elif thinking_match:
        split_pos = thinking_match.start()

    if split_pos:
        game_data = prompt[:split_pos].strip()
        template = prompt[split_pos:].strip()
    else:
        # No clear split point - just use the whole prompt
        game_data = prompt
        template = ""

    # Hash the template
    template_hash = hashlib.md5(template.encode()).hexdigest()[:8] if template else ""

    return game_data, template, template_hash


def _get_prompt_for_logging(prompt: str, log_type: str = "decision") -> str:
    """Get the prompt content to log, only including template when it changes.

    This reduces log file size by not repeating the static thinking framework
    on every turn - only logs it when it changes.
    """
    global _logged_template_hashes

    game_data, template, template_hash = _extract_prompt_parts_for_logging(prompt, log_type)

    # Check if this template hash has been logged before
    if template_hash and template_hash not in _logged_template_hashes:
        # First time seeing this template - log it with marker
        _logged_template_hashes[template_hash] = template
        return f"{game_data}\n\n[TEMPLATE hash={template_hash} - logged below]\n{template}"
    elif template_hash:
        # Template already logged - just reference the hash
        return f"{game_data}\n\n[TEMPLATE hash={template_hash} - see previous log entry]"
    else:
        # No template detected - log everything
        return prompt


async def fetch_available_models(
    api_key: str, *, provider_name: str | None = None, config: dict | None = None
) -> list[str]:
    """Fetch the available models for the configured AI provider."""

    provider = create_ai_provider(
        api_key=api_key, config=config, provider_name=provider_name
    )

    try:
        models = await provider.fetch_available_models()
        if models:
            logger.info(
                "Fetched %s available models from %s provider",
                len(models),
                provider.name,
            )
        return models
    except AIProviderError as exc:
        logger.warning("Failed to fetch available models: %s", exc)
        return []


class AIPlayerAgent:
    """
    AI agent for making game decisions using the configured AI provider.

    Features:
    - Structured JSON output for reliability
    - Difficulty-based context optimization
    - Prompt caching for 90% cost savings
    - GlobalAICostMonitor integration
    - Behavioral difficulty tuning
    """

    def __init__(
        self, player_id: str, difficulty: str, api_key: str, config: dict | None = None
    ):
        self.player_id = player_id
        self.difficulty = difficulty
        self.config = config or {}

        # Provider selection (defaults to Anthropic)
        # Note: For Ollama, provider.name is "openai" (uses OpenAI-compatible API)
        # but we need the actual provider name ("ollama") for cost tracking
        requested_provider = self.config.get("provider")
        self.provider = create_ai_provider(
            api_key=api_key,
            config=self.config,
            provider_name=requested_provider,
        )
        # Use requested provider name for cost tracking (e.g., "ollama" not "openai")
        self.provider_name = requested_provider or self.provider.name

        # Initialize prompt builder
        self.prompt_builder = AIPromptBuilder(difficulty)

        # Model selection based on difficulty
        self.model = self._get_model_for_difficulty()

        # Configuration
        self.max_tokens = self._get_max_tokens()
        self.temperature = self.config.get("temperature", 0.3)
        self.think_time_ms = self._get_think_time()

        logger.info(
            f"AIPlayerAgent initialized: player_id={player_id}, "
            f"difficulty={difficulty}, provider={self.provider_name}, model={self.model}"
        )

    def _get_model_for_difficulty(self) -> str:
        """
        Map difficulty to provider model with validation.
        Falls back to configured defaults if provider has no override.
        """
        desired_model = get_default_model_for_difficulty(self.difficulty)

        # Allow the provider to override based on availability
        provider_model = self.provider.get_model_for_difficulty(self.difficulty)

        if provider_model and provider_model != desired_model:
            logger.debug(
                "Provider %s selected model %s instead of default %s for difficulty %s",
                self.provider_name,
                provider_model,
                desired_model,
                self.difficulty,
            )
            return provider_model

        return desired_model

    def _get_max_tokens(self) -> int:
        """Get max tokens based on difficulty tier"""
        token_map = {
            "easy": int(os.getenv("AI_EASY_MAX_TOKENS", "1200")),
            "medium": int(os.getenv("AI_MEDIUM_MAX_TOKENS", "3000")),
            "hard": int(os.getenv("AI_HARD_MAX_TOKENS", "5000")),
        }
        return token_map.get(self.difficulty, 2000)

    async def _wait_for_human_players(
        self, game_state: dict, interaction: dict, timeout_seconds: int = 90
    ):
        """
        Wait for human players to respond to sharing interaction first.

        For sharing actions, human players should get priority to respond.
        The AI waits up to timeout_seconds for all human players to respond
        before proceeding with its own response.

        Args:
            game_state: Current game state
            interaction: The sharing interaction
            timeout_seconds: Maximum time to wait (default 90 seconds)
        """
        logger.info(
            f"AI player {self.player_id} waiting for human players to respond to sharing action"
        )

        # Extract interaction ID to track if it's been resolved
        interaction_id = interaction.get("interaction_id") or interaction.get("id")

        # Check how many human players are involved
        players = game_state.get("players", [])
        human_players = [p for p in players if not p.get("is_ai", False)]

        if not human_players:
            # No human players - proceed immediately
            logger.debug("No human players in game - AI proceeding immediately")
            return

        # Poll game state to check if humans have responded
        start_time = time.time()
        poll_interval = 0.5  # Check every 500ms

        while (time.time() - start_time) < timeout_seconds:
            await asyncio.sleep(poll_interval)

            # Fetch fresh game state from game manager
            from services.game_manager import game_manager

            game = game_manager.get_game(game_state.get("game_id"))
            if not game:
                # Game no longer exists - proceed
                logger.warning(
                    f"Game {game_state.get('game_id')} not found - AI proceeding"
                )
                return

            # Check if the interaction is still pending
            pending_action = game.state.pending_dogma_action

            if not pending_action:
                # No pending action - humans must have responded
                logger.info("Pending interaction resolved - AI can now respond")
                return

            # Check if this is still the same interaction
            pending_id = getattr(pending_action, "interaction_id", None) or getattr(
                pending_action, "id", None
            )

            if pending_id != interaction_id:
                # Different interaction now - original was resolved
                logger.info("Interaction changed - AI can now respond")
                return

        # Timeout reached
        logger.info(
            f"Timeout ({timeout_seconds}s) reached waiting for human players - AI proceeding"
        )

    def _get_think_time(self) -> int:
        """Get think time based on difficulty tier"""
        time_map = {
            "easy": int(os.getenv("AI_EASY_THINK_TIME_MS", "400")),
            "medium": int(os.getenv("AI_MEDIUM_THINK_TIME_MS", "1200")),
            "hard": int(os.getenv("AI_HARD_THINK_TIME_MS", "2000")),
        }
        return time_map.get(self.difficulty, 1200)

    def _get_thinking_budget(self) -> int | None:
        """
        Get extended thinking token budget for Pro+ difficulties.

        Extended thinking allows the model to use extra tokens for deeper reasoning
        before responding, improving decision quality for high-difficulty AIs.
        Supports both Sonnet 4.5+ and Opus 4+ models.
        """
        # Only enable extended thinking for hard tier (Opus)
        if self.difficulty != "hard":
            return None

        # Enable for Opus 4+ models
        model_lower = self.model.lower()
        if "opus-4" not in model_lower:
            return None

        return int(os.getenv("AI_HARD_THINKING_BUDGET", "15000"))

    def _extract_json_from_response(self, response_text: str) -> str:
        """Extract JSON from response, handling markdown code blocks and mixed content"""
        import re

        # Strip leading/trailing whitespace
        text = response_text.strip()

        # Try to extract JSON from markdown code blocks using regex
        # Matches ```json\n{...}\n``` or ```\n{...}\n```
        markdown_pattern = r"^```(?:json)?\s*\n(.*?)\n```$"
        match = re.search(markdown_pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # If no markdown blocks, try removing just the backticks
        if text.startswith("```"):
            # Remove opening ```json or ```
            text = text[7:] if text.startswith("```json") else text[3:]

            # Remove closing ```
            if text.endswith("```"):
                text = text[:-3]

            text = text.strip()

        # CRITICAL FIX: If response contains prose before JSON, extract just the JSON
        # This handles cases where AI includes reasoning text before the JSON object
        # Example: "To analyze the best move...\n\n{"action_type": "dogma", "card_name": "Metalworking"}"
        if not text.startswith("{"):
            # Find the first { and extract from there to the end
            json_start = text.find("{")
            if json_start != -1:
                text = text[json_start:]

        # Also handle case where there's prose after JSON
        if text.endswith("}"):
            # Find the last } and extract up to there
            json_end = text.rfind("}")
            if json_end != -1:
                text = text[:json_end + 1]

        return text

    def _extract_thinking_and_decision(
        self, response_text: str
    ) -> tuple[str | None, str]:
        """
        Extract <thinking> reasoning and <decision> JSON from response.
        Handles plain JSON responses without tags.

        Returns:
            tuple: (thinking_text, decision_json_text)
        """
        import re

        # Try to extract thinking section (with closing tag)
        thinking_match = re.search(
            r"<thinking>(.*?)</thinking>", response_text, re.DOTALL
        )
        thinking = thinking_match.group(1).strip() if thinking_match else None

        # Try to extract decision section (with closing tag)
        decision_match = re.search(
            r"<decision>(.*?)</decision>", response_text, re.DOTALL
        )
        if decision_match:
            decision_text = decision_match.group(1).strip()
        else:
            # Fallback: no decision tags
            # If response starts with { it's likely plain JSON - use as-is
            # If it starts with <thinking> without closing tags, strip it and look for JSON
            text = response_text.strip()
            if text.startswith("{"):
                decision_text = text
            elif "<thinking>" in text:
                # Strip everything before the first { to handle incomplete thinking tags
                json_start = text.find("{")
                if json_start > 0:
                    decision_text = text[json_start:]
                else:
                    decision_text = text
            else:
                decision_text = text

        return thinking, decision_text

    def _unwrap_interaction_payload(self, interaction: dict) -> dict:
        """Return the canonical interaction payload regardless of wrapper structure."""

        if (
            isinstance(interaction, dict)
            and interaction.get("type") == "dogma_interaction"
            and isinstance(interaction.get("data"), dict)
        ):
            return interaction["data"]

        return interaction

    def _get_choose_option_values(self, options: list) -> tuple[list[str], list[str]]:
        """Return descriptions and values that count as valid choose_option answers."""

        descriptions: list[str] = []
        values: list[str] = []

        for opt in options or []:
            if isinstance(opt, dict):
                description = opt.get("description") or opt.get("label")
                value = opt.get("value")
                if description is not None:
                    descriptions.append(str(description))
                if value is not None:
                    values.append(str(value))
            else:
                option_text = str(opt)
                descriptions.append(option_text)
                values.append(option_text)

        return descriptions, values

    def _validate_choose_option_response(
        self,
        interaction_payload: dict,
        interaction_response: dict,
        *,
        game_id: str | None = None,
    ) -> bool:
        """Validate AI JSON against available choose_option choices."""

        options = interaction_payload.get("options") or []
        allow_cancel = bool(
            interaction_payload.get("allow_cancel")
            or interaction_payload.get("can_cancel")
            or interaction_payload.get("is_optional")
        )

        chosen = interaction_response.get("chosen_option")
        game_identifier = game_id or "unknown"

        if chosen is None:
            if allow_cancel:
                interaction_response.setdefault("cancelled", True)
                return True

            logger.error(
                "Game %s player %s: ChooseOption response missing chosen_option for non-optional prompt",
                game_identifier,
                self.player_id,
            )
            return False

        if isinstance(chosen, str) and chosen.isdigit():
            chosen = int(chosen)
            interaction_response["chosen_option"] = chosen

        if isinstance(chosen, int):
            option_count = len(options)

            if option_count == 0:
                logger.error(
                    "Game %s player %s: ChooseOption response provided index %s but there are no options",
                    game_identifier,
                    self.player_id,
                    chosen,
                )
                return False

            if chosen == 0:
                return True

            if 1 <= chosen <= option_count:
                normalized_index = chosen - 1
                logger.debug(
                    "ChooseOption response used 1-based index %s; normalizing to %s",
                    chosen,
                    normalized_index,
                )
                interaction_response["chosen_option"] = normalized_index
                return True

            logger.error(
                "Game %s player %s: ChooseOption response index %s out of bounds (options: %s)",
                game_identifier,
                self.player_id,
                chosen,
                option_count,
            )
            return False

        chosen_str = str(chosen)
        descriptions, values = self._get_choose_option_values(options)

        valid_strings = set(descriptions + values)
        if valid_strings and chosen_str not in valid_strings:
            logger.error(
                "Game %s player %s: ChooseOption response '%s' not in allowed options: descriptions=%s values=%s",
                game_identifier,
                self.player_id,
                chosen_str,
                descriptions,
                values,
            )
            return False

        return True

    def _pick_default_option(self, options: list) -> str | None:
        """Return a reasonable default option string from the provided list."""

        if not options:
            return None

        first = options[0]
        if isinstance(first, dict):
            return (
                first.get("value")
                or first.get("description")
                or first.get("label")
                or next(
                    (str(v) for v in first.values() if isinstance(v, str)),
                    None,
                )
            )

        return str(first)

    async def make_decision(self, game_state: dict, available_actions: list) -> dict:
        """
        Decide next action based on game state using structured JSON output.

        Uses provider-agnostic prompt engineering:
        - XML structure for game state
        - Chain of Thought reasoning
        - Strategic examples
        - Optional prefilling (Anthropic-specific)
        - Self-improving notes from previous turns

        Returns:
            dict with action details (action_type, age, card_name, etc.)
        """
        start_time = time.time()
        game_id = game_state.get("game_id", "unknown")

        try:
            # Simulate thinking time for realism
            if self.think_time_ms > 0:
                await asyncio.sleep(self.think_time_ms / 1000.0)

            # Retrieve AI notes from memory store
            memory_store = get_memory_store()
            notes = await memory_store.get_notes(game_id, self.player_id)
            notes_text = memory_store.format_notes_for_prompt(notes) if notes else None

            # Build enhanced prompt with CoT (provider-agnostic)
            prompt, prefill = self.prompt_builder.build_action_prompt_with_cot(
                game_state=game_state,
                available_actions=available_actions,
                difficulty=self.difficulty,
                notes_text=notes_text,
            )

            # Use prefill only if provider supports it
            if prefill and not self.provider.supports_prefill():
                logger.debug(
                    f"Provider {self.provider_name} doesn't support prefill, ignoring"
                )
                prefill = None

            # Get extended thinking budget for Pro+ difficulties
            thinking_budget = self._get_thinking_budget()

            # Get tools for structured output
            action_tools = get_action_tools()

            # Call AI provider with tool_use for structured output
            provider_response = await self.provider.send_message(
                prompt=prompt,
                system_prompt=self.prompt_builder.get_cached_system_context(),
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                prefill=prefill,
                thinking_budget=thinking_budget,
                tools=action_tools,
                tool_choice={"type": "tool", "name": "choose_action"},
            )

            input_tokens = provider_response.input_tokens
            output_tokens = provider_response.output_tokens
            cached_tokens = provider_response.cached_tokens

            # Record with GlobalAICostMonitor
            cost_info = await cost_monitor.record_api_call(
                game_id=game_state.get("game_id", "unknown"),
                player_id=self.player_id,
                difficulty=self.difficulty,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                model=self.model,
            )

            latency_ms = (time.time() - start_time) * 1000

            logger.debug(
                f"AI decision made: tokens={input_tokens + output_tokens}, "
                f"cached={cached_tokens}, cost=${cost_info['cost']:.4f}, "
                f"latency={latency_ms:.0f}ms"
            )

            # Log the interaction (with template deduplication)
            log_prompt = _get_prompt_for_logging(prompt, "decision")
            ai_interaction_logger.info(
                f"DECISION REQUEST | game={game_state.get('game_id')} | player={self.player_id} | "
                f"difficulty={self.difficulty} | actions={available_actions}\n"
                f"PROMPT: {log_prompt}\n"
                f"TOOL: {provider_response.tool_name} | INPUT: {provider_response.tool_input}\n"
                f"TOKENS: input={input_tokens}, output={output_tokens}, cached={cached_tokens} | "
                f"COST: ${cost_info['cost']:.4f} | LATENCY: {latency_ms:.0f}ms"
            )

            # Use tool_use response directly (no JSON parsing needed)
            if provider_response.tool_name == "choose_action" and provider_response.tool_input:
                decision = provider_response.tool_input.copy()
            else:
                # Fallback to JSON parsing for non-tool responses (shouldn't happen with tool_choice)
                logger.warning("No tool_use response, falling back to JSON parsing")
                thinking, decision_text = self._extract_thinking_and_decision(
                    provider_response.text
                )
                try:
                    response_text = self._extract_json_from_response(decision_text)
                    decision = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    raise ValueError(f"AI returned invalid response: {provider_response.text}")

            # Validate action_type is in available_actions
            action_type = decision.get("action_type")
            if not action_type:
                logger.error(
                    f"AI decision missing action_type field. Response: {decision}"
                )
                raise ValueError(
                    f"AI response missing required 'action_type' field. "
                    f"Response: {decision}"
                )

            if action_type not in available_actions:
                logger.error(
                    f"AI chose unavailable action '{action_type}'. "
                    f"Available: {available_actions}"
                )
                raise ValueError(
                    f"AI chose invalid action '{action_type}'. "
                    f"Available actions: {available_actions}"
                )

            # Process any note the AI wants to save
            note_data = decision.pop("note", None)
            if note_data and isinstance(note_data, dict):
                turn_number = game_state.get("turn", 0)
                await memory_store.add_note(
                    game_id=game_id,
                    player_id=self.player_id,
                    content=note_data.get("content", ""),
                    category=note_data.get("category", "observation"),
                    turn_number=turn_number,
                    priority=note_data.get("priority", 1),
                )
                logger.debug(f"AI saved note: {note_data.get('category')} - {note_data.get('content', '')[:50]}...")

            # Add metadata (use reasoning from tool response if available)
            decision["_metadata"] = {
                "tokens_used": input_tokens + output_tokens,
                "cached_tokens": cached_tokens,
                "api_cost": cost_info["cost"],
                "latency_ms": latency_ms,
                "model": self.model,
                "provider": self.provider_name,
                "difficulty": self.difficulty,
                "thinking": decision.get("reasoning"),  # From tool response
                "note_saved": note_data is not None,
            }

            return decision

        except CostLimitExceeded as e:
            logger.error(f"Cost limit exceeded: {e}")
            raise

        except AIProviderRateLimitError as e:
            logger.error(f"Rate limit error: {e}")
            raise

        except AIProviderTimeoutError as e:
            logger.error(f"API timeout: {e}")
            raise

        except AIProviderConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise

        except AIProviderError as e:
            logger.error(f"AI provider error: {e}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error in AI decision: {e}", exc_info=True)
            raise

    async def make_interaction_response(
        self, game_state: dict, interaction: dict
    ) -> dict:
        """
        Respond to dogma interaction (card selection, color choice, etc.).

        Returns:
            dict with response details (selected_cards, selected_color, etc.)
        """
        start_time = time.time()

        try:
            # CRITICAL: For sharing actions, AI must wait for human players to respond first
            interaction_type = interaction.get("type", "")
            is_sharing = "sharing" in interaction_type.lower() or interaction.get(
                "context", ""
            ).startswith("sharing")

            if is_sharing:
                # Wait for human players to respond first (with 90 second timeout)
                await self._wait_for_human_players(game_state, interaction)
            else:
                # Normal think time for non-sharing interactions
                if self.think_time_ms > 0:
                    await asyncio.sleep(self.think_time_ms / 1000.0)

            # Build interaction-specific prompt
            prompt = self.prompt_builder.build_interaction_prompt(
                game_state=game_state, interaction=interaction
            )

            # Debug: Log interaction data and prompt
            logger.info("=== AI INTERACTION REQUEST ===")
            logger.info(f"Interaction type: {interaction.get('type')}")
            logger.info(
                f"Interaction data keys: {list(interaction.get('data', {}).keys())}"
            )
            logger.info(
                f"Full interaction: {json.dumps(interaction, indent=2, default=str)}"
            )
            logger.info(f"Prompt length: {len(prompt)} chars")
            logger.info(f"Prompt preview: {prompt[:500]}")
            logger.info("==============================")

            if not prompt or len(prompt) < 10:
                logger.error(
                    f"Empty or invalid prompt generated! Interaction: {interaction}"
                )
                raise ValueError(
                    f"Empty prompt for interaction type: {interaction.get('interaction_type')}"
                )

            # Get extended thinking budget for Pro+ difficulties
            thinking_budget = self._get_thinking_budget()

            # Get appropriate tools based on interaction type
            payload = self._unwrap_interaction_payload(interaction)
            payload_type = payload.get("type", "")
            interaction_tools = get_interaction_tools(payload_type)
            tool_name = interaction_tools[0]["name"] if interaction_tools else None

            # Make AI provider call with tool_use for structured output
            provider_response = await self.provider.send_message(
                prompt=prompt,
                system_prompt=self.prompt_builder.get_cached_system_context(),
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                thinking_budget=thinking_budget,
                tools=interaction_tools,
                tool_choice={"type": "tool", "name": tool_name} if tool_name else None,
            )

            input_tokens = provider_response.input_tokens
            output_tokens = provider_response.output_tokens
            cached_tokens = provider_response.cached_tokens

            # Record cost
            cost_info = await cost_monitor.record_api_call(
                game_id=game_state.get("game_id", "unknown"),
                player_id=self.player_id,
                difficulty=self.difficulty,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                model=self.model,
            )

            latency_ms = (time.time() - start_time) * 1000

            # Log interaction (with template deduplication)
            log_prompt = _get_prompt_for_logging(prompt, "interaction")
            ai_interaction_logger.info(
                f"INTERACTION REQUEST | game={game_state.get('game_id')} | player={self.player_id} | "
                f"difficulty={self.difficulty} | type={interaction.get('interaction_type')}\n"
                f"PROMPT: {log_prompt}\n"
                f"TOOL: {provider_response.tool_name} | INPUT: {provider_response.tool_input}\n"
                f"TOKENS: input={input_tokens}, output={output_tokens}, cached={cached_tokens} | "
                f"COST: ${cost_info['cost']:.4f} | LATENCY: {latency_ms:.0f}ms"
            )

            # Use tool_use response directly
            if provider_response.tool_input:
                interaction_response = provider_response.tool_input.copy()
            else:
                # Fallback to JSON parsing
                logger.warning("No tool_use response, falling back to JSON parsing")
                raw_response = provider_response.text
                response_text = self._extract_json_from_response(raw_response)
                if not response_text or response_text.strip() == "":
                    raise ValueError(f"AI returned empty response: {raw_response}")
                interaction_response = json.loads(response_text)

            # Validate choose_option responses
            if payload_type == "choose_option":
                if not self._validate_choose_option_response(
                    payload,
                    interaction_response,
                    game_id=game_state.get("game_id"),
                ):
                    raise ValueError(
                        f"AI choose_option response validation failed. "
                        f"Response: {interaction_response}, Options: {payload.get('options')}"
                    )

            # Add metadata
            interaction_response["_metadata"] = {
                "tokens_used": input_tokens + output_tokens,
                "cached_tokens": cached_tokens,
                "api_cost": cost_info["cost"],
                "latency_ms": latency_ms,
                "provider": self.provider_name,
            }

            return interaction_response

        except Exception as e:
            logger.error(f"Error in interaction response: {e}", exc_info=True)
            raise

    def get_stats(self) -> dict:
        """Get AI agent statistics"""
        return {
            "player_id": self.player_id,
            "difficulty": self.difficulty,
            "model": self.model,
            "provider": self.provider_name,
            "think_time_ms": self.think_time_ms,
            "max_tokens": self.max_tokens,
        }
