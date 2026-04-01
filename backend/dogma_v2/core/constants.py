"""
Shared constants for the dogma execution engine.
"""

# Variables that persist across player transitions during dogma execution.
# Everything NOT in this set gets cleared when switching from one player
# to the next during sharing, preventing variable leaking.
SYSTEM_CONTEXT_VARS = frozenset({
    # Execution tracking
    "phase_sequence",
    "start_timestamp",
    "card_name",
    "activating_player_id",
    "game_id",

    # Sharing/demand state
    "sharing_players_count",
    "vulnerable_player_ids",
    "demanding_player",
    "in_sharing_phase",
    "in_execution_phase",
    "is_sharing_execution",

    # Effect tracking
    "effects",
    "effect_metadata",
    "effects_count",
    "current_effect_index",
    "current_effect_context",

    # Resume state
    "resumed_action_index",
    "current_player_in_effect",

    # Internal tracking
    "_last_executing_player_id",
    "_last_responding_player_id",
    "_demand_transfer_count_accumulator",
})
