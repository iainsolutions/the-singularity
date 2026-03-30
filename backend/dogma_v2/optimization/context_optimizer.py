"""
Context optimization module for Week 4 Phase Streamlining.

Implements copy-on-write (COW) strategy to minimize memory allocation
and improve performance during phase transitions.
"""

import gc
import logging
import weakref
from types import MappingProxyType as FrozenDict
from typing import Any

from ..core.context import DogmaContext

logger = logging.getLogger(__name__)


class OptimizedContextCache:
    """Cache for frequently accessed context data to avoid repeated lookups."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: dict[str, Any] = {}
        self._access_count: dict[str, int] = {}
        self._dirty_keys: set[str] = set()

    def get(self, key: str, default=None):
        """Get cached value with access tracking."""
        self._access_count[key] = self._access_count.get(key, 0) + 1
        return self._cache.get(key, default)

    def set(self, key: str, value: Any):
        """Set cached value and mark as clean."""
        if len(self._cache) >= self.max_size:
            self._evict_least_used()

        self._cache[key] = value
        self._dirty_keys.discard(key)  # Mark as clean

    def invalidate(self, key: str):
        """Mark cache entry as dirty/invalid."""
        self._dirty_keys.add(key)

    def is_dirty(self, key: str) -> bool:
        """Check if cache entry is dirty."""
        return key in self._dirty_keys

    def clear_dirty(self):
        """Clear all dirty entries."""
        for key in self._dirty_keys:
            self._cache.pop(key, None)
            self._access_count.pop(key, None)
        self._dirty_keys.clear()

    def _evict_least_used(self):
        """Evict least frequently used entries."""
        if not self._cache:
            return

        # Remove the least accessed item
        least_used_key = min(self._access_count.items(), key=lambda x: x[1])[0]
        self._cache.pop(least_used_key, None)
        self._access_count.pop(least_used_key, None)
        self._dirty_keys.discard(least_used_key)


class CopyOnWriteVariables:
    """Copy-on-write implementation for context variables."""

    def __init__(self, base_variables: FrozenDict):
        self._base = base_variables
        self._modifications: dict[str, Any] = {}
        self._deleted_keys: set[str] = set()
        self._materialized = None  # Cached full dict when needed

    def get(self, key: str, default=None):
        """Get variable value with COW semantics."""
        if key in self._deleted_keys:
            return default
        if key in self._modifications:
            return self._modifications[key]
        return self._base.get(key, default)

    def set(self, key: str, value: Any):
        """Set variable value (triggers copy-on-write)."""
        self._modifications[key] = value
        self._deleted_keys.discard(key)
        self._materialized = None  # Invalidate cached dict

    def delete(self, key: str):
        """Delete variable (triggers copy-on-write)."""
        self._deleted_keys.add(key)
        self._modifications.pop(key, None)
        self._materialized = None

    def has_modifications(self) -> bool:
        """Check if any modifications were made."""
        return bool(self._modifications or self._deleted_keys)

    def to_frozen_dict(self) -> FrozenDict:
        """Convert to frozen dict (materializes changes if needed)."""
        if not self.has_modifications():
            return self._base

        if self._materialized is None:
            # Materialize the full dictionary
            result = dict(self._base)
            for key in self._deleted_keys:
                result.pop(key, None)
            result.update(self._modifications)
            self._materialized = FrozenDict(result)

        return self._materialized

    def get_modification_summary(self) -> dict[str, Any]:
        """Get summary of modifications for debugging."""
        return {
            "modified_keys": list(self._modifications.keys()),
            "deleted_keys": list(self._deleted_keys),
            "modification_count": len(self._modifications),
            "deletion_count": len(self._deleted_keys),
        }


class OptimizedDogmaContext:
    """
    Optimized context wrapper that implements copy-on-write semantics
    and intelligent caching for better performance.
    """

    def __init__(self, base_context: DogmaContext):
        self._base = base_context
        self._cow_variables = CopyOnWriteVariables(base_context.variables)
        self._cache = OptimizedContextCache()
        self._modification_tracker = set()  # Track which aspects were modified

        # Performance metrics
        self._copy_avoided_count = 0
        self._cache_hits = 0
        self._cache_misses = 0

    @classmethod
    def create_optimized(cls, base_context: DogmaContext) -> "OptimizedDogmaContext":
        """Create optimized context wrapper."""
        return cls(base_context)

    def get_variable(self, key: str, default=None):
        """Get variable with caching."""
        cache_key = f"var_{key}"

        if not self._cache.is_dirty(cache_key):
            cached_value = self._cache.get(cache_key)
            if cached_value is not None:
                self._cache_hits += 1
                return cached_value

        self._cache_misses += 1
        value = self._cow_variables.get(key, default)
        self._cache.set(cache_key, value)
        return value

    def with_variable(self, key: str, value: Any) -> "OptimizedDogmaContext":
        """Set variable using copy-on-write."""
        # Create new optimized context
        new_context = OptimizedDogmaContext(self._base)
        new_context._cow_variables = CopyOnWriteVariables(
            self._cow_variables.to_frozen_dict()
        )
        new_context._cow_variables.set(key, value)
        new_context._cache = self._cache  # Share cache for read-heavy operations
        new_context._cache.invalidate(f"var_{key}")

        new_context._modification_tracker = self._modification_tracker.copy()
        new_context._modification_tracker.add("variables")

        if not self._cow_variables.has_modifications():
            new_context._copy_avoided_count += 1

        return new_context

    def with_variables(self, updates: dict[str, Any]) -> "OptimizedDogmaContext":
        """Set multiple variables efficiently."""
        if not updates:
            return self

        new_context = OptimizedDogmaContext(self._base)
        new_context._cow_variables = CopyOnWriteVariables(
            self._cow_variables.to_frozen_dict()
        )

        for key, value in updates.items():
            new_context._cow_variables.set(key, value)
            new_context._cache.invalidate(f"var_{key}")

        new_context._cache = self._cache
        new_context._modification_tracker = self._modification_tracker.copy()
        new_context._modification_tracker.add("variables")

        return new_context

    def to_dogma_context(self) -> DogmaContext:
        """Convert back to regular DogmaContext (materializes changes)."""
        if not self._modification_tracker:
            # No modifications, return original
            return self._base

        # Create new context with materialized changes
        new_variables = self._cow_variables.to_frozen_dict()

        # Use dataclasses.replace equivalent for the context
        return DogmaContext(
            game=self._base.game,
            activating_player=self._base.activating_player,
            card=self._base.card,
            transaction_id=self._base.transaction_id,
            current_player=self._base.current_player,
            variables=new_variables,
            results=self._base.results,
            sharing=self._base.sharing,
            phase_history=self._base.phase_history,
            state_snapshots=self._base.state_snapshots,
        )

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get performance metrics for monitoring."""
        return {
            "copies_avoided": self._copy_avoided_count,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self._cache_hits
            / max(1, self._cache_hits + self._cache_misses),
            "modifications_tracked": len(self._modification_tracker),
            "cow_summary": self._cow_variables.get_modification_summary(),
        }

    def force_gc_cleanup(self):
        """Force garbage collection and cache cleanup for memory optimization."""
        self._cache.clear_dirty()
        gc.collect()


