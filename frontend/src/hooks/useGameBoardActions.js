/**
 * Custom hook for managing GameBoard action handlers and callbacks
 */
import { useCallback } from "react";
import { useGameActions } from "./useGameActions";

export function useGameBoardActions(
  sendWebSocketMessage,
  gameState,
  playerId,
) {
  // Extract pending interaction state from game state
  const pendingInteraction = gameState?.state?.pending_dogma_action || gameState?.pendingDogmaAction;

  const {
    selectedCard,
    selectedCardLocation,
    selectedAction,
    selectedAge,
    setSelectedAge,
    multiSelectedCards,
    handleDraw,
    handleMeld,
    handleDogma,
    handleAchieve,
    handleSelectAction,
    executeSelectedAction,
    handleDogmaResponse,
    handleDeclineDogma,
    handleSetupSelection,
    handleCardClick,
    cancelAction,
    submitMultiCardSelection,
    clearMultiCardSelection,
    submitCardOrder, // Cities: Card ordering for Search icon
    // Unseen expansion: Meld source modal
    meldSourceModalOpen,
    meldSourceModalLoading,
    meldSourceModalError,
    pendingMeldCard,
    handleMeldSourceConfirm,
    handleMeldSourceModalClose,
  } = useGameActions(sendWebSocketMessage, pendingInteraction, gameState, playerId);

  // Enhanced card click handler with context
  const onCardClick = useCallback(
    (card, needsToRespond, pendingDogmaActionParam, isMyTurn, cardLocation) => {
      // Use current pendingDogmaAction from gameState instead of stale parameter
      const currentPendingAction = gameState?.state?.pending_dogma_action || pendingDogmaActionParam;
      handleCardClick(card, needsToRespond, currentPendingAction, isMyTurn, cardLocation);
    },
    [handleCardClick, gameState],
  );

  // Enhanced select action handler with turn validation
  const onSelectAction = useCallback(
    (actionType, isMyTurn) => {
      if (!isMyTurn) return;
      handleSelectAction(actionType);
    },
    [handleSelectAction],
  );

  // Enhanced draw handler with age calculation
  const onDraw = useCallback(
    (isMyTurn, actualDrawAge) => {
      if (!isMyTurn) return;
      handleSelectAction("draw");
      handleDraw(actualDrawAge);
    },
    [handleSelectAction, handleDraw],
  );

  // Enhanced decline handler with pending action context
  const onDeclineDogma = useCallback(
    (pendingDogmaAction) => {
      handleDeclineDogma(pendingDogmaAction);
    },
    [handleDeclineDogma],
  );

  return {
    // Selection state
    selectedCard,
    selectedCardLocation,
    selectedAction,
    selectedAge,
    setSelectedAge,
    multiSelectedCards,

    // Basic actions
    handleMeld,
    handleDogma,
    handleAchieve,
    handleDogmaResponse,
    handleSetupSelection,
    executeSelectedAction,
    cancelAction,
    submitMultiCardSelection,
    clearMultiCardSelection,
    submitCardOrder, // Cities: Card ordering for Search icon

    // Enhanced handlers
    onCardClick,
    onSelectAction,
    onDraw,
    onDeclineDogma,

    // Unseen expansion: Meld source modal
    meldSourceModalOpen,
    meldSourceModalLoading,
    meldSourceModalError,
    pendingMeldCard,
    handleMeldSourceConfirm,
    handleMeldSourceModalClose,
  };
}
