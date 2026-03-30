import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    Field,
    computed_field,
    field_validator,
    model_serializer,
    model_validator,
)

from .card import Card
from .deck_manager import DeckManager
from .expansion import ExpansionConfig
from .player import Player
from .score_manager import ScoreManager


logger = logging.getLogger(__name__)

# Import for type hints only (avoid circular import at runtime)
TYPE_CHECKING = False
if TYPE_CHECKING:
    pass


class GamePhase(str, Enum):
    WAITING_FOR_PLAYERS = "waiting_for_players"
    SETUP_CARD_SELECTION = "setup_card_selection"
    PLAYING = "playing"
    FINISHED = "finished"


class ActionType(str, Enum):
    DRAW = "draw"
    MELD = "meld"
    DOGMA = "dogma"
    ACHIEVE = "achieve"
    END_TURN = "end_turn"
    SETUP_SELECTION = "setup_selection"
    TURN_START = "turn_start"


class ActionLogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    player_name: str
    action_type: ActionType
    description: str
    turn_number: int
    # Enhanced fields for dogma debugging
    phase_name: str | None = None
    context_snapshot: dict | None = None
    transaction_id: str | None = None
    # State tracking for detailed action logs
    state_changes: list[dict] = Field(default_factory=list)

    def get_description_for_player(self, player_id: str | None = None) -> str:
        """Generate privacy-filtered description for specific player"""
        if not self.state_changes:
            return self.description

        try:
            from dogma_v2.state_tracker import StateChangeTracker

            tracker = StateChangeTracker.from_dict_list(self.state_changes)
            narrative = tracker.generate_narrative(viewing_player_id=player_id)
            return narrative if narrative else self.description
        except Exception:
            return self.description


class PendingDogmaAction(BaseModel):
    """Represents a dogma action waiting for player input"""

    card_name: str
    effect_index: int
    original_player_id: str  # Player who activated the dogma
    target_player_id: str  # Player who needs to respond
    action_type: str  # "transfer_card", "choose_card", etc.
    context: dict[str, Any] = Field(default_factory=dict)  # Additional data needed

    def to_serializable_dict(self) -> dict[str, Any]:
        """Convert to a dictionary safe for JSON serialization"""
        # Use Pydantic's built-in serialization
        data = self.model_dump(mode="json")

        # Extra safety for context field to handle potential circular refs
        if "context" in data:
            data["context"] = self._sanitize_value(data["context"])

        return data

    @staticmethod
    def _sanitize_value(value: Any, seen: set | None = None, depth: int = 0) -> Any:
        """Recursively sanitize values to prevent circular references"""
        if depth > 10:  # Reasonable depth limit
            return str(value)

        if seen is None:
            seen = set()

        # Handle primitives
        if value is None or isinstance(value, str | int | float | bool):
            return value

        # Handle circular refs
        obj_id = id(value)
        if obj_id in seen:
            return f"<circular reference {type(value).__name__}>"

        seen.add(obj_id)
        try:
            if isinstance(value, dict):
                return {
                    k: PendingDogmaAction._sanitize_value(v, seen, depth + 1)
                    for k, v in value.items()
                }
            elif isinstance(value, list | tuple):
                return [
                    PendingDogmaAction._sanitize_value(v, seen, depth + 1)
                    for v in value
                ]
            elif hasattr(value, "model_dump"):
                return PendingDogmaAction._sanitize_value(
                    value.model_dump(mode="json"), seen, depth + 1
                )
            elif hasattr(value, "__dict__"):
                return str(value)  # Fallback for arbitrary objects
            else:
                return value
        finally:
            seen.remove(obj_id)


class PendingMeldInteraction(BaseModel):
    """Represents a meld action waiting for player interaction (Cities expansion: Search icon)"""

    player_id: str  # Player who melded the city
    city_card_id: str  # City card that was melded
    icon_index: int  # Which icon is pending interaction
    icon_data: dict[str, Any] = Field(
        default_factory=dict
    )  # State needed to resume icon resolution
    messages_so_far: list[str] = Field(
        default_factory=list
    )  # Messages from icons processed before suspension


