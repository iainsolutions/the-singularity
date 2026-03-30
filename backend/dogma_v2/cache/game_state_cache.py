"""
Multi-layer caching system for game state optimization.

This module provides:
- L1: In-memory object cache (cards, players, game state)
- L2: Redis cache for distributed sessions (optional)
- L3: Database read cache for static game data
- Smart cache invalidation on state changes
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Cache levels for multi-tier caching"""

    L1 = "l1_memory"
    L2 = "l2_redis"
    L3 = "l3_database"


@dataclass
class CacheEntry:
    """Cache entry with metadata"""

    value: Any
    timestamp: float
    access_count: int = 0
    last_accessed: float = 0
    ttl: float | None = None

    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl

    def access(self):
        """Record cache access"""
        self.access_count += 1
        self.last_accessed = time.time()


class CacheStatistics:
    """Track cache performance statistics"""

    def __init__(self):
        self._hits = defaultdict(int)
        self._misses = defaultdict(int)
        self._invalidations = defaultdict(int)
        self._start_time = time.time()

    def record_hit(self, cache_type: str):
        """Record cache hit"""
        self._hits[cache_type] += 1

    def record_miss(self, cache_type: str):
        """Record cache miss"""
        self._misses[cache_type] += 1

    def record_invalidation(self, cache_type: str):
        """Record cache invalidation"""
        self._invalidations[cache_type] += 1

    def get_hit_rate(self, cache_type: str = "card") -> float:
        """Get cache hit rate for specific cache type"""
        hits = self._hits[cache_type]
        misses = self._misses[cache_type]
        total = hits + misses
        return hits / total if total > 0 else 0.0

    def get_total_hit_rate(self) -> float:
        """Get overall cache hit rate"""
        total_hits = sum(self._hits.values())
        total_misses = sum(self._misses.values())
        total = total_hits + total_misses
        return total_hits / total if total > 0 else 0.0

    def get_statistics(self) -> dict[str, Any]:
        """Get comprehensive cache statistics"""
        uptime = time.time() - self._start_time
        return {
            "uptime_seconds": uptime,
            "hit_rates": {
                cache_type: self.get_hit_rate(cache_type) for cache_type in self._hits
            },
            "total_hit_rate": self.get_total_hit_rate(),
            "hits": dict(self._hits),
            "misses": dict(self._misses),
            "invalidations": dict(self._invalidations),
        }


class CacheInvalidator:
    """Smart cache invalidation based on state changes"""

    def __init__(self, cache_instance):
        self.cache = cache_instance
        self._dependency_graph = {
            "card_moved": ["card", "player_state", "board_state"],
            "player_state": ["player_state", "game_state"],
            "board_update": ["board_state", "game_state"],
            "score_change": ["player_state", "game_state"],
            "achievement_update": ["player_state", "game_state"],
            "game_phase_change": ["game_state"],
        }

    def invalidate_on_state_change(self, change_type: str, affected_objects: list[str]):
        """Invalidate caches based on state change type"""
        if change_type not in self._dependency_graph:
            logger.warning(f"Unknown change type for invalidation: {change_type}")
            return

        cache_types_to_invalidate = self._dependency_graph[change_type]

        for cache_type in cache_types_to_invalidate:
            if cache_type == "card":
                for obj_id in affected_objects:
                    self.cache.invalidate_card(obj_id)
            elif cache_type == "player_state":
                for obj_id in affected_objects:
                    self.cache.invalidate_player(obj_id)
            elif cache_type == "board_state":
                self.cache.invalidate_board_cache()
            elif cache_type == "game_state":
                self.cache.invalidate_game_cache()

        # Record invalidation statistics
        for cache_type in cache_types_to_invalidate:
            self.cache._cache_stats.record_invalidation(cache_type)


