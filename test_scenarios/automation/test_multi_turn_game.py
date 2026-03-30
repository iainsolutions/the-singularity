#!/usr/bin/env python3
"""
Multi-Turn Game Scenario Tests

Validates state consistency across multiple turns. Existing tests only exercise
single dogma executions; real games break from state accumulation across turns.

Tests:
1. Multi-turn draw-meld-dogma sequence (5 turns, alternating players)
2. Consecutive dogma on same card (Writing x2)
3. Dogma->sharing->dogma sequence (Construction demand x2)
4. Score accumulation -> achievement claim across turns
"""

import os
import sys
import pytest
import requests
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"

ADMIN_URL = f"{BASE_URL}/admin/dev/admin/games"


def create_game() -> tuple[str, str, str]:
    """Create game with human + AI, return (game_id, human_id, ai_id)."""
    response = requests.post(f"{BASE_URL}/api/v1/games", json={})
    assert response.status_code == 200, f"Create game failed: {response.text}"
    game_id = response.json()["game_id"]

    response = requests.post(
        f"{BASE_URL}/api/v1/games/{game_id}/join",
        json={"name": "TestHuman"}
    )
    assert response.status_code == 200
    human_id = response.json()["player_id"]

    response = requests.post(
        f"{BASE_URL}/api/v1/games/{game_id}/add_ai_player",
        json={"difficulty": "beginner"}
    )
    assert response.status_code == 200
    game_state = response.json()["game_state"]
    ai_id = next(p["id"] for p in game_state["players"] if p["is_ai"])

    time.sleep(0.5)
    requests.post(
        f"{ADMIN_URL}/{game_id}/set-state",
        json={"phase": "playing"}
    )

    return game_id, human_id, ai_id


def set_card(game_id: str, player_id: str, card_name: str, location: str):
    """Place a card in a player's hand/board/score_pile."""
    response = requests.post(
        f"{ADMIN_URL}/{game_id}/set-card",
        json={"player_id": player_id, "card_name": card_name, "location": location}
    )
    assert response.status_code == 200, f"set-card {card_name} to {location} failed: {response.text}"


def set_state(game_id: str, **kwargs):
    """Set game state fields (phase, current_player_index, actions_remaining, etc)."""
    payload = {k: v for k, v in kwargs.items() if v is not None}
    response = requests.post(
        f"{ADMIN_URL}/{game_id}/set-state",
        json=payload
    )
    assert response.status_code == 200, f"set-state failed: {response.text}"


def set_deck_order(game_id: str, age: int, card_names: list[str]):
    """Set deterministic draw order for an age deck. First card in list = drawn first."""
    response = requests.post(
        f"{ADMIN_URL}/{game_id}/set-deck-order",
        json={"age": age, "card_order": card_names}
    )
    assert response.status_code == 200, f"set-deck-order failed: {response.text}"


def get_state(game_id: str) -> dict:
    """Get full game state."""
    response = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
    assert response.status_code == 200, f"get state failed: {response.text}"
    return response.json()


def get_player(state: dict, player_id: str) -> dict:
    """Extract player dict from game state."""
    player = next((p for p in state["players"] if p["id"] == player_id), None)
    assert player is not None, f"Player {player_id} not found in game state"
    return player


def do_action(game_id: str, player_id: str, action_type: str, **kwargs) -> dict:
    """Perform a game action and return response json."""
    payload = {"player_id": player_id, "action_type": action_type, **kwargs}
    response = requests.post(
        f"{BASE_URL}/api/v1/games/{game_id}/action",
        json=payload
    )
    assert response.status_code == 200, \
        f"Action {action_type} failed (status {response.status_code}): {response.text}"
    return response.json()


