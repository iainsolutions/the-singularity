from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from models.card import Card, CardColor, DogmaEffect, Symbol


BASE_CARDS_PATH = Path(__file__).with_name("BaseCards.json")
FIGURES_CARDS_PATH = Path(__file__).with_name("FiguresCards.json")

# Feature flag for Figures expansion (default: False for safety)
FIGURES_EXPANSION_ENABLED = os.getenv("FIGURES_EXPANSION_ENABLED", "false").lower() in (
    "true",
    "1",
    "yes",
)

# Expansion card paths (feature-flagged)
EXPANSION_PATHS = {
    "artifacts": Path(__file__).with_name("ArtifactsCards.json"),
    "cities": Path(__file__).with_name("CitiesCards.json"),
    "echoes": Path(__file__).with_name("EchoesCards.json"),
    "unseen": Path(__file__).with_name("UnseenCards.json"),
}

SYMBOL_MAP = {
    "castle": Symbol.CASTLE,
    "leaf": Symbol.LEAF,
    "lightbulb": Symbol.LIGHTBULB,
    "crown": Symbol.CROWN,
    "factory": Symbol.FACTORY,
    "clock": Symbol.CLOCK,
    # Hex symbols from Figures expansion
    # Note: These are stored as strings in JSON but treated as regular symbols in game logic
    # The hex- prefix is stripped when converting to Symbol enums
    "hex-fist": Symbol.CASTLE,  # Placeholder mapping - update when Figures expansion is implemented
    "hex-elephant": Symbol.CASTLE,
    "hex-book": Symbol.LIGHTBULB,
    "hex-scroll": Symbol.LIGHTBULB,
    "hex-papyrus": Symbol.LIGHTBULB,
    "hex-clay-tablet": Symbol.LIGHTBULB,
    "hex-manuscript": Symbol.LIGHTBULB,
    "hex-quill": Symbol.LIGHTBULB,
    "hex-brush": Symbol.LIGHTBULB,
    "hex-scroll-brush": Symbol.LIGHTBULB,
    "hex-cog": Symbol.FACTORY,
    "hex-gear": Symbol.FACTORY,
    "hex-gears": Symbol.FACTORY,
    "hex-clockwork": Symbol.CLOCK,
    "hex-compass": Symbol.CLOCK,
    "hex-compass-rose": Symbol.CLOCK,
    "hex-astrolabe": Symbol.CLOCK,
    "hex-telescope": Symbol.CLOCK,
    "hex-globe": Symbol.CLOCK,
    "hex-lens": Symbol.CLOCK,
    "hex-polyhedron": Symbol.CLOCK,
    "hex-sphere": Symbol.CLOCK,
    "hex-laurel": Symbol.CROWN,
    "hex-laurel-wreath": Symbol.CROWN,
    "hex-helmet": Symbol.CROWN,
    "hex-david": Symbol.CROWN,
    "hex-flag": Symbol.CROWN,
    "hex-swords": Symbol.CROWN,
    "hex-swords-crossed": Symbol.CROWN,
    "hex-grain": Symbol.LEAF,
    "hex-tree": Symbol.LEAF,
    "hex-lotus": Symbol.LEAF,
    "hex-water": Symbol.LEAF,
    "hex-drop": Symbol.LEAF,
    "hex-mortar": Symbol.LEAF,
    "hex-horse": Symbol.CASTLE,
    "hex-turtle-ship": Symbol.CASTLE,
    "hex-dragon": Symbol.CASTLE,
    "hex-pyramid": Symbol.CASTLE,
    "hex-obelisk": Symbol.CASTLE,
    "hex-arrow": Symbol.CASTLE,
    "hex-skull": Symbol.CASTLE,
    "hex-vitruvian": Symbol.CASTLE,
    "hex-wings": Symbol.CASTLE,
    "hex-constellation": Symbol.CLOCK,
    "hex-crescent": Symbol.CROWN,
    "hex-ellipse": Symbol.CLOCK,
    "hex-fan": Symbol.LEAF,
    "hex-hangul": Symbol.LIGHTBULB,
    "hex-mouth": Symbol.CROWN,
}

