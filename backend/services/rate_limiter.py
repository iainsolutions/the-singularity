import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for WebSocket messages to prevent DoS attacks."""

    def __init__(self, max_messages: int = 60, window_seconds: int = 60):
        """Initialize rate limiter.

        Args:
            max_messages: Maximum messages allowed per window
            window_seconds: Time window in seconds
        """
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        self.message_times = defaultdict(deque)
        self.violation_counts = defaultdict(int)
        self.banned_until = {}

        # Future: Use Redis for distributed rate limiting
        # self.redis = RedisConfig.get_redis()

    def is_allowed(self, player_id: str) -> bool:
        """Check if a message from a player is allowed."""
        now = datetime.now()

        # Check if player is banned
        if player_id in self.banned_until:
            if now < self.banned_until[player_id]:
                return False
            else:
                # Ban expired
                del self.banned_until[player_id]
                self.violation_counts[player_id] = 0

        # Clean old timestamps
        cutoff = now - timedelta(seconds=self.window_seconds)
        while (
            self.message_times[player_id] and self.message_times[player_id][0] < cutoff
        ):
            self.message_times[player_id].popleft()

        # Check rate limit
        if len(self.message_times[player_id]) >= self.max_messages:
            self.violation_counts[player_id] += 1

            # Ban player after repeated violations
            if self.violation_counts[player_id] >= 3:
                ban_duration = min(
                    300 * self.violation_counts[player_id], 3600
                )  # Max 1 hour
                self.banned_until[player_id] = now + timedelta(seconds=ban_duration)
                logger.warning(
                    f"Player {player_id} banned for {ban_duration}s due to rate limit violations"
                )

            return False

        # Record message time
        self.message_times[player_id].append(now)
        return True

    def cleanup(self, player_id: str):
        """Clean up data for disconnected player."""
        if player_id in self.message_times:
            del self.message_times[player_id]
        if player_id in self.violation_counts:
            del self.violation_counts[player_id]
        if player_id in self.banned_until:
            del self.banned_until[player_id]