def wait_for_completion(game_id: str, timeout: float = 10.0):
    """Poll until no pending dogma action, or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = get_state(game_id)
        pending = state.get("state", {}).get("pending_dogma_action")
        if pending is None:
            return state
        time.sleep(0.5)
    # Return last state even if still pending (caller can assert)
    return get_state(game_id)


def respond_to_pending(game_id: str, timeout: float = 8.0) -> dict | None:
    """Wait for a pending interaction, have the targeted player auto-respond.

    For AI players this happens automatically; for human players we pick first eligible card(s).
    Returns final state after response, or None if no interaction appeared.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = get_state(game_id)
        pending = state.get("state", {}).get("pending_dogma_action")
        if pending is None:
            return state  # Already completed
        ctx = pending.get("context", {})
        idata = ctx.get("interaction_data", {})
        target_id = pending.get("target_player_id")
        if not idata or not target_id:
            time.sleep(0.5)
            continue

        # Check if target is AI (AI auto-responds)
        target_player = get_player(state, target_id)
        if target_player.get("is_ai"):
            time.sleep(1)
            continue

        # Human player: respond with first eligible cards
        data = idata.get("data", idata)
        eligible = data.get("eligible_cards", [])
        if not eligible:
            time.sleep(0.5)
            continue

        # Determine how many to select
        min_select = data.get("min_selections", 1)
        max_select = data.get("max_selections", min_select)
        count = min(max_select, len(eligible))
        selected = []
        for c in eligible[:count]:
            selected.append(c["card_id"] if isinstance(c, dict) else c)

        response = requests.post(
            f"{BASE_URL}/api/v1/games/{game_id}/dogma-response",
            json={"player_id": target_id, "selected_cards": selected}
        )
        assert response.status_code == 200, f"Dogma response failed: {response.text}"
        time.sleep(0.5)

    return get_state(game_id)


