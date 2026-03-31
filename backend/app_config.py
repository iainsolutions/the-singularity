"""
Application Configuration for The Singularity Game Server

Centralizes all configuration values to eliminate hardcoded constants.
Provides environment-specific defaults and validation.
"""

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


class ServerConfig:
    """Server and networking configuration."""

    def __init__(self):
        self.host = os.getenv("SERVER_HOST", "0.0.0.0")
        self.port = int(os.getenv("SERVER_PORT", "8000"))
        self.debug_mode = os.getenv("INNOVATION_DEBUG", "false").lower() == "true"

    def get_server_url(self) -> str:
        """Get the server URL for external binding."""
        return f"http://{self.host}:{self.port}"

    def get_internal_api_url(self) -> str:
        """
        Get the base URL for internal API requests.

        Uses localhost instead of 0.0.0.0 for in-process HTTP calls.
        Suitable for AI services making requests to the same server.
        """
        # Use localhost for internal requests instead of 0.0.0.0
        internal_host = "localhost" if self.host == "0.0.0.0" else self.host
        return f"http://{internal_host}:{self.port}"


class CORSConfig:
    """CORS (Cross-Origin Resource Sharing) configuration."""

    def __init__(self):
        self.allow_all = os.getenv("CORS_ALLOW_ALL", "false").lower() == "true"
        self.default_origins = self._get_default_origins()
        self.origins = self._parse_origins()

    def _get_default_origins(self) -> list[str]:
        """Get default CORS origins based on environment."""
        environment = os.getenv("INNOVATION_ENV", "development").lower()
        origins_map = {
            "development": ["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"],
            "staging": ["https://staging.innovation.example.com"],
            "production": [],  # Production origins should be configured explicitly
        }
        return origins_map.get(environment, ["http://localhost:3000"])

    def _parse_origins(self) -> list[str]:
        """Parse CORS origins from environment variable."""
        origins_str = os.getenv("CORS_ORIGINS", "")
        if origins_str:
            return [origin.strip() for origin in origins_str.split(",")]
        return self.default_origins

    def get_allowed_origins(self) -> list[str]:
        """Get list of allowed CORS origins."""
        if self.allow_all:
            return ["*"]
        return self.origins


class RedisConfig:
    """Redis configuration for caching and session storage."""

    def __init__(self):
        self.url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.ssl_enabled = os.getenv("REDIS_SSL", "false").lower() == "true"
        self.password = os.getenv("REDIS_PASSWORD")
        self.ssl_cert_reqs = os.getenv("REDIS_SSL_CERT_REQS", "required")

        # Connection pool settings
        self.max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "10"))
        self.socket_keepalive = (
            os.getenv("REDIS_SOCKET_KEEPALIVE", "true").lower() == "true"
        )
        self.socket_keepalive_options = {}

        # Timeouts
        # Accept integer or float seconds from environment (e.g., "5" or "5.0")
        try:
            self.connect_timeout = float(os.getenv("REDIS_CONNECT_TIMEOUT", "5"))
        except ValueError:
            self.connect_timeout = 5.0
        try:
            self.socket_timeout = float(os.getenv("REDIS_SOCKET_TIMEOUT", "5"))
        except ValueError:
            self.socket_timeout = 5.0

    def get_connection_kwargs(self) -> dict:
        """Get Redis connection parameters."""
        kwargs = {
            "socket_keepalive": self.socket_keepalive,
            "socket_keepalive_options": self.socket_keepalive_options,
            "socket_connect_timeout": self.connect_timeout,
            "socket_timeout": self.socket_timeout,
        }

        if self.password:
            kwargs["password"] = self.password

        if self.ssl_enabled:
            kwargs["ssl_cert_reqs"] = self.ssl_cert_reqs

        return kwargs


class SecurityConfig:
    """Security-related configuration."""

    def __init__(self):
        self.environment = os.getenv("INNOVATION_ENV", "development").lower()
        self.is_production = self.environment == "production"
        self.is_staging = self.environment == "staging"
        self.is_development = self.environment == "development"

        # JWT Configuration
        self.jwt_secret_key = os.getenv(
            "JWT_SECRET_KEY", "your-secret-key-change-this-in-production"
        )
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.jwt_expiration_hours = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

        # Default JWT secret warning
        self.default_jwt_secret = "your-secret-key-change-this-in-production"

    def is_using_default_jwt_secret(self) -> bool:
        """Check if using the default JWT secret."""
        return self.jwt_secret_key == self.default_jwt_secret

    def is_jwt_secret_secure(self) -> bool:
        """Check if JWT secret meets security requirements."""
        return len(self.jwt_secret_key) >= 32 and not self.is_using_default_jwt_secret()


