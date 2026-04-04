"""
Global AI Cost Monitoring System

Centralized tracking and enforcement of AI API costs across all games and players.
"""
import os
from datetime import datetime

from logging_config import get_logger

logger = get_logger(__name__)


class CostLimitExceeded(Exception):
    """Raised when cost limits would be exceeded"""

    pass


class GlobalAICostMonitor:
    """
    Centralized monitoring for all AI API costs across the application.

    Features:
    - Real-time cost tracking per game, per player, per difficulty
    - Rate limiting and budget enforcement
    - Cost analytics and reporting
    - Alert system for unusual spending
    """

    def __init__(self):
        self.daily_limit = float(os.getenv("AI_DAILY_COST_LIMIT", "50.00"))
        self.per_game_limit = float(os.getenv("AI_MAX_COST_PER_GAME", "5.00"))

        # Track costs in memory (or Redis for distributed systems)
        self.daily_costs = 0.0
        self.game_costs: dict[str, float] = {}  # game_id -> cost
        self.player_costs: dict[str, float] = {}  # player_id -> cost
        self.last_reset = datetime.now()

        # Cost breakdown by difficulty (3 tiers)
        self.costs_by_difficulty: dict[str, float] = {
            "easy": 0.0,
            "medium": 0.0,
            "hard": 0.0,
        }

        logger.info(
            f"GlobalAICostMonitor initialized: "
            f"daily_limit=${self.daily_limit}, "
            f"per_game_limit=${self.per_game_limit}"
        )

    def validate_difficulty_levels(self, available_difficulties: list[str]):
        """
        Validate that all difficulty levels are configured.
        Called at startup to fail fast if configuration is incomplete.
        """
        missing = [
            d for d in available_difficulties if d not in self.costs_by_difficulty
        ]
        if missing:
            error_msg = (
                f"CRITICAL: Cost monitor missing difficulty levels: {missing}. "
                f"Configured: {list(self.costs_by_difficulty.keys())}. "
                f"This will cause AI players to fail. Fix ai_cost_monitor.py."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        logger.info(
            f"✅ Cost monitor validated for difficulties: {available_difficulties}"
        )

    async def record_api_call(
        self,
        game_id: str,
        player_id: str,
        difficulty: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int,
        model: str,
    ) -> dict:
        """Record an API call and calculate cost"""

        # Check if daily reset needed
        if (datetime.now() - self.last_reset).days >= 1:
            self._reset_daily_costs()

        # Calculate cost
        cost = self._calculate_cost(input_tokens, output_tokens, cached_tokens, model)

        # Check limits BEFORE recording
        if self.daily_costs + cost > self.daily_limit:
            raise CostLimitExceeded(
                f"Daily limit of ${self.daily_limit} would be exceeded"
            )

        game_cost = self.game_costs.get(game_id, 0.0)
        if game_cost + cost > self.per_game_limit:
            raise CostLimitExceeded(
                f"Per-game limit of ${self.per_game_limit} would be exceeded"
            )

        # Validate difficulty level (fail fast if misconfigured)
        if difficulty not in self.costs_by_difficulty:
            error_msg = (
                f"CRITICAL: Unknown difficulty '{difficulty}'. "
                f"Configured difficulties: {list(self.costs_by_difficulty.keys())}. "
                f"This indicates a configuration mismatch. Check ai_cost_monitor.py and ai_service.py."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Record costs
        self.daily_costs += cost
        self.game_costs[game_id] = game_cost + cost
        self.player_costs[player_id] = self.player_costs.get(player_id, 0.0) + cost
        self.costs_by_difficulty[difficulty] += cost

        # Alert if unusual spending
        if cost > 1.0:  # Single call over $1
            logger.warning(
                f"High-cost API call: ${cost:.3f} for {model} "
                f"({input_tokens} input, {output_tokens} output)"
            )

        logger.debug(
            f"API cost recorded: ${cost:.4f} "
            f"(daily: ${self.daily_costs:.2f}/{self.daily_limit})"
        )

        return {
            "cost": cost,
            "daily_remaining": self.daily_limit - self.daily_costs,
            "game_remaining": self.per_game_limit - self.game_costs[game_id],
        }

    def _calculate_cost(
        self, input_tokens: int, output_tokens: int, cached_tokens: int, model: str
    ) -> float:
        """Calculate cost based on model pricing"""

        # Pricing for Claude models (both old and new naming conventions)
        HAIKU_PRICING = {
            "input": 0.25 / 1_000_000,
            "output": 1.25 / 1_000_000,
            "cache_read": 0.025 / 1_000_000,  # 90% off
            "cache_write": 0.3125 / 1_000_000,  # 25% markup
        }
        PRICING = {
            # New naming convention
            "claude-haiku-3-5-20241022": HAIKU_PRICING,
            # Old naming convention (still supported)
            "claude-3-5-haiku-20241022": HAIKU_PRICING,
            "claude-sonnet-4-5-20250929": {
                "input": 3.0 / 1_000_000,
                "output": 15.0 / 1_000_000,
                "cache_read": 0.30 / 1_000_000,
                "cache_write": 3.75 / 1_000_000,
            },
            "claude-opus-4-1-20250122": {
                "input": 15.0 / 1_000_000,
                "output": 75.0 / 1_000_000,
                "cache_read": 1.50 / 1_000_000,
                "cache_write": 18.75 / 1_000_000,
            },
        }

        prices = PRICING.get(model, HAIKU_PRICING)

        # Cached tokens are billed at cache_read rate
        input_cost = (input_tokens - cached_tokens) * prices["input"]
        cache_cost = cached_tokens * prices["cache_read"]
        output_cost = output_tokens * prices["output"]

        return input_cost + cache_cost + output_cost

    def get_stats(self) -> dict:
        """Get current cost statistics"""
        return {
            "daily_spent": self.daily_costs,
            "daily_limit": self.daily_limit,
            "daily_remaining": self.daily_limit - self.daily_costs,
            "games_active": len(self.game_costs),
            "total_players": len(self.player_costs),
            "costs_by_difficulty": self.costs_by_difficulty.copy(),
            "average_cost_per_game": (
                sum(self.game_costs.values()) / len(self.game_costs)
                if self.game_costs
                else 0.0
            ),
        }

    def _reset_daily_costs(self):
        """Reset daily tracking"""
        logger.info(f"Resetting daily costs. Total spent: ${self.daily_costs:.2f}")
        self.daily_costs = 0.0
        self.game_costs.clear()
        self.costs_by_difficulty = {k: 0.0 for k in self.costs_by_difficulty}
        self.last_reset = datetime.now()


# Global singleton instance
cost_monitor = GlobalAICostMonitor()