class TestMultiTurnDrawMeldDogma:
    """Test 1: Multi-turn draw-meld-dogma sequence across 5+ turns."""

    def test_multi_turn_sequence(self):
        """Play 5 turns alternating draw/meld/dogma, verify state consistency each turn."""
        game_id, human_id, ai_id = create_game()
        print(f"\nGame: {game_id}")

        # Human board: Writing (blue, 2 lightbulbs) - simple "draw a 2" effect
        set_card(game_id, human_id, "Writing", "board")
        # AI board: Agriculture (0 lightbulbs, won't share Writing)
        set_card(game_id, ai_id, "Agriculture", "board")

        # Give human some hand cards for melding
        set_card(game_id, human_id, "Sailing", "hand")
        set_card(game_id, human_id, "The Wheel", "hand")

        # Give AI some hand cards
        set_card(game_id, ai_id, "Mysticism", "hand")
        set_card(game_id, ai_id, "Oars", "hand")

        # Ensure deterministic draws: age 1 and age 2 decks
        set_deck_order(game_id, 1, ["Archery", "Code of Laws", "City States", "Domestication"])
        set_deck_order(game_id, 2, ["Calendar", "Mathematics", "Canal Building", "Fermenting", "Monotheism"])

        # Human goes first, 2 actions
        set_state(game_id, phase="playing", current_player_index=0, actions_remaining=2)

        # ---- TURN 1: Human draws + melds ----
        print("\n--- Turn 1: Human draws + melds ---")
        state_before = get_state(game_id)
        assert state_before["state"]["current_player_index"] == 0
        assert state_before["state"]["actions_remaining"] == 2

        # Action 1: Draw
        do_action(game_id, human_id, "draw")
        time.sleep(0.5)
        state = get_state(game_id)
        assert state["state"]["actions_remaining"] == 1, "Should have 1 action left after draw"
        assert state["state"]["current_player_index"] == 0, "Should still be human's turn"
        human = get_player(state, human_id)
        hand_names = [c["name"] for c in human.get("hand", [])]
        print(f"  After draw: hand={hand_names}, actions_remaining=1")

        # Action 2: Meld Sailing
        do_action(game_id, human_id, "meld", card_name="Sailing")
        time.sleep(0.5)
        state = get_state(game_id)
        # Turn should have advanced to AI (index 1)
        assert state["state"]["current_player_index"] == 1, \
            f"Should be AI's turn, got index={state['state']['current_player_index']}"
        print(f"  After meld: turn advanced to AI, actions_remaining={state['state']['actions_remaining']}")
        turn_1_number = state["state"].get("turn_number", 0)

        # Verify human board has Sailing now
        human = get_player(state, human_id)
        board = human.get("board", {})
        green_cards = board.get("green_cards", [])
        green_names = [c["name"] for c in green_cards]
        assert "Sailing" in green_names, f"Sailing should be on board, green_cards={green_names}"
        print(f"  Human board green: {green_names}")

        # ---- TURN 2: AI draws + draws (simple, AI has 2 actions) ----
        print("\n--- Turn 2: AI draws x2 ---")
        do_action(game_id, ai_id, "draw")
        time.sleep(0.5)
        state = get_state(game_id)
        assert state["state"]["current_player_index"] == 1, "Should still be AI's turn"
        assert state["state"]["actions_remaining"] == 1

        do_action(game_id, ai_id, "draw")
        time.sleep(0.5)
        state = get_state(game_id)
        assert state["state"]["current_player_index"] == 0, \
            f"Should be human's turn again, got index={state['state']['current_player_index']}"
        turn_2_number = state["state"].get("turn_number", 0)
        assert turn_2_number > turn_1_number, \
            f"Turn number should increase: was {turn_1_number}, now {turn_2_number}"
        print(f"  Turn advanced back to human, turn_number={turn_2_number}")

        # ---- TURN 3: Human dogmas Writing + draws ----
        print("\n--- Turn 3: Human dogmas Writing + draws ---")
        do_action(game_id, human_id, "dogma", card_name="Writing")
        state = wait_for_completion(game_id, timeout=5)
        pending = state.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"Writing dogma should auto-complete, pending={pending}"
        assert state["state"]["actions_remaining"] == 1, "Should have 1 action left after dogma"
        assert state["state"]["current_player_index"] == 0, "Still human's turn"
        human = get_player(state, human_id)
        hand_count_after_dogma = len(human.get("hand", []))
        print(f"  After Writing dogma: hand_count={hand_count_after_dogma}")

        do_action(game_id, human_id, "draw")
        time.sleep(0.5)
        state = get_state(game_id)
        assert state["state"]["current_player_index"] == 1, "Should be AI's turn"
        turn_3_number = state["state"].get("turn_number", 0)
        assert turn_3_number > turn_2_number
        print(f"  Turn advanced to AI, turn_number={turn_3_number}")

        # ---- TURN 4: AI draws + melds ----
        print("\n--- Turn 4: AI draws + melds ---")
        do_action(game_id, ai_id, "draw")
        time.sleep(0.5)
        ai_state = get_state(game_id)
        ai_player = get_player(ai_state, ai_id)
        ai_hand = [c["name"] for c in ai_player.get("hand", [])]
        print(f"  AI hand after draw: {ai_hand}")

        # AI melds first card from hand
        if ai_hand:
            do_action(game_id, ai_id, "meld", card_name=ai_hand[0])
            time.sleep(0.5)
        else:
            do_action(game_id, ai_id, "draw")
            time.sleep(0.5)

        state = get_state(game_id)
        assert state["state"]["current_player_index"] == 0, "Should be human's turn"
        turn_4_number = state["state"].get("turn_number", 0)
        assert turn_4_number > turn_3_number
        print(f"  Turn advanced to human, turn_number={turn_4_number}")

        # ---- TURN 5: Human dogmas Writing again + draws ----
        print("\n--- Turn 5: Human dogmas Writing + draws ---")
        do_action(game_id, human_id, "dogma", card_name="Writing")
        state = wait_for_completion(game_id, timeout=5)
        assert state["state"]["actions_remaining"] == 1
        human = get_player(state, human_id)
        hand_after_turn5_dogma = len(human.get("hand", []))
        print(f"  After 2nd Writing dogma: hand_count={hand_after_turn5_dogma}")

        do_action(game_id, human_id, "draw")
        time.sleep(0.5)
        state = get_state(game_id)
        assert state["state"]["current_player_index"] == 1, "Should be AI's turn"
        turn_5_number = state["state"].get("turn_number", 0)
        assert turn_5_number > turn_4_number
        print(f"  Final turn_number={turn_5_number}")

        # ---- Final state consistency checks ----
        print("\n--- Final state checks ---")
        final = get_state(game_id)
        assert final["phase"] == "playing", f"Game should still be playing, got {final['phase']}"
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"No pending actions at end: {pending}"

        # Verify no state leakage: human's score pile should be empty (Writing only draws)
        human = get_player(final, human_id)
        assert len(human.get("score_pile", [])) == 0, \
            f"Writing doesn't score, score_pile should be empty: {human.get('score_pile', [])}"

        # Verify turn count is monotonically increasing (5 turn advances)
        assert turn_5_number >= 5, f"Should have at least 5 turn advances, got {turn_5_number}"

        print("\n" + "="*70)
        print("PASSED: Multi-turn draw-meld-dogma sequence (5 turns)")
        print("="*70)