COLOR_MAP = {
    "red": CardColor.RED,
    "yellow": CardColor.YELLOW,
    "green": CardColor.GREEN,
    "blue": CardColor.BLUE,
    "purple": CardColor.PURPLE,
}


logger = logging.getLogger(__name__)


def _load_cards_from_file(file_path: Path) -> tuple[list[dict], str | None]:
    """Load card data from a JSON file.

    Supports two formats:
    - {"cards": [...]} (BaseCards.json format)
    - {"expansion": "name", "cards": [...]} (expansion format with top-level expansion field)
    - [...] (CitiesCards.json format)

    Args:
        file_path: Path to the JSON file

    Returns:
        Tuple of (card dictionaries, expansion name from top-level field or None)
    """
    try:
        with open(file_path) as f:
            data = json.load(f)

        # Handle both formats: {"cards": [...]} or [...]
        if isinstance(data, dict):
            cards = data.get("cards", [])
            expansion_name = data.get("expansion")  # May be None
            return cards, expansion_name
        elif isinstance(data, list):
            return data, None
        else:
            logger.error(f"Unexpected JSON format in {file_path.name}: {type(data)}")
            return [], None
    except FileNotFoundError:
        logger.warning(f"Card file not found: {file_path} (optional expansion)")
        return [], None
    except json.JSONDecodeError as e:
        msg = f"Failed to parse {file_path.name} at line {e.lineno}, col {e.colno}: {e.msg}"
        logger.error(msg)
        raise RuntimeError(msg) from e


def _is_expansion_enabled(expansion_name: str) -> bool:
    """Check if an expansion is enabled via environment variable.

    Args:
        expansion_name: Name of the expansion (e.g., "artifacts", "cities")

    Returns:
        True if expansion is enabled, False otherwise
    """
    env_var = f"{expansion_name.upper()}_EXPANSION_ENABLED"
    return os.getenv(env_var, "false").lower() in ("true", "1", "yes")


