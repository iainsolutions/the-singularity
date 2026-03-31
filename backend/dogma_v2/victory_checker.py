"""
Victory condition checking utility for dogma system.

This module provides centralized victory checking that can be called
immediately after any effect to enforce The Singularity Ultimate rules.
"""

import logging


logger = logging.getLogger(__name__)


class VictoryChecker:
    """Utility class for checking victory conditions during dogma execution"""

    @staticmethod
    def check_immediate_victory(game, context=None) -> str | None:
        """
        Check if any victory conditions have been met and should trigger immediately.

        According to The Singularity Ultimate rules, victory conditions should be checked
        immediately when conditions are met, not just at end of turn.

        Args:
            game: Game object with current state
            context: Optional DogmaContext for additional logging

        Returns:
            Victory message string if victory condition met, None otherwise
        """
        try:
            if not game or not game.players:
                return None

            # CRITICAL: Check achievement victory first
            # Use the game's centralized victory calculation for player count
            required_achievements = game.get_achievements_needed_for_victory()
            for player in game.players:
                achievement_count = len(player.achievements)
                if achievement_count >= required_achievements:
                    victory_msg = f"{player.name} wins with {achievement_count} achievements (immediate victory, needed {required_achievements})"
                    logger.info(f"IMMEDIATE VICTORY: {victory_msg}")

                    # Set game winner for consistency
                    if hasattr(game, "winner"):
                        game.winner = player

                    if hasattr(game.state, "game_ended"):
                        game.state.game_ended = True
                        game.state.victory_type = "achievements"

                    return victory_msg

            # IMPORTANT: Score victory should NOT be checked during dogma
            # Score victory only triggers on age deck exhaustion, not during dogma effects
            # This prevents premature score victories as mentioned in recent commits:
            # "prevent premature score victory during dogma; only check achievement victory by player count"

            # Check for special achievement victory conditions
            special_victory = VictoryChecker._check_special_achievement_victory(
                game, context
            )
            if special_victory:
                return special_victory

            return None  # No immediate victory condition met

        except Exception as e:
            logger.error(f"Victory check failed: {e}", exc_info=True)
            return None

    @staticmethod
    def check_end_of_dogma_victory(game, context=None) -> str | None:
        """
        Check for victory conditions that only apply at the end of dogma completion.

        This includes score victory checks that should happen at turn boundaries,
        not immediately during effects.

        Args:
            game: Game object with current state
            context: Optional DogmaContext for additional logging

        Returns:
            Victory message string if victory condition met, None otherwise
        """
        try:
            if not game or not game.players:
                return None

            # Check achievement victory (for consistency, though immediate check should catch this)
            required_achievements = game.get_achievements_needed_for_victory()
            for player in game.players:
                achievement_count = len(player.achievements)
                if achievement_count >= required_achievements:
                    victory_msg = f"{player.name} wins with {achievement_count} achievements (needed {required_achievements})"
                    logger.info(f"END-OF-DOGMA VICTORY: {victory_msg}")
                    return victory_msg

            # Score victory check - only at end of dogma/turn, not immediately during effects
            # Use the standard game victory method if available
            if (
                hasattr(game, "check_victory_conditions")
                and callable(game.check_victory_conditions)
                and game.check_victory_conditions()
                and hasattr(game, "winner")
                and game.winner
            ):
                return f"{game.winner.name} wins"

            # Simple score check fallback (standard The Singularity rules)
            for player in game.players:
                total_score = sum(card.age for card in player.score_pile)
                achievements_count = len(player.achievements)
                required_score = achievements_count * 5 if achievements_count > 0 else 0

                # Score victory: score >= 5 * achievements (with at least 1 achievement)
                if total_score >= required_score and achievements_count > 0:
                    return f"{player.name} wins with {total_score} points and {achievements_count} achievements"

            # Check for special achievement victory conditions (for end-of-dogma too)
            special_victory = VictoryChecker._check_special_achievement_victory(
                game, context
            )
            if special_victory:
                return special_victory

            return None  # No victory condition met

        except Exception as e:
            logger.error(f"End-of-dogma victory check failed: {e}", exc_info=True)
            return None

    @staticmethod
    def _check_special_achievement_victory(game, context=None) -> str | None:
        """
        Check for special achievement types that trigger immediate victory.

        These include:
        - highest_score_wins: Player with highest score wins immediately
        - lowest_score_wins: Player with lowest score wins immediately
        - Any other special victory achievements
        """
        try:
            if not game or not game.players:
                return None

            # Check all players for special victory achievements
            for player in game.players:
                for achievement in player.achievements:
                    achievement_name = (
                        achievement.name
                        if hasattr(achievement, "name")
                        else str(achievement)
                    )

                    # Check for highest score wins achievement
                    if (
                        "highest_score_wins" in achievement_name.lower()
                        or achievement_name == "Empire State Building"
                    ):
                        # Find player with highest score
                        highest_player = max(
                            game.players,
                            key=lambda p: sum(card.age for card in p.score_pile),
                        )
                        highest_score = sum(
                            card.age for card in highest_player.score_pile
                        )

                        victory_msg = f"{highest_player.name} wins with highest score ({highest_score} points) due to {achievement_name} achievement"
                        logger.info(f"SPECIAL ACHIEVEMENT VICTORY: {victory_msg}")

                        # Set game winner
                        if hasattr(game, "winner"):
                            game.winner = highest_player
                        if hasattr(game, "phase"):
                            from models.game import GamePhase

                            game.phase = GamePhase.FINISHED

                        return victory_msg

                    # Check for lowest score wins achievement
                    elif (
                        "lowest_score_wins" in achievement_name.lower()
                        or achievement_name == "The Internet"
                    ):
                        # Find player with lowest score
                        lowest_player = min(
                            game.players,
                            key=lambda p: sum(card.age for card in p.score_pile),
                        )
                        lowest_score = sum(
                            card.age for card in lowest_player.score_pile
                        )

                        victory_msg = f"{lowest_player.name} wins with lowest score ({lowest_score} points) due to {achievement_name} achievement"
                        logger.info(f"SPECIAL ACHIEVEMENT VICTORY: {victory_msg}")

                        # Set game winner
                        if hasattr(game, "winner"):
                            game.winner = lowest_player
                        if hasattr(game, "phase"):
                            from models.game import GamePhase

                            game.phase = GamePhase.FINISHED

                        return victory_msg

                    # Check for other special victory conditions
                    elif "wins" in achievement_name.lower() and (
                        "immediately" in achievement_name.lower()
                        or "victory" in achievement_name.lower()
                    ):
                        victory_msg = f"{player.name} wins immediately due to {achievement_name} achievement"
                        logger.info(f"SPECIAL ACHIEVEMENT VICTORY: {victory_msg}")

                        # Set game winner
                        if hasattr(game, "winner"):
                            game.winner = player
                        if hasattr(game, "phase"):
                            from models.game import GamePhase

                            game.phase = GamePhase.FINISHED

                        return victory_msg

            return None  # No special achievement victory

        except Exception as e:
            logger.error(
                f"Special achievement victory check failed: {e}", exc_info=True
            )
            return None

    @staticmethod
    def check_age_deck_exhaustion_victory(game, context=None) -> str | None:
        """
        Check if the game should end due to age deck exhaustion.

        According to The Singularity Ultimate rules:
        - Game ends when all age decks 1-10 are empty
        - Player with highest score wins
        - In case of tie, tied players share victory

        Args:
            game: Game object with current state
            context: Optional DogmaContext for additional logging

        Returns:
            Victory message string if age exhaustion victory triggered, None otherwise
        """
        try:
            if not game or not game.players:
                return None

            # Check if all age decks 1-10 are empty
            if not hasattr(game, "deck_manager") or not hasattr(
                game.deck_manager, "age_decks"
            ):
                return None

            all_ages_empty = True
            for age in range(1, 11):  # Ages 1-10
                if (
                    age in game.deck_manager.age_decks
                    and len(game.deck_manager.age_decks[age]) > 0
                ):
                    all_ages_empty = False
                    break

            if not all_ages_empty:
                return None  # Age decks still have cards

            logger.info("Age deck exhaustion detected - all ages 1-10 are empty")

            # Find player(s) with highest score
            player_scores = [
                (player, sum(card.age for card in player.score_pile))
                for player in game.players
            ]

            if not player_scores:
                return None

            max_score = max(score for _, score in player_scores)
            winners = [player for player, score in player_scores if score == max_score]

            # Set game winner(s) and end game
            if hasattr(game, "phase"):
                from models.game import GamePhase

                game.phase = GamePhase.FINISHED

            if len(winners) == 1:
                winner = winners[0]
                if hasattr(game, "winner"):
                    game.winner = winner
                victory_msg = f"{winner.name} wins by highest score ({max_score} points) after age deck exhaustion"
                logger.info(f"AGE EXHAUSTION VICTORY: {victory_msg}")
                return victory_msg
            else:
                # Multiple winners tied
                winner_names = ", ".join(w.name for w in winners)
                victory_msg = f"Tied victory: {winner_names} share the win with {max_score} points after age deck exhaustion"
                logger.info(f"AGE EXHAUSTION TIE: {victory_msg}")
                return victory_msg

        except Exception as e:
            logger.error(f"Age deck exhaustion check failed: {e}", exc_info=True)
            return None

    @staticmethod
    def check_all_victory_conditions(
        game, context=None, check_exhaustion=True
    ) -> str | None:
        """
        Comprehensive victory check that tests all possible victory conditions.

        This is the master method that should be called when you want to check
        for any possible victory condition.

        Args:
            game: Game object with current state
            context: Optional DogmaContext for additional logging
            check_exhaustion: Whether to check age deck exhaustion (default True)

        Returns:
            Victory message string if any victory condition met, None otherwise
        """
        try:
            # 1. Check immediate victory conditions (achievements, special achievements)
            immediate_victory = VictoryChecker.check_immediate_victory(game, context)
            if immediate_victory:
                return immediate_victory

            # 2. Check age deck exhaustion victory (if enabled)
            if check_exhaustion:
                exhaustion_victory = VictoryChecker.check_age_deck_exhaustion_victory(
                    game, context
                )
                if exhaustion_victory:
                    return exhaustion_victory

            # 3. Check end-of-dogma victory conditions (score victory, etc.)
            end_dogma_victory = VictoryChecker.check_end_of_dogma_victory(game, context)
            if end_dogma_victory:
                return end_dogma_victory

            return None  # No victory conditions met

        except Exception as e:
            logger.error(f"Comprehensive victory check failed: {e}", exc_info=True)
            return None