class TestConsecutiveDogmaSameCard:
    """Test 2: Dogma same card twice in one turn."""

    def test_writing_dogma_twice(self):
        """Dogma Writing twice in one turn, verify both draws happen."""
        game_id, human_id, ai_id = create_game()
        print(f"\nGame: {game_id}")

        set_card(game_id, human_id, "Writing", "board")
        set_card(game_id, ai_id, "Agriculture", "board")

        # Deterministic age 2 deck (Writing draws age 2)
        set_deck_order(game_id, 2, ["Calendar", "Mathematics", "Canal Building"])

        set_state(game_id, phase="playing", current_player_index=0, actions_remaining=2)

        initial = get_state(game_id)
        human_init = get_player(initial, human_id)
        init_hand_count = len(human_init.get("hand", []))
        print(f"Initial hand count: {init_hand_count}")

        # Dogma 1
        print("\n--- Dogma Writing #1 ---")
        do_action(game_id, human_id, "dogma", card_name="Writing")
        state = wait_for_completion(game_id, timeout=5)
        assert state["state"]["actions_remaining"] == 1
        human = get_player(state, human_id)
        hand_after_1 = [c["name"] for c in human.get("hand", [])]
        print(f"  Hand after dogma 1: {hand_after_1}")
        assert len(hand_after_1) == init_hand_count + 1, \
            f"Expected {init_hand_count + 1} cards, got {len(hand_after_1)}"

        # Dogma 2
        print("\n--- Dogma Writing #2 ---")
        do_action(game_id, human_id, "dogma", card_name="Writing")
        state = wait_for_completion(game_id, timeout=5)
        human = get_player(state, human_id)
        hand_after_2 = [c["name"] for c in human.get("hand", [])]
        print(f"  Hand after dogma 2: {hand_after_2}")
        assert len(hand_after_2) == init_hand_count + 2, \
            f"Expected {init_hand_count + 2} cards, got {len(hand_after_2)}"

        # Turn should have advanced
        assert state["state"]["current_player_index"] == 1, \
            f"Should be AI's turn after 2 actions, got index={state['state']['current_player_index']}"

        # No pending state leaked
        pending = state.get("state", {}).get("pending_dogma_action")
        assert pending is None, f"No pending after completion: {pending}"

        print("\n" + "="*70)
        print("PASSED: Consecutive Writing dogma x2")
        print("="*70)