def load_cards_from_json(enabled_expansions: list[str] | None = None) -> list[Card]:
    """Load cards from BaseCards.json and enabled expansion files.

    Args:
        enabled_expansions: List of expansion names to force enable (overrides env vars)

    Feature flags control which expansions are loaded by default:
    - ARTIFACTS_EXPANSION_ENABLED (default: false)
    - CITIES_EXPANSION_ENABLED (default: false)
    - ECHOES_EXPANSION_ENABLED (default: false)
    - UNSEEN_EXPANSION_ENABLED (default: false)

    Returns:
        List of Card objects from base game and enabled expansions
    """
    # Load base cards (always enabled)
    base_card_data, _ = _load_cards_from_file(BASE_CARDS_PATH)
    all_card_data = [(card, "base") for card in base_card_data]  # Track expansion source
    logger.info(f"Loaded {len(base_card_data)} base game cards")

    # Load expansion cards if enabled via env var OR passed argument
    for expansion_name, expansion_path in EXPANSION_PATHS.items():
        is_enabled = _is_expansion_enabled(expansion_name)

        # Check if explicitly enabled in arguments
        if enabled_expansions and expansion_name in enabled_expansions:
            is_enabled = True

        if is_enabled:
            expansion_cards, file_expansion_name = _load_cards_from_file(expansion_path)
            if expansion_cards:
                # Use top-level expansion field if present, otherwise use path-based name
                expansion_tag = (file_expansion_name or expansion_name).lower()
                all_card_data.extend([(card, expansion_tag) for card in expansion_cards])
                logger.info(
                    f"Loaded {len(expansion_cards)} cards from {expansion_name.title()} expansion"
                )
        else:
            logger.debug(
                f"{expansion_name.title()} expansion disabled (feature flag/arg)"
            )

    cards: list[Card] = []

    # Process all card data (base + expansions)
    for card_data, expansion_source in all_card_data:
        # Convert string symbols to Symbol enums
        # Hex symbols (hex-bow, hex-city, etc.) are preserved as strings for frontend
        symbols = []
        for sym_str in card_data.get("symbols", []):
            if sym_str and sym_str in SYMBOL_MAP:
                symbols.append(SYMBOL_MAP[sym_str])
            elif sym_str and sym_str.startswith("hex-"):
                # Preserve hex symbols as-is (frontend handles these)
                symbols.append(sym_str)

        # Convert symbol_positions to Symbol enums or preserve hex symbols
        symbol_positions = []
        for pos in card_data.get("symbol_positions", [None, None, None, None]):
            if pos and pos in SYMBOL_MAP:
                symbol_positions.append(SYMBOL_MAP[pos])
            elif pos and pos.startswith("hex-"):
                # Preserve hex symbols as-is
                symbol_positions.append(pos)
            else:
                symbol_positions.append(None)

        # Parse dogma resource
        dogma_resource = None
        if (
            card_data.get("dogma_resource")
            and card_data["dogma_resource"] in SYMBOL_MAP
        ):
            dogma_resource = SYMBOL_MAP[card_data["dogma_resource"]]

        # Parse dogma effects
        dogma_effects = []
        for effect_data in card_data.get("dogma_effects", []):
            dogma_effects.append(
                DogmaEffect(
                    text=effect_data.get(
                        "description", ""
                    ),  # DogmaEffect expects 'text' field
                    symbol_count=effect_data.get("symbol_count", 1),
                    is_demand=effect_data.get("is_demand", False),
                    is_optional=False,  # We can add this to JSON later if needed
                    actions=effect_data.get("actions", []),
                    selection_condition=effect_data.get("selection_condition"),
                )
            )

        # Parse color
        color = COLOR_MAP.get(card_data.get("color", "red"), CardColor.RED)

        # Parse special icons (for Cities expansion cards)
        special_icons = []
        for icon_data in card_data.get("special_icons", []):
            from models.special_icon import SpecialIcon

            special_icons.append(
                SpecialIcon(
                    type=icon_data.get("type"),
                    position=icon_data.get("position", 0),
                    parameters=icon_data.get("parameters", {}),
                )
            )

        # Create card
        card = Card(
            name=card_data.get("name", ""),
            age=card_data.get("age", 1),
            color=color,
            card_id=card_data.get("card_id"),  # Include card_id from JSON
            expansion=card_data.get("expansion", expansion_source),  # Use top-level expansion or fallback
            symbols=symbols,
            symbol_positions=symbol_positions,
            dogma_resource=dogma_resource,
            dogma_effects=dogma_effects,
            special_icons=special_icons,
        )
        cards.append(card)

    # Load Figures expansion cards if feature flag is enabled
    if FIGURES_EXPANSION_ENABLED:
        logger.info("FIGURES_EXPANSION_ENABLED=true, loading FiguresCards.json")
        if FIGURES_CARDS_PATH.exists():
            try:
                with open(FIGURES_CARDS_PATH) as f:
                    figures_data = json.load(f)

                # Process Figures cards with same logic as base cards
                for card_data in figures_data.get("cards", []):
                    # Skip cards with TODO primitives to avoid runtime errors
                    has_todo_primitive = False
                    for effect_data in card_data.get("dogma_effects", []):
                        for action in effect_data.get("actions", []):
                            if isinstance(action, dict) and action.get(
                                "type", ""
                            ).startswith("TODO_"):
                                has_todo_primitive = True
                                break
                        if has_todo_primitive:
                            break

                    if has_todo_primitive:
                        logger.debug(
                            f"Skipping Figures card {card_data.get('card_id')} - contains TODO primitives"
                        )
                        continue

                    # Convert string symbols to Symbol enums
                    symbols = []
                    for sym_str in card_data.get("symbols", []):
                        if sym_str and sym_str in SYMBOL_MAP:
                            symbols.append(SYMBOL_MAP[sym_str])

                    # Convert symbol_positions to Symbol enums
                    symbol_positions = []
                    for pos in card_data.get(
                        "symbol_positions", [None, None, None, None]
                    ):
                        if pos and pos in SYMBOL_MAP:
                            symbol_positions.append(SYMBOL_MAP[pos])
                        else:
                            symbol_positions.append(None)

                    # Parse dogma resource
                    dogma_resource = None
                    if (
                        card_data.get("dogma_resource")
                        and card_data["dogma_resource"] in SYMBOL_MAP
                    ):
                        dogma_resource = SYMBOL_MAP[card_data["dogma_resource"]]

                    # Parse dogma effects
                    dogma_effects = []
                    for effect_data in card_data.get("dogma_effects", []):
                        dogma_effects.append(
                            DogmaEffect(
                                text=effect_data.get("description", ""),
                                symbol_count=effect_data.get("symbol_count", 1),
                                is_demand=effect_data.get("is_demand", False),
                                is_optional=False,
                                actions=effect_data.get("actions", []),
                                selection_condition=effect_data.get(
                                    "selection_condition"
                                ),
                            )
                        )

                    # Parse color
                    color = COLOR_MAP.get(card_data.get("color", "red"), CardColor.RED)

                    # Parse special icons (for expansion cards)
                    special_icons = []
                    for icon_data in card_data.get("special_icons", []):
                        from models.special_icon import SpecialIcon

                        special_icons.append(
                            SpecialIcon(
                                type=icon_data.get("type"),
                                position=icon_data.get("position", 0),
                                parameters=icon_data.get("parameters", {}),
                            )
                        )

                    # Create card
                    card = Card(
                        name=card_data.get("name", ""),
                        age=card_data.get("age", 1),
                        color=color,
                        card_id=card_data.get("card_id"),
                        expansion=card_data.get(
                            "expansion", "figures"
                        ),  # Figures expansion
                        symbols=symbols,
                        symbol_positions=symbol_positions,
                        dogma_resource=dogma_resource,
                        dogma_effects=dogma_effects,
                        special_icons=special_icons,
                    )
                    cards.append(card)

                logger.info(
                    f"Loaded {len(figures_data.get('cards', []))} Figures cards"
                )
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse FiguresCards.json at line {e.lineno}, col {e.colno}: {e.msg}"
                )
                # Don't crash - just skip Figures cards
            except Exception as e:
                logger.error(f"Failed to load FiguresCards.json: {e}")
                # Don't crash - just skip Figures cards
        else:
            logger.warning(
                "FIGURES_EXPANSION_ENABLED=true but FiguresCards.json not found"
            )
    else:
        logger.debug("FIGURES_EXPANSION_ENABLED=false, skipping FiguresCards.json")

    return cards


