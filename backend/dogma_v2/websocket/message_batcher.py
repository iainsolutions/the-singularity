"""
WebSocket message optimization system.

This module provides:
- Message batching to reduce WebSocket message count
- Differential state updates to minimize payload size
- Client state reconciliation for reliability
- Message compression for large state updates
"""

import asyncio
import copy
import json
import logging
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types"""

    GAME_STATE_UPDATE = "game_state_updated"
    PLAYER_ACTION = "player_action"
    DOGMA_INTERACTION = "dogma_interaction"
    BATCH = "batch"
    STATE_DIFF = "state_diff"


@dataclass
class QueuedMessage:
    """Message queued for batching"""

    client_id: str
    message: dict[str, Any]
    timestamp: float
    message_type: MessageType
    priority: int = 0  # Higher priority sends first

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return self.message


@dataclass
class StateDiff:
    """Differential state update"""

    added: dict[str, Any]
    modified: dict[str, Any]
    removed: list[str]
    metadata: dict[str, Any]

    def is_empty(self) -> bool:
        """Check if diff contains no changes"""
        return not (self.added or self.modified or self.removed)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class StateDiffCalculator:
    """Calculate differential state updates to minimize payload size"""

    def __init__(self):
        self._client_states: dict[str, dict[str, Any]] = {}

    def calculate_diff(self, client_id: str, new_state: dict[str, Any]) -> StateDiff:
        """
        Calculate state difference for client.

        Args:
            client_id: Client identifier
            new_state: New state to compare

        Returns:
            StateDiff with only the changes
        """
        previous_state = self._client_states.get(client_id, {})

        diff = StateDiff(
            added={},
            modified={},
            removed=[],
            metadata={
                "timestamp": time.time(),
                "client_id": client_id,
                "state_version": new_state.get("version", 0),
            },
        )

        # Find added and modified keys
        for key, new_value in new_state.items():
            if key not in previous_state:
                diff.added[key] = new_value
            elif previous_state[key] != new_value:
                # For nested objects, try to calculate nested diff
                if isinstance(new_value, dict) and isinstance(
                    previous_state[key], dict
                ):
                    nested_diff = self._calculate_nested_diff(
                        previous_state[key], new_value
                    )
                    if nested_diff:
                        diff.modified[key] = nested_diff
                else:
                    diff.modified[key] = new_value

        # Find removed keys
        for key in previous_state:
            if key not in new_state:
                diff.removed.append(key)

        # Update client state cache
        self._client_states[client_id] = copy.deepcopy(new_state)

        return diff

    def _calculate_nested_diff(
        self, old_dict: dict[str, Any], new_dict: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Calculate diff for nested dictionary"""
        nested_diff = {}
        has_changes = False

        for key, new_value in new_dict.items():
            if key not in old_dict or old_dict[key] != new_value:
                nested_diff[key] = new_value
                has_changes = True

        return nested_diff if has_changes else None

    def apply_diff_to_client(
        self, client_state: dict[str, Any], diff: StateDiff
    ) -> dict[str, Any]:
        """Apply differential update to client state"""
        updated_state = copy.deepcopy(client_state)

        # Apply additions
        for key, value in diff.added.items():
            updated_state[key] = value

        # Apply modifications
        for key, value in diff.modified.items():
            if isinstance(value, dict) and isinstance(updated_state.get(key), dict):
                # Merge nested changes
                updated_state[key].update(value)
            else:
                updated_state[key] = value

        # Apply removals
        for key in diff.removed:
            updated_state.pop(key, None)

        return updated_state

    def get_client_state(self, client_id: str) -> dict[str, Any]:
        """Get cached client state"""
        return self._client_states.get(client_id, {})

    def reset_client_state(self, client_id: str):
        """Reset client state (on reconnection)"""
        self._client_states.pop(client_id, None)


