import { createContext, useContext } from "react";
import { useGameState } from "../hooks/useGameState";

const GameStateContext = createContext(null);

export function GameStateProvider({ children }) {
  const gameState = useGameState();

  return <GameStateContext.Provider value={gameState}>{children}</GameStateContext.Provider>;
}

export function useGameStateContext() {
  const context = useContext(GameStateContext);
  if (!context) {
    throw new Error("useGameStateContext must be used within a GameStateProvider");
  }
  return context;
}