class GameConfig:
    """Game-specific configuration settings."""

    def __init__(self):
        # Cleanup intervals (in seconds)
        self.cleanup_interval = int(os.getenv("GAME_CLEANUP_INTERVAL", "60"))
        self.stale_connection_timeout = int(
            os.getenv("STALE_CONNECTION_TIMEOUT", "300")
        )
        self.game_timeout = int(os.getenv("GAME_TIMEOUT", "1800"))  # 30 minutes
        self.orphan_game_ttl = int(os.getenv("ORPHAN_GAME_TTL", "300"))  # 5 min TTL for orphaned games on startup

        # Game limits
        self.max_games_per_server = int(os.getenv("MAX_GAMES_PER_SERVER", "100"))
        self.max_players_per_game = int(os.getenv("MAX_PLAYERS_PER_GAME", "4"))

        # WebSocket settings
        self.websocket_ping_interval = int(os.getenv("WS_PING_INTERVAL", "20"))
        self.websocket_ping_timeout = int(
            os.getenv("WS_PING_TIMEOUT", "30")
        )  # Should be > ping_interval
        self.max_message_size = int(os.getenv("MAX_MESSAGE_SIZE", "1048576"))  # 1MB

        # Test mode settings
        self.test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
        self.auto_advance_tests = (
            os.getenv("AUTO_ADVANCE_TESTS", "false").lower() == "true"
        )


class LoggingConfig:
    """Logging configuration."""

    def __init__(self):
        self.level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.format = os.getenv(
            "LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        self.json_logging = os.getenv("JSON_LOGGING", "false").lower() == "true"

        # File logging (optional)
        self.log_file = os.getenv("LOG_FILE")
        self.max_log_file_size = int(os.getenv("MAX_LOG_FILE_SIZE", "10485760"))  # 10MB
        self.log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    def get_log_level(self):
        """Get numeric log level."""
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        return level_map.get(self.level, logging.INFO)


class TestConfig:
    """Test-specific configuration."""

    def __init__(self):
        # API endpoints for tests
        self.api_base_url = os.getenv("TEST_API_BASE", "http://localhost:8000")
        self.ws_base_url = os.getenv("TEST_WS_BASE", "ws://localhost:8000")
        self.frontend_base_url = os.getenv(
            "TEST_FRONTEND_BASE", "http://localhost:3000"
        )

        # Test timeouts
        self.test_timeout = int(os.getenv("TEST_TIMEOUT", "30"))
        self.api_timeout = int(os.getenv("TEST_API_TIMEOUT", "10"))
        self.websocket_timeout = int(os.getenv("TEST_WS_TIMEOUT", "15"))

        # Test data
        self.test_game_timeout = int(os.getenv("TEST_GAME_TIMEOUT", "120"))
        self.max_test_games = int(os.getenv("MAX_TEST_GAMES", "10"))


# Thread-safe configuration initialization
class ConfigManager:
    """Thread-safe configuration manager with lazy initialization."""

    def __init__(self):
        self._server_config = None
        self._cors_config = None
        self._redis_config = None
        self._security_config = None
        self._game_config = None
        self._logging_config = None
        self._test_config = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self):
        """Initialize all configurations in a thread-safe manner."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:  # Double-check locking pattern
                return

            try:
                # Initialize all configurations
                self._server_config = ServerConfig()
                self._cors_config = CORSConfig()
                self._redis_config = RedisConfig()
                self._security_config = SecurityConfig()
                self._game_config = GameConfig()
                self._logging_config = LoggingConfig()
                self._test_config = TestConfig()

                self._initialized = True
                logger.info("Configuration manager initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize configuration manager: {e}")
                raise

    def get_server_config(self) -> ServerConfig:
        """Get server configuration (thread-safe)."""
        # Fallback to synchronous initialization for backwards compatibility
        if not self._initialized and self._server_config is None:
            self._server_config = ServerConfig()
        return self._server_config

    def get_cors_config(self) -> CORSConfig:
        """Get CORS configuration (thread-safe)."""
        if not self._initialized and self._cors_config is None:
            self._cors_config = CORSConfig()
        return self._cors_config

    def get_redis_config(self) -> RedisConfig:
        """Get Redis configuration (thread-safe)."""
        if not self._initialized and self._redis_config is None:
            self._redis_config = RedisConfig()
        return self._redis_config

    def get_security_config(self) -> SecurityConfig:
        """Get security configuration (thread-safe)."""
        if not self._initialized and self._security_config is None:
            self._security_config = SecurityConfig()
        return self._security_config

    def get_game_config(self) -> GameConfig:
        """Get game configuration (thread-safe)."""
        if not self._initialized and self._game_config is None:
            self._game_config = GameConfig()
        return self._game_config

    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration (thread-safe)."""
        if not self._initialized and self._logging_config is None:
            self._logging_config = LoggingConfig()
        return self._logging_config

    def get_test_config(self) -> TestConfig:
        """Get test configuration (thread-safe)."""
        if not self._initialized and self._test_config is None:
            self._test_config = TestConfig()
        return self._test_config


