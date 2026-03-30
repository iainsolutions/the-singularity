"""
Object pooling system for memory optimization.

Provides:
- Object pools for frequently created objects
- Memory-efficient data structures
- Memory usage monitoring and leak detection
- Garbage collection optimization
"""

import gc
import logging
import sys
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from typing import Any, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PoolableObject(ABC):
    """Base class for objects that can be pooled"""

    @abstractmethod
    def reset(self):
        """Reset object state for reuse"""
        pass

    @abstractmethod
    def initialize(self, *args, **kwargs):
        """Initialize object with new data"""
        pass


class CardReference(PoolableObject):
    """Memory-efficient card reference with pooling support"""

    __slots__ = ["_hash", "age", "card_id", "color", "location", "name", "owner_id"]

    def __init__(self):
        self.card_id: str | None = None
        self.name: str | None = None
        self.age: int | None = None
        self.color: str | None = None
        self.location: str | None = None
        self.owner_id: str | None = None
        self._hash: int | None = None

    def initialize(
        self,
        card_id: str,
        name: str,
        age: int,
        color: str,
        location: str = "unknown",
        owner_id: str | None = None,
    ):
        """Initialize with card data"""
        self.card_id = card_id
        self.name = name
        self.age = age
        self.color = color
        self.location = location
        self.owner_id = owner_id
        self._hash = None  # Reset cached hash

    def reset(self):
        """Reset for reuse"""
        self.card_id = None
        self.name = None
        self.age = None
        self.color = None
        self.location = None
        self.owner_id = None
        self._hash = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "card_id": self.card_id,
            "name": self.name,
            "age": self.age,
            "color": self.color,
            "location": self.location,
            "owner_id": self.owner_id,
        }

    def __hash__(self):
        if self._hash is None and self.card_id:
            self._hash = hash(self.card_id)
        return self._hash or 0

    def __eq__(self, other):
        if not isinstance(other, CardReference):
            return False
        return self.card_id == other.card_id


class InteractionRequest(PoolableObject):
    """Memory-efficient interaction request with pooling support"""

    __slots__ = [
        "data",
        "interaction_type",
        "player_id",
        "request_id",
        "timeout",
        "timestamp",
    ]

    def __init__(self):
        self.request_id: str | None = None
        self.player_id: str | None = None
        self.interaction_type: str | None = None
        self.data: dict[str, Any] | None = None
        self.timeout: float | None = None
        self.timestamp: float | None = None

    def initialize(
        self,
        request_id: str,
        player_id: str,
        interaction_type: str,
        data: dict[str, Any],
        timeout: float = 300.0,
    ):
        """Initialize with request data"""
        self.request_id = request_id
        self.player_id = player_id
        self.interaction_type = interaction_type
        self.data = data.copy() if data else {}
        self.timeout = timeout
        self.timestamp = time.time()

    def reset(self):
        """Reset for reuse"""
        self.request_id = None
        self.player_id = None
        self.interaction_type = None
        self.data = None
        self.timeout = None
        self.timestamp = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "request_id": self.request_id,
            "player_id": self.player_id,
            "interaction_type": self.interaction_type,
            "data": self.data,
            "timeout": self.timeout,
            "timestamp": self.timestamp,
        }


class DogmaContext(PoolableObject):
    """Memory-efficient dogma context with pooling support"""

    __slots__ = [
        "_initialized",
        "card_name",
        "context_id",
        "effect_type",
        "game_id",
        "metadata",
        "player_id",
        "state_snapshot",
        "variables",
    ]

    def __init__(self):
        self.context_id: str | None = None
        self.game_id: str | None = None
        self.player_id: str | None = None
        self.card_name: str | None = None
        self.effect_type: str | None = None
        self.state_snapshot: dict[str, Any] | None = None
        self.variables: dict[str, Any] | None = None
        self.metadata: dict[str, Any] | None = None
        self._initialized = False

    def initialize(
        self,
        context_id: str,
        game_id: str,
        player_id: str,
        card_name: str,
        effect_type: str = "dogma",
    ):
        """Initialize with context data"""
        self.context_id = context_id
        self.game_id = game_id
        self.player_id = player_id
        self.card_name = card_name
        self.effect_type = effect_type
        self.state_snapshot = {}
        self.variables = {}
        self.metadata = {}
        self._initialized = True

    def reset(self):
        """Reset for reuse"""
        self.context_id = None
        self.game_id = None
        self.player_id = None
        self.card_name = None
        self.effect_type = None
        self.state_snapshot = None
        self.variables = None
        self.metadata = None
        self._initialized = False