class GameStateCache:
    """
    Multi-layer game state caching system.

    Provides fast access to frequently used game objects with intelligent
    invalidation and performance monitoring.
    """

    def __init__(self, max_size_l1: int = 10000, default_ttl: float = 300.0):
        """
        Initialize multi-layer cache system.

        Args:
            max_size_l1: Maximum entries in L1 cache
            default_ttl: Default time-to-live in seconds
        """
        # L1 Cache (In-memory)
        self._card_cache: dict[str, CacheEntry] = {}
        self._player_cache: dict[str, CacheEntry] = {}
        self._game_cache: dict[str, CacheEntry] = {}
        self._board_cache: dict[str, CacheEntry] = {}

        # Cache configuration
        self._max_size_l1 = max_size_l1
        self._default_ttl = default_ttl

        # Statistics and monitoring
        self._cache_stats = CacheStatistics()
        self._invalidator = CacheInvalidator(self)

        # L2 Redis cache (optional - fallback to L1 if not available)
        self._redis_client = self._initialize_redis()

        logger.info(f"GameStateCache initialized with L1 size: {max_size_l1}")

    def _initialize_redis(self):
        """Initialize Redis client for L2 cache if available"""
        try:
            import os

            import redis

            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                client = redis.from_url(redis_url, decode_responses=True)
                client.ping()  # Test connection
                logger.info("L2 Redis cache connected")
                return client
        except Exception as e:
            logger.info(f"L2 Redis cache not available: {e}")

        return None

    def get_cached_card(self, card_id: str):
        """
        Get cached card with L1/L2 fallback.

        Args:
            card_id: Unique card identifier

        Returns:
            Cached card object or None if not found
        """
        # Try L1 cache first
        if card_id in self._card_cache:
            entry = self._card_cache[card_id]
            if not entry.is_expired():
                entry.access()
                self._cache_stats.record_hit("card")
                return entry.value
            else:
                # Remove expired entry
                del self._card_cache[card_id]

        # Try L2 Redis cache if available
        if self._redis_client:
            try:
                redis_key = f"card:{card_id}"
                cached_data = self._redis_client.get(redis_key)
                if cached_data:
                    import json

                    card_data = json.loads(cached_data)
                    # Store in L1 for future access
                    self._store_in_l1("card", card_id, card_data)
                    self._cache_stats.record_hit("card")
                    return card_data
            except Exception as e:
                logger.warning(f"L2 cache error for card {card_id}: {e}")

        # Cache miss - need to load from source
        self._cache_stats.record_miss("card")
        return None

    def store_card(self, card_id: str, card_data: Any, ttl: float | None = None):
        """Store card in cache with optional TTL"""
        ttl = ttl or self._default_ttl

        # Store in L1
        self._store_in_l1("card", card_id, card_data, ttl)

        # Store in L2 Redis if available
        if self._redis_client:
            try:
                import json

                redis_key = f"card:{card_id}"
                self._redis_client.setex(redis_key, int(ttl), json.dumps(card_data))
            except Exception as e:
                logger.warning(f"Failed to store card {card_id} in L2 cache: {e}")

    def get_cached_player(self, player_id: str):
        """Get cached player state"""
        if player_id in self._player_cache:
            entry = self._player_cache[player_id]
            if not entry.is_expired():
                entry.access()
                self._cache_stats.record_hit("player")
                return entry.value
            else:
                del self._player_cache[player_id]

        self._cache_stats.record_miss("player")
        return None

    def store_player(self, player_id: str, player_data: Any, ttl: float | None = None):
        """Store player state in cache"""
        ttl = ttl or self._default_ttl
        self._store_in_l1("player", player_id, player_data, ttl)

    def get_cached_game_state(self, game_id: str):
        """Get cached game state"""
        if game_id in self._game_cache:
            entry = self._game_cache[game_id]
            if not entry.is_expired():
                entry.access()
                self._cache_stats.record_hit("game")
                return entry.value
            else:
                del self._game_cache[game_id]

        self._cache_stats.record_miss("game")
        return None

    def store_game_state(self, game_id: str, game_data: Any, ttl: float | None = None):
        """Store game state in cache"""
        ttl = ttl or self._default_ttl
        self._store_in_l1("game", game_id, game_data, ttl)

    def _store_in_l1(
        self, cache_type: str, key: str, value: Any, ttl: float | None = None
    ):
        """Store entry in L1 cache with LRU eviction if needed"""
        entry = CacheEntry(value=value, timestamp=time.time(), ttl=ttl)

        cache_dict = self._get_cache_dict(cache_type)
        cache_dict[key] = entry

        # Enforce cache size limits with LRU eviction
        if len(cache_dict) > self._max_size_l1:
            self._evict_lru_entries(cache_dict)

    def _get_cache_dict(self, cache_type: str) -> dict[str, CacheEntry]:
        """Get the appropriate cache dictionary"""
        if cache_type == "card":
            return self._card_cache
        elif cache_type == "player":
            return self._player_cache
        elif cache_type == "game":
            return self._game_cache
        elif cache_type == "board":
            return self._board_cache
        else:
            raise ValueError(f"Unknown cache type: {cache_type}")

    def _evict_lru_entries(
        self, cache_dict: dict[str, CacheEntry], target_size: int | None = None
    ):
        """Evict least recently used entries"""
        if target_size is None:
            target_size = int(self._max_size_l1 * 0.8)  # Evict to 80% of max size

        # Sort by last accessed time (oldest first)
        sorted_items = sorted(
            cache_dict.items(), key=lambda x: x[1].last_accessed or x[1].timestamp
        )

        # Remove oldest entries
        entries_to_remove = len(cache_dict) - target_size
        for i in range(entries_to_remove):
            key_to_remove = sorted_items[i][0]
            del cache_dict[key_to_remove]

    def invalidate_card(self, card_id: str):
        """Invalidate specific card cache"""
        self._card_cache.pop(card_id, None)

        if self._redis_client:
            try:
                redis_key = f"card:{card_id}"
                self._redis_client.delete(redis_key)
            except Exception as e:
                logger.warning(
                    f"Failed to invalidate card {card_id} from L2 cache: {e}"
                )

    def invalidate_player(self, player_id: str):
        """Invalidate specific player cache"""
        self._player_cache.pop(player_id, None)

    def invalidate_game_cache(self):
        """Invalidate all game state caches"""
        self._game_cache.clear()

    def invalidate_board_cache(self):
        """Invalidate board state caches"""
        self._board_cache.clear()

    def get_cache_statistics(self) -> dict[str, Any]:
        """Get comprehensive cache statistics"""
        stats = self._cache_stats.get_statistics()
        stats.update(
            {
                "l1_sizes": {
                    "cards": len(self._card_cache),
                    "players": len(self._player_cache),
                    "games": len(self._game_cache),
                    "boards": len(self._board_cache),
                },
                "l2_available": self._redis_client is not None,
                "memory_usage": self._estimate_memory_usage(),
            }
        )
        return stats

    def _estimate_memory_usage(self) -> dict[str, int]:
        """Estimate memory usage of cache"""
        try:
            total_entries = (
                len(self._card_cache)
                + len(self._player_cache)
                + len(self._game_cache)
                + len(self._board_cache)
            )

            # Rough estimate: 1KB per cache entry on average
            estimated_bytes = total_entries * 1024

            return {
                "total_entries": total_entries,
                "estimated_bytes": estimated_bytes,
                "estimated_mb": round(estimated_bytes / (1024 * 1024), 2),
            }
        except Exception:
            return {"error": "Could not estimate memory usage"}

    def cleanup_expired_entries(self):
        """Remove expired entries from all caches"""
        time.time()
        expired_count = 0

        for cache_dict in [
            self._card_cache,
            self._player_cache,
            self._game_cache,
            self._board_cache,
        ]:
            expired_keys = [
                key for key, entry in cache_dict.items() if entry.is_expired()
            ]

            for key in expired_keys:
                del cache_dict[key]
                expired_count += 1

        if expired_count > 0:
            logger.debug(f"Cleaned up {expired_count} expired cache entries")

        return expired_count


# Global cache instance
_game_state_cache: GameStateCache | None = None


def get_game_state_cache() -> GameStateCache:
    """Get global game state cache instance"""
    global _game_state_cache
    if _game_state_cache is None:
        _game_state_cache = GameStateCache()
    return _game_state_cache


def invalidate_on_state_change(change_type: str, affected_objects: list[str]):
    """Convenience function for cache invalidation"""
    cache = get_game_state_cache()
    cache._invalidator.invalidate_on_state_change(change_type, affected_objects)