# Global configuration manager instance
_config_manager = ConfigManager()


# Backwards compatibility functions that use the thread-safe manager
def get_server_config() -> ServerConfig:
    return _config_manager.get_server_config()


def get_cors_config() -> CORSConfig:
    return _config_manager.get_cors_config()


def get_redis_config() -> RedisConfig:
    return _config_manager.get_redis_config()


def get_security_config() -> SecurityConfig:
    return _config_manager.get_security_config()


def get_game_config() -> GameConfig:
    return _config_manager.get_game_config()


def get_logging_config() -> LoggingConfig:
    return _config_manager.get_logging_config()


def get_test_config() -> TestConfig:
    return _config_manager.get_test_config()


# Legacy global variables for backwards compatibility (lazy-loaded)
server_config = get_server_config()
cors_config = get_cors_config()
redis_config = get_redis_config()
security_config = get_security_config()
game_config = get_game_config()
logging_config = get_logging_config()
test_config = get_test_config()


# Async initialization function for explicit initialization
async def initialize_config():
    """Initialize configuration manager asynchronously."""
    await _config_manager.initialize()


def get_config_summary() -> dict:
    """Get a summary of current configuration for debugging."""
    # Use manager functions for thread-safe access
    server = get_server_config()
    cors = get_cors_config()
    redis = get_redis_config()
    security = get_security_config()
    game = get_game_config()
    logging_cfg = get_logging_config()

    return {
        "server": {
            "host": server.host,
            "port": server.port,
            "debug": server.debug_mode,
        },
        "cors": {
            "allow_all": cors.allow_all,
            "origins_count": len(cors.origins),
        },
        "redis": {
            "url_configured": bool(redis.url),
            "ssl_enabled": redis.ssl_enabled,
            "password_set": bool(redis.password),
        },
        "security": {
            "environment": security.environment,
            "jwt_configured": not security.is_using_default_jwt_secret(),
            "jwt_secure": security.is_jwt_secret_secure(),
        },
        "game": {
            "cleanup_interval": game.cleanup_interval,
            "max_games": game.max_games_per_server,
            "test_mode": game.test_mode,
        },
        "logging": {
            "level": logging_cfg.level,
            "json": logging_cfg.json_logging,
            "file": bool(logging_cfg.log_file),
        },
    }


def validate_configuration() -> list[str]:
    """Validate configuration and return list of issues."""
    issues = []

    # Use manager functions for thread-safe access
    server = get_server_config()
    redis = get_redis_config()
    game = get_game_config()

    # Validate server config
    if server.port < 1 or server.port > 65535:
        issues.append(f"Invalid server port: {server.port}")

    # Validate Redis config
    if redis.max_connections < 1:
        issues.append(f"Invalid Redis max_connections: {redis.max_connections}")

    # Validate game config
    if game.cleanup_interval < 10:
        issues.append(
            f"Cleanup interval too short: {game.cleanup_interval}s (minimum 10s)"
        )

    if game.max_players_per_game < 2:
        issues.append(f"Invalid max_players_per_game: {game.max_players_per_game}")

    # Validate WebSocket config
    if game.websocket_ping_interval >= game.websocket_ping_timeout:
        issues.append("WebSocket ping_interval should be less than ping_timeout")

    return issues


def log_configuration_summary():
    """Log a summary of the current configuration."""
    config_summary = get_config_summary()
    logger.info("=" * 60)
    logger.info("CONFIGURATION SUMMARY")
    logger.info("=" * 60)

    for category, settings in config_summary.items():
        logger.info(f"{category.upper()}:")
        for key, value in settings.items():
            logger.info(f"  {key}: {value}")

    # Validate configuration
    issues = validate_configuration()
    if issues:
        logger.warning("Configuration Issues:")
        for issue in issues:
            logger.warning(f"  ⚠️  {issue}")
    else:
        logger.info("✅ Configuration validation passed")

    logger.info("=" * 60)
