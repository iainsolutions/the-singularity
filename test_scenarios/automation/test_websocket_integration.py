#!/usr/bin/env python3
"""
WebSocket Integration Tests

Verifies the WebSocket code path works correctly end-to-end.
All existing scenario tests use REST; real players use WebSocket.
These tests connect via ws://localhost:8000/ws/{game_id}/{player_id}
and exercise dogma actions, interactions, consecutive actions, and broadcasts.

Requires running backend (same as other scenario tests).
"""

import asyncio
import json
import os
import sys
import time

import pytest
import requests
import websockets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"


def create_game_with_two_humans():
    """Create a game with two human players, return game_id, player ids, and tokens."""
    r = requests.post(f"{BASE_URL}/api/v1/games", json={})
    assert r.status_code == 200
    game_id = r.json()["game_id"]

    r = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/join", json={"name": "Player1"})
    assert r.status_code == 200
    p1_id = r.json()["player_id"]
    p1_token = r.json()["token"]

    r = requests.post(f"{BASE_URL}/api/v1/games/{game_id}/join", json={"name": "Player2"})
    assert r.status_code == 200
    p2_id = r.json()["player_id"]
    p2_token = r.json()["token"]

    return {
        "game_id": game_id,
        "p1_id": p1_id, "p1_token": p1_token,
        "p2_id": p2_id, "p2_token": p2_token,
    }


def setup_board(game_id, p1_id, p2_id, p1_board=None, p1_hand=None, p2_board=None,
                current_player_index=0, actions_remaining=2):
    """Set up board state via admin API."""
    time.sleep(0.3)
    requests.post(
        f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
        json={"phase": "playing"}
    )
    if p1_board:
        for card in p1_board:
            requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": p1_id, "card_name": card, "location": "board"}
            )
    if p1_hand:
        for card in p1_hand:
            requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": p1_id, "card_name": card, "location": "hand"}
            )
    if p2_board:
        for card in p2_board:
            requests.post(
                f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-card",
                json={"player_id": p2_id, "card_name": card, "location": "board"}
            )
    requests.post(
        f"{BASE_URL}/admin/dev/admin/games/{game_id}/set-state",
        json={
            "phase": "playing",
            "current_player_index": current_player_index,
            "actions_remaining": actions_remaining,
        }
    )


