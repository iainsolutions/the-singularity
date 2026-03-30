"""
Redis store for game state persistence and session management.
Allows scaling to multiple backend instances.
"""

import asyncio
import contextlib
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from app_config import game_config, redis_config

logger = logging.getLogger(__name__)

# Check if Redis is available
try:
    import redis.asyncio as redis
    from redis.asyncio import Redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not installed. Install with: pip install redis[hiredis]")


class RedisGameStore:
    """
    Redis-based game state storage for scalability.
    Falls back to in-memory storage if Redis is unavailable.
    """

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or redis_config.url
        self.redis_client: Redis | None = None
        self.connected = False
        self.ttl = game_config.game_timeout  # Use configurable game timeout as TTL
        self.orphan_ttl = game_config.orphan_game_ttl  # Short TTL for orphaned games on startup

        # Get Redis connection parameters from centralized config
        self.connection_kwargs = redis_config.get_connection_kwargs()

        # Fallback in-memory storage with expiration tracking
        self.memory_store: dict[str, Any] = {}
        self.memory_expiry: dict[str, float] = {}  # Track expiration times

        # Cleanup task will be started on first connect
        self._cleanup_task = None

    # Removed _parse_redis_config method - now using centralized app_config

    async def _cleanup_expired_memory(self):
        """Periodically clean up expired entries from in-memory store."""
        while True:
            try:
                current_time = time.time()
                expired_keys = []

                # Find expired keys
                for key, expire_time in self.memory_expiry.items():
                    if current_time > expire_time:
                        expired_keys.append(key)

                # Remove expired entries
                for key in expired_keys:
                    if key in self.memory_store:
                        del self.memory_store[key]
                    if key in self.memory_expiry:
                        del self.memory_expiry[key]

                if expired_keys:
                    logger.info(
                        f"Cleaned up {len(expired_keys)} expired entries from memory store"
                    )

                # Use configurable cleanup interval
                await asyncio.sleep(game_config.cleanup_interval * 5)  # 5x cleanup interval

            except Exception as e:
                logger.error(f"Error during memory cleanup: {e}")
                await asyncio.sleep(game_config.cleanup_interval * 5)  # Continue cleanup even if there's an error

    def _set_memory_with_expiry(self, key: str, value: Any, ttl: int):
        """Set a value in memory store with expiration time."""
        import time

        self.memory_store[key] = value
        self.memory_expiry[key] = time.time() + ttl

    def _get_memory_if_valid(self, key: str) -> Any | None:
        """Get a value from memory store if it hasn't expired."""
        import time

        if key not in self.memory_store:
            return None

        # Check if expired
        if key in self.memory_expiry and time.time() > self.memory_expiry[key]:
            # Remove expired entry
            del self.memory_store[key]
            del self.memory_expiry[key]
            return None

        return self.memory_store[key]

    def _delete_from_memory(self, key: str):
        """Delete a key from memory store and expiry tracking."""
        if key in self.memory_store:
            del self.memory_store[key]
        if key in self.memory_expiry:
            del self.memory_expiry[key]

    async def connect(self):
        """Connect to Redis with comprehensive configuration support"""
        if not REDIS_AVAILABLE:
            logger.info("Redis not available, using in-memory storage")
            return

        try:
            # Use centralized Redis configuration
            connection_params = {
                "encoding": "utf-8",
                "decode_responses": False,  # We'll handle decoding ourselves
                "max_connections": redis_config.max_connections,
                **self.connection_kwargs  # Include all connection parameters from config
            }

            # SSL/TLS configuration is handled by redis_config.get_connection_kwargs()
            if redis_config.ssl_enabled:
                connection_params["ssl"] = True
                logger.info("Redis SSL/TLS enabled")

            # Create Redis connection
            self.redis_client = await redis.from_url(
                self.redis_url, **connection_params
            )

            # Test connection
            await self.redis_client.ping()
            self.connected = True

            # Log connection success with security info
            ssl_info = " (SSL/TLS)" if redis_config.ssl_enabled else " (no SSL)"
            auth_info = " (authenticated)" if redis_config.password else ""
            logger.info(f"Connected to Redis at {self.redis_url}{ssl_info}{auth_info}")

            # Mark orphaned games for expiration (games without active connections)
            await self.expire_orphaned_games()

        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Using in-memory storage.")
            logger.debug(f"Redis connection error details: {type(e).__name__}: {e}")
            self.connected = False

        # Start cleanup task for in-memory storage (if not already running)
        if not self._cleanup_task or self._cleanup_task.done():
            try:
                self._cleanup_task = asyncio.create_task(self._cleanup_expired_memory())
                logger.debug("Started memory cleanup task")
            except RuntimeError:
                # No event loop running - cleanup will be manual
                logger.debug("No event loop for cleanup task, will clean up manually")

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self.connected = False

        # Clean up memory cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            logger.debug("Stopped memory cleanup task")

    async def expire_orphaned_games(self) -> int:
        """Set short TTL on all existing games (orphaned after server restart).

        Called on startup to ensure games without active connections expire quickly.
        If a player reconnects, normal save_game() calls reset TTL to full duration.

        Returns number of games marked for expiration.
        """
        if not self.connected or not self.redis_client:
            return 0

        try:
            # Scan for all game keys
            count = 0
            async for key in self.redis_client.scan_iter(match="game:*"):
                # Set short TTL - if current TTL is already shorter, keep it
                key_str = key.decode() if isinstance(key, bytes) else key
                current_ttl = await self.redis_client.ttl(key_str)

                # Only shorten TTL if it's longer than orphan_ttl
                if current_ttl == -1 or current_ttl > self.orphan_ttl:
                    await self.redis_client.expire(key_str, self.orphan_ttl)
                    count += 1

            if count > 0:
                logger.info(
                    f"Marked {count} orphaned games for expiration in {self.orphan_ttl}s"
                )
            return count

        except Exception as e:
            logger.warning(f"Failed to expire orphaned games: {e}")
            return 0

    async def save_game(self, game_id: str, game_data: dict[str, Any], version: int | None = None) -> bool:
        """Save game state to Redis or memory with proper expiration and optional versioning"""
        try:
            # Add version to game data if provided
            if version is not None:
                game_data["version"] = version

            # Serialize game data
            serialized = json.dumps(game_data)

            if self.connected and self.redis_client:
                # Save to Redis with TTL
                await self.redis_client.setex(f"game:{game_id}", self.ttl, serialized)

                # Update game index
                await self.redis_client.zadd(
                    "games:active", {game_id: datetime.now(UTC).timestamp()}
                )

                logger.debug(f"Saved game {game_id} to Redis (version: {version})")
                return True
            else:
                # Fallback to memory with expiration
                self._set_memory_with_expiry(f"game:{game_id}", serialized, self.ttl)
                logger.debug(f"Saved game {game_id} to memory with {self.ttl}s TTL")
                return True

        except Exception as e:
            logger.error(f"Failed to save game {game_id}: {e}")
            return False

    async def load_game(self, game_id: str) -> dict[str, Any] | None:
        """Load game state from Redis or memory with expiration checking"""
        try:
            if self.connected and self.redis_client:
                # Load from Redis
                serialized = await self.redis_client.get(f"game:{game_id}")
                if serialized:
                    # Update TTL on access
                    await self.redis_client.expire(f"game:{game_id}", self.ttl)
                    return json.loads(serialized)
            else:
                # Fallback to memory with expiration check
                serialized = self._get_memory_if_valid(f"game:{game_id}")
                if serialized:
                    return json.loads(serialized)

            return None

        except Exception as e:
            logger.error(f"Failed to load game {game_id}: {e}")
            return None

    async def delete_game(self, game_id: str) -> bool:
        """Delete game from storage"""
        try:
            if self.connected and self.redis_client:
                # Delete from Redis
                await self.redis_client.delete(f"game:{game_id}")
                await self.redis_client.zrem("games:active", game_id)
                logger.debug(f"Deleted game {game_id} from Redis")
                return True
            else:
                # Delete from memory with expiry tracking
                self._delete_from_memory(f"game:{game_id}")
                logger.debug(f"Deleted game {game_id} from memory")
                return True

        except Exception as e:
            logger.error(f"Failed to delete game {game_id}: {e}")
            return False

    async def list_active_games(self) -> list[str]:
        """List all active (non-expired) game IDs"""
        try:
            if self.connected and self.redis_client:
                # Get from Redis sorted set
                game_ids = await self.redis_client.zrange("games:active", 0, -1)
                return [
                    gid.decode() if isinstance(gid, bytes) else gid for gid in game_ids
                ]
            else:
                # Get from memory, but only return non-expired games
                active_games = []
                current_time = time.time()

                for key in list(self.memory_store.keys()):
                    if key.startswith("game:"):
                        # Check if expired
                        if (
                            key in self.memory_expiry
                            and current_time > self.memory_expiry[key]
                        ):
                            # Clean up expired entry
                            self._delete_from_memory(key)
                        else:
                            # Add to active games list
                            game_id = key.replace("game:", "")
                            active_games.append(game_id)

                return active_games

        except Exception as e:
            logger.error(f"Failed to list games: {e}")
            return []

    async def save_player_session(
        self, player_id: str, session_data: dict[str, Any]
    ) -> bool:
        """Save player session data with proper expiration"""
        try:
            serialized = json.dumps(session_data)
            session_ttl = 3600 * 4  # 4 hours for session data

            if self.connected and self.redis_client:
                await self.redis_client.setex(
                    f"session:{player_id}", session_ttl, serialized
                )
                return True
            else:
                # Fallback to memory with session expiration
                self._set_memory_with_expiry(
                    f"session:{player_id}", serialized, session_ttl
                )
                logger.debug(
                    f"Saved session for {player_id} to memory with {session_ttl}s TTL"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to save session for {player_id}: {e}")
            return False

    async def load_player_session(self, player_id: str) -> dict[str, Any] | None:
        """Load player session data with expiration checking"""
        try:
            if self.connected and self.redis_client:
                serialized = await self.redis_client.get(f"session:{player_id}")
                if serialized:
                    return json.loads(serialized)
            else:
                # Fallback to memory with expiration check
                serialized = self._get_memory_if_valid(f"session:{player_id}")
                if serialized:
                    return json.loads(serialized)

            return None

        except Exception as e:
            logger.error(f"Failed to load session for {player_id}: {e}")
            return None

    async def acquire_lock(self, resource: str, timeout: int = 10) -> str | None:
        """
        Acquire a distributed lock for a resource with ownership token.
        Returns lock token on success, None on failure.
        """
        if not self.connected or not self.redis_client:
            # No locking in memory mode - return a fake token
            return str(uuid.uuid4())

        try:
            lock_key = f"lock:{resource}"
            # Generate unique lock token to prevent lock stealing
            lock_token = str(uuid.uuid4())

            # Try to set lock with NX (only if not exists) and EX (expiry)
            result = await self.redis_client.set(
                lock_key, lock_token, nx=True, ex=timeout
            )

            if result:
                return lock_token
            return None

        except Exception as e:
            logger.error(f"Failed to acquire lock for {resource}: {e}")
            return None

    async def release_lock(self, resource: str, lock_token: str) -> bool:
        """
        Release a distributed lock only if the caller owns it.
        Uses Lua script for atomic ownership verification and deletion.
        """
        if not self.connected or not self.redis_client:
            return True

        try:
            lock_key = f"lock:{resource}"

            # Lua script for atomic ownership check and delete
            lua_script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("DEL", KEYS[1])
            else
                return 0
            end
            """

            # Execute the script atomically
            result = await self.redis_client.eval(lua_script, 1, lock_key, lock_token)
            return bool(result)

        except Exception as e:
            logger.error(f"Failed to release lock for {resource}: {e}")
            return False

    async def extend_lock(
        self, resource: str, lock_token: str, timeout: int = 10
    ) -> bool:
        """
        Extend the timeout of an owned lock.
        Returns True if extended successfully, False otherwise.
        """
        if not self.connected or not self.redis_client:
            return True

        try:
            lock_key = f"lock:{resource}"

            # Lua script for atomic ownership check and timeout extension
            lua_script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("EXPIRE", KEYS[1], ARGV[2])
            else
                return 0
            end
            """

            result = await self.redis_client.eval(
                lua_script, 1, lock_key, lock_token, timeout
            )
            return bool(result)

        except Exception as e:
            logger.error(f"Failed to extend lock for {resource}: {e}")
            return False

    async def publish_event(self, channel: str, event: dict[str, Any]) -> bool:
        """Publish an event to a Redis channel for pub/sub"""
        if not self.connected or not self.redis_client:
            # Can't do pub/sub without Redis
            return False

        try:
            serialized = json.dumps(event)
            await self.redis_client.publish(channel, serialized)
            return True

        except Exception as e:
            logger.error(f"Failed to publish event to {channel}: {e}")
            return False

    async def save_game_with_version_check(
        self, game_id: str, game_data: dict[str, Any], expected_version: int
    ) -> tuple[bool, str]:
        """
        Save game state with optimistic locking using version check.
        Returns (success, message) tuple.
        """
        if not self.connected or not self.redis_client:
            # Fallback to regular save in memory mode
            success = await self.save_game(game_id, game_data, expected_version + 1)
            return (success, "Saved without version check (memory mode)")

        try:
            # Lua script for atomic version check and update
            lua_script = """
            local game_key = KEYS[1]
            local new_data = ARGV[1]
            local expected_version = tonumber(ARGV[2])
            local new_version = expected_version + 1
            local ttl = tonumber(ARGV[3])

            -- Get current game data
            local current_data = redis.call('GET', game_key)

            if current_data then
                -- Parse to get current version
                local decoded = cjson.decode(current_data)
                local current_version = decoded.version or 0

                -- Check version match
                if current_version ~= expected_version then
                    return {0, "Version mismatch: expected " .. expected_version .. ", got " .. current_version}
                end
            elseif expected_version ~= 0 then
                -- Game doesn't exist but we expected a specific version
                return {0, "Game not found"}
            end

            -- Parse new data and add version
            local new_decoded = cjson.decode(new_data)
            new_decoded.version = new_version
            local versioned_data = cjson.encode(new_decoded)

            -- Save with TTL
            redis.call('SETEX', game_key, ttl, versioned_data)

            -- Update game index
            redis.call('ZADD', 'games:active', ARGV[4], ARGV[5])

            return {1, new_version}
            """

            # Execute the script atomically
            result = await self.redis_client.eval(
                lua_script,
                1,
                f"game:{game_id}",
                json.dumps(game_data),
                expected_version,
                self.ttl,
                datetime.now(UTC).timestamp(),
                game_id
            )

            if result[0] == 1:
                logger.debug(f"Saved game {game_id} with optimistic lock (new version: {result[1]})")
                return (True, f"Saved with version {result[1]}")
            else:
                logger.warning(f"Version conflict for game {game_id}: {result[1]}")
                return (False, result[1])

        except Exception as e:
            logger.error(f"Failed to save game {game_id} with version check: {e}")
            return (False, str(e))

    async def get_stats(self) -> dict[str, Any]:
        """Get storage statistics"""
        stats = {
            "storage_type": "redis" if self.connected else "memory",
            "connected": self.connected,
        }

        try:
            if self.connected and self.redis_client:
                info = await self.redis_client.info()
                stats.update(
                    {
                        "used_memory": info.get("used_memory_human", "unknown"),
                        "connected_clients": info.get("connected_clients", 0),
                        "total_commands": info.get("total_commands_processed", 0),
                    }
                )

                # Count games
                game_count = await self.redis_client.zcard("games:active")
                stats["active_games"] = game_count
            else:
                # Count only non-expired items from memory
                current_time = time.time()
                active_games = 0
                active_sessions = 0
                expired_keys = []

                for key in self.memory_store:
                    # Check if expired
                    if (
                        key in self.memory_expiry
                        and current_time > self.memory_expiry[key]
                    ):
                        expired_keys.append(key)
                        continue

                    # Count non-expired items
                    if key.startswith("game:"):
                        active_games += 1
                    elif key.startswith("session:"):
                        active_sessions += 1

                # Clean up expired keys found during stats collection
                for key in expired_keys:
                    self._delete_from_memory(key)

                stats.update(
                    {
                        "active_games": active_games,
                        "active_sessions": active_sessions,
                        "memory_entries_total": len(self.memory_store),
                        "expired_entries_cleaned": len(expired_keys),
                    }
                )

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")

        return stats


# Global instance
redis_store = RedisGameStore()
