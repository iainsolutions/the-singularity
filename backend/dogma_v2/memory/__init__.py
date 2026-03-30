"""
Memory management optimization system.
Provides object pooling and memory-efficient data structures.
"""

from .object_pool import CompactGameState, ObjectPool

__all__ = ["CompactGameState", "ObjectPool"]
