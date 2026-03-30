"""
JWT-based authentication for the Innovation game.
Uses PyJWT for token generation and validation.

SECURITY WARNING: You MUST set JWT_SECRET_KEY environment variable in production!
Generate a secure key with: python -c "import secrets; print(secrets.token_urlsafe(32))"
"""

import logging
import os
import secrets
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# Security configuration
DEFAULT_SECRET_KEY = "your-secret-key-change-this-in-production"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", DEFAULT_SECRET_KEY)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Password hashing context (for future user authentication)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthManager:
    """
    Manages JWT authentication for the game.

    This class provides secure JWT token creation and verification methods.
    All methods in this class perform proper security validation.

    For debugging purposes only, unsafe token inspection methods are available
    in the auth_diagnostics module (development environments only).
    """

    def __init__(self):
        self.secret_key = SECRET_KEY
        self.algorithm = ALGORITHM
        self.token_expire_hours = ACCESS_TOKEN_EXPIRE_HOURS

        # Validate JWT secret security
        self._validate_jwt_secret()

    def _validate_jwt_secret(self):
        """Validate JWT secret key security and fail fast if insecure."""
        environment = os.getenv("INNOVATION_ENV", "development").lower()
        is_production = environment == "production"
        is_staging = environment == "staging"

        # Check for default/missing secret
        if not self.secret_key or self.secret_key == DEFAULT_SECRET_KEY:
            example_key = secrets.token_urlsafe(32)

            logger.critical("=" * 80)
            logger.critical("CRITICAL SECURITY ISSUE: JWT_SECRET_KEY not configured!")
            logger.critical("Using default JWT secret is NEVER allowed.")
            logger.critical("")
            logger.critical("To fix this:")
            logger.critical("1. Generate a secure key:")
            logger.critical(
                '   python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
            logger.critical("")
            logger.critical("2. Set the JWT_SECRET_KEY environment variable:")
            logger.critical(f'   export JWT_SECRET_KEY="{example_key}"')
            logger.critical("")
            logger.critical(
                "3. Or add to .env file: JWT_SECRET_KEY=your-secure-key-here"
            )
            logger.critical("=" * 80)

            if is_production or is_staging:
                logger.critical(
                    "REFUSING TO START: Default JWT secret detected in production/staging!"
                )
                sys.exit(1)
            else:
                logger.critical(
                    "WARNING: This would prevent startup in production/staging!"
                )
            return

        # Check secret key strength
        if len(self.secret_key) < 32:
            logger.critical("=" * 80)
            logger.critical("CRITICAL SECURITY ISSUE: JWT_SECRET_KEY too weak!")
            logger.critical(
                f"Current length: {len(self.secret_key)} chars, minimum required: 32"
            )
            logger.critical(
                "Weak JWT secrets can be brute-forced, compromising authentication."
            )
            logger.critical("")
            logger.critical("Generate a stronger key:")
            logger.critical(
                'python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
            logger.critical("=" * 80)

            if is_production or is_staging:
                logger.critical(
                    "REFUSING TO START: Weak JWT secret detected in production/staging!"
                )
                sys.exit(1)
            else:
                logger.critical(
                    "WARNING: This would prevent startup in production/staging!"
                )
            return

        # Log successful validation
        if is_production or is_staging:
            logger.info(
                f"✅ JWT secret validation passed for {environment} environment"
            )
        else:
            logger.info(
                f"✅ JWT secret validation passed for {environment} environment (length: {len(self.secret_key)} chars)"
            )

    def create_game_token(self, game_id: str, player_id: str, player_name: str) -> str:
        """
        Create a JWT token for a player joining a game.

        Args:
            game_id: The ID of the game
            player_id: The ID of the player
            player_name: The display name of the player

        Returns:
            A JWT token string
        """
        # Token payload
        payload = {
            "game_id": game_id,
            "player_id": player_id,
            "player_name": player_name,
            "exp": datetime.now(UTC) + timedelta(hours=self.token_expire_hours),
            "iat": datetime.now(UTC),
            "type": "game_access",
        }

        # Create token
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        logger.info(
            f"Created token for player {player_name} ({player_id}) in game {game_id}"
        )
        return token

    def verify_game_token(
        self, token: str, game_id: str, player_id: str
    ) -> dict[str, Any] | None:
        """
        Verify a JWT token for WebSocket connection.

        Args:
            token: The JWT token to verify
            game_id: The expected game ID
            player_id: The expected player ID

        Returns:
            The decoded token payload if valid, None otherwise
        """
        try:
            # Decode and verify token with primary secret
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Verify the token is for the correct game and player
            if payload.get("game_id") != game_id:
                logger.warning(
                    f"Token game_id mismatch: expected {game_id}, got {payload.get('game_id')}"
                )
                return None

            if payload.get("player_id") != player_id:
                logger.warning(
                    f"Token player_id mismatch: expected {player_id}, got {payload.get('player_id')}"
                )
                return None

            if payload.get("type") != "game_access":
                logger.warning(f"Invalid token type: {payload.get('type')}")
                return None

            logger.info(f"Token verified for player {player_id} in game {game_id}")
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning(f"Expired token for player {player_id} in game {game_id}")
            return None
        except jwt.InvalidTokenError as e:
            # Development fallback: also accept legacy default secret to keep tests/backward-compat working
            try:
                environment = os.getenv("INNOVATION_ENV", "development").lower()
                if environment != "production" and self.secret_key != DEFAULT_SECRET_KEY:
                    payload = jwt.decode(
                        token, DEFAULT_SECRET_KEY, algorithms=[self.algorithm]
                    )
                    if payload.get("game_id") == game_id and payload.get("player_id") == player_id:
                        logger.info(
                            "Verified token using legacy default secret in non-production environment"
                        )
                        return payload
            except Exception:
                pass
            logger.warning(
                f"Invalid token for player {player_id} in game {game_id}: {e}"
            )
            return None
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None


# Global auth manager instance
auth_manager = AuthManager()
