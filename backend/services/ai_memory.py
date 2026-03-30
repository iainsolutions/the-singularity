"""
AI Memory System - Self-improving agent scaffolding.

Allows the AI to write and recall notes during a game, enabling:
- Learning from mistakes within a game
- Tracking opponent patterns
- Documenting card interaction insights
- Building strategic knowledge over time

Inspired by Anthropic's Catan AI approach.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from logging_config import get_logger

logger = get_logger(__name__)

# Maximum notes per game to prevent context bloat
MAX_NOTES_PER_GAME = 20
MAX_NOTE_LENGTH = 500


@dataclass
class AINote:
    """A single note written by the AI."""

    content: str
    category: str  # "strategy", "opponent", "card_insight", "mistake", "observation"
    turn_number: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    priority: int = 1  # 1-3, higher = more important

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "category": self.category,
            "turn_number": self.turn_number,
            "timestamp": self.timestamp,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AINote":
        return cls(
            content=data["content"],
            category=data["category"],
            turn_number=data["turn_number"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            priority=data.get("priority", 1),
        )


class AIMemoryStore:
    """
    Stores AI notes per game in Redis.

    Notes are stored as a JSON array under key: ai_memory:{game_id}:{player_id}
    """

    def __init__(self, redis_client: Any = None):
        self._redis = redis_client
        self._local_store: dict[str, list[AINote]] = {}  # Fallback for no Redis

    def _get_key(self, game_id: str, player_id: str) -> str:
        return f"ai_memory:{game_id}:{player_id}"

    async def add_note(
        self,
        game_id: str,
        player_id: str,
        content: str,
        category: str,
        turn_number: int,
        priority: int = 1,
    ) -> bool:
        """
        Add a note to the AI's memory.

        Returns True if note was added, False if limit reached.
        """
        # Validate and truncate
        content = content[:MAX_NOTE_LENGTH]
        if category not in ("strategy", "opponent", "card_insight", "mistake", "observation"):
            category = "observation"
        priority = max(1, min(3, priority))

        note = AINote(
            content=content,
            category=category,
            turn_number=turn_number,
            priority=priority,
        )

        key = self._get_key(game_id, player_id)

        if self._redis:
            try:
                # Get existing notes
                raw = await self._redis.get(key)
                notes = json.loads(raw) if raw else []

                # Check limit
                if len(notes) >= MAX_NOTES_PER_GAME:
                    # Remove lowest priority, oldest note
                    notes.sort(key=lambda n: (n.get("priority", 1), n.get("turn_number", 0)))
                    notes.pop(0)

                notes.append(note.to_dict())
                await self._redis.set(key, json.dumps(notes), ex=86400)  # 24h expiry
                logger.debug(f"AI note added: game={game_id}, category={category}")
                return True
            except Exception as e:
                logger.error(f"Failed to store AI note: {e}")
                return False
        else:
            # Local fallback
            try:
                if key not in self._local_store:
                    self._local_store[key] = []

                notes = self._local_store[key]
                if len(notes) >= MAX_NOTES_PER_GAME:
                    notes.sort(key=lambda n: (n.get("priority", 1), n.get("turn_number", 0)))
                    notes.pop(0)

                notes.append(note.to_dict())
                return True
            except Exception as e:
                logger.error(f"Failed to store AI note locally: {e}")
                return False

    async def get_notes(
        self,
        game_id: str,
        player_id: str,
        category: str | None = None,
        min_priority: int = 1,
    ) -> list[AINote]:
        """
        Get notes for an AI player.

        Args:
            game_id: Game ID
            player_id: AI player ID
            category: Optional category filter
            min_priority: Minimum priority (1-3)

        Returns:
            List of notes, sorted by turn number (newest first)
        """
        key = self._get_key(game_id, player_id)

        if self._redis:
            try:
                raw = await self._redis.get(key)
                if not raw:
                    return []
                notes_data = json.loads(raw)
                notes = [AINote.from_dict(n) for n in notes_data]
            except Exception as e:
                logger.error(f"Failed to retrieve AI notes: {e}")
                return []
        else:
            raw = self._local_store.get(key, [])
            notes = [AINote.from_dict(n) for n in raw]

        # Filter
        if category:
            notes = [n for n in notes if n.category == category]
        notes = [n for n in notes if n.priority >= min_priority]

        # Sort by turn (newest first)
        notes.sort(key=lambda n: n.turn_number, reverse=True)

        return notes

    async def clear_notes(self, game_id: str, player_id: str) -> None:
        """Clear all notes for a game/player."""
        key = self._get_key(game_id, player_id)

        if self._redis:
            try:
                await self._redis.delete(key)
            except Exception as e:
                logger.error(f"Failed to clear AI notes: {e}")
        else:
            self._local_store.pop(key, None)

    def format_notes_for_prompt(self, notes: list[AINote], max_chars: int = 2000) -> str:
        """
        Format notes for inclusion in AI prompt.

        Returns formatted string with notes grouped by category.
        """
        if not notes:
            return ""

        # Group by category
        by_category: dict[str, list[AINote]] = {}
        for note in notes:
            if note.category not in by_category:
                by_category[note.category] = []
            by_category[note.category].append(note)

        lines = ["<my_notes>"]

        # Priority order for categories
        category_order = ["mistake", "card_insight", "opponent", "strategy", "observation"]

        total_chars = 0
        for cat in category_order:
            if cat not in by_category:
                continue

            cat_notes = by_category[cat]
            cat_notes.sort(key=lambda n: (n.priority, n.turn_number), reverse=True)

            lines.append(f"  <{cat}>")
            for note in cat_notes[:5]:  # Max 5 per category
                note_line = f"    [T{note.turn_number}] {note.content}"
                if total_chars + len(note_line) > max_chars:
                    break
                lines.append(note_line)
                total_chars += len(note_line)
            lines.append(f"  </{cat}>")

            if total_chars >= max_chars:
                break

        lines.append("</my_notes>")
        return "\n".join(lines)


# Global instance
_memory_store: AIMemoryStore | None = None


def get_memory_store(redis_client: Any = None) -> AIMemoryStore:
    """Get or create the global memory store."""
    global _memory_store
    if _memory_store is None:
        _memory_store = AIMemoryStore(redis_client)
    elif redis_client and _memory_store._redis is None:
        _memory_store._redis = redis_client
    return _memory_store
