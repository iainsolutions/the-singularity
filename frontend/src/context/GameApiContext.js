import { createContext, useContext, useEffect } from "react";
import { useGameApi } from "../hooks/useGameApi";
import { useSessionManager } from "../hooks/useSessionManager";
import { getApiBase } from "../utils/config";
import { useGameStateContext } from "./GameStateContext";
import { useWebSocketContext } from "./WebSocketContext";

const GameApiContext = createContext(null);

export function GameApiProvider({ children, navigate }) {
  const gameState = useGameStateContext();
  const webSocket = useWebSocketContext();
  const sessionManager = useSessionManager();
  const API_BASE = getApiBase();

  const gameApi = useGameApi({
    gameId: gameState.gameId,
    playerId: gameState.playerId,
    setLoading: gameState.setLoading,
    setError: gameState.setError,
    setGameData: gameState.setGameData,
    updateGameState: gameState.updateGameState,
    setPlayerName: gameState.setPlayerName,
    saveSession: sessionManager.saveSession,
    clearSession: sessionManager.clearSession,
    setWebSocket: gameState.setWebSocket,
    cleanupWebSocketState: webSocket.cleanupWebSocketState,
    API_BASE,
  });

  // Session restoration on component mount
  useEffect(() => {
    console.log("🔄 [GameApiContext] Session restoration effect running");
    const session = sessionManager.loadSession();
    console.log("🔍 [GameApiContext] Loaded session:", {
      hasSession: !!session,
      gameId: session?.gameId,
      playerId: session?.playerId,
      hasToken: !!session?.token,
    });

    if (session && session.gameId && session.playerId) {
      console.log("✅ [GameApiContext] Valid session found, setting game data");
      gameState.setGameData({
        gameId: session.gameId,
        playerId: session.playerId,
        gameState: null, // Will be fetched
        token: session.token || null, // Restore token from session
      });
      gameState.setPlayerName(session.playerName || "");

      // Try to rejoin the game with token for WebSocket authentication
      console.log("🔄 [GameApiContext] Calling rejoinGame...");
      gameApi
        .rejoinGame(session.gameId, session.playerId, session.token)
        .then(() => {
          // Navigate to game board if rejoin is successful and navigate is available
          console.log("🎲 Session restored, navigating to game board");
          if (navigate) {
            navigate(`/game/${session.gameId}`);
          }
        })
        .catch((_error) => {
          console.error("Failed to rejoin game during session restoration:", _error);
          // Stay on current page if rejoin fails
        });
    } else {
      console.log("⚠️ [GameApiContext] No valid session found");
    }
  }, []); // Run only once on mount

  // Enhanced resetGame and leaveGame functions that coordinate between hooks
  const resetGame = () => {
    console.log("🧹 Resetting game state completely");

    // Clean up WebSocket enhanced state first
    if (webSocket.cleanupWebSocketState) {
      webSocket.cleanupWebSocketState();
    }

    // Close WebSocket connection
    if (gameState.websocket) {
      gameState.websocket.close(1000, "Game reset");
    }

    // Clear session and reset game state
    sessionManager.clearSession();
    gameState.resetGame();
  };

  const leaveGame = async () => {
    console.log("🚪 Leaving game - performing comprehensive cleanup");

    try {
      // Call API to leave game
      await gameApi.leaveGame();
    } catch (error) {
      console.error("Error leaving game:", error);
    }

    // Perform comprehensive cleanup
    resetGame();

    console.log("✅ Game cleanup complete");
  };

  const value = {
    ...gameApi,
    sessionManager,
    resetGame,
    leaveGame,
  };

  return <GameApiContext.Provider value={value}>{children}</GameApiContext.Provider>;
}

export function useGameApiContext() {
  const context = useContext(GameApiContext);
  if (!context) {
    throw new Error("useGameApiContext must be used within a GameApiProvider");
  }
  return context;
}
