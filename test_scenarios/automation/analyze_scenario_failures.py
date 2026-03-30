#!/usr/bin/env python3
"""
Analyze Scenario Test Failures

Parses test output and execution traces to diagnose specific issues with
Archery dogma implementation.

Based on: /docs/specifications/cards/ARCHERY.md

Checks for:
- Field name violations (eligible_cards vs cards)
- Player targeting errors
- Sharing participation logic (based on symbol comparison)
- Sharing bonus rules (Active Player gets bonus when sharing player does something)
- Symbol counting accuracy
- Achievement state management
- Interaction duplicates
- Effect execution order

Usage:
    python3 analyze_scenario_failures.py \
        --test-output test_results.txt \
        --traces trace_*.json \
        --output diagnostics.json
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any


class FailureAnalyzer:
    """Analyzes test failures and execution traces."""

    def __init__(self, test_output: str, trace_files: List[str]):
        self.test_output = test_output
        self.trace_files = trace_files
        self.diagnostics = []

    def analyze(self) -> List[Dict[str, Any]]:
        """Run all analysis checks based on Archery specification."""
        self.check_field_names()
        self.check_player_targeting()
        self.check_sharing_participation()
        self.check_sharing_bonus()
        self.check_symbol_counting()
        self.check_achievement_state()
        self.check_interaction_duplicates()
        self.check_effect_execution_order()

        return self.diagnostics

    def add_diagnostic(self, severity: str, category: str, message: str,
                       location: str = None, details: Dict = None):
        """Add a diagnostic finding."""
        diagnostic = {
            "severity": severity,  # ERROR, WARNING, INFO
            "category": category,
            "message": message,
        }
        if location:
            diagnostic["location"] = location
        if details:
            diagnostic["details"] = details

        self.diagnostics.append(diagnostic)

    def check_field_names(self):
        """Check for eligible_cards field name violations."""
        # Check test output for field name errors
        if "'cards'" in self.test_output or "_eligible_cards" in self.test_output:
            self.add_diagnostic(
                "ERROR",
                "field_name_violation",
                "Field name violation detected: using 'cards' or '_eligible_cards' instead of 'eligible_cards'",
                location="StandardInteractionBuilder",
                details={
                    "expected": "eligible_cards",
                    "found": "'cards' or '_eligible_cards'",
                    "fix": "Use StandardInteractionBuilder with 'eligible_cards' parameter"
                }
            )

        # Check traces for field names
        for trace_file in self.trace_files:
            try:
                with open(trace_file) as f:
                    trace = json.load(f)
                    # Scan trace for interaction data
                    trace_str = json.dumps(trace)
                    if '"cards":' in trace_str and '"eligible_cards"' not in trace_str:
                        self.add_diagnostic(
                            "ERROR",
                            "field_name_violation",
                            f"Trace {Path(trace_file).name} shows 'cards' field instead of 'eligible_cards'",
                            location=f"Trace: {trace_file}"
                        )
            except Exception as e:
                pass  # Ignore trace parsing errors

    def check_player_targeting(self):
        """Check if interactions target the correct players."""
        # Check for wrong player targeting in test output
        if "wrong player" in self.test_output.lower() or \
           "targeted" in self.test_output.lower() and "expected" in self.test_output.lower():

            # Extract failure message
            match = re.search(r'Assertion \d+.*?(?:targeted|player).*?expected.*', self.test_output, re.IGNORECASE)
            if match:
                failure_msg = match.group(0)
                self.add_diagnostic(
                    "ERROR",
                    "wrong_player_targeting",
                    f"Interaction targeted wrong player: {failure_msg}",
                    location="DemandEffect or SelectAchievement primitive",
                    details={
                        "issue": "Using acting_player instead of target player for interactions",
                        "fix": "In demand effects, create interactions for affected players, not activating player"
                    }
                )

    def check_sharing_participation(self):
        """Check sharing effect participation logic per Archery spec."""
        # Per spec: Sharing requires opponent_castles >= active_player_castles
        # Vulnerability: opponent_castles < active_player_castles

        # Check if AI participated in sharing when it shouldn't (0 castles scenario)
        if "AI should NOT participate" in self.test_output or \
           "AI got select_achievement" in self.test_output and "Should be 0" in self.test_output:

            self.add_diagnostic(
                "ERROR",
                "sharing_participation_error",
                "AI participated in sharing despite having insufficient symbols (0 castles)",
                location="ConsolidatedDogmaExecutor Phase 5 (sharing effect)",
                details={
                    "issue": "Sharing participation not checking symbol requirements correctly",
                    "spec_requirement": "opponent_castles >= active_player_castles for sharing",
                    "fix": "Verify sharing participation requires >= active player's symbol count"
                }
            )

        # Check if AI didn't participate when it should (Scenario 2)
        if "AI should participate in sharing" in self.test_output or \
           "AI got select_achievement" in self.test_output and "expected 1" in self.test_output:

            self.add_diagnostic(
                "ERROR",
                "sharing_participation_error",
                "AI did not participate in sharing despite having sufficient symbols",
                location="ConsolidatedDogmaExecutor Phase 5 (sharing effect)",
                details={
                    "issue": "Sharing participation filtering incorrect",
                    "fix": "Check symbol counting includes visible symbols on board"
                }
            )

    def check_sharing_bonus(self):
        """Check sharing bonus detection and application per Archery spec."""
        # Per spec: Active Player gets bonus when sharing player does something with a card
        # Timing: After ALL effects complete (Effect 0 + Effect 1)

        if "sharing bonus" in self.test_output.lower():
            if "should NOT get sharing bonus" in self.test_output or \
               "No bonus expected but given" in self.test_output:

                self.add_diagnostic(
                    "ERROR",
                    "sharing_bonus_incorrect",
                    "Sharing bonus given when it shouldn't be",
                    location="ConsolidatedDogmaExecutor Phase 6 (sharing bonus)",
                    details={
                        "issue": "Sharing bonus logic incorrect",
                        "spec_requirements": [
                            "Sharing player must have participated (>= symbol count)",
                            "Sharing player must have DONE SOMETHING with a card (not just reveal)",
                            "Active Player receives the bonus card",
                            "Timing: AFTER all dogma effects complete"
                        ],
                        "fix": "Review sharing bonus detection in Phase 6"
                    }
                )

            elif "should get sharing bonus" in self.test_output:
                self.add_diagnostic(
                    "ERROR",
                    "sharing_bonus_not_given",
                    "Sharing bonus not given when it should be",
                    location="ConsolidatedDogmaExecutor Phase 6 (sharing bonus)",
                    details={
                        "issue": "Sharing bonus not detecting qualifying opponent",
                        "fix": "Check opponent has more symbols AND did something with a card"
                    }
                )

    def check_symbol_counting(self):
        """Check symbol counting logic."""
        if "castles" in self.test_output.lower() or "symbols" in self.test_output.lower():
            # Look for symbol count mismatches
            match = re.search(r'(\d+) castles.*?(\d+) castles', self.test_output)
            if match:
                self.add_diagnostic(
                    "WARNING",
                    "symbol_counting",
                    f"Symbol count mismatch detected: {match.group(0)}",
                    location="ConsolidatedDogmaExecutor Phase 2 (symbol detection)",
                    details={
                        "issue": "Symbol counting may not include splayed cards correctly",
                        "fix": "Verify get_visible_symbols() includes all visible symbols"
                    }
                )

    def check_achievement_state(self):
        """Check achievement removal and junking."""
        if "still in available achievements" in self.test_output:
            self.add_diagnostic(
                "ERROR",
                "achievement_not_removed",
                "Achievement not removed from available achievements after junking",
                location="JunkCard primitive or achievement management",
                details={
                    "issue": "Achievement junked but still in game.achievement_cards",
                    "fix": "Ensure JunkCard removes from achievement_cards dict"
                }
            )

        if "NOT in junk pile" in self.test_output:
            self.add_diagnostic(
                "ERROR",
                "achievement_not_junked",
                "Achievement not added to junk pile",
                location="JunkCard primitive",
                details={
                    "issue": "Card removed but not placed in junk_pile",
                    "fix": "Verify JunkCard adds to game.junk_pile"
                }
            )

    def check_interaction_duplicates(self):
        """Check for duplicate interactions sent to AI."""
        # Look for duplicate interaction errors
        match = re.search(r'AI asked (\d+) times', self.test_output)
        if match:
            count = int(match.group(1))
            if count > 1:
                self.add_diagnostic(
                    "ERROR",
                    "duplicate_interactions",
                    f"AI received duplicate interactions ({count} times instead of 1)",
                    location="Event Bus or interaction handling",
                    details={
                        "issue": "Multiple interactions sent for same action",
                        "fix": "Check Event Bus for duplicate message delivery or interaction loop"
                    }
                )

    def check_effect_execution_order(self):
        """Check effect execution order per Archery specification."""
        # Per spec: Effect 0 (Demand) executes first, then Effect 1 (Achievement Junking)
        # For Effect 1 (non-demand): Sharing players FIRST, then Active Player LAST

        if "execution order" in self.test_output.lower():
            if "wrong order" in self.test_output.lower() or "incorrect sequence" in self.test_output.lower():
                self.add_diagnostic(
                    "ERROR",
                    "effect_execution_order_error",
                    "Effect execution order incorrect",
                    location="ConsolidatedDogmaExecutor",
                    details={
                        "spec_requirement": "Effect 0 (Demand) → Effect 1 (Achievement Junking)",
                        "sharing_order": "Sharing players FIRST, Active Player LAST",
                        "fix": "Verify ConsolidatedDogmaExecutor phase execution order"
                    }
                )

        # Check for Active Player executing before sharing players in non-demand effects
        if "Active Player" in self.test_output and "before sharing" in self.test_output.lower():
            self.add_diagnostic(
                "ERROR",
                "sharing_execution_order_error",
                "Active Player executed before sharing players in non-demand effect",
                location="ConsolidatedDogmaExecutor Phase 5 (non-demand sharing)",
                details={
                    "spec_requirement": "Sharing players execute FIRST, Active Player executes LAST",
                    "fix": "Check participant ordering in non-demand effect execution"
                }
            )


def main():
    parser = argparse.ArgumentParser(description="Analyze scenario test failures")
    parser.add_argument("--test-output", required=True, help="Path to test output file")
    parser.add_argument("--traces", nargs='+', help="Path to execution trace files")
    parser.add_argument("--output", required=True, help="Output JSON file for diagnostics")

    args = parser.parse_args()

    # Read test output
    try:
        with open(args.test_output) as f:
            test_output = f.read()
    except FileNotFoundError:
        print(f"Error: Test output file not found: {args.test_output}", file=sys.stderr)
        sys.exit(1)

    # Get trace files
    trace_files = []
    if args.traces:
        trace_files = [f for f in args.traces if Path(f).exists()]

    # Analyze
    analyzer = FailureAnalyzer(test_output, trace_files)
    diagnostics = analyzer.analyze()

    # Write output
    output_data = {
        "test_output_file": args.test_output,
        "trace_files": trace_files,
        "diagnostic_count": len(diagnostics),
        "diagnostics": diagnostics
    }

    with open(args.output, 'w') as f:
        json.dump(output_data, f, indent=2)

    # Print summary
    print(f"\n📊 Analysis Complete: {len(diagnostics)} issues found")
    for d in diagnostics:
        severity_icon = "❌" if d["severity"] == "ERROR" else "⚠️" if d["severity"] == "WARNING" else "ℹ️"
        print(f"{severity_icon} [{d['category']}] {d['message']}")

    print(f"\nDiagnostics written to: {args.output}")


if __name__ == "__main__":
    main()
