import { createContext, useContext } from "react";
import { useGameApiContext } from "./GameApiContext";
import { GameProviders } from "./GameProviders";
import { useGameStateContext } from "./GameStateContext";
import { useWebSocketContext } from "./WebSocketContext";

export const GameContext = createContext();

function LegacyGameContextConsumer({ children }) {
  const gameState = useGameStateContext();
  const webSocket = useWebSocketContext();
  const gameApi = useGameApiContext();

  // Construct the legacy value object matching the original GameContext interface
  const value = {
    // Game state
    gameId: gameState.gameId,
    playerId: gameState.playerId,
    playerName: gameState.playerName,
    gameState: gameState.gameState,
    token: gameState.token,
    isConnected: gameState.isConnected,
    websocket: gameState.websocket,
    error: gameState.error,
    loading: gameState.loading,
    // Dogma results state
    dogmaResults: gameState.dogmaResults,
    showDogmaResults: gameState.showDogmaResults,
    activityEvents: gameState.activityEvents,
    // Transaction state
    currentTransaction: gameState.currentTransaction,

    // API functions
    createGame: gameApi.createGame,
    joinGame: gameApi.joinGame,
    rejoinGame: gameApi.rejoinGame,
    startGame: gameApi.startGame,
    performAction: gameApi.performAction,

    // WebSocket functions
    sendWebSocketMessage: webSocket.sendWebSocketMessage,
    reconnectWebSocket: webSocket.reconnectWebSocket,
    enhancedPendingAction: webSocket.enhancedPendingAction,

    // Utility functions
    clearError: gameState.clearError,
    resetGame: gameApi.resetGame, // Use enhanced resetGame from GameApi
    leaveGame: gameApi.leaveGame,
    saveSession: gameApi.sessionManager.saveSession,
    clearSession: gameApi.sessionManager.clearSession,
    setGameState: gameState.updateGameState, // Expose updateGameState as setGameState
    setGameData: gameState.setGameData,
    setPlayerName: gameState.setPlayerName,
    // Dogma results functions
    setDogmaResults: gameState.setDogmaResults,
    hideDogmaResults: gameState.hideDogmaResults,
    clearDogmaResults: gameState.clearDogmaResults,
    addActivityEvent: gameState.addActivityEvent,
    clearActivity: gameState.clearActivity,
    // Transaction functions
    setTransaction: gameState.setTransaction,
    clearTransaction: gameState.clearTransaction,
    startTransaction: gameApi.startTransaction,
    commitTransaction: gameApi.commitTransaction,
    undoTransaction: gameApi.undoTransaction,
  };

  return <GameContext.Provider value={value}>{children}</GameContext.Provider>;
}

export function GameProvider({ children, navigate = null }) {
  return (
    <GameProviders navigate={navigate}>
      <LegacyGameContextConsumer>{children}</LegacyGameContextConsumer>
    </GameProviders>
  );
}

export function useGame() {
  const context = useContext(GameContext);
  if (!context) {
    throw new Error("useGame must be used within a GameProvider");
  }
  return context;
}