class TestDogmaSharingDogmaSequence:
    """Test 3: Dogma with demand/sharing, then dogma again same turn."""

    def test_construction_demand_twice(self):
        """Construction demand x2 in one turn, verify both complete without hanging.

        Construction demand: if opponent has fewer castles, they transfer 2 cards
        from hand to active player's hand, then draw a 2.
        """
        game_id, human_id, ai_id = create_game()
        print(f"\nGame: {game_id}")

        # Human: Construction on board
        set_card(game_id, human_id, "Construction", "board")
        # AI: Writing on board (0 castles, vulnerable to demand)
        set_card(game_id, ai_id, "Writing", "board")

        # AI hand: 5 cards (enough for 2 demands of 2 each)
        for card in ["Sailing", "The Wheel", "Domestication", "Pottery", "Clothing"]:
            set_card(game_id, ai_id, card, "hand")

        set_state(game_id, phase="playing", current_player_index=0, actions_remaining=2)

        initial = get_state(game_id)
        human_init = get_player(initial, human_id)
        ai_init = get_player(initial, ai_id)
        human_hand_init = len(human_init.get("hand", []))
        ai_hand_init = len(ai_init.get("hand", []))
        print(f"Initial: human_hand={human_hand_init}, ai_hand={ai_hand_init}")

        # ---- First Construction dogma ----
        print("\n--- Construction dogma #1 ---")
        do_action(game_id, human_id, "dogma", card_name="Construction")

        # AI auto-responds to demand (AI player handles interactions automatically)
        state = wait_for_completion(game_id, timeout=8)
        pending = state.get("state", {}).get("pending_dogma_action")

        # If still pending, AI might need more time
        if pending:
            time.sleep(3)
            state = get_state(game_id)
            pending = state.get("state", {}).get("pending_dogma_action")

        assert pending is None, f"First dogma should complete, pending={pending}"
        assert state["state"]["actions_remaining"] == 1, \
            f"Expected 1 action remaining, got {state['state']['actions_remaining']}"

        human = get_player(state, human_id)
        ai = get_player(state, ai_id)
        human_hand_after_1 = len(human.get("hand", []))
        ai_hand_after_1 = len(ai.get("hand", []))
        print(f"  After dogma 1: human_hand={human_hand_after_1}, ai_hand={ai_hand_after_1}")

        # Human should have gained 2 cards from demand
        assert human_hand_after_1 >= human_hand_init + 2, \
            f"Human should gain 2+ cards from demand: {human_hand_init} -> {human_hand_after_1}"

        # ---- Second Construction dogma ----
        print("\n--- Construction dogma #2 ---")
        do_action(game_id, human_id, "dogma", card_name="Construction")

        # Wait for AI to respond to second demand
        state = wait_for_completion(game_id, timeout=8)
        pending = state.get("state", {}).get("pending_dogma_action")
        if pending:
            time.sleep(3)
            state = get_state(game_id)
            pending = state.get("state", {}).get("pending_dogma_action")

        assert pending is None, f"Second dogma should complete, pending={pending}"

        # Turn should advance after 2nd action
        assert state["state"]["current_player_index"] == 1, \
            f"Should be AI's turn, got index={state['state']['current_player_index']}"

        human = get_player(state, human_id)
        human_hand_after_2 = len(human.get("hand", []))
        print(f"  After dogma 2: human_hand={human_hand_after_2}")
        assert human_hand_after_2 > human_hand_after_1, \
            f"Human should gain more cards from second demand: {human_hand_after_1} -> {human_hand_after_2}"

        print("\n" + "="*70)
        print("PASSED: Construction demand x2 in one turn")
        print("="*70)


