/**
 * GameBoardContext - Centralized state management for GameBoard components
 */
import { createContext, useContext } from "react";
import { useGameBoardState } from "../hooks/useGameBoardState";
import { useGameNavigation } from "../hooks/useGameNavigation";
import { useGameBoardActions } from "../hooks/useGameBoardActions";
import { useGame } from "./GameContext";

const GameBoardContext = createContext();

export function GameBoardProvider({ children }) {
  const {
    sendWebSocketMessage,
    playerId,
  } = useGame();

  // Consolidated state from custom hooks
  const gameState = useGameBoardState();
  const navigation = useGameNavigation();
  const actions = useGameBoardActions(
    sendWebSocketMessage,
    gameState.gameState,
    playerId,
  );

  // Create enhanced action handlers with state context
  const enhancedActions = {
    ...actions,
    onCardClick: (card, needsToRespond, pendingDogmaAction, isMyTurn, cardLocation) => {
      
      // Use passed needsToRespond but ensure we have the latest pendingDogmaAction
      // The needsToRespond value from the component knows the specific context better
      actions.onCardClick(
        card,
        needsToRespond,  // Keep the passed value - component knows if it needs response
        gameState.pendingDogmaAction || pendingDogmaAction,  // Use latest pending action
        gameState.isMyTurn,
        cardLocation,
      );
    },
    onSelectAction: (actionType) => {
      actions.onSelectAction(actionType, gameState.isMyTurn);
    },
    onDraw: () => {
      actions.onDraw(gameState.isMyTurn, gameState.actualDrawAge);
    },
    handleDeclineDogma: () => {
      actions.onDeclineDogma(gameState.pendingDogmaAction);
    },
  };

  const contextValue = {
    // Game state
    ...gameState,

    // Navigation
    ...navigation,

    // Actions
    ...enhancedActions,
    
    // Override stale pendingDogmaAction with current one
    pendingDogmaAction: gameState.pendingDogmaAction,
  };

  return <GameBoardContext.Provider value={contextValue}>{children}</GameBoardContext.Provider>;
}

export function useGameBoard() {
  const context = useContext(GameBoardContext);
  if (!context) {
    throw new Error("useGameBoard must be used within a GameBoardProvider");
  }
  return context;
}