class ObjectPoolStatistics:
    """Track object pool statistics"""

    def __init__(self):
        self.objects_created = 0
        self.objects_borrowed = 0
        self.objects_returned = 0
        self.pool_hits = 0
        self.pool_misses = 0
        self.peak_pool_size = 0
        self.current_pool_size = 0
        self.memory_saved_bytes = 0

    def record_borrow(self, from_pool: bool = True):
        """Record object borrow"""
        self.objects_borrowed += 1
        if from_pool:
            self.pool_hits += 1
        else:
            self.pool_misses += 1

    def record_return(self):
        """Record object return"""
        self.objects_returned += 1

    def record_creation(self):
        """Record object creation"""
        self.objects_created += 1

    def update_pool_size(self, size: int):
        """Update pool size statistics"""
        self.current_pool_size = size
        if size > self.peak_pool_size:
            self.peak_pool_size = size

    def get_hit_rate(self) -> float:
        """Get pool hit rate"""
        total = self.pool_hits + self.pool_misses
        return self.pool_hits / total if total > 0 else 0.0

    def get_reuse_rate(self) -> float:
        """Get object reuse rate"""
        return self.objects_returned / max(self.objects_created, 1)


class TypedObjectPool(Generic[T]):
    """Generic typed object pool"""

    def __init__(
        self, object_type: type[T], max_size: int = 1000, enable_statistics: bool = True
    ):
        """
        Initialize typed object pool.

        Args:
            object_type: Class of objects to pool
            max_size: Maximum pool size
            enable_statistics: Enable statistics tracking
        """
        self.object_type = object_type
        self.max_size = max_size
        self.enable_statistics = enable_statistics

        self._pool: deque = deque()
        self._active_objects: set[int] = set()  # Track active object IDs
        self._stats = ObjectPoolStatistics() if enable_statistics else None

        logger.debug(
            f"TypedObjectPool created for {object_type.__name__} (max_size: {max_size})"
        )

    def borrow_object(self) -> T:
        """
        Borrow object from pool.

        Returns:
            Object instance (from pool or newly created)
        """
        if self._pool:
            # Get from pool
            obj = self._pool.popleft()
            if self._stats:
                self._stats.record_borrow(from_pool=True)
                self._stats.update_pool_size(len(self._pool))

            # Track as active
            self._active_objects.add(id(obj))

            return obj
        else:
            # Create new object
            obj = self.object_type()
            if self._stats:
                self._stats.record_creation()
                self._stats.record_borrow(from_pool=False)

            # Track as active
            self._active_objects.add(id(obj))

            return obj

    def return_object(self, obj: T):
        """
        Return object to pool.

        Args:
            obj: Object to return
        """
        obj_id = id(obj)

        # Only accept objects that were borrowed from this pool
        if obj_id not in self._active_objects:
            logger.warning("Attempted to return object not from this pool")
            return

        # Remove from active tracking
        self._active_objects.remove(obj_id)

        # Reset object state
        if hasattr(obj, "reset"):
            obj.reset()

        # Return to pool if not full
        if len(self._pool) < self.max_size:
            self._pool.append(obj)
            if self._stats:
                self._stats.record_return()
                self._stats.update_pool_size(len(self._pool))
        # Otherwise, let it be garbage collected

    def get_statistics(self) -> dict[str, Any] | None:
        """Get pool statistics"""
        if not self._stats:
            return None

        return {
            "object_type": self.object_type.__name__,
            "pool_size": len(self._pool),
            "max_size": self.max_size,
            "active_objects": len(self._active_objects),
            "objects_created": self._stats.objects_created,
            "objects_borrowed": self._stats.objects_borrowed,
            "objects_returned": self._stats.objects_returned,
            "hit_rate": self._stats.get_hit_rate(),
            "reuse_rate": self._stats.get_reuse_rate(),
            "peak_pool_size": self._stats.peak_pool_size,
        }

    def clear_pool(self):
        """Clear all objects from pool"""
        self._pool.clear()
        if self._stats:
            self._stats.update_pool_size(0)