def load_achievement_cards_from_json() -> list[Card]:
    """Load achievement cards"""
    achievements: list[Card] = []

    # Standard age achievements (1-9)
    for age in range(1, 10):
        achievements.append(
            Card(
                name=f"Age {age}",
                age=age,
                color=CardColor.PURPLE,
                symbols=[],
                dogma_effects=[],
                is_achievement=True,
                achievement_requirement=f"Requires {age * 5} points and a top card of age {age} or higher",
            )
        )

    # Special achievements
    special_achievements = [
        {
            "name": "Monument",
            "age": 1,
            "requirement": "Tuck six cards or score six cards in a single turn",
        },
        {
            "name": "Empire",
            "age": 1,
            "requirement": "Have three or more icons of all six types",
        },
        {
            "name": "World",
            "age": 1,
            "requirement": "Have twelve or more clocks on your board",
        },
        {
            "name": "Wonder",
            "age": 1,
            "requirement": "Have all five colors on your board and each is splayed either up, left, or right",
        },
        {
            "name": "Universe",
            "age": 1,
            "requirement": "Have five top cards on your board of value 8 or higher",
        },
        # Cities expansion: Fountain achievements (6 total - one per symbol)
        {
            "name": "Crown Fountain",
            "age": 1,
            "requirement": "Have a fountain city with crown icon visible on your board",
        },
        {
            "name": "Lightbulb Fountain",
            "age": 1,
            "requirement": "Have a fountain city with lightbulb icon visible on your board",
        },
        {
            "name": "Castle Fountain",
            "age": 1,
            "requirement": "Have a fountain city with castle icon visible on your board",
        },
        {
            "name": "Leaf Fountain",
            "age": 1,
            "requirement": "Have a fountain city with leaf icon visible on your board",
        },
        {
            "name": "Factory Fountain",
            "age": 1,
            "requirement": "Have a fountain city with factory icon visible on your board",
        },
        {
            "name": "Clock Fountain",
            "age": 1,
            "requirement": "Have a fountain city with clock icon visible on your board",
        },
        # Cities expansion: Flag achievements (5 total - one per color)
        {
            "name": "Red Flag",
            "age": 1,
            "requirement": "Have a red flag city visible and more visible red cards than all opponents",
        },
        {
            "name": "Blue Flag",
            "age": 1,
            "requirement": "Have a blue flag city visible and more visible blue cards than all opponents",
        },
        {
            "name": "Green Flag",
            "age": 1,
            "requirement": "Have a green flag city visible and more visible green cards than all opponents",
        },
        {
            "name": "Yellow Flag",
            "age": 1,
            "requirement": "Have a yellow flag city visible and more visible yellow cards than all opponents",
        },
        {
            "name": "Purple Flag",
            "age": 1,
            "requirement": "Have a purple flag city visible and more visible purple cards than all opponents",
        },
    ]

    for ach in special_achievements:
        achievements.append(
            Card(
                name=ach["name"],
                age=ach["age"],
                color=CardColor.PURPLE,
                symbols=[],
                dogma_effects=[],
                is_achievement=True,
                achievement_requirement=ach["requirement"],
            )
        )

    return achievements