class TestScoreAccumulationAndAchievement:
    """Test 4: Score across multiple turns, then claim achievement."""

    def test_score_then_achieve(self):
        """Score points over multiple turns, verify can_achieve, claim age 1 achievement."""
        game_id, human_id, ai_id = create_game()
        print(f"\nGame: {game_id}")

        # Human board: Writing (lightbulbs, draws age 2)
        set_card(game_id, human_id, "Writing", "board")
        # AI board: Agriculture (won't share)
        set_card(game_id, ai_id, "Agriculture", "board")

        # Pre-seed score pile with enough points for age 1 achievement (need >= 5)
        # Age 1 achievement requires score >= 5 and top card age >= 1
        # Add all score cards at setup before any actions (set-card is in-memory only;
        # dogma actions reload from Redis which would wipe in-memory-only changes)
        set_card(game_id, human_id, "Domestication", "score_pile")
        set_card(game_id, human_id, "Archery", "score_pile")
        set_card(game_id, human_id, "Clothing", "score_pile")
        set_card(game_id, human_id, "Pottery", "score_pile")
        set_card(game_id, human_id, "The Wheel", "score_pile")

        # Ensure age 2 deck has known cards
        set_deck_order(game_id, 2, ["Calendar", "Mathematics", "Canal Building", "Fermenting"])
        # Ensure age 1 deck has cards for AI draws
        set_deck_order(game_id, 1, ["Oars", "Masonry", "City States", "Mysticism"])

        set_state(game_id, phase="playing", current_player_index=0, actions_remaining=2)

        # ---- Turn 1: Human draws x2 ----
        print("\n--- Turn 1: Human draws x2 ---")
        do_action(game_id, human_id, "draw")
        time.sleep(0.3)
        do_action(game_id, human_id, "draw")
        time.sleep(0.5)
        state = get_state(game_id)
        assert state["state"]["current_player_index"] == 1
        human = get_player(state, human_id)
        score = sum(c.get("age", 0) for c in human.get("score_pile", []))
        print(f"  Human score: {score} (from pre-seeded cards)")
        assert score >= 5, f"Score should be >= 5 for age 1 achievement, got {score}"

        # ---- Turn 2: AI draws x2 ----
        print("\n--- Turn 2: AI draws x2 ---")
        do_action(game_id, ai_id, "draw")
        time.sleep(0.3)
        do_action(game_id, ai_id, "draw")
        time.sleep(0.5)
        state = get_state(game_id)
        assert state["state"]["current_player_index"] == 0

        # ---- Turn 3: Verify can_achieve, draw + achieve ----
        print("\n--- Turn 3: Draw + Achieve ---")
        state = get_state(game_id)
        human = get_player(state, human_id)
        score = sum(c.get("age", 0) for c in human.get("score_pile", []))
        print(f"  Human score: {score}")

        computed = human.get("computed_state", {})
        can_achieve = computed.get("can_achieve", [])
        print(f"  can_achieve: {can_achieve}")
        assert 1 in can_achieve, \
            f"Age 1 should be achievable with score={score} and top card age >= 1, can_achieve={can_achieve}"

        # Action 1: Draw
        do_action(game_id, human_id, "draw")
        time.sleep(0.3)
        state = get_state(game_id)
        assert state["state"]["actions_remaining"] == 1
        assert state["state"]["current_player_index"] == 0

        # Action 2: Claim age 1 achievement
        print("  Claiming age 1 achievement...")
        result = do_action(game_id, human_id, "achieve", age=1)
        print(f"  Achieve result: success={result.get('success')}, error={result.get('error')}")
        assert result.get("success"), f"Achieve should succeed, got error: {result.get('error')}"

        # Poll for state to reflect the achievement (Redis sync can lag)
        achievements = []
        for _ in range(5):
            time.sleep(0.5)
            state = get_state(game_id)
            human = get_player(state, human_id)
            achievements = human.get("achievements", [])
            if achievements:
                break

        achievement_names = [
            a.get("name", a.get("achievement_id", "?")) if isinstance(a, dict) else str(a)
            for a in achievements
        ]
        print(f"  Achievements: {achievement_names}")
        assert len(achievements) >= 1, \
            f"Should have at least 1 achievement after claiming, got {achievements}"

        # Turn should advance
        assert state["state"]["current_player_index"] == 1, \
            f"Should be AI's turn after achieve, got index={state['state']['current_player_index']}"

        # ---- Turn 4: AI plays, then back to human ----
        print("\n--- Turn 4: AI draws x2 ---")
        do_action(game_id, ai_id, "draw")
        time.sleep(0.3)
        do_action(game_id, ai_id, "draw")
        time.sleep(0.5)
        state = get_state(game_id)
        assert state["state"]["current_player_index"] == 0

        # ---- Verify achievement persists across turns ----
        print("\n--- Verifying achievement persistence ---")
        human = get_player(state, human_id)
        achievements_final = human.get("achievements", [])
        assert len(achievements_final) >= 1, \
            f"Achievement should persist, got {achievements_final}"

        # Verify score pile still intact
        score_final = sum(c.get("age", 0) for c in human.get("score_pile", []))
        print(f"  Score after achievement: {score_final}")
        # Score should be same as before (achieve doesn't consume score in Innovation)
        assert score_final >= 5, f"Score should remain >= 5, got {score_final}"

        # Can't achieve age 1 again (already claimed)
        computed = human.get("computed_state", {})
        can_achieve = computed.get("can_achieve", [])
        assert 1 not in can_achieve, \
            f"Age 1 should NOT be achievable after claiming, can_achieve={can_achieve}"
        print(f"  can_achieve after claiming: {can_achieve} (age 1 removed)")

        # No leaked state
        pending = state.get("state", {}).get("pending_dogma_action")
        assert pending is None

        print("\n" + "="*70)
        print("PASSED: Score accumulation + achievement claim")
        print("="*70)


