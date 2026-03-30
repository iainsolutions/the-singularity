import json
import logging
import time
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket
from schemas.interaction_data import validate_no_cards_field
from schemas.websocket_messages import ErrorResponse, InteractionResponse


if TYPE_CHECKING:
    from async_game_manager import AsyncGameManager

    from services.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


def safe_get(obj, attr, default=None):
    """Safely get attribute from Pydantic object or dictionary."""
    if hasattr(obj, attr):  # Pydantic object
        return getattr(obj, attr, default)
    elif isinstance(obj, dict):  # Dictionary
        return obj.get(attr, default)
    else:
        return default


class WebSocketHandler:
    """Handles WebSocket message processing and validation."""

    def __init__(
        self, game_manager: "AsyncGameManager", connection_manager: "ConnectionManager"
    ):
        self.game_manager = game_manager
        self.connection_manager = connection_manager

    async def send_validation_error(
        self,
        websocket: WebSocket,
        error_message: str,
        error_code: str = "VALIDATION_ERROR",
    ):
        """Send a validation error response to the client."""
        try:
            error_response = ErrorResponse(
                type="error",
                error_code=error_code,
                error_category="validation_error",
                message=error_message,
                suggested_action="Check message format and try again",
                retry_possible=True,
            )
            await websocket.send_json(error_response.model_dump())
        except Exception as e:
            logger.error(f"Failed to send validation error: {e}")

    def validate_dogma_response(
        self, message: dict
    ) -> tuple[bool, InteractionResponse | None, str | None]:
        """Validate incoming dogma_response using Pydantic models."""
        try:
            # Handle decline/cancel cases more gracefully
            # AI sends "cancelled", humans send "decline" - support both
            is_decline = message.get("decline", False) or message.get("cancelled", False)

            # For decline messages, provide reasonable defaults
            response_data = {
                "interaction_id": message.get("transaction_id", "decline-unknown"),
                "selected_cards": message.get("selected_cards"),
                "selected_achievements": message.get("selected_achievements"),
                "chosen_option": message.get("chosen_option"),
                "selected_color": message.get("selected_color"),
                "cancelled": is_decline,
            }

            # If it's a decline but no transaction_id, try to make it work
            if is_decline and not message.get("transaction_id"):
                response_data["interaction_id"] = f"decline-{int(time.time())}"
                logger.info(
                    f"Decline message without transaction_id, using fallback ID: {response_data['interaction_id']}"
                )

            # Validate using Pydantic model
            validated_response = InteractionResponse(**response_data)
            return True, validated_response, None

        except Exception as e:
            error_msg = f"Invalid dogma_response format: {e!s}"
            logger.warning(error_msg)
            return False, None, error_msg

    def validate_outgoing_interaction(
        self, interaction_data: dict
    ) -> tuple[bool, str | None]:
        """Validate outgoing interaction data using Pydantic models and field name rules."""
        try:
            # First check for the critical field name bug
            validate_no_cards_field(interaction_data)
            return True, None

        except ValueError as e:
            error_msg = f"Field name validation failed: {e!s}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Interaction validation failed: {e!s}"
            logger.warning(error_msg)
            return False, error_msg

    async def validate_interaction_request(self, interaction_request: Any) -> bool:
        """Validate that interaction_request has the expected format."""
        # Handle Pydantic DogmaInteractionRequest objects
        if hasattr(interaction_request, "model_dump"):
            try:
                # Use mode='json' to apply json_encoders (datetime -> ISO string)
                interaction_request = interaction_request.model_dump(mode="json")
            except Exception as e:
                logger.warning(f"Failed to convert Pydantic object to dict: {e}")
                return False

        # Basic format validation for InteractionRequest structure
        if not isinstance(interaction_request, dict):
            logger.warning(
                f"Invalid interaction_request type: expected dict, got {type(interaction_request)}"
            )
            return False

        # If this is a dogma_response, it has different required fields
        if interaction_request.get("type") == "dogma_response":
            if (
                "transaction_id" not in interaction_request
                and "selected_cards" not in interaction_request
            ):
                logger.warning(
                    "Invalid dogma_response: missing transaction_id and selected_cards"
                )
                return False
        # If this is a StandardInteractionBuilder DogmaInteractionRequest
        elif interaction_request.get("type") == "dogma_interaction":
            required_fields = [
                "type",
                "game_id",
                "player_id",
                "interaction_type",
                "data",
            ]
            for field in required_fields:
                if field not in interaction_request:
                    logger.warning(
                        f"Invalid StandardInteractionBuilder request: missing required field '{field}'"
                    )
                    return False
        else:
            # Legacy interaction_request format
            required_fields = ["id", "player_id", "type", "data", "message"]
            missing_fields = [
                field for field in required_fields if field not in interaction_request
            ]

            if missing_fields:
                logger.warning(
                    f"Legacy interaction_request missing fields {missing_fields} - continuing anyway for compatibility"
                )
                critical_fields = ["player_id", "type", "data"]
                if any(field in missing_fields for field in critical_fields):
                    return False

        # Validate interaction type
        if interaction_request.get("type") == "dogma_interaction":
            interaction_type = safe_get(interaction_request, "interaction_type")
        else:
            interaction_type = safe_get(interaction_request, "type")

        valid_types = [
            "select_cards",
            "select_achievement",
            "choose_option",
            "return_cards",
            "select_color",
            "select_symbol",
            "choose_highest_tie",
            "dogma_response",
        ]

        if interaction_type not in valid_types:
            logger.warning(
                f"Unknown interaction type '{interaction_type}' (continuing anyway)"
            )

        # Validate data structure
        data = interaction_request["data"]
        if not isinstance(data, dict):
            logger.warning(
                f"Invalid interaction_request.data: expected dict, got {type(data)}"
            )
            return False

        if data.get("type") == "dogma_interaction":
            if "data" not in data:
                logger.warning(
                    "StandardInteractionBuilder message missing inner 'data' field"
                )
                return False
            inner_data = data.get("data", {})
            if not isinstance(inner_data, dict):
                logger.warning(
                    f"StandardInteractionBuilder inner data must be dict, got {type(inner_data)}"
                )
                return False
            return True
        else:
            logger.debug(
                f"Non-StandardInteractionBuilder message type: {data.get('type')} (allowing for compatibility)"
            )

        if "data" not in data:
            logger.warning(
                "Invalid StandardInteractionBuilder message: missing 'data' field"
            )
            return False

        # Try comprehensive validation
        try:
            from interaction.builder import StandardInteractionBuilder

            is_valid, error = StandardInteractionBuilder.validate_interaction_request(
                data
            )
            if not is_valid:
                logger.warning(
                    f"StandardInteractionBuilder validation warning (continuing anyway): {error}"
                )
            return True
        except ImportError as e:
            logger.warning(
                f"StandardInteractionBuilder not available for comprehensive validation: {e}"
            )
            return True
        except Exception as e:
            logger.warning(
                f"Error during interaction request validation (continuing anyway): {e}"
            )
            return True

    async def create_interaction_message(
        self, interaction_request: dict, result: dict, game_id: str
    ) -> dict:
        """Create interaction message matching WebSocket contract specification."""
        # Handle Pydantic DogmaInteractionRequest objects
        if hasattr(interaction_request, "model_dump"):
            try:
                interaction_request = interaction_request.model_dump(mode="json")
            except Exception as e:
                logger.warning(f"Failed to convert Pydantic object to dict: {e}")

        if "data" not in interaction_request:
            logger.error("interaction_request missing 'data' field")
            # Fallback
            return {
                "type": "dogma_interaction",
                "data": {
                    "interaction_type": result.get(
                        "interaction_type", "player_selection"
                    ),
                    "transaction_id": result.get("transaction_id"),
                    "interaction": {
                        "player_id": safe_get(interaction_request, "player_id"),
                        "message": "Interaction required",
                        "card_name": None,
                        "data": {},
                    },
                    "game_state": result.get(
                        "game_state", self.game_manager.get_game(game_id).to_dict()
                    ),
                },
            }

        builder_message = safe_get(interaction_request, "data", {})
        selection_data = builder_message.get("data", {})

        # VALIDATION
        try:
            is_valid, validation_error = self.validate_outgoing_interaction(
                selection_data
            )
            if not is_valid:
                logger.error(
                    f"Outgoing interaction validation failed: {validation_error}"
                )
        except Exception as e:
            logger.warning(f"Validation check failed: {e}")

        # Create message
        final_message = {
            "type": "dogma_interaction",
            "data": {
                "interaction_type": result.get("interaction_type", "player_selection"),
                "transaction_id": result.get("transaction_id"),
                "interaction": {
                    "player_id": safe_get(interaction_request, "player_id"),
                    "message": safe_get(interaction_request, "message", ""),
                    "card_name": result.get("card_name"),
                    "data": selection_data,
                },
                "game_state": result.get(
                    "game_state", self.game_manager.get_game(game_id).to_dict()
                ),
            },
        }

        logger.debug(
            f"Created interaction message: type={final_message['data']['interaction_type']}, "
            f"target={final_message['data']['interaction']['player_id']}, "
            f"transaction_id={final_message['data']['transaction_id']}"
        )

        return final_message

    async def broadcast_interaction_message(
        self, final_message: dict, game_id: str
    ) -> None:
        """Log and broadcast interaction message to all players in game."""
        logger.info(f"Sending direct interaction message: {final_message['type']}")
        await self.connection_manager.broadcast_to_game(
            json.dumps(final_message), game_id
        )
