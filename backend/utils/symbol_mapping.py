"""
Shared symbol mapping utilities for consistent symbol string-to-enum conversion.
"""

from models.card import Symbol


def get_symbol_map() -> dict[str, Symbol]:
    return {
        "circuit": Symbol.CIRCUIT,
        "neural_net": Symbol.NEURAL_NET,
        "data": Symbol.DATA,
        "algorithm": Symbol.ALGORITHM,
        "human_mind": Symbol.HUMAN_MIND,
        "robot": Symbol.ROBOT,
    }


def string_to_symbol(symbol_name: str) -> Symbol | None:
    if not symbol_name:
        return None
    return get_symbol_map().get(symbol_name.lower())


def get_symbol_names() -> list[str]:
    return list(get_symbol_map().keys())
