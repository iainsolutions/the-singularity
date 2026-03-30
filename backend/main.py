"""
Innovation Game Server - Main FastAPI Application
Modular architecture with separated concerns.
"""

# Load environment variables from .env as early as possible so app_config
# and security settings pick them up when imported.
try:
    from pathlib import Path

    from dotenv import load_dotenv  # type: ignore

    # Try project root .env and backend/.env
    here = Path(__file__).resolve().parent
    for env_path in (here.parent / ".env", here / ".env"):
        if env_path.exists():
            load_dotenv(env_path, override=False)
except Exception:
    # dotenv not installed; continue (start_backend.py also loads .env)
    pass

import logging
import os
import sys
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import configuration before other modules
from app_config import (
    cors_config,
    log_configuration_summary,
    logging_config,
    server_config,
)

# Configure logging from centralized config
logging.basicConfig(
    level=logging_config.get_log_level(),
    format=logging_config.format,
)
logger = logging.getLogger(__name__)

# Core imports (after logging configuration)
from async_game_manager import AsyncGameManager  # noqa: E402
from debug.debug_api import debug_router  # noqa: E402

# Import global activity logger
from logging_config import activity_logger  # noqa: E402

# Security middleware
from middleware.security import create_security_middlewares  # noqa: E402

# Router imports
from routers.ai_games import router as ai_router  # noqa: E402
from routers.ai_games import set_game_manager as set_ai_deps  # noqa: E402
from routers.cards import router as cards_router  # noqa: E402
from routers.cards import set_game_manager as set_cards_deps  # noqa: E402
from routers.games import router as games_router  # noqa: E402
from routers.games import set_dependencies as set_games_deps  # noqa: E402
from routers.system import router as system_router  # noqa: E402
from routers.system import (  # noqa: E402
    set_connection_manager as set_system_connection_manager,
)
from routers.system import set_game_manager as set_system_deps  # noqa: E402
from routers.tracing import router as tracing_router  # noqa: E402
from routers.websocket import router as websocket_router  # noqa: E402
from routers.websocket import set_dependencies as set_websocket_deps  # noqa: E402
from security_config import validate_security_on_startup  # noqa: E402

# Service imports
from services.ai_service import ai_service  # noqa: E402
from services.broadcast_service import initialize_broadcast_service  # noqa: E402
from services.connection_manager import ConnectionManager  # noqa: E402
from services.game_event_bus import GameEventBus  # noqa: E402
from tools.doc_server import create_documentation_router  # noqa: E402

# Utilities
from utils.background_tasks import (  # noqa: E402
    create_periodic_cleanup_task,
    shutdown_cleanup_task,
)

# Global instances
event_bus = GameEventBus()
logger.info(f"DEBUG: Created global Event Bus instance {id(event_bus)}")
game_manager = AsyncGameManager(event_bus)
logger.info(
    f"DEBUG: Created AsyncGameManager instance {id(game_manager)} with event_bus {id(game_manager.event_bus)}"
)
connection_manager = ConnectionManager()

# Initialize centralized broadcast service for hybrid architecture
broadcast_service = initialize_broadcast_service(connection_manager, event_bus)

# Set up dependency injection immediately
connection_manager.set_game_manager(game_manager)
set_cards_deps(game_manager)
set_games_deps(game_manager)
set_system_deps(game_manager)
set_system_connection_manager(connection_manager)
set_websocket_deps(game_manager, connection_manager, event_bus)
set_ai_deps(game_manager, event_bus)

# Connect activity logger to connection manager for WebSocket broadcasting
activity_logger.set_connection_manager(connection_manager)
# Connect activity logger to game manager for persisting events to action_log
activity_logger.set_game_manager(game_manager)

# Background task handles
cleanup_task = None