class ObjectPool:
    """
    Comprehensive object pooling system.

    Manages pools for different object types with automatic cleanup
    and memory monitoring.
    """

    def __init__(self, default_max_size: int = 1000):
        """
        Initialize object pool manager.

        Args:
            default_max_size: Default maximum size for pools
        """
        self.default_max_size = default_max_size
        self._pools: dict[type, TypedObjectPool] = {}

        # Global statistics
        self._global_stats = {
            "total_objects_pooled": 0,
            "total_memory_saved_mb": 0.0,
            "pools_created": 0,
            "cleanup_cycles": 0,
        }

        # Memory monitoring
        self._initial_memory_usage = self._get_memory_usage()
        self._last_cleanup = time.time()

        logger.info("ObjectPool initialized")

    def get_pool(self, object_type: type[T]) -> TypedObjectPool[T]:
        """
        Get or create pool for object type.

        Args:
            object_type: Class of objects to pool

        Returns:
            TypedObjectPool for the specified type
        """
        if object_type not in self._pools:
            pool = TypedObjectPool[object_type](
                object_type=object_type, max_size=self.default_max_size
            )
            self._pools[object_type] = pool
            self._global_stats["pools_created"] += 1
            logger.debug(f"Created pool for {object_type.__name__}")

        return self._pools[object_type]

    def get_card_reference(
        self,
        card_id: str,
        name: str,
        age: int,
        color: str,
        location: str = "unknown",
        owner_id: str | None = None,
    ) -> CardReference:
        """
        Get CardReference from pool.

        Args:
            card_id: Card identifier
            name: Card name
            age: Card age
            color: Card color
            location: Card location
            owner_id: Owner player ID

        Returns:
            Initialized CardReference
        """
        pool = self.get_pool(CardReference)
        card_ref = pool.borrow_object()
        card_ref.initialize(card_id, name, age, color, location, owner_id)
        return card_ref

    def return_card_reference(self, card_ref: CardReference):
        """Return CardReference to pool"""
        pool = self.get_pool(CardReference)
        pool.return_object(card_ref)

    def get_interaction_request(
        self,
        request_id: str,
        player_id: str,
        interaction_type: str,
        data: dict[str, Any],
        timeout: float = 300.0,
    ) -> InteractionRequest:
        """
        Get InteractionRequest from pool.

        Args:
            request_id: Request identifier
            player_id: Target player
            interaction_type: Type of interaction
            data: Interaction data
            timeout: Request timeout

        Returns:
            Initialized InteractionRequest
        """
        pool = self.get_pool(InteractionRequest)
        request = pool.borrow_object()
        request.initialize(request_id, player_id, interaction_type, data, timeout)
        return request

    def return_interaction_request(self, request: InteractionRequest):
        """Return InteractionRequest to pool"""
        pool = self.get_pool(InteractionRequest)
        pool.return_object(request)

    def get_dogma_context(
        self,
        context_id: str,
        game_id: str,
        player_id: str,
        card_name: str,
        effect_type: str = "dogma",
    ) -> DogmaContext:
        """
        Get DogmaContext from pool.

        Args:
            context_id: Context identifier
            game_id: Game identifier
            player_id: Player identifier
            card_name: Card name
            effect_type: Effect type

        Returns:
            Initialized DogmaContext
        """
        pool = self.get_pool(DogmaContext)
        context = pool.borrow_object()
        context.initialize(context_id, game_id, player_id, card_name, effect_type)
        return context

    def return_dogma_context(self, context: DogmaContext):
        """Return DogmaContext to pool"""
        pool = self.get_pool(DogmaContext)
        pool.return_object(context)

    def cleanup_pools(self, force_gc: bool = False):
        """
        Clean up pools and perform garbage collection.

        Args:
            force_gc: Force garbage collection
        """
        self._global_stats["cleanup_cycles"] += 1
        objects_cleaned = 0

        # Clean individual pools
        for pool in self._pools.values():
            pool_size_before = len(pool._pool)
            # Remove oldest objects if pool is large
            if pool_size_before > pool.max_size // 2:
                objects_to_remove = pool_size_before // 4  # Remove 25%
                for _ in range(min(objects_to_remove, pool_size_before)):
                    if pool._pool:
                        pool._pool.popleft()
                        objects_cleaned += 1

        # Force garbage collection if requested
        if force_gc:
            collected = gc.collect()
            logger.debug(f"Garbage collection freed {collected} objects")

        self._last_cleanup = time.time()
        logger.debug(f"Cleaned up {objects_cleaned} pooled objects")

    def get_memory_usage(self) -> dict[str, Any]:
        """Get current memory usage information"""
        current_memory = self._get_memory_usage()
        memory_delta = current_memory - self._initial_memory_usage

        return {
            "current_memory_mb": current_memory / (1024 * 1024),
            "initial_memory_mb": self._initial_memory_usage / (1024 * 1024),
            "memory_delta_mb": memory_delta / (1024 * 1024),
            "total_objects": sum(
                len(pool._pool) + len(pool._active_objects)
                for pool in self._pools.values()
            ),
            "pooled_objects": sum(len(pool._pool) for pool in self._pools.values()),
            "active_objects": sum(
                len(pool._active_objects) for pool in self._pools.values()
            ),
        }

    def _get_memory_usage(self) -> int:
        """Get current memory usage in bytes"""
        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            return process.memory_info().rss
        except ImportError:
            # Fallback to sys.getsizeof approximation
            return sys.getsizeof(self._pools) * 1000  # Rough estimate

    def get_comprehensive_statistics(self) -> dict[str, Any]:
        """Get comprehensive statistics for all pools"""
        pool_stats = {}
        total_hit_rate = 0.0
        total_reuse_rate = 0.0
        pool_count = 0

        for object_type, pool in self._pools.items():
            stats = pool.get_statistics()
            if stats:
                pool_stats[object_type.__name__] = stats
                total_hit_rate += stats["hit_rate"]
                total_reuse_rate += stats["reuse_rate"]
                pool_count += 1

        return {
            "global_stats": self._global_stats,
            "pool_statistics": pool_stats,
            "summary": {
                "total_pools": len(self._pools),
                "avg_hit_rate": total_hit_rate / max(pool_count, 1),
                "avg_reuse_rate": total_reuse_rate / max(pool_count, 1),
                "memory_efficiency": self._calculate_memory_efficiency(),
            },
            "memory_usage": self.get_memory_usage(),
        }

    def _calculate_memory_efficiency(self) -> float:
        """Calculate memory efficiency score"""
        memory_info = self.get_memory_usage()
        total_objects = memory_info["total_objects"]

        if total_objects == 0:
            return 1.0

        # Estimate memory savings from pooling
        estimated_savings = 0
        for pool in self._pools.values():
            if pool._stats:
                # Rough calculation: each pooled object saves creation overhead
                estimated_savings += (
                    pool._stats.objects_returned * 100
                )  # 100 bytes per object

        return min(
            1.0,
            estimated_savings / max(memory_info["current_memory_mb"] * 1024 * 1024, 1),
        )


