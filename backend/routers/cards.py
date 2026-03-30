"""
Card-related API endpoints for Innovation game server.
Handles card database access and caching functionality.
"""

import time

from fastapi import APIRouter

from logging_config import get_logger

logger = get_logger(__name__)

# Router instance
router = APIRouter(prefix="/api/v1")

# Import game manager - will be set by main.py
game_manager = None

# Global cache for processed card data
_cards_cache = None
_cards_cache_timestamp = 0
_CARDS_CACHE_TTL = 3600  # 1 hour cache TTL


def set_game_manager(gm):
    """Set game manager dependency injected from main.py"""
    global game_manager
    game_manager = gm


# Enum conversion now handled in service layer (AsyncGameManager._convert_card_enums_to_strings)


def _load_and_process_cards():
    """Load cards through service layer"""
    if not game_manager:
        raise RuntimeError("Game manager not initialized")

    # Delegate to service layer instead of direct data access
    return game_manager.get_cards_database()


def get_cached_cards_database():
    """Get cards database with intelligent caching"""
    global _cards_cache, _cards_cache_timestamp

    current_time = time.time()

    # Check if cache is still valid
    if (
        _cards_cache is not None
        and current_time - _cards_cache_timestamp < _CARDS_CACHE_TTL
    ):
        logger.debug("Serving cards database from cache")
        return _cards_cache

    # Cache is invalid or doesn't exist, reload
    logger.debug("Loading and caching cards database")
    _cards_cache = _load_and_process_cards()
    _cards_cache_timestamp = current_time

    return _cards_cache


def invalidate_cards_cache():
    """Manually invalidate the cards cache (for testing or updates)"""
    global _cards_cache, _cards_cache_timestamp
    _cards_cache = None
    _cards_cache_timestamp = 0
    logger.info("Cards cache invalidated")


@router.get("/cards/database")
async def get_cards_database():
    """Get all card data for the frontend (cached for performance)"""
    return get_cached_cards_database()


@router.post("/cards/cache/invalidate")
async def invalidate_cards_cache_endpoint():
    """Invalidate cards cache (development/testing endpoint)"""
    invalidate_cards_cache()
    return {"success": True, "message": "Cards cache invalidated"}
