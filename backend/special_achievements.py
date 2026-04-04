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
        "Emergence": {
            "age": 1,
            "description": "Archive 6 cards OR Score 6 cards in a single turn",
            "check_function": "check_emergence",
        },
        "Dominion": {
            "age": 2,
            "description": "Have 3+ of every icon type visible on board",
            "check_function": "check_dominion",
        },
        "Consciousness": {
            "age": 3,
            "description": "Have 12+ visible Human Mind icons on board",
            "check_function": "check_consciousness",
        },
        "Apotheosis": {
            "age": 4,
            "description": "Have all 5 colors, each Proliferated right/up/aslant",
            "check_function": "check_apotheosis",
        },
        "Transcendence": {
            "age": 5,
            "description": "Have all 5 colors, each top card Era 8+",
            "check_function": "check_transcendence",
        },
        "Abundance": {
            "age": 6,
            "description": "Have 5+ Score cards from different eras",
            "check_function": "check_abundance",
        },
    }

    def __init__(self):
        self.turn_tracking = {}

    def reset_turn_tracking(self, game_id: str, player_id: str):
        key = f"{game_id}_{player_id}"
        self.turn_tracking[key] = {"cards_archived": 0, "cards_scored": 0}

    def track_card_action(
        self, game_id: str, player_id: str, action: str, count: int = 1
    ):
        key = f"{game_id}_{player_id}"
        if key not in self.turn_tracking:
            self.reset_turn_tracking(game_id, player_id)

        if action == "archive":
            self.turn_tracking[key]["cards_archived"] += count
        elif action == "score":
            self.turn_tracking[key]["cards_scored"] += count

    def check_all_achievements(self, game: "Game", player: "Player") -> list[str]:
        earned = []

        for name, config in self.SPECIAL_ACHIEVEMENTS.items():
            if self._player_has_achievement(player, name):
                continue
            if self._achievement_claimed(game, name):
                continue

            check_method = getattr(self, config["check_function"])
            if check_method(game, player):
                self._award_achievement(game, player, name, config["age"])
                earned.append(name)
                logger.info(f"Player {player.name} earned special achievement: {name}")

        return earned

    def check_emergence(self, game: "Game", player: "Player") -> bool:
        """Archive 6+ cards OR Score 6+ cards in a single turn."""
        key = f"{game.game_id}_{player.id}"
        tracking = self.turn_tracking.get(key, {})
        return tracking.get("cards_archived", 0) >= 6 or tracking.get("cards_scored", 0) >= 6

    def check_dominion(self, game: "Game", player: "Player") -> bool:
        """3+ of every icon type visible on board."""
        if not hasattr(player, "board"):
            return False

        symbol_counts = self._count_board_symbols(player.board)
        required_symbols = [
            Symbol.CIRCUIT, Symbol.NEURAL_NET, Symbol.DATA,
            Symbol.ALGORITHM, Symbol.HUMAN_MIND, Symbol.ROBOT,
        ]
        return all(symbol_counts.get(symbol, 0) >= 3 for symbol in required_symbols)

    def check_consciousness(self, game: "Game", player: "Player") -> bool:
        """12+ visible Human Mind icons on board."""
        if not hasattr(player, "board"):
            return False

        symbol_counts = self._count_board_symbols(player.board)
        return symbol_counts.get(Symbol.HUMAN_MIND, 0) >= 12

    def check_apotheosis(self, game: "Game", player: "Player") -> bool:
        """All 5 colors, each Proliferated right/up/aslant."""
        if not hasattr(player, "board"):
            return False

        board = player.board
        colors_properly_splayed = 0

        for color in ["red", "blue", "green", "purple", "yellow"]:
            stack = getattr(board, f"{color}_cards", [])
            if not stack or len(stack) < 2:
                return False
            if hasattr(board, "splay_directions"):
                splay = board.splay_directions.get(color)
                if splay in ["right", "up", "aslant"]:
                    colors_properly_splayed += 1

        return colors_properly_splayed == 5

    def check_transcendence(self, game: "Game", player: "Player") -> bool:
        """All 5 colors, each top card Era 8+."""
        if not hasattr(player, "board"):
            return False

        board = player.board
        high_value_cards = 0

        for color in ["red", "blue", "green", "purple", "yellow"]:
            stack = getattr(board, f"{color}_cards", [])
            if not stack:
                return False
            top_card = stack[-1]
            if hasattr(top_card, "age") and top_card.age >= 8:
                high_value_cards += 1

        return high_value_cards == 5

    def check_abundance(self, game: "Game", player: "Player") -> bool:
        """5+ cards in Score pile from different eras."""
        if not hasattr(player, "score_pile"):
            return False

        unique_ages = set()
        for card in player.score_pile:
            if hasattr(card, "age"):
                unique_ages.add(card.age)

        return len(unique_ages) >= 5

    def _count_board_symbols(self, board) -> dict[Symbol, int]:
        counts = {}

        for color in ["red", "blue", "green", "purple", "yellow"]:
            stack = getattr(board, f"{color}_cards", [])
            if not stack:
                continue

            splay = None
            if hasattr(board, "splay_directions"):
                splay = board.splay_directions.get(color)

            visible_symbols = self._get_visible_symbols(stack, splay)
            for symbol in visible_symbols:
                counts[symbol] = counts.get(symbol, 0) + 1

        return counts

    def _get_visible_symbols(self, stack: list, splay: str | None) -> list[Symbol]:
        if not stack:
            return []

        visible = []

        if not splay or len(stack) == 1:
            top_card = stack[-1]
            if hasattr(top_card, "symbol_positions") and any(top_card.symbol_positions):
                for symbol in top_card.symbol_positions:
                    if symbol:
                        visible.append(symbol)
            elif hasattr(top_card, "symbols"):
                visible.extend(top_card.symbols)
        else:
            for i, card in enumerate(stack):
                if i == len(stack) - 1:
                    # Top card — all symbols visible
                    if hasattr(card, "symbol_positions") and any(card.symbol_positions):
                        for symbol in card.symbol_positions:
                            if symbol:
                                visible.append(symbol)
                    elif hasattr(card, "symbols"):
                        visible.extend(card.symbols)
                elif splay == "left":
                    # Left splay reveals positions [2, 3] (bottom_right, top_right)
                    if hasattr(card, "symbol_positions") and any(card.symbol_positions):
                        positions = card.symbol_positions
                        if len(positions) > 2 and positions[2]:
                            visible.append(positions[2])
                        if len(positions) > 3 and positions[3]:
                            visible.append(positions[3])
                elif splay == "right":
                    # Right splay reveals positions [0, 1] (top_left, bottom_left)
                    if hasattr(card, "symbol_positions") and any(card.symbol_positions):
                        positions = card.symbol_positions
                        if positions[0]:
                            visible.append(positions[0])
                        if len(positions) > 1 and positions[1]:
                            visible.append(positions[1])
                elif splay in ["up", "aslant"]:
                    # Up/aslant splay reveals positions [1, 2, 3]
                    if hasattr(card, "symbol_positions") and any(card.symbol_positions):
                        positions = card.symbol_positions
                        for idx in [1, 2, 3]:
                            if len(positions) > idx and positions[idx]:
                                visible.append(positions[idx])

        return visible

    def _player_has_achievement(self, player: "Player", name: str) -> bool:
        if not hasattr(player, "achievements"):
            return False

        for achievement in player.achievements:
            if isinstance(achievement, str):
                if achievement == name:
                    return True
            elif hasattr(achievement, "name") and achievement.name == name:
                return True

        return False

    def _achievement_claimed(self, game: "Game", name: str) -> bool:
        for player in game.players:
            if self._player_has_achievement(player, name):
                return True
        return False

    def _award_achievement(self, game: "Game", player: "Player", name: str, age: int):
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

        if not hasattr(player, "achievements"):
            player.achievements = []
        player.achievements.append(achievement)

        logger.info(f"Special achievement {name} awarded to {player.name}")


# Global instance
special_achievement_checker = SpecialAchievementChecker()
