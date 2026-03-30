/**
 * Custom hook for managing GameBoard navigation and route logic
 */
import { useEffect, useCallback, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useGame } from "../context/GameContext";

export function useGameNavigation() {
  const { gameId: urlGameId } = useParams();
  const navigate = useNavigate();
  const { gameId, gameState, leaveGame, setGameData, setPlayerName, rejoinGame, saveSession } = useGame();

  // Track whether we're still waiting for session restoration
  const [sessionRestorationAttempted, setSessionRestorationAttempted] = useState(false);
  const sessionCheckTimeout = useRef(null);

  // Handle token-based authentication from URL on mount
  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const token = searchParams.get("token");

    if (token && urlGameId && !gameId) {
      console.log("🎫 Token found in URL, authenticating...", {
        urlGameId,
        token: token.substring(0, 20) + "...",
      });

      // Decode the JWT token to get player info
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        console.log("🎫 Token decoded:", {
          gameId: payload.game_id,
          playerId: payload.player_id,
          playerName: payload.player_name,
        });

        // Set game data from token
        setGameData({
          gameId: payload.game_id,
          playerId: payload.player_id,
          gameState: null,
          token: token,
        });
        setPlayerName(payload.player_name || "");

        // Save session immediately for future refreshes using centralized session manager
        saveSession(payload.game_id, payload.player_id, payload.player_name || "", token);
        console.log("💾 Session saved to localStorage");

        // Rejoin game with token
        rejoinGame(payload.game_id, payload.player_id, token)
          .then(() => {
            console.log("✅ Successfully authenticated with token");
          })
          .catch((error) => {
            console.error("❌ Failed to authenticate with token:", error);
          });

        // Remove token from URL for security
        searchParams.delete("token");
        const newUrl =
          window.location.pathname + (searchParams.toString() ? "?" + searchParams.toString() : "");
        window.history.replaceState({}, "", newUrl);
      } catch (error) {
        console.error("❌ Failed to decode token:", error);
      }
    }
  }, [urlGameId, gameId, setGameData, setPlayerName, rejoinGame, saveSession]);

  // Set a timeout to mark session restoration as attempted after 2 seconds
  useEffect(() => {
    if (!sessionRestorationAttempted && !gameId) {
      sessionCheckTimeout.current = setTimeout(() => {
        console.log("⏰ Session restoration timeout - marking as attempted");
        setSessionRestorationAttempted(true);
      }, 2000);
    }

    // Clear timeout if gameId becomes available
    if (gameId && sessionCheckTimeout.current) {
      clearTimeout(sessionCheckTimeout.current);
      setSessionRestorationAttempted(true);
    }

    return () => {
      if (sessionCheckTimeout.current) {
        clearTimeout(sessionCheckTimeout.current);
      }
    };
  }, [gameId, sessionRestorationAttempted]);

  // Handle route validation and game state redirects
  useEffect(() => {
    // Skip validation if we're still loading - wait for session restoration
    // On page refresh, gameId starts null until session is restored
    if (!gameId && !gameState && !sessionRestorationAttempted) {
      console.log("⏳ Waiting for session restoration...", { urlGameId });
      return; // Wait for game to load
    }

    // If we have a urlGameId but no gameId yet, this is likely a page refresh
    // where session restoration is in progress - give it more time (up to timeout)
    if (!gameId && urlGameId && !sessionRestorationAttempted) {
      console.log("⏳ Session restoration in progress for game:", urlGameId);
      return; // Wait for session to be restored
    }

    if (!gameId || gameId !== urlGameId) {
      // If we don't have a matching game, redirect to lobby
      console.log("⚠️ Game ID mismatch, redirecting to lobby", { gameId, urlGameId, sessionRestorationAttempted });
      navigate("/");
      return;
    }

    // Only redirect for truly invalid states - NOT for finished games
    // Finished games stay on the game page to show victory screen
    if (gameState) {
      // Don't redirect if game is in progress, waiting, or finished (show victory screen)
      // Also don't redirect if gameState exists but phase is undefined (loading state)
    }
  }, [gameId, urlGameId, gameState, navigate, sessionRestorationAttempted]);

  // Centralized leave game handler
  const handleLeaveGame = useCallback(async () => {
    // Use centralized leave game logic from context
    await leaveGame();
    // Navigate back to lobby after cleanup
    navigate("/");
  }, [leaveGame, navigate]);

  return {
    urlGameId,
    handleLeaveGame,
  };
}