class MessageBatcher:
    """
    Batch WebSocket messages to reduce frequency and optimize payload size.

    Features:
    - Configurable batch window
    - Message prioritization
    - Compatible message merging
    - Automatic state diffing
    """

    def __init__(
        self,
        batch_window_ms: int = 50,
        max_batch_size: int = 100,
        enable_compression: bool = True,
    ):
        """
        Initialize message batcher.

        Args:
            batch_window_ms: Time window to collect messages (milliseconds)
            max_batch_size: Maximum messages per batch
            enable_compression: Enable message compression for large payloads
        """
        self.batch_window = batch_window_ms / 1000.0  # Convert to seconds
        self.max_batch_size = max_batch_size
        self.enable_compression = enable_compression

        # Message queues per client
        self._pending_messages: dict[str, deque] = defaultdict(deque)
        self._batch_timers: dict[str, asyncio.Handle | None] = {}

        # State management
        self.diff_calculator = StateDiffCalculator()

        # Statistics
        self._stats = {
            "messages_queued": 0,
            "messages_sent": 0,
            "batches_sent": 0,
            "compression_ratio": 0.0,
            "avg_batch_size": 0.0,
        }

        # WebSocket send callback (set by integration)
        self._websocket_send_callback: Callable | None = None

        logger.info(f"MessageBatcher initialized with {batch_window_ms}ms window")

    def set_websocket_callback(self, send_callback: Callable):
        """Set callback for sending WebSocket messages"""
        self._websocket_send_callback = send_callback

    def queue_message(self, client_id: str, message: dict[str, Any], priority: int = 0):
        """
        Queue message for batching.

        Args:
            client_id: Client identifier
            message: Message to send
            priority: Message priority (higher = send first)
        """
        message_type = MessageType(message.get("type", "unknown"))

        queued_msg = QueuedMessage(
            client_id=client_id,
            message=message,
            timestamp=time.time(),
            message_type=message_type,
            priority=priority,
        )

        self._pending_messages[client_id].append(queued_msg)
        self._stats["messages_queued"] += 1

        # Schedule batch send if not already scheduled
        if not self._batch_timers.get(client_id):
            self._schedule_batch_send(client_id)

        # Send immediately if batch size reached
        if len(self._pending_messages[client_id]) >= self.max_batch_size:
            asyncio.create_task(self._send_batched_messages(client_id))

    def queue_state_update(self, client_id: str, game_state: dict[str, Any]):
        """
        Queue state update with differential optimization.

        Args:
            client_id: Client identifier
            game_state: Full game state
        """
        # Calculate state diff to minimize payload
        diff = self.diff_calculator.calculate_diff(client_id, game_state)

        if diff.is_empty():
            logger.debug(f"No state changes for client {client_id}, skipping update")
            return

        # Create optimized state update message
        message = {
            "type": MessageType.STATE_DIFF,
            "diff": diff.to_dict(),
            "timestamp": time.time(),
        }

        self.queue_message(
            client_id, message, priority=1
        )  # State updates have priority

    def _schedule_batch_send(self, client_id: str):
        """Schedule batch send after window expires"""
        if self._batch_timers.get(client_id):
            return  # Already scheduled

        def send_batch():
            self._batch_timers[client_id] = None
            asyncio.create_task(self._send_batched_messages(client_id))

        loop = asyncio.get_event_loop()
        self._batch_timers[client_id] = loop.call_later(self.batch_window, send_batch)

    async def _send_batched_messages(self, client_id: str):
        """Send batched messages for client"""
        if not self._pending_messages[client_id]:
            return

        # Cancel any pending timer
        if self._batch_timers.get(client_id):
            self._batch_timers[client_id].cancel()
            self._batch_timers[client_id] = None

        # Get all pending messages
        messages = list(self._pending_messages[client_id])
        self._pending_messages[client_id].clear()

        if not messages:
            return

        # Sort by priority (highest first)
        messages.sort(key=lambda x: x.priority, reverse=True)

        # Try to merge compatible messages
        merged_messages = self._merge_compatible_messages(messages)

        # Create batch message
        if len(merged_messages) == 1:
            # Send single message directly
            batch_message = merged_messages[0].to_dict()
        else:
            # Send as batch
            batch_message = {
                "type": MessageType.BATCH,
                "messages": [msg.to_dict() for msg in merged_messages],
                "batch_size": len(merged_messages),
                "timestamp": time.time(),
            }

        # Apply compression if enabled and beneficial
        if self.enable_compression:
            batch_message = self._apply_compression(batch_message)

        # Send via WebSocket
        if self._websocket_send_callback:
            try:
                await self._websocket_send_callback(client_id, batch_message)
                self._update_send_statistics(len(messages), 1)
                logger.debug(f"Sent batch of {len(messages)} messages to {client_id}")
            except Exception as e:
                logger.error(f"Failed to send batch to {client_id}: {e}")
        else:
            logger.warning("No WebSocket callback set - messages dropped")

    def _merge_compatible_messages(
        self, messages: list[QueuedMessage]
    ) -> list[QueuedMessage]:
        """Merge compatible messages to reduce batch size"""
        if len(messages) <= 1:
            return messages

        merged = []
        game_state_updates = []

        for message in messages:
            if message.message_type == MessageType.GAME_STATE_UPDATE:
                game_state_updates.append(message)
            elif message.message_type == MessageType.STATE_DIFF:
                # Merge multiple state diffs (keep latest only)
                if not any(
                    msg.message_type == MessageType.STATE_DIFF for msg in merged
                ):
                    merged.append(message)
                else:
                    # Replace existing state diff with latest
                    for i, msg in enumerate(merged):
                        if msg.message_type == MessageType.STATE_DIFF:
                            merged[i] = message
                            break
            else:
                # Don't merge other message types
                merged.append(message)

        # For game state updates, keep only the latest
        if game_state_updates:
            merged.append(game_state_updates[-1])

        return merged

    def _apply_compression(self, message: dict[str, Any]) -> dict[str, Any]:
        """Apply compression if message size exceeds threshold"""
        try:
            message_json = json.dumps(message)
            original_size = len(message_json.encode("utf-8"))

            # Only compress if message is large enough to benefit
            if original_size > 1024:  # 1KB threshold
                import gzip

                compressed_data = gzip.compress(message_json.encode("utf-8"))

                if len(compressed_data) < original_size * 0.8:  # 20% savings minimum
                    compression_ratio = len(compressed_data) / original_size
                    self._stats["compression_ratio"] = (
                        self._stats["compression_ratio"] + compression_ratio
                    ) / 2

                    return {
                        "type": "compressed",
                        "original_type": message.get("type"),
                        "compressed_data": compressed_data.hex(),
                        "original_size": original_size,
                        "compressed_size": len(compressed_data),
                    }

        except Exception as e:
            logger.warning(f"Compression failed: {e}")

        return message

    def _update_send_statistics(self, messages_count: int, batches_count: int):
        """Update sending statistics"""
        self._stats["messages_sent"] += messages_count
        self._stats["batches_sent"] += batches_count
        self._stats["avg_batch_size"] = self._stats["messages_sent"] / max(
            self._stats["batches_sent"], 1
        )

    def get_statistics(self) -> dict[str, Any]:
        """Get batching statistics"""
        pending_count = sum(len(queue) for queue in self._pending_messages.values())

        return {
            **self._stats,
            "pending_messages": pending_count,
            "active_clients": len(self._pending_messages),
            "batch_efficiency": self._calculate_batch_efficiency(),
            "active_timers": sum(1 for timer in self._batch_timers.values() if timer),
        }

    def _calculate_batch_efficiency(self) -> float:
        """Calculate batching efficiency (messages per batch)"""
        if self._stats["batches_sent"] == 0:
            return 0.0
        return self._stats["messages_sent"] / self._stats["batches_sent"]

    async def flush_client_messages(self, client_id: str):
        """Force send all pending messages for client"""
        if self._pending_messages.get(client_id):
            await self._send_batched_messages(client_id)

    async def flush_all_messages(self):
        """Force send all pending messages for all clients"""
        for client_id in list(self._pending_messages.keys()):
            if self._pending_messages[client_id]:
                await self._send_batched_messages(client_id)

    def reset_client(self, client_id: str):
        """Reset client state (on disconnection)"""
        # Clear pending messages
        self._pending_messages[client_id].clear()

        # Cancel batch timer
        if self._batch_timers.get(client_id):
            self._batch_timers[client_id].cancel()
            self._batch_timers[client_id] = None

        # Reset state diff calculator
        self.diff_calculator.reset_client_state(client_id)

        logger.debug(f"Reset message batcher for client {client_id}")


# Global message batcher instance
_message_batcher: MessageBatcher | None = None


def get_message_batcher() -> MessageBatcher:
    """Get global message batcher instance"""
    global _message_batcher
    if _message_batcher is None:
        _message_batcher = MessageBatcher()
    return _message_batcher


def set_websocket_callback(send_callback: Callable):
    """Set WebSocket send callback for global batcher"""
    batcher = get_message_batcher()
    batcher.set_websocket_callback(send_callback)
