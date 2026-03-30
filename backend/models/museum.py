"""Museum models for Artifacts expansion.

This module defines the Museum instance (runtime game state) and Museum definitions (static reference data).
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from .card import Card


@dataclass
class Museum:
    """
    Represents a Museum instance in a player's collection.

    This is a RUNTIME instance, not the static definition.
    Museum instances only store museum_id (reference) and current artifact (state).
    Static data (name, requirements) is looked up from MUSEUM_DEFINITIONS.
    """

    # Identification (references static museum card data)
    museum_id: str  # "masonry", "construction", "translation", "invention", "astronomy"

    # Current artifact (runtime state)
    artifact: Optional[Card] = None

    def has_artifact(self) -> bool:
        """Check if museum contains an artifact"""
        return self.artifact is not None

    def is_vacant(self) -> bool:
        """Check if museum is empty"""
        return self.artifact is None

    def get_definition(self) -> "MuseumDefinition":
        """Get static museum definition data"""
        return MUSEUM_DEFINITIONS[self.museum_id]

    def get_museum_name(self) -> str:
        """Get museum name from definition"""
        return self.get_definition().museum_name

    def validate_artifact_compatibility(self, artifact: Card) -> bool:
        """Validate that this museum can accept the given artifact"""
        if self.artifact is not None:
            return False  # Museum already has an artifact
        if not artifact.is_artifact():
            return False  # Only artifacts can be placed in museums
        return True

    def get_artifact_age(self) -> Optional[int]:
        """Get age of artifact in this museum, if any"""
        return self.artifact.age if self.artifact else None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "museum_id": self.museum_id,
            "museum_name": self.get_museum_name(),
            "artifact": self.artifact.to_dict() if self.artifact else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Museum":
        """Deserialize from dictionary"""
        artifact = None
        if data.get("artifact"):
            artifact = Card(**data["artifact"])

        return cls(museum_id=data["museum_id"], artifact=artifact)


@dataclass
class MuseumDefinition:
    """Static definition of a museum type (NOT a runtime instance)"""

    museum_id: str
    museum_name: str
    requirement_text: str
    alternate_claim_method: str
    display_order: int


# Museum static definitions (reference data - NOT game state)
MUSEUM_DEFINITIONS = {
    "masonry": MuseumDefinition(
        museum_id="masonry",
        museum_name="Masonry",
        requirement_text="3x Same Icon in a Color",
        alternate_claim_method="Three of the same icon visible in a single color stack",
        display_order=1,
    ),
    "construction": MuseumDefinition(
        museum_id="construction",
        museum_name="Construction",
        requirement_text="12x Any Icon",
        alternate_claim_method="Twelve total visible icons of any single type",
        display_order=2,
    ),
    "translation": MuseumDefinition(
        museum_id="translation",
        museum_name="Translation",
        requirement_text="5 Splays (Right or better)",
        alternate_claim_method="Five splayed stacks at Right, Up, or Aslant",
        display_order=3,
    ),
    "invention": MuseumDefinition(
        museum_id="invention",
        museum_name="Invention",
        requirement_text="5 Top Cards ≥ Age 8",
        alternate_claim_method="Five top cards each Age 8 or higher",
        display_order=4,
    ),
    "astronomy": MuseumDefinition(
        museum_id="astronomy",
        museum_name="Astronomy",
        requirement_text="2x Same Icon in 4 Colors",
        alternate_claim_method="Two of same icon visible in each of four different colors",
        display_order=5,
    ),
}


def create_museum_supply() -> list[Museum]:
    """Create initial museum supply (5 vacant museums)"""
    return [
        Museum(museum_id=museum_id, artifact=None)
        for museum_id in [
            "masonry",
            "construction",
            "translation",
            "invention",
            "astronomy",
        ]
    ]


# Museum achievement IDs (used when claiming museums as achievements)
# Museum achievement IDs are in the 1000+ range to avoid collisions
# with base game achievements (1-11) and future special achievements.
MUSEUM_ACHIEVEMENT_BASE_ID = 1000
MUSEUM_ACHIEVEMENT_IDS = {
    museum_id: MUSEUM_ACHIEVEMENT_BASE_ID + idx
    for idx, museum_id in enumerate(
        ["masonry", "construction", "translation", "invention", "astronomy"], start=1
    )
}


def get_museum_achievement_id(museum_id: str) -> int:
    """Get deterministic achievement ID for a museum."""
    return MUSEUM_ACHIEVEMENT_IDS.get(museum_id, MUSEUM_ACHIEVEMENT_BASE_ID)
