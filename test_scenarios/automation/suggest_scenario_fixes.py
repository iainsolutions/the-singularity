#!/usr/bin/env python3
"""
Suggest Fixes for Scenario Test Failures

Takes diagnostic output and generates specific, actionable fix suggestions.

Usage:
    python3 suggest_scenario_fixes.py \\
        --diagnostics diagnostics.json \\
        --output fixes.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any


class FixSuggester:
    """Generates fix suggestions from diagnostics."""

    def __init__(self, diagnostics: List[Dict[str, Any]]):
        self.diagnostics = diagnostics
        self.fixes = []

    def generate_fixes(self) -> List[Dict[str, Any]]:
        """Generate fix suggestions for all diagnostics."""
        for diagnostic in self.diagnostics:
            category = diagnostic.get("category")

            if category == "field_name_violation":
                self.suggest_field_name_fix(diagnostic)
            elif category == "wrong_player_targeting":
                self.suggest_player_targeting_fix(diagnostic)
            elif category == "sharing_participation_error":
                self.suggest_sharing_participation_fix(diagnostic)
            elif category == "sharing_bonus_incorrect" or category == "sharing_bonus_not_given":
                self.suggest_sharing_bonus_fix(diagnostic)
            elif category == "symbol_counting":
                self.suggest_symbol_counting_fix(diagnostic)
            elif category == "achievement_not_removed" or category == "achievement_not_junked":
                self.suggest_achievement_fix(diagnostic)
            elif category == "duplicate_interactions":
                self.suggest_duplicate_fix(diagnostic)
            elif category == "conditional_logic_error":
                self.suggest_conditional_fix(diagnostic)

        return self.fixes

    def add_fix(self, diagnostic: Dict, file_path: str, description: str,
                search_pattern: str = None, suggested_code: str = None,
                confidence: str = "MEDIUM", manual_review: bool = True):
        """Add a fix suggestion."""
        fix = {
            "diagnostic": diagnostic,
            "file": file_path,
            "description": description,
            "confidence": confidence,  # HIGH, MEDIUM, LOW
            "manual_review_required": manual_review
        }

        if search_pattern:
            fix["search_pattern"] = search_pattern
        if suggested_code:
            fix["suggested_code"] = suggested_code

        self.fixes.append(fix)

    def suggest_field_name_fix(self, diagnostic: Dict):
        """Suggest fix for field name violations."""
        self.add_fix(
            diagnostic,
            "backend/action_primitives/transfer_cards.py",
            "Change field name from 'cards' or '_eligible_cards' to 'eligible_cards'",
            search_pattern="StandardInteractionBuilder.build_select_cards",
            suggested_code=(
                "interaction = StandardInteractionBuilder.build_select_cards(\n"
                "    prompt=\"Select cards to transfer\",\n"
                "    eligible_cards=[card.to_dict() for card in cards],  # Use 'eligible_cards'\n"
                "    min_cards=1,\n"
                "    max_cards=1\n"
                ")"
            ),
            confidence="HIGH",
            manual_review=False
        )

        # Check other primitives too
        self.add_fix(
            diagnostic,
            "backend/action_primitives/demand_effect.py",
            "Verify DemandEffect uses 'eligible_cards' field name",
            search_pattern="StandardInteractionBuilder",
            confidence="HIGH",
            manual_review=True
        )

    def suggest_player_targeting_fix(self, diagnostic: Dict):
        """Suggest fix for player targeting issues."""
        self.add_fix(
            diagnostic,
            "backend/action_primitives/demand_effect.py",
            (
                "DemandEffect should create interactions for AFFECTED players (those with fewer symbols), "
                "not the ACTIVATING player. Check that interactions are created with target_player_id "
                "set to each affected opponent."
            ),
            search_pattern="def execute",
            suggested_code=(
                "# For each affected player, create interaction\n"
                "for affected_player in affected_players:\n"
                "    interaction = StandardInteractionBuilder.build_select_cards(\n"
                "        prompt=\"Select highest card\",\n"
                "        eligible_cards=eligible_cards,\n"
                "        target_player_id=affected_player.id  # Target the affected player!\n"
                "    )\n"
            ),
            confidence="MEDIUM",
            manual_review=True
        )

    def suggest_sharing_participation_fix(self, diagnostic: Dict):
        """Suggest fix for sharing participation logic."""
        self.add_fix(
            diagnostic,
            "backend/dogma_v2/consolidated_phases.py",
            (
                "Sharing participation requires players to have >= N symbols of the dogma type. "
                "Verify Phase 5 (execute_sharing) correctly filters participants based on symbol count. "
                "Check get_visible_symbols() includes all visible board symbols."
            ),
            search_pattern="def execute_sharing|Phase 5",
            confidence="MEDIUM",
            manual_review=True
        )

        self.add_fix(
            diagnostic,
            "backend/game_logic/game.py",
            "Verify get_visible_symbols() counts symbols from splayed and non-splayed cards correctly",
            search_pattern="def get_visible_symbols",
            confidence="MEDIUM",
            manual_review=True
        )

    def suggest_sharing_bonus_fix(self, diagnostic: Dict):
        """Suggest fix for sharing bonus logic."""
        self.add_fix(
            diagnostic,
            "backend/dogma_v2/consolidated_phases.py",
            (
                "Sharing bonus detection (Phase 6) must check:\n"
                "1. Opponent participated in sharing (has sufficient symbols)\n"
                "2. Opponent DID SOMETHING with a card (not just revealed)\n\n"
                "The 'did something' check means: meld, tuck, transfer, draw, score, junk, achieve, splay, etc. "
                "Revealing does NOT count.\n\n"
                "NOTE: Having MORE symbols than activator is NOT required - only participation + doing something."
            ),
            search_pattern="def detect_sharing_bonus|Phase 6",
            confidence="MEDIUM",
            manual_review=True
        )

    def suggest_symbol_counting_fix(self, diagnostic: Dict):
        """Suggest fix for symbol counting."""
        self.add_fix(
            diagnostic,
            "backend/game_logic/game.py",
            (
                "Symbol counting must include:\n"
                "1. All symbols on non-splayed cards (all 4 corners)\n"
                "2. Only visible symbols on splayed cards:\n"
                "   - Right splay: rightmost symbol only\n"
                "   - Up splay: all symbols except bottom-left\n"
                "   - Left splay: leftmost symbol only\n"
                "Check get_visible_symbols() implementation"
            ),
            search_pattern="def get_visible_symbols",
            confidence="MEDIUM",
            manual_review=True
        )

    def suggest_achievement_fix(self, diagnostic: Dict):
        """Suggest fix for achievement state management."""
        self.add_fix(
            diagnostic,
            "backend/action_primitives/junk_cards.py",
            (
                "JunkCard must:\n"
                "1. Remove achievement from game.achievement_cards[age]\n"
                "2. Add achievement to game.junk_pile\n"
                "Verify both operations happen atomically"
            ),
            search_pattern="class JunkCard|def execute",
            confidence="MEDIUM",
            manual_review=True
        )

    def suggest_duplicate_fix(self, diagnostic: Dict):
        """Suggest fix for duplicate interactions."""
        self.add_fix(
            diagnostic,
            "backend/game_logic/event_bus.py",
            (
                "Duplicate interactions suggest Event Bus is delivering messages multiple times. "
                "Check:\n"
                "1. Event Bus doesn't have duplicate subscribers\n"
                "2. Interaction isn't being created multiple times in dogma flow\n"
                "3. No recursive execution causing re-triggering"
            ),
            search_pattern="class GameEventBus|def publish",
            confidence="LOW",
            manual_review=True
        )

        self.add_fix(
            diagnostic,
            "backend/dogma_v2/consolidated_executor.py",
            "Check if demand loop or sharing loop is creating duplicate interactions",
            search_pattern="for.*affected_player|for.*sharing_participant",
            confidence="MEDIUM",
            manual_review=True
        )

    def suggest_conditional_fix(self, diagnostic: Dict):
        """Suggest fix for conditional logic errors."""
        self.add_fix(
            diagnostic,
            "backend/action_primitives/conditional_action.py",
            (
                "ConditionalAction evaluation issues:\n"
                "1. Check variable exists in execution context\n"
                "2. Verify condition type (variable_exists, equals, greater_than, etc.)\n"
                "3. Ensure store_result variables are properly stored by previous primitives"
            ),
            search_pattern="def evaluate_condition|class ConditionalAction",
            confidence="MEDIUM",
            manual_review=True
        )

        self.add_fix(
            diagnostic,
            "backend/dogma_v2/consolidated_executor.py",
            "Verify context variables are stored correctly (e.g., demand_transferred_count)",
            search_pattern="store_result|context\[",
            confidence="MEDIUM",
            manual_review=True
        )


def main():
    parser = argparse.ArgumentParser(description="Suggest fixes for scenario test failures")
    parser.add_argument("--diagnostics", required=True, help="Path to diagnostics JSON file")
    parser.add_argument("--output", required=True, help="Output JSON file for fix suggestions")

    args = parser.parse_args()

    # Read diagnostics
    try:
        with open(args.diagnostics) as f:
            data = json.load(f)
            diagnostics = data.get("diagnostics", [])
    except FileNotFoundError:
        print(f"Error: Diagnostics file not found: {args.diagnostics}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in diagnostics file", file=sys.stderr)
        sys.exit(1)

    # Generate fixes
    suggester = FixSuggester(diagnostics)
    fixes = suggester.generate_fixes()

    # Write output
    output_data = {
        "diagnostics_file": args.diagnostics,
        "fix_count": len(fixes),
        "fixes": fixes
    }

    with open(args.output, 'w') as f:
        json.dump(output_data, f, indent=2)

    # Print summary
    print(f"\n🔧 Fix Suggestions: {len(fixes)} generated")
    for fix in fixes:
        confidence_icon = "🟢" if fix["confidence"] == "HIGH" else "🟡" if fix["confidence"] == "MEDIUM" else "🔴"
        review = "⚠️ Manual review required" if fix["manual_review_required"] else "✅ Auto-applicable"
        print(f"\n{confidence_icon} {fix['file']}")
        print(f"   {fix['description']}")
        print(f"   {review}")

    print(f"\nFix suggestions written to: {args.output}")


if __name__ == "__main__":
    main()
