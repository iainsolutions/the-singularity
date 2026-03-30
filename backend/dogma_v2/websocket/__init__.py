"""
WebSocket message optimization system.
Provides message batching, differential updates, and state synchronization.
"""

from .message_batcher import MessageBatcher, StateDiffCalculator

__all__ = ["MessageBatcher", "StateDiffCalculator"]