class ContextOptimizer:
    """
    Main optimizer class that manages optimized contexts across phase executions.
    Implements advanced optimization strategies for Week 4.
    """

    def __init__(self):
        self._optimization_stats = {
            "contexts_optimized": 0,
            "total_copies_avoided": 0,
            "memory_saved_bytes": 0,
            "optimization_enabled": True,
        }
        self._context_pool = []  # Reusable context objects
        self._weak_refs = weakref.WeakSet()  # Track active contexts

    def optimize_context(self, context: DogmaContext) -> OptimizedDogmaContext:
        """Create optimized context wrapper."""
        if not self._optimization_stats["optimization_enabled"]:
            return context  # Return original if optimization disabled

        optimized = OptimizedDogmaContext.create_optimized(context)
        self._optimization_stats["contexts_optimized"] += 1
        self._weak_refs.add(optimized)

        return optimized

    def batch_optimize_contexts(
        self, contexts: list[DogmaContext]
    ) -> list[OptimizedDogmaContext]:
        """Optimize multiple contexts in batch for better efficiency."""
        if not contexts:
            return []

        return [self.optimize_context(ctx) for ctx in contexts]

    def enable_optimization(self, enabled: bool = True):
        """Enable or disable context optimization."""
        self._optimization_stats["optimization_enabled"] = enabled
        logger.info(f"Context optimization {'enabled' if enabled else 'disabled'}")

    def get_memory_usage_estimate(self) -> int:
        """Estimate memory usage of active optimized contexts."""
        active_contexts = len(self._weak_refs)
        # Rough estimate: each context ~1KB base + variables
        return active_contexts * 1024

    def force_cleanup(self):
        """Force cleanup of all cached data and trigger GC."""
        for ctx_ref in list(self._weak_refs):
            if hasattr(ctx_ref, "force_gc_cleanup"):
                ctx_ref.force_gc_cleanup()

        self._context_pool.clear()
        gc.collect()

        logger.debug("Context optimizer cleanup completed")

    def get_optimization_stats(self) -> dict[str, Any]:
        """Get comprehensive optimization statistics."""
        total_performance = {}
        context_count = 0

        for ctx_ref in self._weak_refs:
            if hasattr(ctx_ref, "get_performance_metrics"):
                metrics = ctx_ref.get_performance_metrics()
                context_count += 1
                for key, value in metrics.items():
                    if isinstance(value, (int, float)):
                        total_performance[key] = total_performance.get(key, 0) + value

        return {
            **self._optimization_stats,
            "active_contexts": context_count,
            "memory_usage_estimate_bytes": self.get_memory_usage_estimate(),
            "average_performance": {
                key: value / max(1, context_count)
                for key, value in total_performance.items()
            }
            if context_count > 0
            else {},
        }


# Global context optimizer instance
_context_optimizer = ContextOptimizer()


def get_context_optimizer() -> ContextOptimizer:
    """Get the global context optimizer instance."""
    return _context_optimizer


def optimize_context_for_phase(context: DogmaContext) -> OptimizedDogmaContext:
    """
    Optimize context for phase execution.
    This is the main entry point for phase optimization.
    """
    return _context_optimizer.optimize_context(context)


def cleanup_context_optimizations():
    """Cleanup all context optimizations and free memory."""
    _context_optimizer.force_cleanup()


def get_context_optimization_stats() -> dict[str, Any]:
    """Get current context optimization statistics."""
    return _context_optimizer.get_optimization_stats()