# Log key environment flags for visibility (especially for admin endpoints)
with suppress(Exception):
    logger.info(
        "Environment flags: INNOVATION_DEBUG=%s ENABLE_DEV_ENDPOINTS=%s",
        os.getenv("INNOVATION_DEBUG", "false"),
        os.getenv("ENABLE_DEV_ENDPOINTS", "false"),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Lifespan context manager for startup and shutdown events"""
    global cleanup_task

    # Startup
    logger.info("=" * 80)
    logger.info("Starting Innovation Game Server")
    logger.info("=" * 80)

    # Log configuration summary
    log_configuration_summary()

    # Run comprehensive security validation
    security_status = validate_security_on_startup()

    if not security_status["is_secure"]:
        logger.critical("Server startup aborted due to security issues")
        sys.exit(1)

    logger.info("Security validation complete")
    logger.info("=" * 80)

    # Initialize game manager
    await game_manager.initialize()
    logger.info("Game manager initialized")

    # Bootstrap AI players for games loaded from Redis
    # (separate from game manager to maintain player-agnostic design)
    from services.ai_bootstrap import bootstrap_all_ai_players

    await bootstrap_all_ai_players(game_manager, event_bus)
    logger.info("AI player bootstrap complete")

    # Initialize AI service (fetch available models)
    await ai_service.initialize_models()
    logger.info("AI service models initialized")

    # Start background cleanup task
    cleanup_task = await create_periodic_cleanup_task(connection_manager)
    logger.info("Background cleanup task started")

    logger.info("Server startup complete")
    logger.info("=" * 80)

    yield

    # Shutdown
    logger.info("=" * 80)
    logger.info("Shutting down Innovation Game Server")
    logger.info("=" * 80)

    # Stop background tasks
    if cleanup_task:
        await shutdown_cleanup_task(cleanup_task)
        logger.info("Background cleanup task stopped")

    # Shutdown connection manager
    await connection_manager.shutdown()
    logger.info("Connection manager shutdown complete")

    # Shutdown game manager
    await game_manager.shutdown()
    logger.info("Game manager shutdown complete")

    logger.info("Server shutdown complete")
    logger.info("=" * 80)


# FastAPI app with lifespan management
app = FastAPI(
    title="Innovation Game API",
    description="Real-time multiplayer Innovation card game server",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration using centralized config
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_config.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security middlewares
app = create_security_middlewares(app)

# Include routers
app.include_router(games_router, tags=["games"])
app.include_router(cards_router, tags=["cards"])
app.include_router(system_router, tags=["system"])
app.include_router(websocket_router, tags=["websocket"])
app.include_router(ai_router, tags=["ai"])
app.include_router(debug_router, tags=["debug"])
app.include_router(tracing_router, tags=["tracing"])

# Add documentation router
documentation_router = create_documentation_router()
app.include_router(documentation_router, tags=["documentation"])

# Add monitoring router (Week 8 Performance Monitoring)
try:
    from monitoring.dashboard import create_monitoring_router

    monitoring_router = create_monitoring_router()
    app.include_router(monitoring_router, tags=["monitoring"])
    logger.info("Performance monitoring endpoints enabled")
except ImportError as e:
    logger.warning(f"Performance monitoring not available: {e}")
except Exception as e:
    logger.warning(f"Could not enable performance monitoring: {e}")

# Add debug endpoints if enabled (non-production environments only)
try:
    import os

    # NEW: Snapshot system (replacement for debug_admin_endpoints)
    if os.getenv("INNOVATION_ENV", "development").lower() != "production":
        from pathlib import Path

        from routers import snapshot_router
        from services.game_snapshot_manager import GameSnapshotManager

        # Create snapshot manager
        snapshot_storage_path = Path("debug-tools/snapshots")
        snapshot_manager = GameSnapshotManager(
            game_manager=game_manager,
            storage_path=snapshot_storage_path,
            max_snapshots_per_game=10,
            connection_manager=connection_manager,
            event_bus=event_bus,
        )

        # Set dependency in router
        snapshot_router.set_snapshot_manager(snapshot_manager)

        # Include snapshot router
        app.include_router(snapshot_router.router, prefix="/api/v1", tags=["snapshots"])
        logger.info(f"✅ Snapshot system enabled (storage: {snapshot_storage_path})")

except ImportError:
    logger.warning("Debug endpoints not available")
except Exception as e:
    logger.warning(f"Could not enable debug tools: {e}")

# Include authenticated admin routes (always available)
try:
    from routers.admin import router as secure_admin_router
    from routers.admin import set_dependencies as set_admin_deps

    set_admin_deps(game_manager, connection_manager)
    app.include_router(secure_admin_router, prefix="/api/v1", tags=["admin"])
    logger.info("Authenticated admin routes enabled (/api/v1/admin/*)")
except ImportError:
    logger.warning("Authenticated admin routes not available")
except Exception as e:
    logger.warning(f"Could not enable authenticated admin routes: {e}")

# Include enhanced admin routes (save/restore, board setup, etc.) in non-production
try:
    import os

    if os.getenv("INNOVATION_ENV", "development").lower() != "production":
        from admin_routes import router as admin_routes_router

        app.include_router(admin_routes_router, prefix="/admin/dev", tags=["admin-dev"])
        logger.info("Enhanced admin routes enabled (/admin/dev/*)")
    else:
        logger.info("Development admin routes disabled in production environment")
except ImportError:
    logger.warning("Enhanced admin routes not available")
except Exception as e:
    logger.warning(f"Could not enable enhanced admin routes: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=server_config.host, port=server_config.port)
