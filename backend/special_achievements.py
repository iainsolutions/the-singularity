"""
Special Achievements Module

Handles automatic checking and awarding of special achievements.
"""

import logging
from typing import TYPE_CHECKING, ClassVar

from models.card import Symbol

if TYPE_CHECKING:
    from models.game import Game
    from models.player import Player

logger = logging.getLogger(__name__)


class SpecialAchievementChecker:
    """Checks for and awards special achievements"""

    SPECIAL_ACHIEVEMENTS: ClassVar[dict[str, dict[str, str | int]]] = {
        "Monument": {
            "age": 1,
            "description": "At least four top cards with a DEMAND effect",
            "check_function": "check_monument",
        },
        "Empire": {
            "age": 2,
            "description": "At least three icons of each of these six types on your board",
            "check_function": "check_empire",
        },
        "World": {
            "age": 3,
            "description": "At least twelve clock symbols on your board",
            "check_function": "check_world",
        },
        "Wonder": {
            "age": 4,
            "description": "Five colors splayed on your board, each splayed right, up, or aslant",
            "check_function": "check_wonder",
        },
        "Universe": {
            "age": 5,
            "description": "Five top cards, each of value at least 8",
            "check_function": "check_universe",
        },
        "Wealth": {
            "age": 6,
            "description": "At least eight bonuses on your board",
            "check_function": "check_wealth",
        },
    }

    def __init__(self):
        # Track cards tucked/scored per turn for Monument achievement
        self.turn_tracking = {}

    def reset_turn_tracking(self, game_id: str, player_id: str):
        """Reset tracking for a new turn"""
        key = f"{game_id}_{player_id}"
        self.turn_tracking[key] = {"cards_tucked": 0, "cards_scored": 0}

    def track_card_action(
        self, game_id: str, player_id: str, action: str, count: int = 1
    ):
        """Track card actions for Monument achievement"""
        key = f"{game_id}_{player_id}"
        if key not in self.turn_tracking:
            self.reset_turn_tracking(game_id, player_id)

        if action == "tuck":
            self.turn_tracking[key]["cards_tucked"] += count
        elif action == "score":
            self.turn_tracking[key]["cards_scored"] += count

    def check_all_achievements(self, game: "Game", player: "Player") -> list[str]:
        """Check all special achievements for a player"""
        earned = []

        for name, config in self.SPECIAL_ACHIEVEMENTS.items():
            # Skip if player already has this achievement
            if self._player_has_achievement(player, name):
                continue

            # Skip if achievement is already claimed by someone
            if self._achievement_claimed(game, name):
                continue

            # CRITICAL: Skip if achievement requires expansion that's not enabled
            if config.get("expansion"):
                expansion = config["expansion"]
                if not hasattr(game, "expansions_enabled") or expansion not in game.expansions_enabled:
                    logger.debug(f"Skipping {name} - {expansion} expansion not enabled")
                    continue

            # Check if player meets the requirements
            check_method = getattr(self, config["check_function"])
            if check_method(game, player):
                # Award the achievement
                self._award_achievement(game, player, name, config["age"])
                earned.append(name)
                logger.info(f"Player {player.name} earned special achievement: {name}")

        return earned

    def check_monument(self, game: "Game", player: "Player") -> bool:
        """Check Monument: At least four top cards with a DEMAND effect"""
        if not hasattr(player, "board"):
            return False

        board = player.board
        demand_cards = 0

        for color in ["red", "blue", "green", "purple", "yellow"]:
            stack = getattr(board, f"{color}_cards", [])
            if stack:
                top_card = stack[-1]
                # Check if the top card has demand effects
                if hasattr(top_card, "dogma_effects"):
                    for effect in top_card.dogma_effects:
                        if (
                            isinstance(effect, dict)
                            and effect.get("type") == "DemandEffect"
                        ):
                            demand_cards += 1
                            break  # Count this card once even if it has multiple demands

        return demand_cards >= 4

    def check_empire(self, game: "Game", player: "Player") -> bool:
        """Check Empire: Three or more icons of all six types"""
        if not hasattr(player, "board"):
            return False

        # Count all symbols on the board
        symbol_counts = self._count_board_symbols(player.board)

        # Check if all 6 symbol types have at least 3
        required_symbols = [
            Symbol.CASTLE,
            Symbol.LEAF,
            Symbol.LIGHTBULB,
            Symbol.CROWN,
            Symbol.FACTORY,
            Symbol.CLOCK,
        ]

        return all(symbol_counts.get(symbol, 0) >= 3 for symbol in required_symbols)

    def check_world(self, game: "Game", player: "Player") -> bool:
        """Check World: Twelve or more clocks on your board"""
        if not hasattr(player, "board"):
            return False

        symbol_counts = self._count_board_symbols(player.board)
        return symbol_counts.get(Symbol.CLOCK, 0) >= 12

    def check_wonder(self, game: "Game", player: "Player") -> bool:
        """Check Wonder: Five colors splayed on your board, each splayed right, up, or aslant"""
        if not hasattr(player, "board"):
            return False

        board = player.board
        colors_with_cards = 0
        colors_properly_splayed = 0

        for color in ["red", "blue", "green", "purple", "yellow"]:
            stack = getattr(board, f"{color}_cards", [])
            if stack and len(stack) > 1:  # Need at least 2 cards to be splayed
                colors_with_cards += 1
                # Check splay direction
                if hasattr(board, "splay_directions"):
                    splay = board.splay_directions.get(color)
                    if splay in ["right", "up", "aslant"]:
                        colors_properly_splayed += 1

        # Need all 5 colors on board, each splayed right, up, or aslant
        return colors_with_cards == 5 and colors_properly_splayed == 5

    def check_universe(self, game: "Game", player: "Player") -> bool:
        """Check Universe: Five top cards each is of value 8 or higher"""
        if not hasattr(player, "board"):
            return False

        board = player.board
        high_value_cards = 0

        for color in ["red", "blue", "green", "purple", "yellow"]:
            stack = getattr(board, f"{color}_cards", [])
            if stack:
                top_card = stack[-1]
                if hasattr(top_card, "age") and top_card.age >= 8:
                    high_value_cards += 1

        return high_value_cards >= 5

    def check_wealth(self, game: "Game", player: "Player") -> bool:
        """Check Wealth: At least eight bonuses on your board"""
        if not hasattr(player, "board"):
            return False

        board = player.board
        bonus_count = 0

        for color in ["red", "blue", "green", "purple", "yellow"]:
            stack = getattr(board, f"{color}_cards", [])
            if not stack:
                continue

            # Count bonuses based on splay direction
            splay = None
            if hasattr(board, "splay_directions"):
                splay = board.splay_directions.get(color)

            # Each card can contribute multiple bonuses
            visible_bonuses = self._get_visible_bonuses(stack, splay)
            bonus_count += visible_bonuses

        return bonus_count >= 8

    # ===== Echoes Expansion Special Achievements =====

    def check_supremacy(self, game: "Game", player: "Player") -> bool:
        """Check Supremacy (Echoes): 4+ colors each with 3+ visible instances of same icon"""
        if not hasattr(player, "board"):
            return False

        board = player.board

        # All valid symbols (including crown)
        valid_symbols = [Symbol.CASTLE, Symbol.LEAF, Symbol.LIGHTBULB, Symbol.FACTORY, Symbol.CLOCK, Symbol.CROWN]

        for symbol in valid_symbols:
            colors_with_3_plus = 0

            for color in ["red", "blue", "green", "yellow", "purple"]:
                stack = getattr(board, f"{color}_cards", [])
                if not stack:
                    continue

                # Get splay direction for this color
                splay = None
                if hasattr(board, "splay_directions"):
                    splay = board.splay_directions.get(color)

                # Count all VISIBLE instances of this symbol in this color stack
                visible_symbols = self._get_visible_symbols(stack, splay)
                color_count = visible_symbols.count(symbol)

                # This color qualifies if it has 3+ visible instances of this symbol
                if color_count >= 3:
                    colors_with_3_plus += 1

            # Need at least 4 colors where each has 3+ visible instances of this symbol
            if colors_with_3_plus >= 4:
                return True

        return False

    def check_destiny(self, game: "Game", player: "Player") -> bool:
        """Check Destiny (Echoes): Return blue cards from your forecast

        This is typically triggered by a card effect (Barometer).
        We check if the player recently returned blue cards from forecast.
        """
        # This achievement requires special tracking by the card effect
        # For now, we'll check if it was explicitly marked
        if hasattr(player, "_destiny_triggered") and player._destiny_triggered:
            return True
        return False

    def check_heritage(self, game: "Game", player: "Player") -> bool:
        """Check Heritage (Echoes): At least five crowns on your board in one color"""
        if not hasattr(player, "board"):
            return False

        board = player.board

        for color in ["red", "blue", "green", "yellow", "purple"]:
            stack = getattr(board, f"{color}_cards", [])
            if not stack:
                continue

            # Count crowns in this color stack
            splay = None
            if hasattr(board, "splay_directions"):
                splay = board.splay_directions.get(color)

            crown_count = 0

            # Count visible crowns based on splay
            for i, card in enumerate(stack):
                if i == len(stack) - 1:
                    # Top card - all crowns visible
                    if hasattr(card, "symbol_positions"):
                        crown_count += card.symbol_positions.count(Symbol.CROWN)
                    elif hasattr(card, "symbols"):
                        crown_count += card.symbols.count(Symbol.CROWN)
                elif splay:
                    # Apply splay visibility rules for non-top cards
                    if hasattr(card, "symbol_positions"):
                        positions = card.symbol_positions
                        if splay == "left" and len(positions) > 3:
                            if positions[3] == Symbol.CROWN:
                                crown_count += 1
                        elif splay == "right" and len(positions) > 0:
                            if positions[0] == Symbol.CROWN:
                                crown_count += 1
                            if len(positions) > 1 and positions[1] == Symbol.CROWN:
                                crown_count += 1
                        elif splay in ["up", "aslant"] and len(positions) > 1:
                            for pos in positions[1:4]:  # Bottom row
                                if pos == Symbol.CROWN:
                                    crown_count += 1

            if crown_count >= 5:
                return True

        return False

    def check_history(self, game: "Game", player: "Player") -> bool:
        """Check History (Echoes): At least three echo effects in one color"""
        if not hasattr(player, "board"):
            return False

        board = player.board

        for color in ["red", "blue", "green", "yellow", "purple"]:
            stack = getattr(board, f"{color}_cards", [])
            if not stack:
                continue

            # Count cards with echo effects in this stack
            echo_count = 0
            for card in stack:
                if hasattr(card, "echo_effect") and card.echo_effect:
                    echo_count += 1
                elif hasattr(card, "has_echo") and card.has_echo():
                    echo_count += 1

            if echo_count >= 3:
                return True

        return False

    def _get_visible_bonuses(self, stack: list, splay: str | None) -> int:
        """Count visible bonuses from a stack based on splay direction"""
        if not stack:
            return 0

        bonus_count = 0

        # For now, assume each card can have multiple bonus effects
        # This would need to be implemented based on the actual card bonus system
        # which might be stored in card.bonus_effects or similar
        for i, card in enumerate(stack):
            if i == len(stack) - 1:
                # Top card - all bonuses visible
                if hasattr(card, "bonus_effects"):
                    bonus_count += len(card.bonus_effects)
                elif hasattr(card, "bonuses"):
                    bonus_count += card.bonuses
            elif splay:
                # Non-top cards in splayed stacks might show some bonuses
                # This depends on the specific bonus visibility rules
                if hasattr(card, "bonus_effects"):
                    # Simplified: half bonuses visible when splayed
                    bonus_count += max(1, len(card.bonus_effects) // 2)
                elif hasattr(card, "bonuses"):
                    bonus_count += max(1, card.bonuses // 2)

        return bonus_count

    def _count_board_symbols(self, board) -> dict[Symbol, int]:
        """Count all visible symbols on a player's board"""
        counts = {}

        for color in ["red", "blue", "green", "purple", "yellow"]:
            stack = getattr(board, f"{color}_cards", [])
            if not stack:
                continue

            # Get splay direction
            splay = None
            if hasattr(board, "splay_directions"):
                splay = board.splay_directions.get(color)

            # Count symbols based on splay
            visible_symbols = self._get_visible_symbols(stack, splay)
            for symbol in visible_symbols:
                counts[symbol] = counts.get(symbol, 0) + 1

        return counts

    def _get_visible_symbols(self, stack: list, splay: str | None) -> list[Symbol]:
        """Get all visible symbols from a stack based on splay direction"""
        if not stack:
            return []

        visible = []

        if not splay or len(stack) == 1:
            # No splay or single card - only top card visible
            top_card = stack[-1]
            if hasattr(top_card, "symbol_positions") and any(top_card.symbol_positions):
                # Add all non-None symbols from symbol_positions
                for symbol in top_card.symbol_positions:
                    if symbol:
                        visible.append(symbol)
            elif hasattr(top_card, "symbols"):
                visible.extend(top_card.symbols)
        else:
            # Apply splay rules
            for i, card in enumerate(stack):
                if i == len(stack) - 1:
                    # Top card - all symbols visible
                    if hasattr(card, "symbol_positions") and any(card.symbol_positions):
                        # Add all non-None symbols from symbol_positions
                        for symbol in card.symbol_positions:
                            if symbol:
                                visible.append(symbol)
                    elif hasattr(card, "symbols"):
                        visible.extend(card.symbols)
                elif splay == "left":
                    # Left splay - bottom and right symbols visible on non-top cards
                    if hasattr(card, "symbol_positions") and any(card.symbol_positions):
                        positions = card.symbol_positions
                        # Position 2 is right, position 3 is bottom
                        if positions[2]:  # Right
                            visible.append(positions[2])
                        if positions[3]:  # Bottom
                            visible.append(positions[3])
                    elif hasattr(card, "symbols"):
                        # Fallback: if splayed, only count some symbols (this is simplified)
                        # For proper testing, we'd need to know which position each symbol is in
                        visible.extend(card.symbols)
                elif splay == "right":
                    # Right splay - bottom and left symbols visible on non-top cards
                    if hasattr(card, "symbol_positions") and any(card.symbol_positions):
                        positions = card.symbol_positions
                        # Position 0 is left, position 3 is bottom
                        if positions[0]:  # Left
                            visible.append(positions[0])
                        if positions[3]:  # Bottom
                            visible.append(positions[3])
                    elif hasattr(card, "symbols"):
                        # Fallback: if splayed, only count some symbols (this is simplified)
                        visible.extend(card.symbols)
                elif splay == "up":
                    # Up splay - bottom symbol visible on non-top cards
                    if hasattr(card, "symbol_positions") and any(card.symbol_positions):
                        positions = card.symbol_positions
                        if positions[3]:  # Bottom
                            visible.append(positions[3])
                    elif hasattr(card, "symbols"):
                        # Fallback: if splayed, only count some symbols (this is simplified)
                        visible.extend(card.symbols)
                elif splay == "aslant":
                    # Aslant splay - specific visibility rules for this new splay type
                    # This would need to be defined based on the actual Innovation Ultimate rules
                    # For now, assume it behaves similarly to up splay
                    if hasattr(card, "symbol_positions") and any(card.symbol_positions):
                        positions = card.symbol_positions
                        if positions[3]:  # Bottom
                            visible.append(positions[3])
                    elif hasattr(card, "symbols"):
                        # Fallback: simplified rule
                        visible.extend(card.symbols)

        return visible

    def _player_has_achievement(self, player: "Player", name: str) -> bool:
        """Check if player already has this achievement"""
        if not hasattr(player, "achievements"):
            return False

        for achievement in player.achievements:
            # Handle both string achievements (from card effects) and Card objects
            if isinstance(achievement, str):
                if achievement == name:
                    return True
            elif hasattr(achievement, "name") and achievement.name == name:
                return True

        return False

    def _achievement_claimed(self, game: "Game", name: str) -> bool:
        """Check if any player has already claimed this achievement"""
        for player in game.players:
            if self._player_has_achievement(player, name):
                return True
        return False

    def _award_achievement(self, game: "Game", player: "Player", name: str, age: int):
        """Award a special achievement to a player"""
        # Create achievement card
        from models.card import Card, CardColor

        achievement = Card(
            name=name,
            age=age,
            color=CardColor.PURPLE,
            symbols=[],
            dogma_effects=[],
            is_achievement=True,
            achievement_requirement=self.SPECIAL_ACHIEVEMENTS[name]["description"],
        )

        # Add to player's achievements
        if not hasattr(player, "achievements"):
            player.achievements = []
        player.achievements.append(achievement)

        # Log the achievement
        logger.info(f"Special achievement {name} awarded to {player.name}")

        # Victory conditions are checked separately by the game manager
        # Special achievements don't immediately end the game


# Global instance
special_achievement_checker = SpecialAchievementChecker()
