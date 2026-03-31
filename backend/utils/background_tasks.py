"""
Background tasks and utilities for The Singularity game server.
Handles periodic cleanup and maintenance tasks.
"""

import asyncio
import logging

from app_config import game_config

logger = logging.getLogger(__name__)


async def create_periodic_cleanup_task(connection_manager):
    """
    Create and return a periodic cleanup task.

    Args:
        connection_manager: The connection manager to perform cleanup on

    Returns:
        asyncio.Task: The cleanup task
    """

    async def periodic_cleanup():
        """Periodically clean up stale connections and game data"""
        while True:
            try:
                await asyncio.sleep(game_config.cleanup_interval)  # Configurable cleanup interval
                await connection_manager.cleanup_stale_connections()
                # Also clean up old games that have no active players
                for game_id in list(connection_manager.game_connections.keys()):
                    if not connection_manager.game_connections[game_id]:
                        logger.info(f"Removing empty game connections for {game_id}")
                        del connection_manager.game_connections[game_id]
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")

    return asyncio.create_task(periodic_cleanup())


async def shutdown_cleanup_task(cleanup_task):
    """
    Properly shutdown a cleanup task.

    Args:
        cleanup_task: The cleanup task to shutdown
    """
    if cleanup_task and not cleanup_task.done():
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            logger.debug("Cleanup task cancelled during shutdown")
        except Exception as e:
            logger.warning(f"Error during cleanup task shutdown: {e}")