async def recv_until(ws, msg_type, timeout=15):
    """Receive messages until one with the given type arrives. Return it."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    collected = []
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            types = [m.get("type") for m in collected]
            raise TimeoutError(
                f"Timed out waiting for '{msg_type}'. Got: {types}"
            )
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            msg = json.loads(raw)
            collected.append(msg)
            if msg.get("type") == msg_type:
                return msg
        except asyncio.TimeoutError:
            types = [m.get("type") for m in collected]
            raise TimeoutError(
                f"Timed out waiting for '{msg_type}'. Got: {types}"
            )


async def recv_any(ws, timeout=5):
    """Collect all messages within timeout window."""
    loop = asyncio.get_running_loop()
    messages = []
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            messages.append(json.loads(raw))
        except asyncio.TimeoutError:
            break
    return messages


def get_game_state(game_id):
    """Get current game state via REST."""
    r = requests.get(f"{BASE_URL}/api/v1/games/{game_id}")
    assert r.status_code == 200
    return r.json()


def delete_game(game_id):
    """Best-effort cleanup."""
    try:
        requests.delete(f"{BASE_URL}/api/v1/games/{game_id}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test 1: WebSocket dogma action + state update
# ---------------------------------------------------------------------------
class TestWebSocketDogmaAction:
    """Send a simple dogma (Writing - draw a 2) via WebSocket, verify state update."""

    @pytest.mark.timeout(60)
    def test_dogma_via_websocket(self):
        asyncio.run(self._run())

    async def _run(self):
        ctx = create_game_with_two_humans()
        game_id = ctx["game_id"]
        try:
            # Writing on P1 board (lightbulb); P2 has Agriculture (no lightbulbs) -> no sharing
            setup_board(
                game_id, ctx["p1_id"], ctx["p2_id"],
                p1_board=["Writing"],
                p2_board=["Agriculture"],
            )

            # Record initial hand size
            initial = get_game_state(game_id)
            p1_init = next((p for p in initial["players"] if p["id"] == ctx["p1_id"]), None)
            init_hand = len(p1_init.get("hand", []))

            # Connect via WebSocket
            ws_uri = f"{WS_URL}/ws/{game_id}/{ctx['p1_id']}?token={ctx['p1_token']}"
            async with websockets.connect(ws_uri) as ws:
                # Consume the initial game_state_update sent on connect
                initial_msg = await recv_until(ws, "game_state_update", timeout=5)
                assert initial_msg["type"] == "game_state_update"

                # Send dogma action via WebSocket
                await ws.send(json.dumps({
                    "type": "game_action",
                    "data": {"action_type": "dogma", "card_name": "Writing"}
                }))

                # Should receive action_performed with updated state
                result_msg = await recv_until(ws, "action_performed", timeout=15)
                assert result_msg["type"] == "action_performed"
                result = result_msg.get("result", {})
                assert result.get("success") is True, f"Action failed: {result.get('error')}"

                # Verify state: hand should have increased by 1 (drew age 2)
                game_state = result.get("game_state", {})
                p1_final = next(
                    p for p in game_state["players"] if p["id"] == ctx["p1_id"]
                )
                final_hand = len(p1_final.get("hand", []))
                assert final_hand == init_hand + 1, (
                    f"Expected hand +1 after Writing draw. "
                    f"Initial: {init_hand}, Final: {final_hand}"
                )
                print(f"OK hand {init_hand} -> {final_hand} (drew age 2)")

            # Double-check via REST
            final = get_game_state(game_id)
            p1 = next((p for p in final["players"] if p["id"] == ctx["p1_id"]), None)
            assert len(p1.get("hand", [])) == init_hand + 1
            print("OK REST confirms hand size")
        finally:
            delete_game(game_id)


# ---------------------------------------------------------------------------
# Test 2: Consecutive dogma actions via WebSocket
# ---------------------------------------------------------------------------
class TestWebSocketConsecutiveActions:
    """Player has 2 actions, sends both dogma actions via WebSocket."""

    @pytest.mark.timeout(60)
    def test_consecutive_dogma_via_websocket(self):
        asyncio.run(self._run())

    async def _run(self):
        ctx = create_game_with_two_humans()
        game_id = ctx["game_id"]
        try:
            # Writing on P1 board - simple draw, no interaction
            # Give P1 two actions
            setup_board(
                game_id, ctx["p1_id"], ctx["p2_id"],
                p1_board=["Writing"],
                p2_board=["Agriculture"],
                actions_remaining=2,
            )

            initial = get_game_state(game_id)
            p1_init = next((p for p in initial["players"] if p["id"] == ctx["p1_id"]), None)
            init_hand = len(p1_init.get("hand", []))

            ws_uri = f"{WS_URL}/ws/{game_id}/{ctx['p1_id']}?token={ctx['p1_token']}"
            async with websockets.connect(ws_uri) as ws:
                await recv_until(ws, "game_state_update", timeout=5)

                # First dogma
                await ws.send(json.dumps({
                    "type": "game_action",
                    "data": {"action_type": "dogma", "card_name": "Writing"}
                }))
                msg1 = await recv_until(ws, "action_performed", timeout=15)
                assert msg1["result"]["success"] is True, (
                    f"First dogma failed: {msg1['result'].get('error')}"
                )
                print("OK first dogma completed")

                # Drain any remaining messages (broadcast of first action)
                await asyncio.sleep(1)
                try:
                    while True:
                        await asyncio.wait_for(ws.recv(), timeout=0.5)
                except asyncio.TimeoutError:
                    pass  # No more messages

                # Verify first dogma via REST
                mid = get_game_state(game_id)
                p1_mid = next((p for p in mid["players"] if p["id"] == ctx["p1_id"]), None)
                mid_hand = len(p1_mid.get("hand", []))
                print(f"After first dogma: hand={mid_hand}, actions={mid['state']['actions_remaining']}")

                # Second dogma
                await ws.send(json.dumps({
                    "type": "game_action",
                    "data": {"action_type": "dogma", "card_name": "Writing"}
                }))
                msg2 = await recv_until(ws, "action_performed", timeout=15)
                assert msg2["result"]["success"] is True, (
                    f"Second dogma failed: {msg2['result'].get('error')}"
                )
                print("OK second dogma completed")

            # Verify: hand should have increased by 2
            final = get_game_state(game_id)
            p1 = next((p for p in final["players"] if p["id"] == ctx["p1_id"]), None)
            final_hand = len(p1.get("hand", []))
            print(f"Final: hand={final_hand}, actions={final['state']['actions_remaining']}")
            assert final_hand == init_hand + 2, (
                f"Expected hand +2 after two Writing dogmas. "
                f"Initial: {init_hand}, Final: {final_hand}"
            )
            print(f"OK hand {init_hand} -> {final_hand} (drew twice)")
        finally:
            delete_game(game_id)


# ---------------------------------------------------------------------------
# Test 4: WebSocket broadcasts game_state_updated to other player
# ---------------------------------------------------------------------------
class TestWebSocketBroadcast:
    """After dogma, the OTHER player's WebSocket should receive game_state_updated."""

    @pytest.mark.timeout(60)
    def test_broadcast_to_other_player(self):
        asyncio.run(self._run())

    async def _run(self):
        ctx = create_game_with_two_humans()
        game_id = ctx["game_id"]
        try:
            setup_board(
                game_id, ctx["p1_id"], ctx["p2_id"],
                p1_board=["Writing"],
                p2_board=["Agriculture"],
            )

            ws1_uri = f"{WS_URL}/ws/{game_id}/{ctx['p1_id']}?token={ctx['p1_token']}"
            ws2_uri = f"{WS_URL}/ws/{game_id}/{ctx['p2_id']}?token={ctx['p2_token']}"

            async with websockets.connect(ws1_uri) as ws1, \
                        websockets.connect(ws2_uri) as ws2:
                # Consume initial state messages on both connections
                await recv_until(ws1, "game_state_update", timeout=5)
                await recv_until(ws2, "game_state_update", timeout=5)

                # P1 sends dogma via WebSocket
                await ws1.send(json.dumps({
                    "type": "game_action",
                    "data": {"action_type": "dogma", "card_name": "Writing"}
                }))

                # P1 should get action_performed
                p1_msg = await recv_until(ws1, "action_performed", timeout=15)
                assert p1_msg["result"]["success"] is True

                # P2 should receive a broadcast (action_performed or game_state_updated)
                # Collect messages on P2's ws for a few seconds
                p2_messages = await recv_any(ws2, timeout=5)
                p2_types = [m.get("type") for m in p2_messages]
                print(f"P2 received message types: {p2_types}")

                has_state_update = any(
                    t in ("game_state_updated", "action_performed", "game_state_update")
                    for t in p2_types
                )
                assert has_state_update, (
                    f"P2 should receive a state update broadcast after P1's dogma. "
                    f"Got message types: {p2_types}"
                )
                print("OK P2 received broadcast after P1 dogma")
        finally:
            delete_game(game_id)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
