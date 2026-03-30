import asyncio
import logging
from contextlib import asynccontextmanager

from app_config import RedisConfig


logger = logging.getLogger(__name__)

# Check if Redis is available
try:
    import redis.asyncio as redis
    from redis.asyncio.lock import Lock

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not installed. Install with: pip install redis[hiredis]")


class InMemoryLock:
    """
    In-memory lock implementation that mimics Redis Lock interface.
    Used as fallback when Redis is unavailable.
    """

    def __init__(self, resource_id: str, timeout: int = 30):
        self.resource_id = resource_id
        self.timeout = timeout
        self._lock = asyncio.Lock()
        self._acquired = False

    async def acquire(
        self, blocking: bool = True, blocking_timeout: float | None = None
    ) -> bool:
        """Acquire the lock."""
        try:
            if blocking_timeout:
                self._acquired = await asyncio.wait_for(
                    self._lock.acquire(), timeout=blocking_timeout
                )
            else:
                self._acquired = await self._lock.acquire()
            return self._acquired
        except TimeoutError:
            return False

    async def release(self):
        """Release the lock."""
        if self._acquired and self._lock.locked():
            self._lock.release()
            self._acquired = False


class LockService:
    """
    Service for managing distributed locks using Redis.
    Falls back to in-memory locks when Redis is unavailable.
    """

    def __init__(self, redis_config: RedisConfig | None = None):
        self.config = redis_config or RedisConfig()
        self.redis_client: redis.Redis | None = None
        self.connected = False
        self._memory_locks: dict[str, InMemoryLock] = {}
        self._connect()

    def _connect(self):
        """Initialize Redis connection with fallback to in-memory."""
        if not REDIS_AVAILABLE:
            logger.info("Redis library not available, using in-memory locks")
            self.connected = False
            return

        try:
            self.redis_client = redis.from_url(
                self.config.url, **self.config.get_connection_kwargs()
            )
            self.connected = True
            logger.info(f"LockService connected to Redis at {self.config.url}")
        except Exception as e:
            logger.warning(
                f"Failed to connect to Redis for locking: {e}. Using in-memory locks."
            )
            self.connected = False

    def _get_or_create_memory_lock(
        self, resource_id: str, timeout: int = 30
    ) -> InMemoryLock:
        """Get or create an in-memory lock for a resource."""
        if resource_id not in self._memory_locks:
            self._memory_locks[resource_id] = InMemoryLock(resource_id, timeout)
        return self._memory_locks[resource_id]

    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("LockService Redis connection closed")

    def get_lock(
        self, resource_id: str, timeout: int = 30, blocking_timeout: int = 10
    ) -> Lock | InMemoryLock:
        """
        Get a distributed lock for a specific resource.

        Args:
            resource_id: Unique identifier for the resource (e.g., game_id).
            timeout: How long the lock is valid for in seconds (auto-release).
            blocking_timeout: How long to wait to acquire the lock.

        Returns:
            A Redis Lock object or InMemoryLock that can be used as an async context manager.
        """
        if self.connected and self.redis_client:
            # Use Redis lock
            lock_name = f"lock:{resource_id}"
            return self.redis_client.lock(
                name=lock_name, timeout=timeout, blocking_timeout=blocking_timeout
            )
        else:
            # Use in-memory lock as fallback
            return self._get_or_create_memory_lock(resource_id, timeout)

    @asynccontextmanager
    async def acquire_lock(
        self, resource_id: str, timeout: int = 30, blocking_timeout: int = 10
    ):
        """
        Async context manager for acquiring a lock.

        Usage:
            async with lock_service.acquire_lock("game_123"):
                # critical section
        """
        lock = self.get_lock(resource_id, timeout, blocking_timeout)

        # For in-memory locks, pass blocking_timeout to acquire
        if isinstance(lock, InMemoryLock):
            acquired = await lock.acquire(
                blocking=True, blocking_timeout=blocking_timeout
            )
        else:
            acquired = await lock.acquire()

        if not acquired:
            logger.warning(
                f"Failed to acquire lock for {resource_id} after {blocking_timeout}s"
            )
            raise TimeoutError(f"Could not acquire lock for {resource_id}")

        try:
            logger.debug(f"Acquired lock for {resource_id}")
            yield lock
        finally:
            try:
                await lock.release()
                logger.debug(f"Released lock for {resource_id}")
            except Exception as e:
                # Lock might have expired or been released already (Redis)
                # or already released (in-memory)
                # Check if this is a Redis LockError only if Redis is available
                is_redis_lock_error = (
                    REDIS_AVAILABLE
                    and hasattr(redis, "exceptions")
                    and isinstance(e, redis.exceptions.LockError)
                )

                if is_redis_lock_error:
                    logger.warning(
                        f"Failed to release Redis lock for {resource_id} (might have expired)"
                    )
                else:
                    logger.debug(f"Lock release for {resource_id}: {e}")


# Global instance
_lock_service: LockService | None = None


def get_lock_service() -> LockService:
    """Get or create the global LockService instance."""
    global _lock_service
    if _lock_service is None:
        _lock_service = LockService()
    return _lock_service