class GameState(BaseModel):
    current_player_index: int = 0
    actions_remaining: int = 2
    current_action: ActionType | None = None
    pending_dogma_action: PendingDogmaAction | None = None
    pending_meld_interaction: PendingMeldInteraction | None = (
        None  # Cities: Meld action waiting for icon interaction
    )
    original_player_index: int | None = (
        None  # Backup of player before dogma interaction
    )
    setup_selections_made: list[str] = Field(
        default_factory=list
    )  # Track which players have made setup selections
    first_player_index: int | None = None  # Track who went first (for action count)
    players_who_have_taken_first_turn: list[int] = Field(
        default_factory=list
    )  # Track which players have had their first turn

    # Additional state tracking for Dogma v2 system
    current_age: int = 1  # Track the current age being drawn from
    actions_taken: int = 0  # Track total actions taken in game (for statistics)
    turn_number: int = 1  # Track the current turn number for action log

    # Cities expansion state tracking
    endorse_used_this_turn: bool = False  # Track if endorse has been used this turn


class Game(BaseModel):
    game_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    players: list[Player] = Field(default_factory=list)
    phase: GamePhase = GamePhase.WAITING_FOR_PLAYERS
    state: GameState = Field(default_factory=GameState)

    # Expansion configuration
    expansion_config: ExpansionConfig = Field(default_factory=ExpansionConfig)

    # Card piles managed by DeckManager
    deck_manager: DeckManager = Field(default_factory=DeckManager)

    # Artifacts expansion: Artifact decks, museums, and dig events
    artifact_decks: dict[int, list[Card]] = Field(
        default_factory=dict
    )  # Age -> artifact cards
    museum_supply: list = Field(
        default_factory=list
    )  # Available museums (list[Museum])
    pending_dig_events: list[dict] = Field(
        default_factory=list
    )  # Dig events waiting for player choice

    # Figures expansion: Event bus for karma/auspice/echo events
    _event_bus: Any = None  # GameEventBus instance (lazily initialized)

    # Action log with rotation settings
    action_log: list[ActionLogEntry] = Field(default_factory=list)
    MAX_ACTION_LOG_SIZE: int = 100  # Keep last 100 actions in memory
    archived_log_count: int = 0  # Track how many logs have been archived

    # Performance optimization: track total actions to avoid O(n²) turn calculation
    total_actions: int = Field(default=0)

    # Activity tracking for cleanup
    last_activity: datetime = Field(default_factory=datetime.now)

    # Game settings
    max_players: int = 4
    min_players: int = 2
    winner: Player | None = None

    # Transaction system for undo/rollback support
    pending_transaction: dict | None = None
    transaction_history: list[dict] = Field(default_factory=list)
    MAX_TRANSACTION_HISTORY: int = 50  # Keep last 50 transactions

    # Pydantic validators
    @field_validator("expansion_config", mode="before")
    @classmethod
    def validate_expansion_config(cls, v):
        """Convert dict to ExpansionConfig if needed during deserialization.

        This is critical for Redis loading where expansion_config is stored as dict.
        Without this validator, Pydantic will fail to properly deserialize from Redis.
        """
        if isinstance(v, dict):
            return ExpansionConfig.from_dict(v)
        return v

    @model_validator(mode="before")
    @classmethod
    def deserialize_flattened_decks(cls, data: Any) -> Any:
        """Handle deserialization from old format (flattened deck fields)."""
        if isinstance(data, dict):
            # Check if deck fields exist at root level
            deck_fields = [
                "age_decks",
                "cities_decks",
                "unseen_decks",
                "achievement_cards",
                "special_achievements",
                "special_achievements_available",
                "special_achievements_junk",
                "junk_pile",
            ]

            # If any deck field is present at root, move it to deck_manager
            if any(f in data for f in deck_fields):
                deck_data = {}
                for field in deck_fields:
                    if field in data:
                        deck_data[field] = data.pop(field)

                # If deck_manager already exists (partial update?), merge or overwrite
                # But usually we are loading full state.
                if "deck_manager" not in data:
                    data["deck_manager"] = deck_data
                else:
                    # If both exist, deck_manager takes precedence, or we merge?
                    # Assuming clean load, just set it.
                    if isinstance(data["deck_manager"], dict):
                        data["deck_manager"].update(deck_data)

        return data

    @model_serializer(mode="wrap")
    def serialize_flattened_decks(self, handler) -> dict[str, Any]:
        """Serialize with flattened deck fields for backward compatibility."""
        dumped = handler(self)

        # Flatten deck_manager fields to root
        if "deck_manager" in dumped:
            deck_data = dumped.pop("deck_manager")
            if isinstance(deck_data, dict):
                # Ensure special achievement fields are included even if empty
                if "special_achievements_available" not in deck_data:
                    deck_data["special_achievements_available"] = self.deck_manager.special_achievements_available
                if "special_achievements_junk" not in deck_data:
                    deck_data["special_achievements_junk"] = self.deck_manager.special_achievements_junk
                dumped.update(deck_data)

        return dumped

    # No need for custom __init__ anymore - Pydantic handles game_id generation

    @computed_field
    @property
    def current_player(self) -> Player | None:
        """Get the current player based on the game state"""
        if not self.players or self.state.current_player_index >= len(self.players):
            return None
        return self.players[self.state.current_player_index]

    @computed_field
    @property
    def current_player_name(self) -> str | None:
        """Get the current player's name"""
        player = self.current_player
        return player.name if player else None

    @property
    def event_bus(self):
        """Get or create the event bus for karma effects (Figures expansion)"""
        if self._event_bus is None and self.is_expansion_enabled("figures"):
            from game_logic.events import GameEventBus

            self._event_bus = GameEventBus()
            logger.info("Initialized GameEventBus for Figures expansion")
        return self._event_bus

    @property
    def score_manager(self) -> ScoreManager:
        """Get the score manager instance"""
        return ScoreManager(self.expansion_config)

    @property
    def achievement_cards(self) -> dict[int, list[Card]]:
        """Compatibility property: proxies to deck_manager.achievement_cards"""
        return self.deck_manager.achievement_cards

    @achievement_cards.setter
    def achievement_cards(self, value: dict[int, list[Card]]) -> None:
        """Compatibility setter: proxies to deck_manager.achievement_cards"""
        self.deck_manager.achievement_cards = value

    @property
    def junk_pile(self) -> list[Card]:
        """Compatibility property: proxies to deck_manager.junk_pile"""
        return self.deck_manager.junk_pile

    @junk_pile.setter
    def junk_pile(self, value: list[Card]) -> None:
        """Compatibility setter: proxies to deck_manager.junk_pile"""
        self.deck_manager.junk_pile = value

    def can_join(self) -> bool:
        """Check if the game can accept new players"""
        return (
            self.phase == GamePhase.WAITING_FOR_PLAYERS
            and len(self.players) < self.max_players
        )

    def add_player(self, player: Player):
        """Add a player to the game"""
        if self.can_join():
            self.players.append(player)
            return True
        return False

    def get_player_by_id(self, player_id: str) -> Player | None:
        """Find a player by their ID"""
        for player in self.players:
            if player.id == player_id:
                return player
        return None

    def can_start(self) -> bool:
        """Check if the game can be started"""
        return (
            self.phase == GamePhase.WAITING_FOR_PLAYERS
            and len(self.players) >= self.min_players
        )

    def start_game(self):
        """Start the game by dealing initial cards to players"""
        if not self.can_start():
            raise ValueError("Cannot start game")

        self.phase = GamePhase.SETUP_CARD_SELECTION

        # Set up the decks first (this loads all cards)
        # Set up the decks first (this loads all cards)
        self.setup_decks()

        # Initialize expansion zones for all players
        self._initialize_player_expansion_zones()

        # Deal two cards from age 1 to each player for setup selection
        # Use the already-loaded age 1 deck
        for player in self.players:
            for _ in range(2):
                card = self.draw_card(1)
                if card:
                    player.hand.append(card)

    def make_setup_selection_by_id(self, player_id: str, card_id: str):
        """Handle a player's setup card selection using card ID"""
        if self.phase != GamePhase.SETUP_CARD_SELECTION:
            raise ValueError("Not in setup phase")

        player = self.get_player_by_id(player_id)
        if not player:
            raise ValueError("Player not found")

        # Find the card in player's hand by ID
        card_to_meld = None
        for card in player.hand:
            if card.card_id == card_id:
                card_to_meld = card
                break

        if not card_to_meld:
            raise ValueError(f"Card with ID {card_id} not found in hand")

        # Remove card from hand and meld it to board
        player.hand.remove(card_to_meld)

        # ARTIFACTS EXPANSION: Check for dig events before melding
        # Get the card that will be covered (if any)
        color_stack = player.board.get_cards_by_color(str(card_to_meld.color.value))
        covered_card = None
        if color_stack:
            # The top card of the stack will be covered by the new meld
            covered_card = color_stack[-1]

        # Perform the meld
        player.board.add_card(card_to_meld)

        # ARTIFACTS EXPANSION: Detect dig event after meld
        if self.expansion_config.is_enabled("artifacts"):
            from game_logic.artifacts.dig_event_detector import DigEventDetector

            dig_age = DigEventDetector.check_dig_event(
                game=self,
                melded_card=card_to_meld,
                covered_card=covered_card,
                player_id=player.id,
            )

            if dig_age is not None:
                # Store dig event for handling by async_game_manager
                if not hasattr(self, "pending_dig_events"):
                    self.pending_dig_events = []

                dig_event = {
                    "dig_age": dig_age,
                    "player_id": player.id,
                    "melded_card": card_to_meld.name,
                    "covered_card": covered_card.name if covered_card else None,
                }
                self.pending_dig_events.append(dig_event)

        # Mark player as having made their selection
        player.setup_selection_made = True

        # Add log entry
        self.add_log_entry(
            player.name,
            ActionType.MELD,
            f"Selected and melded {card_to_meld.name} during setup",
        )

        # Check if all players have made their selections
        all_selected = all(p.setup_selection_made for p in self.players)
        if all_selected:
            self.complete_setup()

    def complete_setup(self):
        """Complete the setup phase and transition to playing"""
        # Decks are already set up in start_game(), no need to do it again

        # Determine first player based on alphabetically lowest melded card
        first_player_index = 0
        lowest_card_name = None

        for i, player in enumerate(self.players):
            # Get all melded cards from the player's board
            melded_cards = []
            melded_cards.extend(player.board.blue_cards)
            melded_cards.extend(player.board.red_cards)
            melded_cards.extend(player.board.green_cards)
            melded_cards.extend(player.board.yellow_cards)
            melded_cards.extend(player.board.purple_cards)

            if melded_cards:
                card_name = melded_cards[
                    0
                ].name  # There should be exactly one melded card
                if lowest_card_name is None or card_name < lowest_card_name:
                    lowest_card_name = card_name
                    first_player_index = i

        # Initialize state for first turn - first player starts with only 1 action
        self.state.current_player_index = first_player_index
        self.state.first_player_index = first_player_index  # Track who went first
        self.state.actions_remaining = 1
        self.phase = GamePhase.PLAYING

        # Add initial log entry
        first_player = self.players[first_player_index]
        self.add_log_entry(
            first_player.name,
            ActionType.TURN_START,
            f"Game started - {first_player.name} begins with 1 action (melded {lowest_card_name})",
        )

    def can_make_setup_selection(self, player_id: str) -> bool:
        """Check if a player can make a setup selection"""
        if self.phase != GamePhase.SETUP_CARD_SELECTION:
            return False

        player = self.get_player_by_id(player_id)
        return player is not None and not player.setup_selection_made

    def setup_decks(self):
        """Set up the age decks for the game"""
        self.deck_manager.setup_decks(self.expansion_config)

        # ARTIFACTS EXPANSION: Load artifact decks if enabled
        if self.expansion_config.is_enabled("artifacts"):
            from data.artifact_loader import load_artifacts_for_game
            from models.museum import create_museum_supply

            self.artifact_decks = load_artifacts_for_game(shuffle=True)
            logger.info(
                f"Loaded {sum(len(cards) for cards in self.artifact_decks.values())} "
                f"artifact cards across {len(self.artifact_decks)} ages"
            )

            # Initialize museum supply
            self.museum_supply = create_museum_supply()
            logger.info(f"Initialized {len(self.museum_supply)} museums")

    def _initialize_player_expansion_zones(self):
        """Initialize expansion-specific zones for all players based on enabled expansions."""
        for player in self.players:
            # ARTIFACTS EXPANSION: Museums are in game.museum_supply (shared), not per-player
            # Player museums list starts empty and gets populated when they claim museums
            # No initialization needed here - museum_supply already initialized in setup_decks()

            # UNSEEN EXPANSION: Initialize Safe
            if self.expansion_config.is_enabled("unseen"):
                if not player.safe:
                    from models.safe import Safe

                    player.safe = Safe(player_id=player.id)
                    logger.debug(f"Initialized Safe for {player.name}")

            # ECHOES EXPANSION: Initialize Forecast Zone
            if self.expansion_config.is_enabled("echoes"):
                if not player.forecast_zone:
                    from models.forecast_zone import ForecastZone

                    player.forecast_zone = ForecastZone(player_id=player.id)
                    logger.debug(f"Initialized Forecast Zone for {player.name}")

    def _setup_unseen_decks(self):
        """Deprecated: Handled by DeckManager"""
        pass

    def next_turn(self):
        """Advance to the next player's turn"""
        self.state.current_player_index = (self.state.current_player_index + 1) % len(
            self.players
        )
        self.state.actions_remaining = 2  # Subsequent players get 2 actions per turn

        # UNSEEN EXPANSION: Reset first draw tracking for all players
        if self.expansion_config.is_enabled("unseen"):
            for player in self.players:
                player.reset_draw_tracking()
            logger.debug("Reset first draw tracking for all players (Unseen expansion)")

    def draw_card(self, age: int) -> Card | None:
        """Draw a card from the specified age deck, skipping to higher ages if empty"""
        card = self.deck_manager.draw_card(age)

        if not card:
            # No cards available in any age
            self.end_game_by_age_exhaustion()
            return None

        return card

    def end_game_by_age_exhaustion(self):
        """End the game when all age decks are exhausted"""
        self.phase = GamePhase.FINISHED

        self.winner = self.score_manager.check_score_victory(self.players)

    def return_card(self, card: Card, age: int):
        """Return a card to the bottom of its age deck"""
        self.deck_manager.return_card(card, age)

    def is_expansion_enabled(self, expansion: str) -> bool:
        """Check if an expansion is enabled for this game.

        Args:
            expansion: Expansion name ("cities", "artifacts", etc.)

        Returns:
            bool: True if expansion is enabled
        """
        return self.expansion_config.is_enabled(expansion)

    def get_achievements_needed_for_victory(self) -> int:
        """Calculate achievements needed for victory based on player count and expansions.

        Formula from official rules: 8 - (# of Players) + (# of Expansions), minimum 3

        Returns:
            int: Number of achievements needed to win
        """
        return self.score_manager.get_achievements_needed_for_victory(len(self.players))

    def check_victory_conditions(self) -> bool:
        """Check if an achievement victory has been met.

        Score victory is determined only when the game ends due to
        age exhaustion (handled in draw/end logic), not here.
        """
        winner = self.score_manager.check_achievement_victory(self.players)
        if winner:
            self.winner = winner
            self.phase = GamePhase.FINISHED
            return True

        return False

    def check_score_victory(self, player: Player) -> bool:
        """Deprecated: Score victory is only determined on age exhaustion."""
        return False

    def add_log_entry(
        self,
        player_name: str,
        action_type: ActionType,
        description: str,
        phase_name: str | None = None,
        context_snapshot: dict | None = None,
        transaction_id: str | None = None,
        state_changes: list[dict] | None = None,
    ):
        """Add an entry to the action log with rotation to prevent unbounded growth"""
        self.total_actions += 1

        # Use actual turn number from game state, not calculated from actions
        turn_number = getattr(self.state, "turn_number", 1)

        log_entry = ActionLogEntry(
            player_name=player_name,
            action_type=action_type,
            description=description,
            turn_number=turn_number,
            phase_name=phase_name,
            context_snapshot=context_snapshot,
            transaction_id=transaction_id,
            state_changes=state_changes or [],
        )
        self.action_log.append(log_entry)

        # Implement rotation if log exceeds maximum size
        if len(self.action_log) > self.MAX_ACTION_LOG_SIZE:
            # Archive oldest entries (keep 75% of max size after rotation)
            keep_count = int(self.MAX_ACTION_LOG_SIZE * 0.75)
            archived_count = len(self.action_log) - keep_count

            # Track archived logs for potential future retrieval
            self.archived_log_count += archived_count

            # Keep only the most recent entries
            self.action_log = self.action_log[-keep_count:]

            logger.info(
                f"Rotated action log: archived {archived_count} entries, "
                f"kept {keep_count} recent entries (total archived: {self.archived_log_count})"
            )

        logger.debug(
            f"Added log entry #{self.total_actions}: {player_name} - {description}"
        )

    def get_log_summary(self) -> dict:
        """Get a summary of action log status"""
        return {
            "current_entries": len(self.action_log),
            "archived_entries": self.archived_log_count,
            "total_entries": self.total_actions,
            "max_size": self.MAX_ACTION_LOG_SIZE,
            "oldest_turn": self.action_log[0].turn_number if self.action_log else None,
            "newest_turn": self.action_log[-1].turn_number if self.action_log else None,
        }

    def start_transaction(self, player_id: str, action_type: str) -> str:
        """
        Start a new transaction for undo/rollback support.

        Creates a snapshot of the current game state that can be restored
        if the player chooses to undo the action.

        Args:
            player_id: ID of player starting the action
            action_type: Type of action (draw, meld, dogma, achieve)

        Returns:
            transaction_id: Unique identifier for this transaction
        """
        transaction_id = str(uuid.uuid4())
        self.pending_transaction = {
            "id": transaction_id,
            "player_id": player_id,
            "action_type": action_type,
            "snapshot": self._create_snapshot(),
            "started_at": datetime.now(),
        }
        logger.debug(f"Started transaction {transaction_id} for {action_type}")
        return transaction_id

    def commit_transaction(self):
        """
        Commit the pending transaction.

        Moves the transaction to history and marks it as permanent.
        All action log entries associated with this transaction are finalized.
        """
        if not self.pending_transaction:
            logger.warning("No pending transaction to commit")
            return

        transaction_id = self.pending_transaction["id"]

        # Add to history (with rotation)
        self.transaction_history.append(self.pending_transaction)
        if len(self.transaction_history) > self.MAX_TRANSACTION_HISTORY:
            # Keep only recent history
            keep_count = int(self.MAX_TRANSACTION_HISTORY * 0.75)
            self.transaction_history = self.transaction_history[-keep_count:]
            logger.debug(f"Rotated transaction history, keeping {keep_count} entries")

        # Clear pending
        self.pending_transaction = None

        logger.debug(f"Committed transaction {transaction_id}")

    def rollback_transaction(self):
        """
        Rollback the pending transaction.

        Restores the game state to the snapshot taken when the transaction started.
        Removes all action log entries created during the transaction.
        """
        if not self.pending_transaction:
            logger.warning("No pending transaction to rollback")
            return

        transaction_id = self.pending_transaction["id"]

        # Restore game state from snapshot
        try:
            self._restore_snapshot(self.pending_transaction["snapshot"])
            logger.info(f"Rolled back transaction {transaction_id}")
        except Exception as e:
            logger.error(
                f"Failed to rollback transaction {transaction_id}: {e}", exc_info=True
            )
            raise

        # Clear pending transaction
        self.pending_transaction = None

    def _create_snapshot(self) -> dict:
        """
        Create a complete snapshot of the current game state for rollback.

        Returns:
            dict: Serialized game state including all players, cards, and state
        """

        return {
            "players": [p.model_dump(mode="json") for p in self.players],
            "expansion_config": self.expansion_config.to_dict(),
            "state": self.state.model_dump(mode="json"),
            "deck_manager": self.deck_manager.model_dump(mode="json"),
            "action_log": [entry.model_dump(mode="json") for entry in self.action_log],
            "total_actions": self.total_actions,
            "archived_log_count": self.archived_log_count,
        }

    def _restore_snapshot(self, snapshot: dict):
        """
        Restore game state from a snapshot.

        Args:
            snapshot: Previously created snapshot from _create_snapshot()
        """
        # Restore players
        self.players = [Player.model_validate(p) for p in snapshot["players"]]

        # Restore state
        self.state = GameState.model_validate(snapshot["state"])

        # Restore decks (DeckManager)
        if "deck_manager" in snapshot:
            self.deck_manager = DeckManager.model_validate(snapshot["deck_manager"])
        else:
            # Legacy snapshot support (if needed, or just fail gracefully)
            # Attempt to reconstruct DeckManager from legacy fields if present
            # This is a fallback for old snapshots
            try:
                legacy_data = {}
                if "age_decks" in snapshot:
                    legacy_data["age_decks"] = snapshot["age_decks"]
                if "achievement_cards" in snapshot:
                    legacy_data["achievement_cards"] = snapshot["achievement_cards"]
                if "junk_pile" in snapshot:
                    legacy_data["junk_pile"] = snapshot["junk_pile"]

                if legacy_data:
                    self.deck_manager = DeckManager.model_validate(legacy_data)
            except Exception as e:
                logger.warning(f"Failed to restore legacy deck state: {e}")
                # Initialize empty if failed
                self.deck_manager = DeckManager()

        # Restore expansion config
        if "expansion_config" in snapshot:
            from .expansion import ExpansionConfig

            self.expansion_config = ExpansionConfig.from_dict(
                snapshot["expansion_config"]
            )
        else:
            from .expansion import ExpansionConfig

            self.expansion_config = ExpansionConfig()  # Default to no expansions

        # Restore action log
        if "action_log" in snapshot:
            self.action_log = [
                ActionLogEntry.model_validate(entry) for entry in snapshot["action_log"]
            ]
        else:
            self.action_log = []

        # Restore counters
        self.total_actions = snapshot.get("total_actions", 0)
        self.archived_log_count = snapshot.get("archived_log_count", 0)

        logger.debug("Restored game state from snapshot")

    def _validate_serialization_safety(self, obj, path=""):
        """
        Validate that an object is safe for JSON serialization.

        This method recursively checks for non-serializable objects that could
        contaminate the game state, particularly immutable objects from DogmaContext
        like FrozenDict or SharingContext.

        Args:
            obj: Object to validate
            path: Current path for debugging (e.g., "state.setup_selections_made")

        Raises:
            ValueError: If non-serializable objects are detected
        """
        # Check for known problematic types
        type_name = type(obj).__name__

        # FrozenDict from DogmaContext should never be in game state
        if type_name == "FrozenDict":
            raise ValueError(
                f"FrozenDict detected in game state at {path} - immutable objects from DogmaContext are contaminating persistent state"
            )

        # SharingContext should never be in game state
        if type_name == "SharingContext":
            raise ValueError(
                f"SharingContext detected in game state at {path} - sharing context should not enter persistent state"
            )

        # Check for other frozen/immutable dataclasses
        if hasattr(obj, "__dataclass_fields__") and getattr(obj, "__frozen__", False):
            # This is a frozen dataclass - likely from DogmaContext
            raise ValueError(
                f"Frozen dataclass {type_name} detected in game state at {path} - immutable objects should not enter persistent state"
            )

        # Recursively check containers
        if isinstance(obj, dict):
            for key, value in obj.items():
                self._validate_serialization_safety(
                    value, f"{path}.{key}" if path else str(key)
                )
        elif isinstance(obj, list | tuple):
            for i, value in enumerate(obj):
                self._validate_serialization_safety(
                    value, f"{path}[{i}]" if path else f"[{i}]"
                )
        elif hasattr(obj, "__dict__"):
            # Check object attributes (for complex objects)
            for attr_name, attr_value in vars(obj).items():
                if not attr_name.startswith("_"):  # Skip private attributes
                    self._validate_serialization_safety(
                        attr_value, f"{path}.{attr_name}" if path else attr_name
                    )

    def _format_state_changes_for_display(
        self,
        state_changes: list[dict],
        player_id: str | None = None,
    ) -> list[dict]:
        """
        Format state_changes with description field for frontend display.

        Args:
            state_changes: Raw state_changes from action log entry
            player_id: Viewing player ID for privacy filtering (None = public view)

        Returns:
            List of formatted changes with description field
        """
        if not state_changes:
            logger.debug("FORMAT: Empty state_changes input, returning []")
            return []

        try:
            from dogma_v2.state_tracker import StateChangeTracker

            logger.debug(f"FORMAT: Processing {len(state_changes)} state_changes")
            # Log first entry structure for debugging
            if state_changes:
                import json

                logger.debug(
                    f"FORMAT: First entry structure: {json.dumps(state_changes[0], indent=2)}"
                )

            # Reconstruct tracker from serialized data
            tracker = StateChangeTracker.from_dict_list(state_changes)
            formatted = []

            logger.debug(
                f"FORMAT: Tracker reconstructed with {len(tracker.changes)} changes"
            )

            for i, change in enumerate(tracker.changes):
                # Get formatted description with privacy filtering
                description = tracker._format_change(
                    change, viewing_player_id=player_id
                )

                logger.debug(
                    f"FORMAT: Change {i}: description={'<present>' if description else None}, change_type={change.change_type}"
                )

                # None means filtered out for privacy (e.g., owner-only draw for other players)
                if description:
                    formatted.append(
                        {
                            "description": description,
                            "change_type": change.change_type,
                            "visibility": change.visibility.value,
                            "context": change.context,
                        }
                    )

            logger.debug(
                f"FORMAT: Returning {len(formatted)} formatted changes (from {len(state_changes)} input)"
            )
            return formatted
        except Exception as e:
            # Fallback: return original data if formatting fails
            logger.warning(f"Failed to format state_changes: {e}", exc_info=True)
            return state_changes

    def to_dict(self, viewer_id: str | None = None):
        """
        Serialize game state to dictionary.

        Args:
            viewer_id: Optional player ID for privacy filtering (Unseen expansion Safes)
        """
        logger.debug(
            f"Serializing game {self.game_id} with {len(self.action_log)} action log entries"
        )

        # CRITICAL: Validate that no immutable objects from DogmaContext have leaked into game state
        # This prevents FrozenDict serialization errors that corrupt Redis data
        try:
            self._validate_serialization_safety(self, "game")
        except ValueError as e:
            logger.error(f"Serialization safety validation failed: {e}")
            # In production, we might want to raise this error to prevent corruption
            # For now, log and continue to maintain backward compatibility
            logger.warning("Continuing with serialization despite validation failure")

        result = {
            "game_id": self.game_id,
            "players": [
                player.to_dict(
                    include_computed=True,
                    achievement_cards=self.deck_manager.achievement_cards,
                    viewer_id=viewer_id,  # UNSEEN: Pass viewer_id for Safe filtering
                )
                for player in self.players
            ],
            "phase": self.phase.value,
            "expansion_config": self.expansion_config.to_dict(),
            "current_player_index": self.state.current_player_index,  # Root level for frontend
            "actions_remaining": self.state.actions_remaining,  # Root level for frontend
            "state": {
                "current_player_index": self.state.current_player_index,
                "actions_remaining": self.state.actions_remaining,
                "current_action": (
                    self.state.current_action.value
                    if self.state.current_action
                    else None
                ),
                "pending_dogma_action": (
                    self.state.pending_dogma_action.to_serializable_dict()
                    if self.state.pending_dogma_action
                    else None
                ),
                "original_player_index": self.state.original_player_index,
                # Add missing fields from GameState
                "setup_selections_made": list(
                    getattr(self.state, "setup_selections_made", [])
                ),
                "first_player_index": getattr(self.state, "first_player_index", None),
                "players_who_have_taken_first_turn": list(
                    getattr(self.state, "players_who_have_taken_first_turn", [])
                ),
                "current_age": getattr(self.state, "current_age", 1),
                "actions_taken": getattr(self.state, "actions_taken", 0),
                "turn_number": getattr(self.state, "turn_number", 1),
            },
            "current_player": (
                self.current_player.to_dict(
                    include_computed=True,
                    achievement_cards=self.deck_manager.achievement_cards,
                    viewer_id=viewer_id,  # UNSEEN: Pass viewer_id for Safe filtering
                )
                if self.current_player
                else None
            ),
            "current_player_id": (
                self.current_player.id if self.current_player else None
            ),
            "turn_number": getattr(self.state, "turn_number", 1),
            # ALWAYS include age_decks for proper serialization/deserialization
            "age_decks": {
                str(age): [card.to_dict() for card in cards]
                for age, cards in self.deck_manager.age_decks.items()
            },
            "age_deck_sizes": {
                age: len(cards) for age, cards in self.deck_manager.age_decks.items()
            },
            # UNSEEN EXPANSION: Include Unseen decks (hidden information - only sizes visible)
            "unseen_deck_sizes": (
                {
                    age: len(cards)
                    for age, cards in self.deck_manager.unseen_decks.items()
                }
                if hasattr(self.deck_manager, "unseen_decks")
                and self.deck_manager.unseen_decks
                else {}
            ),
            "achievement_cards": {
                str(age): [card.to_dict() for card in cards]
                for age, cards in self.deck_manager.achievement_cards.items()
            },
            "junk_pile": [card.to_dict() for card in self.deck_manager.junk_pile],
            "action_log": [
                {
                    "timestamp": entry.timestamp.isoformat(),
                    "player_name": entry.player_name,
                    "action_type": entry.action_type.value,
                    "description": entry.description,
                    "turn_number": entry.turn_number,
                    # Persist enhanced debug fields when available
                    "phase_name": entry.phase_name,
                    "context_snapshot": entry.context_snapshot,
                    "transaction_id": entry.transaction_id,
                    # CRITICAL FIX: Store raw state_changes for Redis, NOT formatted versions
                    # Formatting happens in get_game_state() API endpoint for frontend display
                    "state_changes": entry.state_changes,
                }
                for entry in self.action_log
            ],
            # Add missing fields
            "MAX_ACTION_LOG_SIZE": getattr(self, "MAX_ACTION_LOG_SIZE", 100),
            "archived_log_count": getattr(self, "archived_log_count", 0),
            "total_actions": getattr(self, "total_actions", 0),
            "last_activity": (
                self.last_activity.isoformat()
                if hasattr(self, "last_activity") and self.last_activity
                else None
            ),
            "max_players": self.max_players,
            "min_players": self.min_players,
            "winner": self.winner.to_dict() if self.winner else None,
            # Transaction state
            "current_transaction": (
                self.pending_transaction if self.pending_transaction else None
            ),
        }

        # Artifacts expansion: Add artifact decks and museums
        if self.artifact_decks:
            result["artifact_deck_sizes"] = {
                age: len(cards) for age, cards in self.artifact_decks.items()
            }
        else:
            result["artifact_deck_sizes"] = {}

        if self.museum_supply:
            from .museum import Museum

            result["museum_supply"] = [
                museum.to_dict() if isinstance(museum, Museum) else museum
                for museum in self.museum_supply
            ]
        else:
            result["museum_supply"] = []

        if self.pending_dig_events:
            result["pending_dig_events"] = self.pending_dig_events
        else:
            result["pending_dig_events"] = []

        return result
