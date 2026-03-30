import { createContext, useContext } from "react";
import { useWebSocketEnhanced } from "../hooks/useWebSocketEnhanced";
import { getWsBase } from "../utils/config";
import { useGameStateContext } from "./GameStateContext";

const WebSocketContext = createContext(null);

export function WebSocketProvider({ children }) {
  const gameState = useGameStateContext();
  const WS_BASE = getWsBase();

  const webSocket = useWebSocketEnhanced({
    gameId: gameState.gameId,
    playerId: gameState.playerId,
    token: gameState.token,
    websocket: gameState.websocket,
    isConnected: gameState.isConnected,
    setWebSocket: gameState.setWebSocket,
    setConnected: gameState.setConnected,
    setError: gameState.setError,
    updateGameState: gameState.updateGameState,
    setDogmaResults: gameState.setDogmaResults,
    addActivityEvent: gameState.addActivityEvent,
    WS_BASE,
  });

  return <WebSocketContext.Provider value={webSocket}>{children}</WebSocketContext.Provider>;
}

export function useWebSocketContext() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error("useWebSocketContext must be used within a WebSocketProvider");
  }
  return context;
}