class TestTurnBoundaryStateIntegrity:
    """Bonus: Verify no state corruption at turn boundaries over many turns."""

    def test_six_turns_alternating(self):
        """6 turns of alternating draws, verify monotonic state progression."""
        game_id, human_id, ai_id = create_game()
        print(f"\nGame: {game_id}")

        set_card(game_id, human_id, "Writing", "board")
        set_card(game_id, ai_id, "Agriculture", "board")

        # Large decks so draws don't run out
        set_deck_order(game_id, 1, [
            "Archery", "Sailing", "The Wheel", "Oars",
            "Mysticism", "Domestication", "City States", "Masonry",
            "Metalworking", "Code of Laws", "Clothing", "Pottery"
        ])

        set_state(game_id, phase="playing", current_player_index=0, actions_remaining=2)

        prev_turn = get_state(game_id)["state"].get("turn_number", 0)
        human_hand_sizes = []
        ai_hand_sizes = []

        for turn in range(6):
            current_idx = turn % 2
            player_id = human_id if current_idx == 0 else ai_id
            player_label = "Human" if current_idx == 0 else "AI"

            state = get_state(game_id)
            assert state["state"]["current_player_index"] == current_idx, \
                f"Turn {turn}: expected player_index={current_idx}, got {state['state']['current_player_index']}"

            # 2 draws per turn
            for action in range(2):
                do_action(game_id, player_id, "draw")
                time.sleep(0.3)

            state = get_state(game_id)
            current_turn = state["state"].get("turn_number", 0)

            # Turn number should monotonically increase
            if turn > 0:
                assert current_turn > prev_turn, \
                    f"Turn {turn}: turn_number should increase: {prev_turn} -> {current_turn}"
            prev_turn = current_turn

            # Track hand sizes (should grow since we're only drawing)
            human = get_player(state, human_id)
            ai = get_player(state, ai_id)
            human_hand_sizes.append(len(human.get("hand", [])))
            ai_hand_sizes.append(len(ai.get("hand", [])))

            print(f"  Turn {turn} ({player_label}): turn_number={current_turn}, "
                  f"human_hand={human_hand_sizes[-1]}, ai_hand={ai_hand_sizes[-1]}")

        # Verify hand sizes are monotonically non-decreasing for each player
        # (each draws 2 cards per own turn)
        for i in range(1, len(human_hand_sizes)):
            assert human_hand_sizes[i] >= human_hand_sizes[i-1], \
                f"Human hand should not shrink: {human_hand_sizes}"
        for i in range(1, len(ai_hand_sizes)):
            assert ai_hand_sizes[i] >= ai_hand_sizes[i-1], \
                f"AI hand should not shrink: {ai_hand_sizes}"

        # Final state should be clean
        final = get_state(game_id)
        assert final["phase"] == "playing"
        pending = final.get("state", {}).get("pending_dogma_action")
        assert pending is None

        print("\n" + "="*70)
        print("PASSED: 6 turns state integrity")
        print("="*70)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