class CompactGameState:
    """
    Memory-efficient game state representation using __slots__ and
    compact data structures.
    """

    __slots__ = [
        "_achievements",
        "_card_registry",
        "_players",
        "_shared_data",
        "current_player",
        "game_id",
        "phase",
        "turn_number",
    ]

    def __init__(self, game_id: str):
        self.game_id = game_id
        self.turn_number = 0
        self.current_player = 0
        self.phase = "setup"

        # Use compact data structures
        self._players = CompactPlayerArray()
        self._card_registry = CompactCardRegistry()
        self._shared_data = {}
        self._achievements = set()

    def add_player(self, player_id: str, player_name: str):
        """Add player to compact array"""
        self._players.add_player(player_id, player_name)

    def get_memory_usage(self) -> int:
        """Calculate memory usage of game state"""
        base_size = sys.getsizeof(self)
        players_size = self._players.get_memory_usage()
        cards_size = self._card_registry.get_memory_usage()
        shared_size = sys.getsizeof(self._shared_data)
        achievements_size = sys.getsizeof(self._achievements)

        return base_size + players_size + cards_size + shared_size + achievements_size

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "game_id": self.game_id,
            "turn_number": self.turn_number,
            "current_player": self.current_player,
            "phase": self.phase,
            "players": self._players.to_dict(),
            "achievements": list(self._achievements),
        }


