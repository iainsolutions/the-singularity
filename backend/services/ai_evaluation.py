"""
AI Player Evaluation Framework

Tracks AI performance metrics, decision quality, and win rates to measure
improvements from Phase 1 and Phase 2 optimizations.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class DecisionMetrics:
    """Metrics for a single AI decision"""

    game_id: str
    player_id: str
    difficulty: str
    turn_number: int
    action_type: str
    card_name: str | None = None
    reasoning: str | None = None
    api_cost: float = 0.0
    latency_ms: float = 0.0
    tokens_used: int = 0
    cached_tokens: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Quality indicators
    used_dogma: bool = False
    avoided_empty_hand_dogma: bool = False
    checked_sharing: bool = False
    used_s_tier_card: bool = False  # Tools, Machinery, Software, etc.
    followed_phase_guidance: bool = False


@dataclass
class GameMetrics:
    """Metrics for a complete game"""

    game_id: str
    start_time: str
    end_time: str | None = None
    winner_id: str | None = None

    # Player tracking
    ai_players: list[dict] = field(
        default_factory=list
    )  # {player_id, difficulty, model}
    human_players: list[str] = field(default_factory=list)

    # Outcome
    ai_won: bool = False
    winning_difficulty: str | None = None
    total_turns: int = 0

    # Costs
    total_api_cost: float = 0.0
    total_tokens: int = 0
    total_cached_tokens: int = 0

    # Decisions
    decisions: list[DecisionMetrics] = field(default_factory=list)

    # Quality metrics
    dogma_usage_rate: float = 0.0  # % of actions that were dogma
    empty_hand_errors: int = 0  # Times AI used Oars/Code of Laws with empty hand
    sharing_checks: int = 0  # Times AI reasoning mentioned sharing
    s_tier_usage: int = 0  # Times AI used Tools/Machinery/Software


class AIEvaluationFramework:
    """Framework for tracking and analyzing AI player performance"""

    def __init__(self, data_dir: str = "data/ai_evaluation"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # In-memory tracking
        self.active_games: dict[str, GameMetrics] = {}
        self.completed_games: list[GameMetrics] = []

        # Aggregated statistics
        self.stats_by_difficulty: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "games_played": 0,
                "games_won": 0,
                "win_rate": 0.0,
                "total_cost": 0.0,
                "avg_cost_per_game": 0.0,
                "dogma_usage_rate": 0.0,
                "empty_hand_errors": 0,
                "s_tier_usage": 0,
            }
        )

        logger.info(f"AI Evaluation Framework initialized: {self.data_dir}")

    def start_game(
        self,
        game_id: str,
        ai_players: list[dict],
        human_players: list[str],
    ) -> None:
        """Start tracking a new game"""
        metrics = GameMetrics(
            game_id=game_id,
            start_time=datetime.utcnow().isoformat(),
            ai_players=ai_players,
            human_players=human_players,
        )
        self.active_games[game_id] = metrics
        logger.debug(
            f"Started tracking game {game_id} with {len(ai_players)} AI players"
        )

    def record_decision(
        self,
        game_id: str,
        player_id: str,
        difficulty: str,
        turn_number: int,
        decision: dict,
        metadata: dict | None = None,
    ) -> None:
        """Record an AI decision with quality analysis"""
        if game_id not in self.active_games:
            logger.warning(f"Game {game_id} not being tracked, skipping decision")
            return

        game = self.active_games[game_id]
        metadata = metadata or {}

        # Extract decision details
        action_type = decision.get("action_type", "unknown")
        card_name = decision.get("card_name")
        reasoning = decision.get("reasoning", "")

        # Quality analysis
        used_dogma = action_type == "dogma"
        checked_sharing = "shar" in reasoning.lower() if reasoning else False

        # S-tier cards: Tools, Machinery, Software, Compass
        s_tier_cards = {"Tools", "Machinery", "Software", "Compass", "Code of Laws"}
        used_s_tier = card_name in s_tier_cards if card_name else False

        # Check for empty hand dogma anti-pattern
        hand_dependent_cards = {"Code of Laws", "Clothing", "Masonry"}
        avoided_empty_hand = True
        if card_name in hand_dependent_cards and action_type == "dogma":
            # This would need game state to verify, mark as suspicious
            avoided_empty_hand = "empty" not in reasoning.lower()

        # Create decision metrics
        decision_metrics = DecisionMetrics(
            game_id=game_id,
            player_id=player_id,
            difficulty=difficulty,
            turn_number=turn_number,
            action_type=action_type,
            card_name=card_name,
            reasoning=reasoning,
            api_cost=metadata.get("api_cost", 0.0),
            latency_ms=metadata.get("latency_ms", 0.0),
            tokens_used=metadata.get("tokens_used", 0),
            cached_tokens=metadata.get("cached_tokens", 0),
            used_dogma=used_dogma,
            avoided_empty_hand_dogma=avoided_empty_hand,
            checked_sharing=checked_sharing,
            used_s_tier_card=used_s_tier,
        )

        game.decisions.append(decision_metrics)
        game.total_api_cost += decision_metrics.api_cost
        game.total_tokens += decision_metrics.tokens_used
        game.total_cached_tokens += decision_metrics.cached_tokens

    def end_game(
        self,
        game_id: str,
        winner_id: str | None,
        total_turns: int,
    ) -> None:
        """Finalize game tracking and compute metrics"""
        if game_id not in self.active_games:
            logger.warning(f"Game {game_id} not being tracked, cannot end")
            return

        game = self.active_games.pop(game_id)
        game.end_time = datetime.utcnow().isoformat()
        game.winner_id = winner_id
        game.total_turns = total_turns

        # Determine if AI won
        for ai_player in game.ai_players:
            if ai_player["player_id"] == winner_id:
                game.ai_won = True
                game.winning_difficulty = ai_player["difficulty"]
                break

        # Compute quality metrics
        dogma_count = sum(1 for d in game.decisions if d.used_dogma)
        total_decisions = len(game.decisions)
        game.dogma_usage_rate = (
            dogma_count / total_decisions if total_decisions > 0 else 0
        )

        game.empty_hand_errors = sum(
            1 for d in game.decisions if not d.avoided_empty_hand_dogma
        )
        game.sharing_checks = sum(1 for d in game.decisions if d.checked_sharing)
        game.s_tier_usage = sum(1 for d in game.decisions if d.used_s_tier_card)

        # Save and update stats
        self.completed_games.append(game)
        self._update_difficulty_stats(game)
        self._save_game_metrics(game)

        logger.info(
            f"Game {game_id} completed: "
            f"AI won={game.ai_won}, "
            f"dogma_rate={game.dogma_usage_rate:.1%}, "
            f"cost=${game.total_api_cost:.4f}"
        )

    def _update_difficulty_stats(self, game: GameMetrics) -> None:
        """Update aggregated statistics by difficulty"""
        for ai_player in game.ai_players:
            difficulty = ai_player["difficulty"]
            stats = self.stats_by_difficulty[difficulty]

            stats["games_played"] += 1
            if game.ai_won and game.winning_difficulty == difficulty:
                stats["games_won"] += 1

            stats["win_rate"] = (
                stats["games_won"] / stats["games_played"]
                if stats["games_played"] > 0
                else 0
            )
            stats["total_cost"] += game.total_api_cost
            stats["avg_cost_per_game"] = (
                stats["total_cost"] / stats["games_played"]
                if stats["games_played"] > 0
                else 0
            )

            # Average quality metrics across all games for this difficulty
            stats["dogma_usage_rate"] = (
                stats["dogma_usage_rate"] * (stats["games_played"] - 1)
                + game.dogma_usage_rate
            ) / stats["games_played"]
            stats["empty_hand_errors"] += game.empty_hand_errors
            stats["s_tier_usage"] += game.s_tier_usage

    def _save_game_metrics(self, game: GameMetrics) -> None:
        """Save game metrics to file"""
        try:
            filename = f"game_{game.game_id}_{game.start_time.replace(':', '-')}.json"
            filepath = self.data_dir / filename

            # Convert to dict for JSON serialization
            game_dict = {
                "game_id": game.game_id,
                "start_time": game.start_time,
                "end_time": game.end_time,
                "winner_id": game.winner_id,
                "ai_players": game.ai_players,
                "human_players": game.human_players,
                "ai_won": game.ai_won,
                "winning_difficulty": game.winning_difficulty,
                "total_turns": game.total_turns,
                "total_api_cost": game.total_api_cost,
                "total_tokens": game.total_tokens,
                "total_cached_tokens": game.total_cached_tokens,
                "dogma_usage_rate": game.dogma_usage_rate,
                "empty_hand_errors": game.empty_hand_errors,
                "sharing_checks": game.sharing_checks,
                "s_tier_usage": game.s_tier_usage,
                "decisions": [
                    {
                        "turn_number": d.turn_number,
                        "action_type": d.action_type,
                        "card_name": d.card_name,
                        "reasoning": d.reasoning,
                        "api_cost": d.api_cost,
                        "latency_ms": d.latency_ms,
                        "tokens_used": d.tokens_used,
                        "used_dogma": d.used_dogma,
                        "checked_sharing": d.checked_sharing,
                        "used_s_tier_card": d.used_s_tier_card,
                    }
                    for d in game.decisions
                ],
            }

            with open(filepath, "w") as f:
                json.dump(game_dict, f, indent=2)

            logger.debug(f"Saved game metrics to {filepath}")

        except Exception as e:
            logger.error(f"Failed to save game metrics: {e}", exc_info=True)

    def get_difficulty_stats(self, difficulty: str | None = None) -> dict:
        """Get statistics for a specific difficulty or all difficulties"""
        if difficulty:
            return dict(self.stats_by_difficulty.get(difficulty, {}))
        return {diff: dict(stats) for diff, stats in self.stats_by_difficulty.items()}

    def get_summary_report(self) -> str:
        """Generate a human-readable summary report"""
        lines = [
            "=" * 80,
            "AI EVALUATION SUMMARY REPORT",
            "=" * 80,
            "",
            f"Total games completed: {len(self.completed_games)}",
            f"Active games: {len(self.active_games)}",
            "",
            "PERFORMANCE BY DIFFICULTY:",
            "-" * 80,
        ]

        difficulties = [
            "novice",
            "beginner",
            "intermediate",
            "skilled",
            "advanced",
            "pro",
            "expert",
            "master",
        ]

        for difficulty in difficulties:
            stats = self.stats_by_difficulty.get(difficulty)
            if not stats or stats["games_played"] == 0:
                continue

            lines.append(f"\n{difficulty.upper()}:")
            lines.append(f"  Games: {stats['games_played']}")
            lines.append(f"  Win Rate: {stats['win_rate']:.1%}")
            lines.append(f"  Avg Cost/Game: ${stats['avg_cost_per_game']:.4f}")
            lines.append(f"  Dogma Usage: {stats['dogma_usage_rate']:.1%}")
            lines.append(f"  Empty Hand Errors: {stats['empty_hand_errors']}")
            lines.append(f"  S-Tier Usage: {stats['s_tier_usage']} times")

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def export_stats(self, filename: str = "ai_evaluation_stats.json") -> None:
        """Export all statistics to JSON file"""
        try:
            filepath = self.data_dir / filename

            export_data = {
                "export_time": datetime.utcnow().isoformat(),
                "total_games": len(self.completed_games),
                "difficulty_stats": {
                    diff: dict(stats)
                    for diff, stats in self.stats_by_difficulty.items()
                },
                "recent_games": [
                    {
                        "game_id": game.game_id,
                        "ai_won": game.ai_won,
                        "winning_difficulty": game.winning_difficulty,
                        "dogma_usage_rate": game.dogma_usage_rate,
                        "total_cost": game.total_api_cost,
                    }
                    for game in self.completed_games[-20:]  # Last 20 games
                ],
            }

            with open(filepath, "w") as f:
                json.dump(export_data, f, indent=2)

            logger.info(f"Exported evaluation stats to {filepath}")

        except Exception as e:
            logger.error(f"Failed to export stats: {e}", exc_info=True)


# Global instance
_evaluation_framework: AIEvaluationFramework | None = None


def get_evaluation_framework() -> AIEvaluationFramework:
    """Get or create global evaluation framework"""
    global _evaluation_framework
    if _evaluation_framework is None:
        _evaluation_framework = AIEvaluationFramework()
    return _evaluation_framework


# Convenience functions
def track_game_start(
    game_id: str, ai_players: list[dict], human_players: list[str]
) -> None:
    """Start tracking a game"""
    get_evaluation_framework().start_game(game_id, ai_players, human_players)


def track_decision(
    game_id: str,
    player_id: str,
    difficulty: str,
    turn_number: int,
    decision: dict,
    metadata: dict | None = None,
) -> None:
    """Track an AI decision"""
    get_evaluation_framework().record_decision(
        game_id, player_id, difficulty, turn_number, decision, metadata
    )


def track_game_end(game_id: str, winner_id: str | None, total_turns: int) -> None:
    """End game tracking"""
    get_evaluation_framework().end_game(game_id, winner_id, total_turns)


def get_stats(difficulty: str | None = None) -> dict:
    """Get evaluation statistics"""
    return get_evaluation_framework().get_difficulty_stats(difficulty)


def print_summary() -> None:
    """Print summary report"""
    print(get_evaluation_framework().get_summary_report())


def export_stats(filename: str = "ai_evaluation_stats.json") -> None:
    """Export statistics to file"""
    get_evaluation_framework().export_stats(filename)
