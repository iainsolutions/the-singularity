"""
AI Prompt Builder with Tiered Context Optimization

Builds difficulty-appropriate prompts with optimized context sizing for faster,
cheaper responses on lower difficulties.
"""

from logging_config import get_logger

logger = get_logger(__name__)

# Viability warning markers - used by AITurnExecutor to filter actions.
# USELESS = provably cannot produce any effect (hard filter).
# LOW_VALUE = technically playable but unlikely to help (kept for prompt warnings).
VIABILITY_USELESS = "USELESS"
VIABILITY_LOW_VALUE = "LOW VALUE"


class AIPromptBuilder:
    """Build optimized prompts for AI decision making"""

    def __init__(self, difficulty: str):
        self.difficulty = difficulty
        self._card_descriptions = None  # Cache for card descriptions
        self._card_data_cache = None  # Cache for full card data (viability checks)

    def build_action_prompt_with_cot(
        self,
        game_state: dict,
        available_actions: list,
        difficulty: str | None = None,
        notes_text: str | None = None,
    ) -> tuple[str, str | None]:
        """Build a minimal prompt: game state + available actions. Let the model reason."""
        parts = []

        # Game state
        parts.append("<game_state>")
        parts.append(self._format_game_state_xml(game_state))
        parts.append("</game_state>")

        # Available actions with dogma symbol hints
        action_lines = []
        player_state = game_state.get("current_player_state", {})
        player_symbols = player_state.get("symbol_counts", {})
        opponents = game_state.get("opponents", [])
        card_data_cache = self._get_card_data_cache()

        for action in available_actions:
            if action.startswith("dogma:"):
                card_name = action.split(":", 1)[1]
                card_data = card_data_cache.get(card_name, {})
                resource = card_data.get("dogma_resource")
                if resource and opponents:
                    my_count = player_symbols.get(resource, 0)
                    opp_counts = [o.get("symbol_counts", {}).get(resource, 0) for o in opponents]
                    max_opp = max(opp_counts) if opp_counts else 0
                    has_demand = any(e.get("is_demand") for e in card_data.get("dogma_effects", []))
                    tags = []
                    if max_opp >= my_count:
                        tags.append("SHARED")
                    if has_demand:
                        if max_opp >= my_count:
                            tags.append("DEMAND BLOCKED")
                        else:
                            tags.append("DEMAND ACTIVE")
                    hint = f" [{', '.join(tags)}, {resource}: you {my_count} vs opp {max_opp}]" if tags else f" [{resource}: you {my_count} vs opp {max_opp}]"
                    action_lines.append(f"{action}{hint}")
                else:
                    action_lines.append(action)
            else:
                action_lines.append(action)

        parts.append(f"\n<available_actions>\n{', '.join(action_lines)}\n</available_actions>")

        # Previous error context (retries only)
        previous_error = game_state.get("_previous_error")
        if previous_error:
            parts.append(
                f"\n<error>{previous_error}\n"
                f"You MUST choose from the available_actions list above.</error>"
            )

        parts.append(
            '\nChoose the best action. Return ONLY JSON:\n'
            '{"reasoning": "why this action", "action_type": "exact action from list"}'
        )

        return "\n".join(parts), None

    def _format_game_state_xml(self, game_state: dict) -> str:
        """Format game state with XML tags (provider-agnostic)."""
        player_state = game_state.get("current_player_state", {})
        hand = player_state.get("hand", [])
        board = player_state.get("board", {})
        symbols = player_state.get("symbol_counts", {})
        card_descriptions = self._get_card_descriptions()

        lines = []

        # Turn info
        lines.append("  <turn_info>")
        lines.append(
            f"    <turn_number>{game_state.get('turn_number', 0)}</turn_number>"
        )
        lines.append(
            f"    <actions_remaining>{player_state.get('actions_remaining', 0)}</actions_remaining>"
        )
        lines.append("  </turn_info>")

        # Your position
        lines.append("\n  <your_position>")
        lines.append(f'    <hand count="{len(hand)}">')
        if hand:
            for card in hand:
                desc = card_descriptions.get(card["name"], "")
                if desc:
                    lines.append(
                        f"      <card name=\"{card['name']}\" age=\"{card['age']}\" color=\"{card['color']}\">"
                    )
                    lines.append(f"        <effect>{desc}</effect>")
                    lines.append("      </card>")
                else:
                    lines.append(
                        f"      <card name=\"{card['name']}\" age=\"{card['age']}\" color=\"{card['color']}\" />"
                    )
        else:
            lines.append("      <empty />")
        lines.append("    </hand>")

        # Board (with splay states)
        splay_directions = board.get("splay_directions", {})
        lines.append("    <board>")
        has_board = False
        for color in ["red", "blue", "green", "yellow", "purple"]:
            color_cards = board.get(f"{color}_cards", [])
            if color_cards:
                has_board = True
                top = color_cards[-1]
                splay = splay_directions.get(color, "none")
                desc = card_descriptions.get(top.get("name"), "")
                if desc:
                    lines.append(
                        f'      <stack color="{color}" count="{len(color_cards)}" splay="{splay}">'
                    )
                    lines.append(
                        f"        <top name=\"{top.get('name')}\" age=\"{top.get('age')}\">"
                    )
                    lines.append(f"          <effect>{desc}</effect>")
                    lines.append("        </top>")
                    lines.append("      </stack>")
                else:
                    lines.append(
                        f'      <stack color="{color}" count="{len(color_cards)}" splay="{splay}"><top name="{top.get("name")}" age="{top.get("age")}" /></stack>'
                    )
        if not has_board:
            lines.append("      <empty />")
        lines.append("    </board>")

        # Score and achievements
        lines.append(f"    <score>{player_state.get('score_total', 0)}</score>")
        lines.append(
            f"    <achievements>{len(player_state.get('achievements', []))}</achievements>"
        )

        # Symbols
        lines.append("    <symbols>")
        lines.append(f"      <castles>{symbols.get('castle', 0)}</castles>")
        lines.append(f"      <crowns>{symbols.get('crown', 0)}</crowns>")
        lines.append(f"      <leaves>{symbols.get('leaf', 0)}</leaves>")
        lines.append(f"      <lightbulbs>{symbols.get('lightbulb', 0)}</lightbulbs>")
        lines.append(f"      <factories>{symbols.get('factory', 0)}</factories>")
        lines.append(f"      <clocks>{symbols.get('clock', 0)}</clocks>")
        lines.append("    </symbols>")

        # Achievement status (compact format for strategic planning)
        available_ages = game_state.get("available_achievement_ages", [])
        your_achievements = player_state.get("achievements", [])
        your_ages = [a.get("age", 0) for a in your_achievements if a.get("age")]
        opponent_ages = []
        for opp in game_state.get("opponents", []):
            for a in opp.get("achievements", []):
                if a.get("age"):
                    opponent_ages.append(a.get("age"))
        lines.append("    <achievement_status>")
        lines.append(f'      <available ages="{",".join(map(str, available_ages))}" />')
        lines.append(f'      <yours ages="{",".join(map(str, sorted(your_ages)))}" count="{len(your_achievements)}" />')
        lines.append(f'      <opponent ages="{",".join(map(str, sorted(opponent_ages)))}" />')
        lines.append("    </achievement_status>")

        # Deck status (empty/low for draw planning)
        deck_status = game_state.get("deck_status", {})
        empty_ages = deck_status.get("empty", [])
        low_ages = deck_status.get("low", [])
        if empty_ages or low_ages:
            lines.append(f'    <deck_status empty="{",".join(map(str, empty_ages))}" low="{",".join(map(str, low_ages))}" />')
        lines.append("  </your_position>")

        # AI Memory (strategic context from previous turns)
        ai_memory = player_state.get("ai_memory", {})
        if ai_memory:
            lines.append("\n  <your_memory>")
            
            # Goals (what you're trying to achieve)
            goals = ai_memory.get("goals", [])
            if goals:
                lines.append("    <goals>")
                for goal in goals:
                    lines.append(f"      <goal>{goal}</goal>")
                lines.append("    </goals>")
            
            # Plan (multi-turn strategy)
            plan = ai_memory.get("plan", "")
            if plan:
                lines.append(f"    <plan>{plan}</plan>")
            
            # Observations (what you've learned)
            observations = ai_memory.get("observations", [])
            if observations:
                lines.append("    <observations>")
                for obs in observations:
                    lines.append(f"      <observation>{obs}</observation>")
                lines.append("    </observations>")
            
            lines.append("  </your_memory>")

        # Opponents
        opponents = game_state.get("opponents", [])
        if opponents:
            lines.append("\n  <opponents>")
            for opp in opponents:
                opp_symbols = opp.get("symbol_counts", {})
                lines.append(f"    <opponent name=\"{opp['name']}\">")
                lines.append(f"      <score>{opp['score_total']}</score>")
                lines.append(
                    f"      <achievements>{len(opp.get('achievements', []))}</achievements>"
                )
                lines.append(f"      <hand_count>{opp['hand_count']}</hand_count>")
                lines.append("      <symbols>")
                lines.append(
                    f"        <castles>{opp_symbols.get('castle', 0)}</castles>"
                )
                lines.append(f"        <crowns>{opp_symbols.get('crown', 0)}</crowns>")
                lines.append(f"        <leaves>{opp_symbols.get('leaf', 0)}</leaves>")
                lines.append(f"        <lightbulbs>{opp_symbols.get('lightbulb', 0)}</lightbulbs>")
                lines.append(f"        <factories>{opp_symbols.get('factory', 0)}</factories>")
                lines.append(f"        <clocks>{opp_symbols.get('clock', 0)}</clocks>")
                lines.append("      </symbols>")
                # Opponent board (top cards and colors — needed for demand/sharing evaluation)
                opp_board = opp.get("board", {})
                opp_board_lines = []
                for color in ["red", "blue", "green", "yellow", "purple"]:
                    opp_color_cards = opp_board.get(f"{color}_cards", [])
                    if opp_color_cards:
                        top = opp_color_cards[-1]
                        splay = opp_board.get("splay_directions", {}).get(color, "none")
                        top_name = top.get("name", "?")
                        top_age = top.get("age", "?")
                        desc = card_descriptions.get(top_name, "")
                        if desc:
                            opp_board_lines.append(
                                f'        <stack color="{color}" count="{len(opp_color_cards)}" splay="{splay}">'
                            )
                            opp_board_lines.append(
                                f'          <top name="{top_name}" age="{top_age}">'
                            )
                            opp_board_lines.append(f"            <effect>{desc}</effect>")
                            opp_board_lines.append("          </top>")
                            opp_board_lines.append("        </stack>")
                        else:
                            opp_board_lines.append(
                                f'        <stack color="{color}" count="{len(opp_color_cards)}" splay="{splay}">'
                                f'<top name="{top_name}" age="{top_age}" /></stack>'
                            )
                if opp_board_lines:
                    lines.append("      <board>")
                    lines.extend(opp_board_lines)
                    lines.append("      </board>")
                lines.append("    </opponent>")
            lines.append("  </opponents>")

        return "\n".join(lines)

    def _get_advanced_thinking_framework(
        self, game_state: dict, available_actions: list
    ) -> str:
        """Get structured algorithmic thinking framework."""
        # Pre-compute achievement check
        achieve_actions = [a for a in available_actions if a.startswith("achieve:")]
        achieve_hint = ""
        if achieve_actions:
            achieve_hint = f"""
## 🏆 ACHIEVEMENT AVAILABLE: {achieve_actions}
STOP! Achievements win the game. Unless opponent wins THIS TURN, CLAIM IT NOW.
"""

        return f"""
<task>
Choose ONE action from the annotated list above.
{achieve_hint}
## DECISION PRIORITY:
1. achieve → ALWAYS claim if available (6 achievements = WIN)
2. dogma marked UNSHARED that draws/scores/melds for you → USE IT
3. dogma with DEMAND VIABLE that hurts opponent → USE IT
4. meld a card that enables a better dogma next turn → MELD
5. draw → safe default

## KEY RULES:
- SHARED means opponent executes the same non-demand effects - avoid unless YOUR benefit outweighs theirs
- DEMAND BLOCKED means the demand effect does nothing - only use if non-demand effects are still good
- Higher age cards are generally better - meld/draw to advance

</task>

<decision>
Return ONLY JSON:
{{"reasoning": "1 sentence: what I gain", "action_type": "exact action from list"}}
</decision>
"""

    def _get_card_descriptions(self) -> dict[str, str]:
        """Load and cache card effect descriptions from BaseCards.json"""
        if self._card_descriptions is not None:
            return self._card_descriptions

        try:
            from data.cards import get_all_cards

            all_cards = get_all_cards()
            self._card_descriptions = {}

            for card in all_cards:
                # Cities expansion: Handle special icons for city cards
                if hasattr(card, 'special_icons') and card.special_icons:
                    icon_descriptions = []
                    for icon in card.special_icons:
                        icon_type = icon.type
                        if icon_type == "search":
                            target = icon.parameters.get("target_icon", "unknown")
                            icon_descriptions.append(f"Search for {target} cards")
                        elif icon_type == "plus":
                            icon_descriptions.append("Draw +1 age")
                        elif icon_type == "arrow":
                            direction = icon.parameters.get("direction", "right")
                            icon_descriptions.append(f"Splay {direction}")
                        elif icon_type == "junk":
                            icon_descriptions.append("Junk achievement")
                        elif icon_type == "uplift":
                            icon_descriptions.append("Uplift deck (+2 age)")
                        elif icon_type == "unsplay":
                            icon_descriptions.append("Unsplay opponents")
                        elif icon_type == "flag":
                            color = icon.parameters.get("target_color", "color")
                            icon_descriptions.append(f"{color.capitalize()} Flag achievement")
                        elif icon_type == "fountain":
                            icon_param = icon.parameters.get("target_icon", "icon")
                            icon_descriptions.append(f"{icon_param.capitalize()} Fountain achievement")

                    self._card_descriptions[card.name] = " | ".join(icon_descriptions) if icon_descriptions else "City card"

                # Base game cards: Extract dogma effects
                else:
                    effects_text = []
                    for effect in card.dogma_effects:
                        if effect.text:
                            effects_text.append(effect.text)

                    if effects_text:
                        self._card_descriptions[card.name] = " | ".join(effects_text)
                    else:
                        self._card_descriptions[card.name] = "No dogma effect"

            logger.debug(
                f"Loaded descriptions for {len(self._card_descriptions)} cards"
            )
            return self._card_descriptions

        except Exception as e:
            logger.error(f"Failed to load card descriptions: {e}")
            self._card_descriptions = {}
            return self._card_descriptions

    def build_action_prompt(
        self, game_state: dict, available_actions: list, difficulty: str | None = None
    ) -> str:
        """Build difficulty-optimized prompt for action decisions"""

        diff = difficulty or self.difficulty

        prompt_parts = []

        # Core state (always included)
        prompt_parts.append(self._format_current_state(game_state))
        prompt_parts.append(f"\nAVAILABLE ACTIONS: {', '.join(available_actions)}")

        # CRITICAL: Achievement priority warning (for ALL difficulties)
        if "achieve" in available_actions:
            player_state = game_state.get("current_player_state", {})
            score = player_state.get("score_total", 0)
            achievements = player_state.get("achievements", [])
            achievement_count = len(achievements)

            # Calculate which ages are eligible
            board = player_state.get("board", {})
            max_age = 1
            for color in ["red", "blue", "green", "yellow", "purple"]:
                color_cards = board.get(f"{color}_cards", [])
                if color_cards:
                    top_card = color_cards[-1]
                    max_age = max(max_age, top_card.get("age", 1))

            eligible_ages = [
                age for age in range(1, 11) if score >= (age * 5) and max_age >= age
            ]

            prompt_parts.append("\n" + "=" * 70)
            prompt_parts.append("🏆 ACHIEVEMENT AVAILABLE - HIGH PRIORITY ACTION! 🏆")
            prompt_parts.append("=" * 70)
            prompt_parts.append(
                f"You currently have {achievement_count}/6 achievements (need 6 to WIN!)"
            )
            prompt_parts.append(f"Your score: {score} points")
            prompt_parts.append(f"Eligible to claim ages: {eligible_ages}")
            prompt_parts.append("")
            prompt_parts.append(
                "⚠️  STRATEGIC PRIORITY: CLAIM ACHIEVEMENTS when available!"
            )
            prompt_parts.append(
                "   - Achievements are a PRIMARY win condition (6 achievements = instant win)"
            )
            prompt_parts.append(
                "   - If 'achieve' is offered, you meet ALL requirements"
            )
            prompt_parts.append("   - Each achievement gets you closer to victory")
            prompt_parts.append("   - Opponent might claim it first if you wait!")
            prompt_parts.append("")
            prompt_parts.append(
                "💡 Unless you have a CRITICAL reason (e.g., opponent about to win and you"
            )
            prompt_parts.append(
                "   must block them THIS turn), you should CLAIM THE ACHIEVEMENT NOW!"
            )
            prompt_parts.append("=" * 70 + "\n")

        # Add anti-pattern warnings for all difficulties
        from services.ai_card_synergies import CardSynergies

        warnings = CardSynergies.get_anti_pattern_warnings(game_state)
        if warnings:
            prompt_parts.append("\n" + "\n".join(warnings))

        # Add phase-specific guidance for intermediate+
        if diff in ["intermediate", "skilled", "advanced", "pro", "expert", "master"]:
            player_state = game_state.get("current_player_state", {})
            # Determine current phase based on highest card age on board
            board = player_state.get("board", {})
            max_age = 1
            for color in ["red", "blue", "green", "yellow", "purple"]:
                color_cards = board.get(f"{color}_cards", [])
                if color_cards:
                    top_card = color_cards[-1]
                    max_age = max(max_age, top_card.get("age", 1))

            phase_guidance = CardSynergies.get_phase_guidance(max_age)
            prompt_parts.append("\nCURRENT PHASE GUIDANCE:")
            prompt_parts.append("Priority actions:")
            for action in phase_guidance["priority_actions"]:
                prompt_parts.append(f"  - {action}")
            prompt_parts.append("Avoid:")
            for avoid in phase_guidance["avoid"]:
                prompt_parts.append(f"  - {avoid}")

        if diff in ["novice", "beginner"]:
            # Minimal context - just current state
            prompt_parts.append(self._format_opponents_basic(game_state))

            # Add critical dogma viability checks for novice players
            prompt_parts.append(
                "\n⚠️ CRITICAL DOGMA CHECKS (Read BEFORE using dogma!):"
            )
            prompt_parts.append(self._get_dogma_viability_warnings(game_state))

            prompt_parts.append(
                "\nREMEMBER: Only use DOGMA if the card effect will actually work! "
                "Check the warnings above. If a dogma is marked as USELESS, just DRAW instead.\n\n"
                "DEMAND MECHANICS: Demands ONLY affect opponents with FEWER of the required symbol than you. "
                "If an opponent has >= your symbol count, they are NOT vulnerable and the demand does NOTHING to them!"
            )

        elif diff in ["intermediate", "skilled"]:
            # Add recent history and opponent info
            prompt_parts.append(self._format_opponents_detailed(game_state))
            prompt_parts.append(self._format_recent_actions(game_state, count=5))
            prompt_parts.append(
                "\nPRIORITIZE DOGMA: Your default action should be dogma. "
                "Only draw/meld when you need to set up better dogmas. "
                "Dogma is how you score, draw efficiently, and gain advantage."
            )

        elif diff in ["advanced", "pro", "expert", "master"]:
            # Full context
            prompt_parts.append(self._format_opponents_detailed(game_state))
            prompt_parts.append(self._format_recent_actions(game_state, count=10))
            prompt_parts.append(self._format_board_analysis(game_state))
            prompt_parts.append(self._format_achievement_status(game_state))
            prompt_parts.append(self._format_sharing_analysis(game_state))
            prompt_parts.append(
                "\nDOGMA-FIRST STRATEGY: Dogma should be 80-90% of your actions. "
                "Plan dogma chains multiple turns ahead. Draw/meld only to enable "
                "powerful dogma sequences. Every decision = which dogma to enable next."
            )
            prompt_parts.append(
                "\nDEMAND EFFECTS: Demands only affect opponents with FEWER of the required symbol than you. "
                "Check symbol counts before using demands! If opponent has >= your symbol count, the demand won't work."
            )

        # Response format instructions
        prompt_parts.append(self._get_response_format())

        return "\n\n".join(prompt_parts)

    def _format_select_cards_prompt(
        self,
        message: str,
        eligible_cards: list,
        min_count: int,
        max_count: int,
        is_optional: bool = False,
        include_strategic_considerations: bool = False,
        game_state: dict | None = None,
    ) -> list[str]:
        """Helper method to format select_cards interaction prompts.

        Consolidates the card selection formatting logic used in both direct
        select_cards interactions and nested dogma_interaction select_cards.

        Args:
            message: Interaction message to display
            eligible_cards: List of cards that can be selected
            min_count: Minimum number of cards to select
            max_count: Maximum number of cards to select
            is_optional: Whether the selection can be declined
            include_strategic_considerations: Whether to include advanced strategy tips
            game_state: Game state for strategic considerations (required if include_strategic_considerations=True)

        Returns:
            List of prompt parts to be joined
        """
        prompt_parts = []

        # Check if this is a demand effect (opponent taking cards from you)
        # Check both game_state flag AND message content for transfer-to-opponent semantics
        is_demand_target = (
            game_state.get("is_demand_target", False) if game_state else False
        )

        # Also detect from message content (e.g., "DEMAND:" or "transfer to opponent")
        is_transfer_to_opponent = (
            "DEMAND:" in message.upper()
            or "TRANSFER TO OPPONENT" in message.lower()
            or "GIVE TO OPPONENT" in message.lower()
        )

        if is_demand_target or is_transfer_to_opponent:
            prompt_parts.append(f"OPPONENT DEMAND: {message}")
            prompt_parts.append(
                "Note: You are responding to an opponent's card effect. "
                "Check the recent actions to see which card is being activated and review "
                "that card's dogma_effects in the opponent's board to understand what happens to your selected cards.\n\n"
                "STRATEGY: When forced to give cards to your opponent (transfer/demand effects), "
                "select your LEAST useful cards to minimize the loss. Consider:\n"
                "- Cards that don't fit your current board strategy\n"
                "- Cards with symbols you don't need\n"
                "- Duplicate colors you already have splayed\n"
                "Don't give away your best cards - save those for your own melds and dogmas!"
            )
        else:
            prompt_parts.append(f"INTERACTION: {message}")

        prompt_parts.append("\nELIGIBLE CARDS:")
        for card in eligible_cards:
            prompt_parts.append(
                f"  - {card.get('name')} (age {card.get('age')}, {card.get('color')})"
            )

        # CRITICAL: Include current board state so AI can make informed decisions
        # Without this, AI makes up facts like "duplicate color I already have splayed"
        if game_state:
            prompt_parts.append("\nYOUR CURRENT BOARD:")
            player_state = game_state.get("current_player_state", {})
            board = player_state.get("board", {})

            # Show board stacks
            has_stacks = False
            for color in ["red", "blue", "green", "yellow", "purple"]:
                color_cards = board.get(f"{color}_cards", [])
                if color_cards:
                    if not has_stacks:
                        prompt_parts.append("  Stacks:")
                        has_stacks = True
                    top_card = color_cards[-1] if color_cards else {}
                    top_name = top_card.get("name", "Unknown") if isinstance(top_card, dict) else getattr(top_card, "name", "Unknown")
                    prompt_parts.append(f"    - {color}: {top_name} (top)")

            if not has_stacks:
                prompt_parts.append("  No cards on board")

            # Show hand if selecting from hand
            if message and ("from your hand" in message.lower() or "from hand" in message.lower()):
                hand = player_state.get("hand", [])
                if hand:
                    prompt_parts.append(f"  Hand: {len(hand)} cards")

        # Format requirements with optional flag
        if is_optional:
            prompt_parts.append(
                f"\nREQUIREMENTS: Select {min_count} to {max_count} cards (optional)"
            )
        else:
            prompt_parts.append(
                f"\nREQUIREMENTS: Select {min_count} to {max_count} cards"
            )

        # Add strategic considerations for advanced players
        if include_strategic_considerations and game_state:
            prompt_parts.append(self._format_strategic_considerations(game_state))

        # Format JSON response instructions
        if is_optional:
            # More detailed instructions for optional selections
            prompt_parts.append(
                "\n\nRespond with ONLY valid JSON (no extra text):\n"
                "{\n"
                '  "selected_cards": ["Card Name"],\n'
                '  "reasoning": "Brief explanation"\n'
                "}\n\n"
                "IMPORTANT: Use card NAMES (not IDs). Return pure JSON only. Empty array [] is valid if min_count is 0."
            )
        else:
            # Simpler instructions for required selections
            prompt_parts.append(
                "\n\nRespond with JSON:\n"
                "{\n"
                '  "selected_cards": ["Card Name"],\n'
                '  "reasoning": "Brief explanation"\n'
                "}\n\n"
                "IMPORTANT: Use card NAMES (not IDs)."
            )

        return prompt_parts

    def build_interaction_prompt(self, game_state: dict, interaction: dict) -> str:
        """Build prompt for responding to dogma interactions"""

        interaction_type = interaction.get("type")
        message = interaction.get("message", "")

        prompt_parts = []

        # Only check for "select_cards" - the canonical type from StandardInteractionBuilder
        # "card_selection" was legacy from old phase-based system (CardSelectionInteraction)
        if interaction_type == "select_cards":
            eligible_cards = interaction.get("eligible_cards", [])
            min_count = interaction.get("min_count", 1)
            max_count = interaction.get("max_count", 1)
            is_optional = interaction.get("is_optional", False)

            # Use helper method to format select_cards prompt
            prompt_parts.extend(
                self._format_select_cards_prompt(
                    message=message,
                    eligible_cards=eligible_cards,
                    min_count=min_count,
                    max_count=max_count,
                    is_optional=is_optional,
                    include_strategic_considerations=True,  # All difficulties get best prompts
                    game_state=game_state,
                )
            )

        elif interaction_type == "choose_option":
            prompt_parts.extend(
                self._format_choose_option_prompt(
                    message=message,
                    options=interaction.get("options", []),
                    allow_cancel=interaction.get("allow_cancel")
                    or interaction.get("can_cancel")
                    or interaction.get("is_optional"),
                    default_option=interaction.get("default_option"),
                    store_result=interaction.get("store_result"),
                )
            )

        elif interaction_type == "color_choice":
            eligible_colors = interaction.get("eligible_colors", [])

            prompt_parts.append(f"INTERACTION: {message}")
            prompt_parts.append(f"\nELIGIBLE COLORS: {', '.join(eligible_colors)}")

            # All difficulties get best prompts (board by color is useful for color selection)
            prompt_parts.append(self._format_board_by_color(game_state))

            prompt_parts.append(
                "\n\nRespond with JSON:\n"
                "{\n"
                '  "selected_color": "red",\n'
                '  "reasoning": "Explanation"\n'
                "}"
            )

        elif interaction_type == "share_effect":
            effect_text = interaction.get("effect_text", "")
            can_share = interaction.get("can_share", False)

            prompt_parts.append(f"SHARE EFFECT INTERACTION: {message}")
            prompt_parts.append(f"\nEffect: {effect_text}")

            if can_share:
                prompt_parts.append(
                    "\nYou meet the symbol requirement and CAN execute this share effect."
                )
                prompt_parts.append("You can choose to execute it or decline.")
            else:
                prompt_parts.append(
                    "\nYou do NOT meet the symbol requirement and cannot execute this share."
                )

            # All difficulties get best prompts (strategic considerations)
            prompt_parts.append(self._format_strategic_considerations(game_state))

            prompt_parts.append(
                "\n\nRespond with JSON:\n"
                "{\n"
                '  "execute_share": true,  // or false to decline\n'
                '  "reasoning": "Brief explanation of your decision"\n'
                "}"
            )

        elif interaction_type == "dogma_interaction":
            # Handle wrapped dogma interactions (from StandardInteractionBuilder)
            # Extract the actual nested interaction data
            nested_data = interaction.get("data", {})
            nested_type = nested_data.get("type")
            # CRITICAL: Get message from nested data, not top level
            nested_message = nested_data.get("message", "")

            if nested_type == "select_cards":
                # Re-route to select_cards handler using shared helper method
                eligible_cards = nested_data.get("eligible_cards", [])
                min_count = nested_data.get("min_count", 0)
                max_count = nested_data.get("max_count", 1)
                is_optional = nested_data.get("is_optional", False)

                # Use helper method to format select_cards prompt
                prompt_parts.extend(
                    self._format_select_cards_prompt(
                        message=nested_message,
                        eligible_cards=eligible_cards,
                        min_count=min_count,
                        max_count=max_count,
                        is_optional=is_optional,
                        include_strategic_considerations=False,  # Don't include strategy for nested interactions
                        game_state=game_state,
                    )
                )
            elif nested_type == "choose_option":
                prompt_parts.extend(
                    self._format_choose_option_prompt(
                        message=nested_message,
                        options=nested_data.get("options", []),
                        allow_cancel=nested_data.get("allow_cancel")
                        or nested_data.get("can_cancel")
                        or nested_data.get("is_optional"),
                        default_option=nested_data.get("default_option"),
                        store_result=nested_data.get("store_result"),
                    )
                )
            else:
                # Other nested interaction types
                prompt_parts.append(f"INTERACTION: {nested_message}")
                prompt_parts.append(f"\nInteraction data: {nested_data}")
                prompt_parts.append(
                    "\n\nRespond with ONLY valid JSON (no extra text). "
                    "Format depends on interaction type."
                )

        else:
            # Fallback for truly unknown interaction types
            prompt_parts.append(f"INTERACTION: {message}")
            prompt_parts.append(f"\nInteraction type: {interaction_type}")
            prompt_parts.append(f"\nInteraction data: {interaction}")
            prompt_parts.append(
                "\n\nRespond with ONLY valid JSON based on the interaction type (no extra text)."
            )

        return "\n".join(prompt_parts)

    def _format_choose_option_prompt(
        self,
        *,
        message: str,
        options: list,
        allow_cancel: bool | None = False,
        default_option: str | None = None,
        store_result: str | None = None,
    ) -> list[str]:
        """Format option selection prompts with clear evaluation guidance."""

        prompt_parts = [f"INTERACTION: {message}"]

        normalized_options = options or []
        if not isinstance(normalized_options, list):
            normalized_options = [normalized_options]

        prompt_parts.append("\nOPTIONS:")
        for idx, option in enumerate(normalized_options, start=1):
            if isinstance(option, dict):
                description = option.get("description") or option.get("label")
                value = option.get("value")
                extra_details: list[str] = []
                if value is not None and value != description:
                    extra_details.append(f"value={value}")
                summary = option.get("summary") or option.get("details")
                if summary:
                    extra_details.append(summary)
                if option.get("actions"):
                    extra_details.append("triggers follow-up actions")
                rendered = description or str(option)
                if extra_details:
                    rendered = f"{rendered} ({'; '.join(extra_details)})"
                prompt_parts.append(f"  {idx}. {rendered}")
            else:
                prompt_parts.append(f"  {idx}. {option}")

        if default_option:
            prompt_parts.append(
                f"\nDEFAULT OPTION: {default_option} (only use if it remains the best choice)."
            )

        if store_result:
            prompt_parts.append(
                f"This decision populates the '{store_result}' field—return the option value that should be stored."
            )

        evaluation_tips = (
            "Evaluate each option's impact on your board, hand, and upcoming turns. "
            "Compare how the choice advances your current strategy, disrupts opponents, "
            "or preserves future flexibility before deciding."
        )
        prompt_parts.append(f"\nSTRATEGY NOTES: {evaluation_tips}")

        response_instructions = [
            "\nRespond with ONLY valid JSON (no additional prose):",
            "{",
            '  "chosen_option": "exact option text or stored value",',
            '  "reasoning": "Brief explanation for why this option is best"',
            "}",
        ]

        if allow_cancel:
            response_instructions.append(
                'If declining is optimal, use "chosen_option": null and include "cancelled": true with reasoning.'
            )

        prompt_parts.append("\n".join(response_instructions))

        return prompt_parts

    def get_cached_system_context(self) -> list:
        """Minimal system context: just the game rules."""
        return [
            {
                "type": "text",
                "text": self._get_rules_minimal(),
                "cache_control": {"type": "ephemeral"},
            },
        ]

    def _get_rules_minimal(self) -> str:
        """Concise Innovation rules — everything the AI needs, nothing it doesn't."""
        return """You are playing Innovation, a card game. Win by claiming 6 achievements.

ACTIONS (2 per turn):
- Draw: draw a card from the age deck matching your highest top card age (or age 1)
- Meld: play a card from hand onto your board (on its color stack, covering the old top card)
- Dogma: activate the top card's effect on a color stack
- Achieve: claim an achievement (need score >= age*5 AND a top card of that age or higher)

DOGMA MECHANICS:
- Each card has a dogma resource symbol (castle, crown, leaf, lightbulb, factory, clock)
- Non-demand effects: opponents with >= your count of that symbol SHARE the effect (they benefit too)
- "I demand" effects: only hit opponents with FEWER of that symbol than you
- If sharing helps the opponent more than you, don't use that dogma — just draw
- Read the effect text carefully: if you don't meet the requirements (e.g. need hand cards you don't have), the dogma does nothing

SYMBOLS:
- Symbols come from cards on your board (not hand)
- Splaying a stack reveals extra symbols on covered cards
- Symbol counts determine dogma sharing and demand eligibility

SCORING & ACHIEVEMENTS:
- Score pile is separate from hand and board
- To achieve age N: need score >= N*5 AND at least one top card of age >= N on your board
- First to 6 achievements wins

RESPONSE FORMAT:
Return ONLY valid JSON: {"reasoning": "brief explanation", "action_type": "exact action from available_actions list"}
For interactions (card selection etc): {"selected_cards": ["card_id"]} or {"chosen_option": "value"} or {"decline": true}"""

    def _format_current_state(self, game_state: dict) -> str:
        """Format current game state"""
        player_state = game_state.get("current_player_state", {})
        card_descriptions = self._get_card_descriptions()

        parts = ["CURRENT GAME STATE:"]
        parts.append(f"Turn: {game_state.get('turn_number', 0)}")
        parts.append(f"Actions remaining: {player_state.get('actions_remaining', 0)}")

        # Hand - now with card effects
        hand = player_state.get("hand", [])
        hand_count = len(hand)
        if hand:
            parts.append(f"\nYour hand ({hand_count} cards):")
            for c in hand:
                card_name = c["name"]
                description = card_descriptions.get(card_name, "")
                if description:
                    parts.append(f"  - {card_name} (age {c['age']}): {description}")
                else:
                    parts.append(f"  - {card_name} (age {c['age']})")
        else:
            parts.append("\n⚠️  Your hand: EMPTY (0 cards)")
            parts.append(
                "    WARNING: Cannot use dogmas that require hand cards! (e.g., Code of Laws, Oars)"
            )

        # Board - show what cards you can dogma with (with effects)
        board = player_state.get("board", {})
        has_board_cards = any(
            board.get(f"{color}_cards")
            for color in ["red", "blue", "green", "yellow", "purple"]
        )
        if has_board_cards:
            parts.append("\nYOUR BOARD (cards you can dogma):")
            for color in ["red", "blue", "green", "yellow", "purple"]:
                color_cards = board.get(f"{color}_cards", [])
                if color_cards:
                    top_card = color_cards[-1]  # Top card is first in list
                    card_name = top_card.get("name")
                    description = card_descriptions.get(card_name, "")

                    # Add warning if card needs hand cards but hand is empty
                    hand_warning = ""
                    if hand_count == 0 and self._requires_hand_cards(card_name):
                        hand_warning = " ⚠️  USELESS - requires hand cards!"

                    if description:
                        parts.append(
                            f"  {color.upper()}: {card_name} (age {top_card.get('age')}): {description}{hand_warning}"
                        )
                    else:
                        parts.append(
                            f"  {color.upper()}: {card_name} (age {top_card.get('age')}){hand_warning}"
                        )
        else:
            parts.append("\nYour board: Empty (no cards to dogma!)")

        # Symbol counts for demand evaluation
        symbol_counts = player_state.get("symbol_counts", {})
        if symbol_counts:
            counts_str = ", ".join(
                [f"{sym}: {count}" for sym, count in symbol_counts.items()]
            )
            parts.append(f"\nYour symbols: {counts_str}")

        # Score
        parts.append(f"Your score: {player_state.get('score_total', 0)}")

        return "\n".join(parts)

    def _requires_hand_cards(self, card_name: str) -> bool:
        """Check if a card's dogma effect requires cards in hand"""
        # Common cards that need hand cards for their primary effects
        hand_dependent_cards = {
            "Code of Laws",  # Tuck from hand
            "Oars",  # Meld from hand (I DEMAND)
            "Clothing",  # Meld from hand
            "Agriculture",  # Return from hand
            "Masonry",  # Meld from hand (I DEMAND)
            "City States",  # I DEMAND: transfer from hand
            "Currency",  # Exchange hands
            "Mathematics",  # Return from hand
            "Philosophy",  # Meld/score from hand
            "Alchemy",  # Reveal from hand
            "Translation",  # Meld from hand
            "Perspective",  # Return from hand (I DEMAND)
        }
        return card_name in hand_dependent_cards

    def _analyze_card_requirements(self, card_data: dict) -> dict:
        """
        Analyze a card's action primitives to determine what it needs to work.
        Returns dict with requirements like: {needs_hand_cards, needs_specific_age_deck, needs_splay_targets, etc}
        """
        requirements = {
            "needs_hand_cards": False,
            "needs_hand_count": 0,
            "needs_age_decks": [],
            "needs_splay_targets": False,
            "needs_board_colors_in_hand": False,
            "is_demand": False,
            "demand_symbol": None,
        }

        dogma_effects = card_data.get("dogma_effects", [])

        for effect in dogma_effects:
            if effect.get("is_demand"):
                requirements["is_demand"] = True
                # Skip demand effects for hand/board requirements -
                # those apply to opponents, not the current player
                continue

            # Recursively check all actions (non-demand effects only)
            actions = effect.get("actions", [])
            self._analyze_actions_for_requirements(actions, requirements)

        return requirements

    def _analyze_actions_for_requirements(self, actions: list, requirements: dict):
        """Recursively analyze action primitives to detect requirements"""
        for action in actions:
            action_type = action.get("type", "")

            # SelectCards from hand
            if action_type == "SelectCards" and action.get("source") == "hand":
                min_count = action.get("min_count", action.get("count", 1))
                if min_count > 0:
                    requirements["needs_hand_cards"] = True
                    # Use min() so card is viable if ANY effect can run
                    if requirements["needs_hand_count"] == 0:
                        requirements["needs_hand_count"] = min_count
                    else:
                        requirements["needs_hand_count"] = min(
                            requirements["needs_hand_count"], min_count
                        )

            # TuckCard from hand (not last_drawn or other sources)
            elif action_type == "TuckCard" and action.get("cards") != "last_drawn":
                requirements["needs_hand_cards"] = True
                requirements["needs_board_colors_in_hand"] = True

            # SplayCards (needs 2+ cards in stack to reveal anything)
            elif action_type == "SplayCards":
                requirements["needs_splay_targets"] = True

            # DrawCards from specific age
            elif action_type == "DrawCards" and "age" in action:
                age = action.get("age")
                if age and age not in requirements["needs_age_decks"]:
                    requirements["needs_age_decks"].append(age)

            # DemandEffect
            elif action_type == "DemandEffect":
                requirements["is_demand"] = True
                requirements["demand_symbol"] = action.get("required_symbol")

            # TransferBetweenPlayers from hand
            elif (
                action_type == "TransferBetweenPlayers"
                and action.get("from_location") == "hand"
            ):
                requirements["needs_hand_cards"] = True

            # Recurse into conditional actions
            elif action_type == "ConditionalAction":
                if_true = action.get("if_true", [])
                if_false = action.get("if_false", [])
                self._analyze_actions_for_requirements(if_true, requirements)
                self._analyze_actions_for_requirements(if_false, requirements)

    def _check_card_viability(
        self, card_name: str, card_data: dict, player_state: dict, game_state: dict
    ) -> str | None:
        """
        Check if a card can actually do anything useful based on its requirements and current game state.
        Returns warning string if card is useless/low-value, None if card is viable.
        """
        requirements = self._analyze_card_requirements(card_data)
        hand = player_state.get("hand", [])
        hand_count = len(hand)
        board = player_state.get("board", {})
        age_decks = game_state.get("age_decks", {})
        opponents = game_state.get("opponents", [])
        player_symbols = player_state.get("symbol_counts", {})

        # Check demand viability
        if requirements["is_demand"] and requirements["demand_symbol"]:
            player_count = player_symbols.get(requirements["demand_symbol"], 0)
            any_opponent_vulnerable = False

            for opponent in opponents:
                opp_symbols = opponent.get("symbol_counts", {})
                opp_count = opp_symbols.get(requirements["demand_symbol"], 0)
                if opp_count < player_count:
                    any_opponent_vulnerable = True
                    break

            if not any_opponent_vulnerable:
                return (
                    f"⚠️ {card_name}: {VIABILITY_USELESS} DEMAND - You have {player_count} {requirements['demand_symbol']}, "
                    f"but all opponents have >= {player_count}. "
                    f"Demands only work on opponents with FEWER symbols than you! DRAW or MELD instead!"
                )

        # Check hand card requirements
        if requirements["needs_hand_cards"]:
            if hand_count == 0:
                return f"⚠️ {card_name}: {VIABILITY_USELESS} - needs hand cards, your hand is EMPTY. DRAW first!"
            elif requirements["needs_hand_count"] > hand_count:
                return (
                    f"⚠️ {card_name}: {VIABILITY_USELESS} - needs {requirements['needs_hand_count']} cards in hand, "
                    f"you only have {hand_count}. DRAW first!"
                )

        # Check board colors in hand requirement (e.g., Code of Laws tuck)
        if requirements["needs_board_colors_in_hand"] and hand_count > 0:
            board_colors = []
            for color in ["red", "blue", "green", "yellow", "purple"]:
                if board.get(f"{color}_cards"):
                    board_colors.append(color)

            hand_colors = [card.get("color") for card in hand]
            matching_colors = [c for c in hand_colors if c in board_colors]

            if not matching_colors:
                return (
                    f"⚠️ {card_name}: {VIABILITY_USELESS} - you have no cards in hand matching colors on your board. "
                    f"Your board has: {', '.join(board_colors)}. DRAW or MELD instead!"
                )

        # Check splay targets (need 2+ cards to reveal anything)
        if requirements["needs_splay_targets"]:
            splayable_colors = []
            for color in ["red", "blue", "green", "yellow", "purple"]:
                color_cards = board.get(f"{color}_cards", [])
                if len(color_cards) >= 2:
                    splayable_colors.append(color)

            if not splayable_colors:
                return (
                    f"⚠️ {card_name}: {VIABILITY_LOW_VALUE} - none of your color stacks have 2+ cards, "
                    f"so splaying won't reveal anything. Consider DRAWING or MELDING instead!"
                )

        # Check age deck availability
        for age in requirements["needs_age_decks"]:
            deck = age_decks.get(str(age), [])
            if not deck or len(deck) == 0:
                return (
                    f"✅ {card_name}: BONUS - age {age} deck is empty! "
                    f"You'll draw from age {age+1} instead - even better value!"
                )
            elif len(deck) < 2:
                # Only note if card draws multiple cards - not necessarily bad
                return (
                    f"ℹ️ {card_name}: NOTE - age {age} deck only has {len(deck)} cards left. "
                    f"Additional draws will come from age {age+1} - potentially better!"
                )

        return None

    def check_dogma_viability(self, card_name: str, game_state: dict) -> str | None:
        """
        Public wrapper for _check_card_viability.
        Returns warning string if card is useless, None if viable.
        Loads card data automatically.
        """
        card_descriptions_data = self._get_card_data_cache()
        card_data = card_descriptions_data.get(card_name)
        if not card_data:
            return None  # Unknown card, don't filter

        player_state = game_state.get("current_player_state", {})
        return self._check_card_viability(card_name, card_data, player_state, game_state)

    def _get_card_data_cache(self) -> dict[str, dict]:
        """Load and cache full card data (with dogma_effects) by name.

        Cache is permanent for the lifetime of the AIPromptBuilder instance.
        Card definitions are static at runtime (loaded from BaseCards.json at import).
        If expansions are toggled, create a new AIPromptBuilder instance.
        """
        if self._card_data_cache is None:
            try:
                from data.cards import get_all_cards
                all_cards = get_all_cards()
                cache = {}
                for card in all_cards:
                    cache[card.name] = {
                        "dogma_resource": card.dogma_resource.value if card.dogma_resource else None,
                        "age": card.age,
                        "color": card.color.value if hasattr(card.color, "value") else str(card.color),
                        "symbols": [s.value if hasattr(s, "value") else str(s) for s in card.symbols] if card.symbols else [],
                        "dogma_effects": [
                            {
                                "is_demand": effect.is_demand,
                                "text": effect.text if hasattr(effect, "text") else str(effect),
                                "actions": [a.model_dump() if hasattr(a, "model_dump") else a for a in effect.actions],
                            }
                            for effect in card.dogma_effects
                        ] if card.dogma_effects else []
                    }
                self._card_data_cache = cache  # Only cache on success
            except Exception as e:
                logger.error(f"Failed to load card data cache: {e}", exc_info=True)
                return {}  # Return empty but don't cache - next call retries
        return self._card_data_cache

    def _get_dogma_viability_warnings(self, game_state: dict) -> str:
        """Generate warnings about cards that won't work properly (for novice/beginner)"""
        player_state = game_state.get("current_player_state", {})
        hand = player_state.get("hand", [])
        hand_count = len(hand)
        board = player_state.get("board", {})

        # Get recent actions for repetition detection
        recent_actions = game_state.get("recent_actions", [])

        warnings = []

        # CRITICAL: Check for oversized hand
        if hand_count > 10:
            warnings.append(
                f"🚨 CRITICAL: You have {hand_count} cards in hand! This is WAY TOO MANY! "
                f"You should MELD cards to build your board, not hoard them! "
                f"MELD at least {hand_count - 5} cards before using dogma again!"
            )
        elif hand_count > 6:
            warnings.append(
                f"⚠️ WARNING: You have {hand_count} cards in hand. This is too many! "
                f"Consider MELDING cards to build your board instead of drawing more. "
                f"Cards in hand don't help you - cards on your board give you symbols and dogma effects!"
            )

        # CRITICAL: Warn about draw-only dogmas when hand is already large
        draw_only_dogmas = {"The Wheel", "Sailing", "Canal Building"}
        for color in ["red", "blue", "green", "yellow", "purple"]:
            color_cards = board.get(f"{color}_cards", [])
            if color_cards:
                top_card = color_cards[-1]
                card_name = top_card.get("name")
                if card_name in draw_only_dogmas and hand_count > 4:
                    warnings.append(
                        f"🛑 STOP! {card_name} only draws cards - you already have {hand_count} cards in hand! "
                        f"MELD your cards instead! Drawing more is USELESS - you need BOARD POWER, not more hand cards!"
                    )

        # Check for action repetition (last 3 actions)
        if len(recent_actions) >= 3:
            last_three = recent_actions[-3:]
            card_mentions = {}
            for action_text in last_three:
                if "activated" in action_text:
                    parts = action_text.split("activated")
                    if len(parts) > 1:
                        card_name = parts[1].strip().split()[0]
                        card_mentions[card_name] = card_mentions.get(card_name, 0) + 1

            for card_name, count in card_mentions.items():
                if count >= 3:
                    warnings.append(
                        f"🔁 REPETITION WARNING: You've activated {card_name} {count} times in a row! "
                        f"This is usually a mistake. If the card isn't helping you win, try a different action! "
                        f"Consider DRAWING to get better cards or MELDING to build your board."
                    )

        # INTELLIGENT CARD ANALYSIS: Check each card on board using action primitive analysis
        for color in ["red", "blue", "green", "yellow", "purple"]:
            color_cards = board.get(f"{color}_cards", [])
            if not color_cards:
                continue

            top_card = color_cards[-1]
            card_name = top_card.get("name")

            # Use intelligent analyzer instead of hardcoded checks
            warning = self._check_card_viability(
                card_name, top_card, player_state, game_state
            )
            if warning:
                warnings.append(warning)

        # If no warnings, give positive feedback
        if not warnings:
            warnings.append(
                "✅ Your hand size looks good and your board dogmas should work."
            )

        return "\n".join(warnings)

    def _format_recent_actions(self, game_state: dict, count: int) -> str:
        """Format recent action history"""
        recent_actions = game_state.get("recent_actions", [])[-count:]

        if not recent_actions:
            return ""

        parts = [f"\nRECENT ACTIONS (last {count}):"]
        for action in recent_actions:
            parts.append(f"  - {action}")

        return "\n".join(parts)

    def _format_board_analysis(self, game_state: dict) -> str:
        """Format board state analysis"""
        player_state = game_state.get("current_player_state", {})
        board = player_state.get("board", {})
        card_descriptions = self._get_card_descriptions()

        if not board or not any(board.values()):
            return "\nYour board: Empty (no cards to dogma!)"

        parts = ["\nYOUR BOARD (cards you can dogma):"]
        for color in ["red", "blue", "green", "yellow", "purple"]:
            if color in board and board[color]:
                top_card = board[color][0]  # Top card is first in list
                card_name = top_card.get("name")
                description = card_descriptions.get(card_name, "")
                if description:
                    parts.append(
                        f"  {color.upper()}: {card_name} (age {top_card.get('age')}): {description}"
                    )
                else:
                    parts.append(
                        f"  {color.upper()}: {card_name} (age {top_card.get('age')})"
                    )

        return "\n".join(parts)

    def _format_achievement_status(self, game_state: dict) -> str:
        """Format achievement progress"""
        player_state = game_state.get("current_player_state", {})
        achievements = player_state.get("achievements", [])

        return f"\nAchievements: {len(achievements)}/6 needed"

    def _format_sharing_analysis(self, game_state: dict) -> str:
        """
        Analyze and report sharing risks in compact table format.

        Shows symbol comparison where opponent can share (their count >= yours).
        """
        player_state = game_state.get("current_player_state", {})
        opponents = game_state.get("opponents", [])
        player_symbols = player_state.get("symbol_counts", {})

        if not opponents or not player_symbols:
            return ""

        # Build compact sharing risk table
        lines = ["", "<sharing_risk>"]
        lines.append("| Symbol | You | Opp | Risk |")
        lines.append("|--------|-----|-----|------|")

        # Compare symbols with first opponent (2-player game assumed)
        opp = opponents[0]
        opp_symbols = opp.get("symbol_counts", {})

        for symbol in ["bulb", "castle", "crown", "leaf", "clock", "factory"]:
            yours = player_symbols.get(symbol, 0)
            theirs = opp_symbols.get(symbol, 0)
            if theirs > 0 or yours > 0:  # Only show if either has any
                risk = "SHARE" if theirs >= yours else "safe"
                lines.append(f"| {symbol} | {yours} | {theirs} | {risk} |")

        lines.append("</sharing_risk>")
        lines.append("")
        lines.append("TIP: Use dogmas where your symbol > opponent. Else DRAW.")

        return "\n".join(lines)

    def _format_strategic_considerations(self, game_state: dict) -> str:
        """Format strategic considerations"""
        return "\nSTRATEGIC CONSIDERATIONS: Analyze the impact of each choice."

    def _format_board_by_color(self, game_state: dict) -> str:
        """Format board state by color"""
        return "\n[Board by color: Implementation pending]"

    def _format_opponents_basic(self, game_state: dict) -> str:
        """Format basic opponent info for beginner difficulties"""
        opponents = game_state.get("opponents", [])
        if not opponents:
            return ""

        parts = ["\nOPPONENTS:"]
        for opp in opponents:
            parts.append(
                f"  {opp['name']}: Score={opp['score_total']}, "
                f"Hand={opp['hand_count']} cards"
            )
        return "\n".join(parts)

    def _format_opponents_detailed(self, game_state: dict) -> str:
        """Format detailed opponent info for intermediate+ difficulties"""
        opponents = game_state.get("opponents", [])
        if not opponents:
            return ""

        card_descriptions = self._get_card_descriptions()
        parts = ["\nOPPONENTS:"]
        for opp in opponents:
            parts.append(f"\n{opp['name']}:")
            parts.append(f"  Score: {opp['score_total']}")
            parts.append(f"  Achievements: {len(opp.get('achievements', []))}")
            parts.append(f"  Hand: {opp['hand_count']} cards")

            # Add symbol counts for demand evaluation
            symbol_counts = opp.get("symbol_counts", {})
            if symbol_counts:
                counts_str = ", ".join(
                    [f"{sym}: {count}" for sym, count in symbol_counts.items()]
                )
                parts.append(f"  Symbols: {counts_str}")

            # Show opponent's board (what they can dogma with) - now with effects
            board = opp.get("board", {})
            has_board_cards = any(
                board.get(f"{color}_cards")
                for color in ["red", "blue", "green", "yellow", "purple"]
            )
            if has_board_cards:
                parts.append("  Board:")
                for color in ["red", "blue", "green", "yellow", "purple"]:
                    color_cards = board.get(f"{color}_cards", [])
                    if color_cards:
                        top_card = color_cards[-1]
                        card_name = top_card.get("name")
                        description = card_descriptions.get(card_name, "")
                        if description:
                            parts.append(
                                f"    {color.upper()}: {card_name} (age {top_card.get('age')}): {description}"
                            )
                        else:
                            parts.append(
                                f"    {color.upper()}: {card_name} (age {top_card.get('age')})"
                            )
            else:
                parts.append("  Board: Empty")

        return "\n".join(parts)

    def _get_response_format(self) -> str:
        """Get response format instructions"""
        return (
            "\n\nRespond with ONLY valid JSON (no comments or extra text):\n"
            "{\n"
            '  "action_type": "draw",\n'
            '  "card_name": "Archery",\n'
            '  "age": 1,\n'
            '  "reasoning": "Brief explanation of your strategy"\n'
            "}\n\n"
            "Required fields by action_type:\n"
            "- draw: action_type + reasoning\n"
            "- meld: action_type + card_name + reasoning\n"
            "- dogma: action_type + card_name + reasoning\n"
            "- achieve: action_type + age + reasoning\n"
            "- end_turn: action_type + reasoning"
        )

    def _get_game_rules(self) -> str:
        """Get cached game rules"""
        return """# Innovation Rules Summary

**CRITICAL: INTERACTION RESPONSE FORMAT**
When responding to player interactions (card selections, color choices, etc.), you MUST:
- Return ONLY valid JSON
- NO explanations, NO commentary, NO markdown formatting
- NO text before or after the JSON
- Just the raw JSON object
- Example CORRECT response: {"selected_cards": ["B 012"]}
- Example INCORRECT response: "I'll select this card: {"selected_cards": ["B 012"]}"

**OPTIONAL SELECTIONS (decline pattern):**
- Some selections are optional (e.g., "Select 1 achievement(s) or decline")
- To DECLINE an optional selection, respond with: {"decline": true}
- DO NOT use null or empty arrays - use explicit decline flag
- Example declining: {"decline": true}
- Example selecting: {"selected_achievement": "Age 1"}

## Turn Structure:
1. Player has 2 actions per turn
2. Available actions: Draw, Meld, Dogma, Achieve
3. Actions decrease actions_remaining counter
4. Turn ends when actions_remaining = 0 or player chooses "end_turn"

## Core Actions:

### Draw
- Draw one card from age deck
- Age = highest top card on board, or age 1 if empty
- If deck empty, draw from next higher age

### Meld
- Play one card from hand to board
- Goes on top of matching color stack
- Card must match one of 5 colors (red, blue, green, yellow, purple)
- **NO HAND LIMIT**: You can hold as many cards as you want
- **Strategic Value of Melding:**
  - Cards in your HAND provide NO symbols or dogma effects
  - Cards on your BOARD give you symbols, dogma effects, and power
  - Melding builds your board presence and unlocks dogma abilities
  - Balance between holding cards for flexibility vs building board strength
  - Consider melding when: (1) Need symbols for dogma effects, (2) Want to unlock new dogma abilities, (3) Building toward achievements
  - Consider holding cards when: (1) Waiting for better meld targets, (2) Cards needed for specific dogma effects (like Code of Laws), (3) Strategic timing matters

### Dogma
- Activate dogma effect of top card
- **CRITICAL: READ THE CARD TEXT BEFORE USING DOGMA!**
  - Check if you meet the effect's requirements
  - Example: "Meld cards with castle symbols" - Do you HAVE castle cards?
  - If the effect requires something you don't have, the dogma DOES NOTHING (wasted action!)
  - **DON'T waste actions on useless dogmas - DRAW instead!**

- **SHARING MECHANICS (CRITICAL):**
  - Each dogma card has a resource symbol (castle, crown, leaf, lightbulb, factory, clock)
  - Before executing I DEMAND effects: Check if opponents can SHARE
  - **Sharing is based on SYMBOL COUNTS, NOT card colors**
  - If opponent has >= your count of the dogma's resource symbol, they SHARE the effect
  - Example: You dogma Code of Laws (crown symbol). If opponent has >= crown symbols on their board, they share
  - **Card color is COMPLETELY IRRELEVANT to sharing** - only symbol counts matter
  - **SHARING = OPPONENT BENEFITS = BAD FOR YOU (usually)**

  **HOW TO ANALYZE SHARING (CRITICAL FOR DOGMA DECISIONS):**
  - Each player's board includes "symbol_counts" (precalculated for you!)
  - Before using dogma: Check the card's "dogma_resource" field
  - Compare YOUR symbol count vs OPPONENT's symbol count for that resource
  - If opponent has >= your count, they SHARE (benefit from your dogma!)
  - Example: Tools has dogma_resource="lightbulb"
    - Check your symbol_counts["lightbulb"] vs opponent's symbol_counts["lightbulb"]
    - If opponent >= you, they get the benefit too!
  - **If opponent shares, they get a FREE ACTION at your expense!**
  - Even if dogma gives you a small benefit (like drawing 1 card), if opponent shares, just DRAW instead
  - Why give opponent a free action when you can just draw yourself?
  - Only use dogma when: (1) Effect is significantly better than drawing, AND (2) Opponent won't share
  - **DEFEND AGAINST DEMANDS**: Look at opponent's top cards and their dogma_resource
    - If you have >= symbols, you're SAFE from their I DEMAND effects
    - If you have < symbols, they can demand from you!

- **IMPORTANT**: There are NO achievement points for dogma actions - only for claiming achievements!
- Effects execute in order: shares first, then non-cooperatives

### Achieve
- Claim achievement card
- Requirements:
  - Score >= (age * 5)
  - **Top card age ≥ achievement age** (CRITICAL - see below!)
- Achievements count toward victory

**CRITICAL ACHIEVEMENT STRATEGY:**
- You CANNOT claim an achievement without a top card of that age or higher!
- Example: To claim Age 3 achievement, you need:
  - Score >= 15 points (3 × 5), AND
  - At least one top card on your board of age 3+
- If you have 50+ points but your highest top card is age 2, you can ONLY claim ages 1-2!
- **FIX: MELD higher age cards to unlock higher achievements!**
- **FIX: DRAW from higher ages to get cards you can meld!**
- Your draw age = highest top card age on board (or 1 if empty)

## Victory Conditions:
1. Achievements: 6 achievements
2. Score: If highest age exhausted, highest score wins
"""

