"""
State Change Tracker for comprehensive dogma action logging.

Tracks all game state changes during dogma execution with privacy-aware
narrative generation that respects hidden information rules.
"""

from dataclasses import dataclass
from enum import Enum


class Visibility(Enum):
    """Visibility levels for state changes"""

    PUBLIC = "public"  # Visible to all players
    OWNER_ONLY = "owner_only"  # Only visible to the player who owns the cards
    PRIVATE = "private"  # Not shown in logs (used for rollback data)


@dataclass
class StateChange:
    """Represents a single state change in the game"""

    change_type: str
    data: dict
    visibility: Visibility
    context: str = ""  # Additional context (e.g., "sharing", "demand", "effect")


class StateChangeTracker:
    """
    Tracks all state changes during dogma execution and generates
    privacy-aware narratives for the action log.
    """

    def __init__(self):
        self.changes: list[StateChange] = []
        self.player_id_map: dict[str, str] = {}  # player_name -> player_id

    def set_player_mapping(self, players: list):
        """Set mapping of player names to IDs for privacy filtering"""
        self.player_id_map = {p.name: p.id for p in players}

    def record_draw(
        self,
        player_name: str,
        card_name: str,
        age: int,
        revealed: bool = False,
        context: str = "draw",
    ):
        """Record a card draw"""
        self.changes.append(
            StateChange(
                change_type="draw",
                data={
                    "player": player_name,
                    "card": card_name,
                    "age": age,
                    "revealed": revealed,
                },
                visibility=Visibility.PUBLIC if revealed else Visibility.OWNER_ONLY,
                context=context,
            )
        )

    def record_transfer(
        self,
        card_name: str,
        from_player: str,
        to_player: str,
        from_location: str,
        to_location: str,
        context: str = "transfer",
    ):
        """Record a card transfer (always public)"""
        self.changes.append(
            StateChange(
                change_type="transfer",
                data={
                    "card": card_name,
                    "from_player": from_player,
                    "to_player": to_player,
                    "from_location": from_location,
                    "to_location": to_location,
                },
                visibility=Visibility.PUBLIC,
                context=context,
            )
        )

    def record_meld(
        self, player_name: str, card_name: str, color: str, context: str = "meld"
    ):
        """Record a card meld (always public)"""
        self.changes.append(
            StateChange(
                change_type="meld",
                data={"player": player_name, "card": card_name, "color": color},
                visibility=Visibility.PUBLIC,
                context=context,
            )
        )

    def record_score(self, player_name: str, card_name: str, context: str = "score"):
        """Record a card score (always public)"""
        self.changes.append(
            StateChange(
                change_type="score",
                data={"player": player_name, "card": card_name},
                visibility=Visibility.PUBLIC,
                context=context,
            )
        )

    def record_tuck(
        self, player_name: str, card_name: str, color: str, context: str = "tuck"
    ):
        """Record a card tuck (always public)"""
        self.changes.append(
            StateChange(
                change_type="tuck",
                data={"player": player_name, "card": card_name, "color": color},
                visibility=Visibility.PUBLIC,
                context=context,
            )
        )

    def record_symbol_check(
        self,
        player_name: str,
        symbol: str,
        count: int,
        context: str = "check",
        meets_requirement: bool | None = None,
        required_count: int | None = None,
    ):
        """Record a symbol count check (always public)"""
        # CRITICAL FIX: Convert Symbol enum to string if needed
        # Symbol enum objects print as "Symbol.ALGORITHM" instead of "algorithm"
        # Symbol inherits from (str, Enum) so we can get the value directly
        if hasattr(symbol, "value"):
            symbol_str = symbol.value
        else:
            symbol_str = str(symbol).lower()

        self.changes.append(
            StateChange(
                change_type="symbol_check",
                data={
                    "player": player_name,
                    "symbol": symbol_str,  # Store as string, not enum
                    "count": count,
                    "meets_requirement": meets_requirement,
                    "required_count": required_count,
                },
                visibility=Visibility.PUBLIC,
                context=context,
            )
        )

    def record_hand_check(
        self, player_name: str, symbol: str, has_cards: bool, context: str = "check"
    ):
        """Record a hand check (public boolean result only, not specifics)"""
        self.changes.append(
            StateChange(
                change_type="hand_check",
                data={"player": player_name, "symbol": symbol, "has_cards": has_cards},
                visibility=Visibility.PUBLIC,
                context=context,
            )
        )

    def record_splay(
        self, player_name: str, color: str, direction: str, context: str = "splay"
    ):
        """Record a splay operation (always public)"""
        self.changes.append(
            StateChange(
                change_type="splay",
                data={"player": player_name, "color": color, "direction": direction},
                visibility=Visibility.PUBLIC,
                context=context,
            )
        )

    def record_return_to_deck(
        self,
        player_name: str,
        card_name: str,
        age: int,
        position: str = "bottom",
        context: str = "return",
    ):
        """Record returning a card to deck"""
        self.changes.append(
            StateChange(
                change_type="return",
                data={
                    "player": player_name,
                    "card": card_name,
                    "age": age,
                    "position": position,
                },
                visibility=Visibility.PUBLIC,
                context=context,
            )
        )

    def get_changes_for_effect(self, effect_context: str) -> list[StateChange]:
        """
        Get all state changes for a specific effect context.

        This is a performance optimization to avoid iterating through all state
        changes when we only care about a specific effect. In long games, the
        changes list can grow quite large.

        Args:
            effect_context: The effect context to filter by (e.g., "effect_1", "effect_2")

        Returns:
            List of StateChange objects that match the given effect context
        """
        return [c for c in self.changes if c.context == effect_context]

    def generate_narrative(
        self, viewing_player_id: str | None = None, group_by_context: bool = True
    ) -> str:
        """
        Generate human-readable narrative respecting visibility rules.

        Args:
            viewing_player_id: ID of player viewing the log (for privacy filtering)
            group_by_context: Whether to group changes by context

        Returns:
            Multi-line narrative string
        """
        if not self.changes:
            return ""

        if group_by_context:
            return self._generate_grouped_narrative(viewing_player_id)
        else:
            return self._generate_linear_narrative(viewing_player_id)

    def _generate_linear_narrative(self, viewing_player_id: str | None) -> str:
        """Generate narrative in chronological order"""
        lines = []

        for change in self.changes:
            line = self._format_change(change, viewing_player_id)
            if line:
                lines.append(f"• {line}")

        return "\n".join(lines)

    def _generate_grouped_narrative(self, viewing_player_id: str | None) -> str:
        """Generate narrative grouped by context with descriptive headers"""
        # Group changes by context
        grouped = {}
        for change in self.changes:
            ctx = change.context or "other"
            if ctx not in grouped:
                grouped[ctx] = []
            grouped[ctx].append(change)

        sections = []

        # Generate sections with descriptive headers
        # Process all contexts found, not just predefined ones
        contexts_found = list(grouped.keys())

        # Sort contexts logically (effects first, then special contexts)
        def context_sort_key(ctx):
            if ctx.startswith("effect_"):
                return (0, int(ctx.split("_")[1]))
            elif ctx == "demand_fallback":
                return (1, 0)
            elif ctx == "sharing_bonus":
                return (2, 0)
            elif ctx == "sharing_active":
                return (3, 0)
            elif ctx == "sharing_opponent":
                return (4, 0)
            else:
                return (5, 0)

        contexts_found.sort(key=context_sort_key)

        for ctx in contexts_found:
            section_lines = []
            for change in grouped[ctx]:
                line = self._format_change(change, viewing_player_id)
                if line:
                    section_lines.append(f"• {line}")

            if section_lines:
                # Add descriptive header
                header = self._get_context_header(ctx)
                if header:
                    sections.append(f"{header}:\n" + "\n".join(section_lines))
                else:
                    sections.append("\n".join(section_lines))

        return "\n\n".join(sections)

    def _get_context_header(self, context: str) -> str | None:
        """Get descriptive header for a context"""
        if context.startswith("effect_"):
            effect_num = context.split("_")[1]
            return f"Effect {effect_num}"
        elif context == "demand_fallback":
            return "Demand Fallback"
        elif context == "sharing_bonus":
            return "Sharing Bonus"
        elif context == "sharing_active":
            return "Sharing Check (Active Player)"
        elif context == "sharing_opponent":
            return "Sharing Check (Opponents)"
        else:
            # No header for generic contexts
            return None

    def _format_change(
        self, change: StateChange, viewing_player_id: str | None
    ) -> str | None:
        """Format a single change into a readable line"""
        data = change.data

        # Check visibility - CRITICAL FIX for Bug #3 (privacy)
        if change.visibility == Visibility.OWNER_ONLY:
            player_name = data.get("player", "")
            player_id = self.player_id_map.get(player_name) if player_name else None
            # viewing_player_id=None means "public view" - hide private details
            # viewing_player_id=<id> means "player-specific view" - show if owner matches
            is_owner = viewing_player_id is not None and player_id == viewing_player_id
            if not is_owner:
                # Hide details from non-owners and public view
                if change.change_type == "draw":
                    return f"{data['player']} researched an era {data['age']} card"
                return None  # Skip other owner-only changes

        # Format based on type
        if change.change_type == "draw":
            if data["revealed"]:
                return f"{data['player']} researches and reveals {data['card']} (era {data['age']})"
            else:
                # Owner can see full details
                return f"{data['player']} researches {data['card']} (era {data['age']})"

        elif change.change_type == "transfer":
            # Handle non-player locations (achievements, junk_pile, etc.)
            from_loc = data['from_location']
            to_loc = data['to_location']

            # Format source - some locations are global, not player-owned
            if from_loc in ("achievements", "junk_pile", "junk", "deck"):
                from_str = f"the {from_loc.replace('_', ' ')}"
            else:
                from_str = f"{data['from_player']}'s {from_loc}"

            # Format destination - some locations are global, not player-owned
            if to_loc in ("achievements", "junk_pile", "junk", "deck"):
                to_str = f"the {to_loc.replace('_', ' ')}"
            else:
                to_str = f"{data['to_player']}'s {to_loc}"

            return f"{data['card']} transferred from {from_str} to {to_str}"

        elif change.change_type == "meld":
            return f"{data['player']} deploys {data['card']} to {data['color']} stack"

        elif change.change_type == "score":
            return f"{data['player']} harvests {data['card']}"

        elif change.change_type == "tuck":
            return f"{data['player']} archives {data['card']} under {data['color']} stack"

        elif change.change_type == "symbol_check":
            line = f"{data['player']} has {data['count']} {data['symbol']}"
            if data.get("required_count") is not None:
                meets_requirement = data.get("meets_requirement")
                required_count = data["required_count"]

                # Different messages for demands vs sharing
                context = change.context.lower()
                is_demand = "demand" in context
                is_sharing = "sharing" in context

                if is_demand:
                    if meets_requirement:
                        line += f" (meets requirement of {required_count})"
                    else:
                        line += " (is vulnerable to the demand)"
                elif is_sharing:
                    if meets_requirement:
                        line += " (shares in the dogma)"
                    else:
                        line += " (does not share in the dogma)"
                else:
                    # Generic formatting for other contexts
                    meets = "meets" if meets_requirement else "does not meet"
                    line += f" ({meets} requirement of {required_count})"
            return line

        elif change.change_type == "hand_check":
            has_cards = "has" if data["has_cards"] else "does not have"
            return f"{data['player']} {has_cards} cards with {data['symbol']} in hand"

        elif change.change_type == "splay":
            return f"{data['player']} proliferates {data['color']} stack {data['direction']}"

        elif change.change_type == "return":
            return f"{data['player']} recalls {data['card']} to {data['position']} of era {data['age']} supply"

        return None

    def get_changes_as_dict(self) -> list[dict]:
        """Export changes as dictionaries for serialization"""
        return [
            {
                "change_type": c.change_type,
                "data": c.data,
                "visibility": c.visibility.value,
                "context": c.context,
            }
            for c in self.changes
        ]

    @classmethod
    def from_dict_list(cls, changes_data: list[dict]) -> "StateChangeTracker":
        """Reconstruct tracker from serialized data"""
        import logging

        logger = logging.getLogger(__name__)

        tracker = cls()
        if not changes_data:
            logger.debug("DESERIALIZE: Empty changes_data, returning empty tracker")
            return tracker

        logger.debug(f"DESERIALIZE: Processing {len(changes_data)} entries")

        for i, change_data in enumerate(changes_data):
            # Skip malformed entries - be very defensive
            try:
                logger.debug(
                    f"DESERIALIZE: Entry {i}: type={type(change_data)}, keys={list(change_data.keys()) if isinstance(change_data, dict) else 'N/A'}"
                )

                if not isinstance(change_data, dict):
                    logger.warning(f"DESERIALIZE: Entry {i} is not a dict, skipping")
                    continue
                if "change_type" not in change_data or "data" not in change_data:
                    logger.warning(
                        f"DESERIALIZE: Entry {i} missing required fields. Has: {list(change_data.keys())}"
                    )
                    continue
                if not isinstance(change_data["data"], dict):
                    logger.warning(
                        f"DESERIALIZE: Entry {i} has non-dict data: {type(change_data['data'])}"
                    )
                    continue

                tracker.changes.append(
                    StateChange(
                        change_type=change_data["change_type"],
                        data=change_data["data"],
                        visibility=Visibility(change_data.get("visibility", "public")),
                        context=change_data.get("context", ""),
                    )
                )
                logger.debug(
                    f"DESERIALIZE: Entry {i} successfully reconstructed as {change_data['change_type']}"
                )
            except Exception as e:
                # Silently skip any entries that fail to reconstruct
                logger.warning(
                    f"DESERIALIZE: Entry {i} failed to reconstruct: {e}", exc_info=True
                )
                continue

        logger.debug(
            f"DESERIALIZE: Reconstructed tracker with {len(tracker.changes)} changes from {len(changes_data)} input entries"
        )
        return tracker