class CompactPlayerArray:
    """Memory-efficient player array using __slots__"""

    __slots__ = ["_player_lookup", "_players"]

    def __init__(self):
        self._players = []  # List of CompactPlayer objects
        self._player_lookup = {}  # Quick lookup by ID

    def add_player(self, player_id: str, player_name: str):
        """Add player to array"""
        player = CompactPlayer(player_id, player_name, len(self._players))
        self._players.append(player)
        self._player_lookup[player_id] = len(self._players) - 1

    def get_player(self, player_id: str) -> Optional["CompactPlayer"]:
        """Get player by ID"""
        index = self._player_lookup.get(player_id)
        return self._players[index] if index is not None else None

    def get_memory_usage(self) -> int:
        """Calculate memory usage"""
        base_size = sys.getsizeof(self._players) + sys.getsizeof(self._player_lookup)
        players_size = sum(player.get_memory_usage() for player in self._players)
        return base_size + players_size

    def to_dict(self) -> list[dict[str, Any]]:
        """Convert to dictionary list"""
        return [player.to_dict() for player in self._players]


class CompactPlayer:
    """Memory-efficient player representation"""

    __slots__ = [
        "_board_cards",
        "_hand_size",
        "_score_pile_size",
        "achievements",
        "index",
        "name",
        "player_id",
        "score",
    ]

    def __init__(self, player_id: str, name: str, index: int):
        self.player_id = player_id
        self.name = name
        self.index = index
        self.score = 0
        self.achievements = 0  # Bitfield for achievements

        # Compact representations
        self._hand_size = 0
        self._board_cards = [None] * 5  # One per color
        self._score_pile_size = 0

    def get_memory_usage(self) -> int:
        """Calculate memory usage"""
        return sys.getsizeof(self) + sys.getsizeof(self._board_cards)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "player_id": self.player_id,
            "name": self.name,
            "index": self.index,
            "score": self.score,
            "hand_size": self._hand_size,
            "score_pile_size": self._score_pile_size,
        }


class CompactCardRegistry:
    """Memory-efficient card registry"""

    __slots__ = ["_cards_by_id", "_cards_by_name", "_memory_usage"]

    def __init__(self):
        self._cards_by_id = {}
        self._cards_by_name = defaultdict(list)
        self._memory_usage = 0

    def get_memory_usage(self) -> int:
        """Get estimated memory usage"""
        return self._memory_usage

    def register_card(self, card_data: dict[str, Any]):
        """Register card in compact form"""
        # This would store cards in a memory-efficient format
        self._memory_usage += sys.getsizeof(card_data)


# Global object pool instance
_object_pool: ObjectPool | None = None


def get_object_pool() -> ObjectPool:
    """Get global object pool instance"""
    global _object_pool
    if _object_pool is None:
        _object_pool = ObjectPool()
    return _object_pool
