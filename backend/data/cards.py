from __future__ import annotations

import json
import logging
from pathlib import Path

from models.card import Card, CardColor, DogmaEffect, Symbol


CARDS_PATH = Path(__file__).with_name("SingularityCards.json")

SYMBOL_MAP = {
    "circuit": Symbol.CIRCUIT,
    "neural_net": Symbol.NEURAL_NET,
    "data": Symbol.DATA,
    "algorithm": Symbol.ALGORITHM,
    "human_mind": Symbol.HUMAN_MIND,
    "robot": Symbol.ROBOT,
}

COLOR_MAP = {
    "red": CardColor.RED,
    "yellow": CardColor.YELLOW,
    "green": CardColor.GREEN,
    "blue": CardColor.BLUE,
    "purple": CardColor.PURPLE,
}


logger = logging.getLogger(__name__)


def load_cards_from_json() -> list[Card]:
    """Load cards from SingularityCards.json."""
    try:
        with open(CARDS_PATH) as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Card file not found: {CARDS_PATH}")
        return []
    except json.JSONDecodeError as e:
        msg = f"Failed to parse {CARDS_PATH.name} at line {e.lineno}, col {e.colno}: {e.msg}"
        logger.error(msg)
        raise RuntimeError(msg) from e

    card_data_list = data.get("cards", [])
    cards: list[Card] = []

    for card_data in card_data_list:
        # symbols array is the 4-position layout [top_left, bottom_left, bottom_right, top_right]
        raw_positions = card_data.get("symbols", [None, None, None, None])

        # Build symbol_positions (with nulls preserved) and symbols (non-null only)
        symbol_positions = []
        symbols = []
        for pos in raw_positions:
            if pos and pos in SYMBOL_MAP:
                sym = SYMBOL_MAP[pos]
                symbol_positions.append(sym)
                symbols.append(sym)
            else:
                symbol_positions.append(None)

        # Read dogma_resource directly from JSON
        dogma_resource = SYMBOL_MAP.get(card_data.get("dogma_resource")) if card_data.get("dogma_resource") else None

        # Parse dogma effects
        dogma_effects = []
        for effect_data in card_data.get("dogma_effects", []):
            dogma_effects.append(
                DogmaEffect(
                    text=effect_data.get("description") or effect_data.get("text") or "",
                    symbol_count=effect_data.get("symbol_count", 1),
                    is_demand=effect_data.get("is_demand", False),
                    is_optional=False,
                    actions=effect_data.get("actions", []),
                    selection_condition=effect_data.get("selection_condition"),
                )
            )

        color = COLOR_MAP.get(card_data.get("color", "red"), CardColor.RED)

        card = Card(
            name=card_data.get("name", ""),
            age=card_data.get("age", 1),
            color=color,
            card_id=card_data.get("card_id") or card_data.get("id"),
            symbols=symbols,
            symbol_positions=symbol_positions,
            dogma_resource=dogma_resource,
            dogma_effects=dogma_effects,
        )
        cards.append(card)

    logger.info(f"Loaded {len(cards)} cards from {CARDS_PATH.name}")
    return cards


def load_achievement_cards_from_json() -> tuple[list[Card], list[Card]]:
    """Load achievement cards from SingularityCards.json top-level data.

    Returns:
        Tuple of (standard_achievements, special_achievements)
    """
    standard_achievements: list[Card] = []
    special_achievements: list[Card] = []

    # Try to load from JSON metadata
    try:
        with open(CARDS_PATH) as f:
            data = json.load(f)
    except Exception:
        data = {}

    # Standard era achievements
    standard = data.get("standard_achievements", [])
    if standard:
        for ach in standard:
            standard_achievements.append(
                Card(
                    name=ach["name"],
                    age=ach["era"],
                    color=CardColor.PURPLE,
                    symbols=[],
                    dogma_effects=[],
                    is_achievement=True,
                    achievement_requirement=f"Requires {ach['score_required']} points and a top card of era {ach['era']} or higher",
                )
            )
    else:
        names = [
            "First Computation", "Turing Complete", "Logical Reasoning",
            "Expert Knowledge", "Pattern Recognition", "Deep Understanding",
            "Foundation", "General Intelligence", "Convergence",
        ]
        for age, name in enumerate(names, 1):
            standard_achievements.append(
                Card(
                    name=name, age=age, color=CardColor.PURPLE,
                    symbols=[], dogma_effects=[], is_achievement=True,
                    achievement_requirement=f"Requires {age * 5} points and a top card of era {age} or higher",
                )
            )

    # Special achievements
    special = data.get("special_achievements", [])
    if special:
        for ach in special:
            special_achievements.append(
                Card(
                    name=ach["name"], age=1, color=CardColor.PURPLE,
                    card_id=ach.get("id"), symbols=[], dogma_effects=[],
                    is_achievement=True,
                    achievement_requirement=ach.get("trigger", ach.get("description", "")),
                )
            )
    else:
        for name, req in [
            ("Emergence", "Archive 6+ OR Harvest 6+ in a single turn"),
            ("Dominion", "3+ of every icon type visible on board"),
            ("Consciousness", "12+ visible Human Mind icons on board"),
            ("Apotheosis", "All 5 colors, each Proliferated right/up/aslant"),
            ("Transcendence", "All 5 colors, each top card Era 8+"),
            ("Abundance", "5+ Harvest cards from different eras"),
        ]:
            special_achievements.append(
                Card(
                    name=name, age=1, color=CardColor.PURPLE,
                    symbols=[], dogma_effects=[], is_achievement=True,
                    achievement_requirement=req,
                )
            )

    return standard_achievements, special_achievements


def get_all_cards() -> list[Card]:
    return load_cards_from_json()


def get_achievement_cards() -> tuple[list[Card], list[Card]]:
    return load_achievement_cards_from_json()
