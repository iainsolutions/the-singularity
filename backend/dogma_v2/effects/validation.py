"""
Effect Validation and Metadata System.

This module provides comprehensive validation for effect configurations
and metadata about effect capabilities, ensuring proper effect setup
and providing debugging/development tools.
"""

import logging
from dataclasses import dataclass
from typing import Any, ClassVar

from .base import EffectType
from .factory import EffectFactory

logger = logging.getLogger(__name__)


@dataclass
class EffectMetadata:
    """Metadata about an effect configuration."""
    effect_type: str
    adapter_type: str
    effect_category: EffectType
    required_fields: set[str]
    optional_fields: set[str]
    validation_errors: list[str]
    validation_warnings: list[str]
    description: str
    complexity_score: int  # 1-10 scale based on configuration complexity


class EffectValidator:
    """
    Comprehensive effect validation system.

    Validates effect configurations, provides metadata,
    and offers debugging/development tools.
    """

    # Core required fields that all effects should have
    UNIVERSAL_REQUIRED_FIELDS: ClassVar[set[str]] = {'type'}

    # Common optional fields across many effects
    UNIVERSAL_OPTIONAL_FIELDS: ClassVar[set[str]] = {
        'description', 'condition', 'store_result', 'optional'
    }

    # Effect-specific validation rules
    EFFECT_VALIDATION_RULES: ClassVar[dict[str, dict[str, Any]]] = {
        # Interaction Effects
        'SelectCards': {
            'required': {'source'},
            'optional': {'min_count', 'max_count', 'criteria', 'message'},
            'validation': lambda cfg: EffectValidator._validate_select_cards(cfg)
        },
        'ChooseOption': {
            'required': {'options'},
            'optional': {'message', 'default_option'},
            'validation': lambda cfg: EffectValidator._validate_choose_option(cfg)
        },
        'SelectHighest': {
            'required': {'source'},
            'optional': {'criteria', 'message'},
            'validation': None
        },
        'SelectLowest': {
            'required': {'source'},
            'optional': {'criteria', 'message'},
            'validation': None
        },
        'SelectColor': {
            'required': set(),
            'optional': {'available_colors', 'message'},
            'validation': None
        },
        'SelectSymbol': {
            'required': set(),
            'optional': {'available_symbols', 'message'},
            'validation': None
        },
        'SelectAchievement': {
            'required': set(),
            'optional': {'max_age', 'criteria', 'message'},
            'validation': None
        },

        # Transfer Effects
        'DrawCards': {
            'required': {'age', 'count'},
            'optional': {'location', 'to_player'},
            'validation': lambda cfg: EffectValidator._validate_draw_cards(cfg)
        },
        'MeldCard': {
            'required': set(),
            'optional': {'selection', 'card', 'to_player'},
            'validation': None
        },
        'ScoreCards': {
            'required': set(),
            'optional': {'selection', 'source', 'count'},
            'validation': lambda cfg: EffectValidator._validate_score_cards(cfg)
        },
        'ArchiveCard': {
            'required': {'selection', 'under_card'},
            'optional': {'location'},
            'validation': None
        },
        'JunkCard': {
            'required': {'selection'},
            'optional': {'source'},
            'validation': None
        },
        'JunkCards': {
            'required': {'selection'},
            'optional': {'source', 'count'},
            'validation': None
        },
        'TransferCards': {
            'required': {'from_location', 'to_location'},
            'optional': {'count', 'selection'},
            'validation': None
        },
        'TransferBetweenPlayers': {
            'required': {'from_player', 'to_player', 'from_location', 'to_location'},
            'optional': {'count', 'selection'},
            'validation': None
        },
        'ExchangeCards': {
            'required': {'location1', 'location2'},
            'optional': {'count1', 'count2', 'selection1', 'selection2'},
            'validation': None
        },
        'ReturnCards': {
            'required': {'selection', 'to_location'},
            'optional': {'source'},
            'validation': None
        },

        # Board Effects
        'SplayCards': {
            'required': {'color', 'direction'},
            'optional': {'player'},
            'validation': lambda cfg: EffectValidator._validate_splay_cards(cfg)
        },
        'FilterCards': {
            'required': set(),
            'optional': {'criteria', 'filter', 'source'},
            'validation': lambda cfg: EffectValidator._validate_filter_cards(cfg)
        },
        'RevealAndProcess': {
            'required': {'source', 'actions'},
            'optional': {'count', 'criteria'},
            'validation': None
        },

        # Control Flow Effects
        'ConditionalAction': {
            'required': {'condition'},
            'optional': {'if_true', 'if_false'},
            'validation': lambda cfg: EffectValidator._validate_conditional_action(cfg)
        },
        'LoopAction': {
            'required': {'actions'},
            'optional': {'condition', 'max_iterations'},
            'validation': lambda cfg: EffectValidator._validate_loop_action(cfg)
        },
        'RepeatAction': {
            'required': {'actions', 'count'},
            'optional': {'max_iterations'},
            'validation': lambda cfg: EffectValidator._validate_repeat_action(cfg)
        },
        'ExecuteDogma': {
            'required': set(),
            'optional': {'card_name', 'card', 'target_player'},
            'validation': lambda cfg: EffectValidator._validate_execute_dogma(cfg)
        },

        # Calculation Effects
        'CountCards': {
            'required': {'store_result'},
            'optional': {'source', 'location', 'criteria'},
            'validation': None
        },
        'CountSymbols': {
            'required': {'symbol', 'store_result'},
            'optional': {'source', 'location'},
            'validation': None
        },
        'CountColorsWithSymbol': {
            'required': {'symbol', 'store_result'},
            'optional': {'source'},
            'validation': None
        },
        'CountColorsWithSplay': {
            'required': {'store_result'},
            'optional': {'splay_direction', 'source'},
            'validation': None
        },
        'CountUniqueColors': {
            'required': {'store_result'},
            'optional': {'source'},
            'validation': None
        },
        'CountUniqueValues': {
            'required': {'store_result'},
            'optional': {'source'},
            'validation': None
        },
        'CalculateValue': {
            'required': {'operand1', 'operand2', 'operation', 'store_result'},
            'optional': set(),
            'validation': lambda cfg: EffectValidator._validate_calculate_value(cfg)
        },
        'GetCardAge': {
            'required': {'store_result'},
            'optional': {'selection', 'card'},
            'validation': lambda cfg: EffectValidator._validate_property_extraction(cfg)
        },
        'GetCardColor': {
            'required': {'store_result'},
            'optional': {'selection', 'card'},
            'validation': lambda cfg: EffectValidator._validate_property_extraction(cfg)
        },

        # Achievement Effects
        'ClaimAchievement': {
            'required': {'achievement'},
            'optional': {'player'},
            'validation': None
        },
        'MakeAvailable': {
            'required': {'achievement_name'},
            'optional': set(),
            'validation': None
        },
        'HasAchievement': {
            'required': set(),
            'optional': {'achievement_name', 'achievement_age', 'player'},
            'validation': lambda cfg: EffectValidator._validate_has_achievement(cfg)
        },
        'CanClaim': {
            'required': {'achievement'},
            'optional': {'player'},
            'validation': None
        },
        'AchievementCount': {
            'required': set(),
            'optional': {'min_count', 'max_count', 'player'},
            'validation': None
        },

        # Special Effects
        'DemandEffect': {
            'required': {'symbol_requirement', 'actions'},
            'optional': {'allow_sharing'},
            'validation': lambda cfg: EffectValidator._validate_demand_effect(cfg)
        }
    }

    @classmethod
    def validate_effect(cls, config: dict[str, Any]) -> EffectMetadata:
        """
        Validate a single effect configuration.

        Args:
            config: Effect configuration to validate

        Returns:
            EffectMetadata with validation results
        """
        effect_type = config.get('type', '')
        adapter_type = EffectFactory.get_adapter_for_effect_type(effect_type)

        # Determine effect category
        effect_category = cls._determine_effect_category(effect_type, adapter_type)

        # Get validation rules
        rules = cls.EFFECT_VALIDATION_RULES.get(effect_type, {
            'required': set(),
            'optional': set(),
            'validation': None
        })

        required_fields = cls.UNIVERSAL_REQUIRED_FIELDS | rules.get('required', set())
        optional_fields = cls.UNIVERSAL_OPTIONAL_FIELDS | rules.get('optional', set())

        # Validate fields
        errors = []
        warnings = []

        # Check required fields
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")

        # Check for unknown fields
        known_fields = required_fields | optional_fields
        for field in config:
            if field not in known_fields:
                warnings.append(f"Unknown field: {field}")

        # Run custom validation if available
        custom_validation = rules.get('validation')
        if custom_validation:
            try:
                custom_errors = custom_validation(config)
                if custom_errors:
                    errors.extend(custom_errors)
            except Exception as e:
                errors.append(f"Validation function failed: {e}")

        # Generate description
        description = cls._generate_description(config, effect_type)

        # Calculate complexity score
        complexity_score = cls._calculate_complexity(config, effect_type)

        return EffectMetadata(
            effect_type=effect_type,
            adapter_type=adapter_type,
            effect_category=effect_category,
            required_fields=required_fields,
            optional_fields=optional_fields,
            validation_errors=errors,
            validation_warnings=warnings,
            description=description,
            complexity_score=complexity_score
        )

    @classmethod
    def validate_effect_list(cls, configs: list[dict[str, Any]]) -> list[EffectMetadata]:
        """
        Validate a list of effect configurations.

        Args:
            configs: List of effect configurations

        Returns:
            List of EffectMetadata for each configuration
        """
        return [cls.validate_effect(config) for config in configs]

    @classmethod
    def get_validation_summary(cls, metadata_list: list[EffectMetadata]) -> dict[str, Any]:
        """
        Get summary of validation results.

        Args:
            metadata_list: List of EffectMetadata

        Returns:
            Summary dictionary with statistics
        """
        total_effects = len(metadata_list)
        effects_with_errors = sum(1 for m in metadata_list if m.validation_errors)
        effects_with_warnings = sum(1 for m in metadata_list if m.validation_warnings)

        error_count = sum(len(m.validation_errors) for m in metadata_list)
        warning_count = sum(len(m.validation_warnings) for m in metadata_list)

        adapter_counts = {}
        complexity_distribution = {}

        for metadata in metadata_list:
            # Count by adapter
            adapter = metadata.adapter_type
            adapter_counts[adapter] = adapter_counts.get(adapter, 0) + 1

            # Count by complexity
            complexity = metadata.complexity_score
            complexity_distribution[complexity] = complexity_distribution.get(complexity, 0) + 1

        return {
            'total_effects': total_effects,
            'effects_with_errors': effects_with_errors,
            'effects_with_warnings': effects_with_warnings,
            'total_errors': error_count,
            'total_warnings': warning_count,
            'error_rate': effects_with_errors / total_effects if total_effects > 0 else 0,
            'warning_rate': effects_with_warnings / total_effects if total_effects > 0 else 0,
            'adapter_distribution': adapter_counts,
            'complexity_distribution': complexity_distribution,
            'average_complexity': sum(m.complexity_score for m in metadata_list) / total_effects if total_effects > 0 else 0
        }

    @staticmethod
    def _determine_effect_category(effect_type: str, adapter_type: str) -> EffectType:
        """Determine the EffectType category from effect and adapter types."""
        if adapter_type == "DemandEffectAdapter":
            return EffectType.DEMAND
        elif adapter_type == "InteractionEffectAdapter":
            return EffectType.INTERACTION
        elif adapter_type == "TransferEffectAdapter":
            return EffectType.TRANSFER
        elif adapter_type == "BoardManipulationAdapter":
            return EffectType.BOARD
        elif adapter_type == "ControlFlowAdapter":
            if effect_type == "ConditionalAction":
                return EffectType.CONDITIONAL
            else:
                return EffectType.LOOP
        elif adapter_type == "CalculationEffectAdapter":
            return EffectType.CALCULATION
        elif adapter_type == "AchievementEffectAdapter":
            return EffectType.ACHIEVEMENT
        else:
            return EffectType.STANDARD

    @staticmethod
    def _generate_description(config: dict[str, Any], effect_type: str) -> str:
        """Generate a descriptive string for the effect."""
        if 'description' in config:
            return config['description']

        # Generate based on effect type (simplified version of adapter descriptions)
        if effect_type == 'SelectCards':
            source = config.get('source', 'cards')
            min_count = config.get('min_count', 1)
            max_count = config.get('max_count', min_count)
            if min_count == max_count:
                return f"Select {min_count} card(s) from {source}"
            else:
                return f"Select {min_count}-{max_count} card(s) from {source}"
        elif effect_type == 'DrawCards':
            age = config.get('age', '?')
            count = config.get('count', 1)
            return f"Draw {count} age {age} card(s)"
        elif effect_type == 'SplayCards':
            color = config.get('color', 'cards')
            direction = config.get('direction', 'unknown')
            return f"Splay {color} cards {direction}"
        else:
            return f"{effect_type} effect"

    @staticmethod
    def _calculate_complexity(config: dict[str, Any], effect_type: str) -> int:
        """Calculate complexity score (1-10) based on configuration."""
        score = 1  # Base score

        # Add points for various complexity factors
        if 'condition' in config:
            score += 2
        if 'actions' in config:
            actions = config['actions']
            if isinstance(actions, list):
                score += len(actions) // 2
        if 'selection' in config:
            score += 1
        if effect_type in ['ConditionalAction', 'LoopAction', 'RepeatAction']:
            score += 2
        if effect_type == 'DemandEffect':
            score += 3
        if len(config) > 5:  # Many parameters
            score += 1

        return min(score, 10)  # Cap at 10

    # Custom validation methods for specific effect types

    @staticmethod
    def _validate_select_cards(config: dict[str, Any]) -> list[str]:
        """Validate SelectCards configuration."""
        errors = []

        min_count = config.get('min_count', 1)
        max_count = config.get('max_count', min_count)

        if not isinstance(min_count, int) or min_count < 0:
            errors.append("min_count must be non-negative integer")
        if not isinstance(max_count, int) or max_count < min_count:
            errors.append("max_count must be >= min_count")

        return errors

    @staticmethod
    def _validate_choose_option(config: dict[str, Any]) -> list[str]:
        """Validate ChooseOption configuration."""
        errors = []

        options = config.get('options', [])
        if not isinstance(options, list) or len(options) == 0:
            errors.append("options must be non-empty list")

        return errors

    @staticmethod
    def _validate_draw_cards(config: dict[str, Any]) -> list[str]:
        """Validate DrawCards configuration."""
        errors = []

        age = config.get('age')
        count = config.get('count')

        if not isinstance(age, int) or not (1 <= age <= 10):
            errors.append("age must be integer between 1 and 10")
        if not isinstance(count, int) or count < 1:
            errors.append("count must be positive integer")

        return errors

    @staticmethod
    def _validate_score_cards(config: dict[str, Any]) -> list[str]:
        """Validate ScoreCards configuration."""
        errors = []

        # Cannot have both selection and source
        if 'selection' in config and 'source' in config:
            errors.append("Cannot specify both 'selection' and 'source'")

        return errors

    @staticmethod
    def _validate_splay_cards(config: dict[str, Any]) -> list[str]:
        """Validate SplayCards configuration."""
        errors = []

        direction = config.get('direction', '').lower()
        valid_directions = {'left', 'right', 'up', 'none', 'aslant'}

        if direction not in valid_directions:
            errors.append(f"direction must be one of {valid_directions}")

        return errors

    @staticmethod
    def _validate_filter_cards(config: dict[str, Any]) -> list[str]:
        """Validate FilterCards configuration."""
        errors = []

        # Requires either criteria or filter
        if 'criteria' not in config and 'filter' not in config:
            errors.append("FilterCards requires 'criteria' or 'filter'")

        return errors

    @staticmethod
    def _validate_conditional_action(config: dict[str, Any]) -> list[str]:
        """Validate ConditionalAction configuration."""
        errors = []

        # Should have at least one action branch
        if 'if_true' not in config and 'if_false' not in config:
            errors.append("ConditionalAction requires 'if_true' or 'if_false'")

        return errors

    @staticmethod
    def _validate_loop_action(config: dict[str, Any]) -> list[str]:
        """Validate LoopAction configuration."""
        errors = []

        # Requires either condition or count (through RepeatAction)
        if 'condition' not in config and config.get('type') != 'RepeatAction':
            errors.append("LoopAction requires 'condition'")

        return errors

    @staticmethod
    def _validate_repeat_action(config: dict[str, Any]) -> list[str]:
        """Validate RepeatAction configuration."""
        errors = []

        count = config.get('count')
        if not isinstance(count, int) or count < 0:
            errors.append("count must be non-negative integer")
        if isinstance(count, int) and count > 100:
            errors.append("count exceeds maximum (100)")

        return errors

    @staticmethod
    def _validate_execute_dogma(config: dict[str, Any]) -> list[str]:
        """Validate ExecuteDogma configuration."""
        errors = []

        # Requires either card_name or card
        if 'card_name' not in config and 'card' not in config:
            errors.append("ExecuteDogma requires 'card_name' or 'card'")

        return errors

    @staticmethod
    def _validate_calculate_value(config: dict[str, Any]) -> list[str]:
        """Validate CalculateValue configuration."""
        errors = []

        operation = config.get('operation')
        valid_operations = {'add', 'subtract', 'multiply', 'divide', 'min', 'max'}

        if operation not in valid_operations:
            errors.append(f"operation must be one of {valid_operations}")

        return errors

    @staticmethod
    def _validate_property_extraction(config: dict[str, Any]) -> list[str]:
        """Validate property extraction effects (GetCardAge, GetCardColor)."""
        errors = []

        # Requires either selection or card
        if 'selection' not in config and 'card' not in config:
            errors.append("Property extraction requires 'selection' or 'card'")

        return errors

    @staticmethod
    def _validate_has_achievement(config: dict[str, Any]) -> list[str]:
        """Validate HasAchievement configuration."""
        errors = []

        # Requires either achievement_name or achievement_age
        if 'achievement_name' not in config and 'achievement_age' not in config:
            errors.append("HasAchievement requires 'achievement_name' or 'achievement_age'")

        return errors

    @staticmethod
    def _validate_demand_effect(config: dict[str, Any]) -> list[str]:
        """Validate DemandEffect configuration."""
        errors = []

        symbol_req = config.get('symbol_requirement')
        if not symbol_req:
            errors.append("DemandEffect missing symbol_requirement")

        actions = config.get('actions', [])
        if not isinstance(actions, list) or len(actions) == 0:
            errors.append("DemandEffect requires non-empty actions list")

        return errors
