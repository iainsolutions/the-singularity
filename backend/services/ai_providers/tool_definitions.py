"""Tool definitions for AI structured outputs using tool_use."""

# Tool for choosing a game action (draw, meld, dogma, achieve)
GAME_ACTION_TOOL = {
    "name": "choose_action",
    "description": """Choose a game action. PRIORITY: 1.Achieve 2.Dogma(S-tier) 3.Splay 4.Meld 5.Draw.
S-TIER DOGMAS: Tools(with 3+ hand cards)=free age3 meld, Machinery=opponent gives cards.
If dogma:Tools available AND hand>=3, USE IT - trades 3 age1 for 1 age3.
AVOID: Draw with hand>5, meld instead of S-tier dogma, same action 3x in row.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "REQUIRED. Explain: position, why this action beats alternatives, risks."
            },
            "action_type": {
                "type": "string",
                "description": "The full action string from available_actions (e.g., 'draw:1', 'meld:Pottery', 'dogma:Masonry', 'achieve:1')"
            },
            "note": {
                "type": "object",
                "description": "Optional note to remember for future turns. Use to record insights about cards, opponents, or strategic lessons.",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The note content (max 500 chars)"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["strategy", "opponent", "card_insight", "mistake", "observation"],
                        "description": "Category of the note"
                    },
                    "priority": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 3,
                        "description": "1=low, 2=medium, 3=high"
                    }
                },
                "required": ["content", "category"]
            }
        },
        "required": ["reasoning", "action_type"]
    }
}

# Tool for selecting cards in response to dogma interactions
SELECT_CARDS_TOOL = {
    "name": "select_cards",
    "description": "Select cards for a dogma interaction. Use when prompted to choose cards.",
    "input_schema": {
        "type": "object",
        "properties": {
            "selected_cards": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of card names to select"
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of the selection (optional)"
            }
        },
        "required": ["selected_cards"]
    }
}

# Tool for choosing an option from a list (e.g., color choice, yes/no)
CHOOSE_OPTION_TOOL = {
    "name": "choose_option",
    "description": "Choose from a list of options. Use when prompted to select an option.",
    "input_schema": {
        "type": "object",
        "properties": {
            "selected_option": {
                "type": "string",
                "description": "The option to select (must match one of the provided options exactly)"
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of the choice (optional)"
            }
        },
        "required": ["selected_option"]
    }
}

# Tool for selecting a player
SELECT_PLAYER_TOOL = {
    "name": "select_player",
    "description": "Select a player. Use when prompted to choose a player.",
    "input_schema": {
        "type": "object",
        "properties": {
            "selected_player": {
                "type": "string",
                "description": "The player ID or name to select"
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of the choice (optional)"
            }
        },
        "required": ["selected_player"]
    }
}

# Tool for writing notes (self-improving agent scaffolding)
WRITE_NOTE_TOOL = {
    "name": "write_note",
    "description": "Write a note to remember for future decisions. Use to record insights about cards, opponent patterns, or strategic lessons. Notes persist throughout the game.",
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The note content (max 500 chars). Be concise and specific."
            },
            "category": {
                "type": "string",
                "enum": ["strategy", "opponent", "card_insight", "mistake", "observation"],
                "description": "Category: 'mistake' for lessons learned, 'card_insight' for card interactions, 'opponent' for player patterns, 'strategy' for plans, 'observation' for general notes"
            },
            "priority": {
                "type": "integer",
                "minimum": 1,
                "maximum": 3,
                "description": "Importance: 1=low, 2=medium, 3=high (high priority notes are kept longer)"
            }
        },
        "required": ["content", "category"]
    }
}


def get_action_tools(include_notes: bool = True) -> list[dict]:
    """Get tools for choosing a game action."""
    tools = [GAME_ACTION_TOOL]
    if include_notes:
        tools.append(WRITE_NOTE_TOOL)
    return tools


def get_interaction_tools(interaction_type: str, include_notes: bool = True) -> list[dict]:
    """Get tools for responding to a dogma interaction based on type."""
    if "card" in interaction_type.lower() or "select" in interaction_type.lower():
        tools = [SELECT_CARDS_TOOL]
    elif "option" in interaction_type.lower() or "choose" in interaction_type.lower():
        tools = [CHOOSE_OPTION_TOOL]
    elif "player" in interaction_type.lower():
        tools = [SELECT_PLAYER_TOOL]
    else:
        # Default to card selection as most common
        tools = [SELECT_CARDS_TOOL]

    if include_notes:
        tools.append(WRITE_NOTE_TOOL)
    return tools


def get_tool_by_name(name: str) -> dict | None:
    """Get a tool definition by name."""
    tools = {
        "choose_action": GAME_ACTION_TOOL,
        "select_cards": SELECT_CARDS_TOOL,
        "choose_option": CHOOSE_OPTION_TOOL,
        "select_player": SELECT_PLAYER_TOOL,
        "write_note": WRITE_NOTE_TOOL,
    }
    return tools.get(name)
