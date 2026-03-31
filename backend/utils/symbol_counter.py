"""
Symbol Counter Utility

Provides utilities for counting symbols on player boards and determining sharing eligibility.
"""

import logging
from typing import TYPE_CHECKING

from models.card import Symbol

if TYPE_CHECKING:
    from models.game import Game, Player

logger = logging.getLogger(__name__)


class SymbolCounter:
    """Utility class for counting symbols and determining sharing eligibility"""

    @staticmethod
    def get_symbol_enum(symbol_str: str) -> Symbol | None:
        """Convert a string to Symbol enum

        Args:
            symbol_str: String representation of symbol (e.g., 'circuit', 'Neural_Net', 'DATA')

        Returns:
            Symbol enum or None if not found
        """
        if hasattr(symbol_str, "value"):
            # Already a Symbol enum
            return symbol_str

        symbol_lower = str(symbol_str).lower()

        for sym in Symbol:
            if sym.value.lower() == symbol_lower:
                return sym

        logger.warning(f"Could not find Symbol enum for {symbol_str}")
        return None

    @staticmethod
    def count_player_symbols(player: "Player", symbol: str) -> int:
        """Count how many of a specific symbol a player has on their board

        Args:
            player: The player whose board to count
            symbol: The symbol to count (string or Symbol enum)

        Returns:
            Number of symbols on the player's board
        """
        symbol_enum = SymbolCounter.get_symbol_enum(symbol)
        if not symbol_enum:
            return 0

        return player.board.count_symbol(symbol_enum)

    @staticmethod
    def find_sharing_players(
        game: "Game", activating_player: "Player", featured_symbol: str
    ) -> list["Player"]:
        """Find all players who can share a dogma effect

        A player can share if they have at least as many of the featured symbol
        as the activating player.

        Args:
            game: The game instance
            activating_player: The player activating the dogma
            featured_symbol: The dogma's featured symbol

        Returns:
            List of players who can share the effect
        """
        symbol_enum = SymbolCounter.get_symbol_enum(featured_symbol)
        if not symbol_enum:
            return []

        # Count activating player's symbols
        activator_count = activating_player.board.count_symbol(symbol_enum)
        logger.info(
            f"Activating player has {activator_count} {featured_symbol} symbols"
        )

        # Find players who can share
        sharing_players = []
        for other_player in game.players:
            if other_player.id == activating_player.id:
                continue

            other_count = other_player.board.count_symbol(symbol_enum)

            if other_count >= activator_count:
                logger.info(
                    f"{other_player.name} can share with {other_count} {featured_symbol} symbols"
                )
                sharing_players.append(other_player)
            else:
                logger.debug(
                    f"{other_player.name} cannot share (has {other_count} {featured_symbol} symbols)"
                )

        return sharing_players

    @staticmethod
    def find_demand_targets(
        game: "Game", demanding_player: "Player", required_symbol: str
    ) -> list["Player"]:
        """Find all players who are affected by a demand

        A player is affected by a demand if they have fewer of the required symbol
        than the demanding player.

        Args:
            game: The game instance
            demanding_player: The player making the demand
            required_symbol: The symbol required to ignore the demand

        Returns:
            List of players who must respond to the demand
        """
        symbol_enum = SymbolCounter.get_symbol_enum(required_symbol)
        if not symbol_enum:
            return []

        # Count demanding player's symbols
        demander_count = demanding_player.board.count_symbol(symbol_enum)
        logger.info(f"Demanding player has {demander_count} {required_symbol} symbols")

        # Find players who must respond
        target_players = []
        for other_player in game.players:
            if other_player.id == demanding_player.id:
                continue

            other_count = other_player.board.count_symbol(symbol_enum)

            if other_count < demander_count:
                logger.info(
                    f"{other_player.name} must respond to demand (has {other_count} {required_symbol} symbols)"
                )
                target_players.append(other_player)
            else:
                logger.debug(
                    f"{other_player.name} ignores demand (has {other_count} {required_symbol} symbols)"
                )

        return target_players