def get_all_cards() -> list[Card]:
    return load_cards_from_json()


def get_achievement_cards() -> list[Card]:
    return load_achievement_cards_from_json()


def load_unseen_cards() -> list[Card]:
    """
    Load Unseen expansion cards.

    Returns:
        List of Unseen Card objects
    """
    unseen_path = Path(__file__).with_name("UnseenCards.json")

    try:
        with open(unseen_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.warning("UnseenCards.json not found")
        return []
    except json.JSONDecodeError as e:
        logger.error(
            f"Failed to parse UnseenCards.json at line {e.lineno}, col {e.colno}: {e.msg}"
        )
        return []

    cards: list[Card] = []

    for card_data in data.get("cards", []):
        # Convert string symbols to Symbol enums
        symbols = []
        for sym_str in card_data.get("symbols", []):
            if sym_str and sym_str in SYMBOL_MAP:
                symbols.append(SYMBOL_MAP[sym_str])
            elif sym_str and sym_str.startswith("hex-"):
                # Preserve hex symbols as-is (for Unseen expansion special symbols)
                symbols.append(sym_str)

        # Convert symbol_positions to Symbol enums or preserve hex symbols
        symbol_positions = []
        for pos in card_data.get("symbol_positions", [None, None, None, None]):
            if pos and pos in SYMBOL_MAP:
                symbol_positions.append(SYMBOL_MAP[pos])
            elif pos and pos.startswith("hex-"):
                # Preserve hex symbols as-is
                symbol_positions.append(pos)
            else:
                symbol_positions.append(None)

        # Parse dogma resource
        dogma_resource = None
        if (
            card_data.get("dogma_resource")
            and card_data["dogma_resource"] in SYMBOL_MAP
        ):
            dogma_resource = SYMBOL_MAP[card_data["dogma_resource"]]

        # Parse dogma effects
        dogma_effects = []
        for effect_data in card_data.get("dogma_effects", []):
            dogma_effects.append(
                DogmaEffect(
                    text=effect_data.get("description", ""),
                    symbol_count=effect_data.get("symbol_count", 1),
                    is_demand=effect_data.get("is_demand", False),
                    is_optional=False,
                    actions=effect_data.get("actions", []),
                    selection_condition=effect_data.get("selection_condition"),
                )
            )

        # Parse color
        color = COLOR_MAP.get(card_data.get("color", "red"), CardColor.RED)

        # Parse Safeguard keyword (Unseen expansion specific)
        safeguard = None
        if card_data.get("safeguard"):
            safeguard = card_data["safeguard"]

        # Create card with expansion="unseen"
        card = Card(
            name=card_data.get("name", ""),
            age=card_data.get("age", 1),
            color=color,
            card_id=card_data.get("card_id"),
            symbols=symbols,
            symbol_positions=symbol_positions,
            dogma_resource=dogma_resource,
            dogma_effects=dogma_effects,
            expansion="unseen",
            safeguard=safeguard,
        )
        cards.append(card)

    logger.info(f"Loaded {len(cards)} Unseen cards")
    return cards
