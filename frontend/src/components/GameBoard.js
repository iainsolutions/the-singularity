/**
 * GameBoard - Refactored main game board component with modular architecture
 */
import { GameBoardProvider, useGameBoard } from "../context/GameBoardContext";
import GameLayout from "./game/GameLayout";
import GameLoadingScreen from "./game/GameLoadingScreen";
import ErrorBoundary from "./ErrorBoundary";

function GameBoardContent() {
  const {
    // Loading and error state
    isLoading,
    hasValidPlayer,
    loadingTimeout,
    error,
    clearError,
    gameId,
    playerId,
    isConnected,
    gameState,

    // Game state
    currentPlayer,
    otherPlayers,
    isMyTurn,
    needsToRespond,
    pendingDogmaAction,
    playerDrawAge,
    actualDrawAge,

    // AI turn tracking
    aiTurnStartTime,
    lastAIActionTime,
    onRetryAITurn,

    // Actions
    selectedCard,
    selectedCardLocation,
    selectedAge,
    setSelectedAge,
    multiSelectedCards,
    onCardClick,
    onDraw,
    handleMeld,
    handleDogma,
    handleAchieve,
    handleSetupSelection,
    handleDeclineDogma,
    cancelAction,
    submitMultiCardSelection,
    submitCardOrder, // Cities: Card ordering for Search icon
    handleLeaveGame,

    // Unseen expansion: Meld source modal
    meldSourceModalOpen,
    meldSourceModalLoading,
    meldSourceModalError,
    pendingMeldCard,
    handleMeldSourceConfirm,
    handleMeldSourceModalClose,
  } = useGameBoard();

  // Early return for loading states
  if (isLoading) {
    return (
      <GameLoadingScreen
        loadingTimeout={loadingTimeout}
        onLeaveGame={handleLeaveGame}
        error={error}
        gameId={gameId}
        playerId={playerId}
        isConnected={isConnected}
        gameState={gameState}
      />
    );
  }

  // Early return if no valid player found
  if (!hasValidPlayer) {
    return (
      <div style={{ padding: "2rem", textAlign: "center", color: "#6a994e" }}>
        Loading game state...
      </div>
    );
  }

  return (
    <>
      <GameLayout
        // Game state
        gameId={gameId}
        gameState={gameState}
        currentPlayer={currentPlayer}
        otherPlayers={otherPlayers}
        isMyTurn={isMyTurn}
        needsToRespond={needsToRespond}
        pendingDogmaAction={pendingDogmaAction}
        playerDrawAge={playerDrawAge}
        actualDrawAge={actualDrawAge}
        error={error}
        clearError={clearError}
        // AI turn tracking
        aiTurnStartTime={aiTurnStartTime}
        lastAIActionTime={lastAIActionTime}
        onRetryAITurn={onRetryAITurn}
        // Actions and handlers
        selectedCard={selectedCard}
        selectedCardLocation={selectedCardLocation}
        selectedAge={selectedAge}
        setSelectedAge={setSelectedAge}
        multiSelectedCards={multiSelectedCards}
        onCardClick={onCardClick}
        onDraw={onDraw}
        handleMeld={handleMeld}
        handleDogma={handleDogma}
        handleAchieve={handleAchieve}
        handleSetupSelection={handleSetupSelection}
        handleDeclineDogma={handleDeclineDogma}
        cancelAction={cancelAction}
        submitMultiCardSelection={submitMultiCardSelection}
        submitCardOrder={submitCardOrder}
        handleLeaveGame={handleLeaveGame}
        // Unseen expansion: Meld source modal
        meldSourceModalOpen={meldSourceModalOpen}
        meldSourceModalLoading={meldSourceModalLoading}
        meldSourceModalError={meldSourceModalError}
        pendingMeldCard={pendingMeldCard}
        handleMeldSourceConfirm={handleMeldSourceConfirm}
        handleMeldSourceModalClose={handleMeldSourceModalClose}
      />
    </>
  );
}

function GameBoard() {
  return (
    <ErrorBoundary name="GameBoard">
      <GameBoardProvider>
        <ErrorBoundary name="GameBoardContent">
          <GameBoardContent />
        </ErrorBoundary>
      </GameBoardProvider>
    </ErrorBoundary>
  );
}

export default GameBoard;
