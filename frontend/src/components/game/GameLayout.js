/**
 * GameLayout - Handles the overall game layout and responsive behavior
 */
import { Container, Paper, Box, Alert, useTheme, useMediaQuery, Typography, Button, Backdrop } from "@mui/material";
import EmojiEventsIcon from "@mui/icons-material/EmojiEvents";
import GameHeader from "./GameHeader";
import GamePanels from "./GamePanels";
import PlayersList from "./PlayersList";
import SetupPhasePanel from "./SetupPhasePanel";
import ActionLog from "../ActionLog";
import AICostMonitor from "./AICostMonitor";
import AITurnIndicator from "./AITurnIndicator";
import { useGame } from "../../context/GameContext";
import ActionsPanel from "./ActionsPanel";
import MeldSourceModal from "./MeldSourceModal";
// import DogmaResultsDisplay from "../DogmaResultsDisplay"; // Disabled - info appears in action log

function GameLayout({
  // Game state
  gameId,
  gameState,
  currentPlayer,
  otherPlayers,
  isMyTurn,
  needsToRespond,
  pendingDogmaAction,
  playerDrawAge,
  actualDrawAge,
  error,
  clearError,
  // AI turn tracking
  aiTurnStartTime,
  lastAIActionTime,
  onRetryAITurn,

  // Actions and handlers
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
}) {
  const { activityEvents, clearActivity } = useGame();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("lg"));
  const isTablet = useMediaQuery(theme.breakpoints.down("xl"));

  // Calculate age deck sizes from age_decks if age_deck_sizes is not available
  const ageDeckSizes =
    gameState.age_deck_sizes ||
    Object.fromEntries(
      Object.entries(gameState.age_decks || {}).map(([age, cards]) => [
        parseInt(age),
        Array.isArray(cards) ? cards.length : 0,
      ]),
    );

  // Get expansion deck sizes
  const citiesDeckSizes = gameState.cities_deck_sizes || {};
  const echoesDeckSizes = gameState.echoes_deck_sizes || {};
  const figuresDeckSizes = gameState.figures_deck_sizes || {};
  const artifactsDeckSizes = gameState.artifacts_deck_sizes || {};
  const unseenDeckSizes = gameState.unseen_expansion_deck_sizes || {};

  return (
    <Container maxWidth={false} sx={{ padding: { xs: 0.5, sm: 1 }, pb: isMyTurn ? 12 : 1 }}>
      <title>Innovation - Game {gameId?.slice(0, 8)}</title>

      {/* Game Header */}
      <Paper elevation={1} sx={{ mb: 1, p: 1.5 }}>
        <GameHeader gameId={gameId} gameState={gameState} onLeaveGame={handleLeaveGame} />
      </Paper>

      {/* Error Display */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={clearError}>
          {error}
        </Alert>
      )}

      {/* Dogma Results Display - Disabled as info appears in action log */}

      {/* Setup Card Selection Phase */}
      {gameState?.phase === "setup_card_selection" && currentPlayer && (
        <Paper elevation={1} sx={{ mb: 1, p: 1.5 }}>
          <SetupPhasePanel cards={currentPlayer.hand} onCardSelect={handleSetupSelection} />
        </Paper>
      )}

      {/* Age Decks, Junk Pile, and Achievements */}
      <GamePanels
        selectedAge={selectedAge}
        setSelectedAge={setSelectedAge}
        ageDeckSizes={ageDeckSizes}
        citiesDeckSizes={citiesDeckSizes}
        echoesDeckSizes={echoesDeckSizes}
        figuresDeckSizes={figuresDeckSizes}
        artifactsDeckSizes={artifactsDeckSizes}
        unseenDeckSizes={unseenDeckSizes}
        achievementCards={gameState.achievement_cards}
        junkPile={gameState.junk_pile}
        isMyTurn={isMyTurn}
        currentPlayer={currentPlayer}
        isMobile={isMobile}
        isTablet={isTablet}
      />

      {/* AI Turn Indicator - Show when AI player is taking their turn */}
      {(() => {
        const currentPlayerData = gameState?.players?.[gameState?.state?.current_player_index];
        const isAITurn = currentPlayerData?.is_ai && gameState?.phase === "playing";
        const aiPlayerName = currentPlayerData?.name || "AI";

        return isAITurn ? (
          <AITurnIndicator
            isAITurn={isAITurn}
            aiPlayerName={aiPlayerName}
            turnStartTime={aiTurnStartTime}
            lastActionTime={lastAIActionTime}
            onRetryAITurn={onRetryAITurn}
          />
        ) : null;
      })()}

      {/* Main Game Layout */}
      <Box
        sx={{
          display: "flex",
          gap: 2,
          pb: isMyTurn || needsToRespond ? { xs: 20, sm: 18, md: 16 } : 0,
        }}
      >
        {/* Main Game Area */}
        <Box sx={{ flex: 1 }}>
          <PlayersList
            currentPlayer={currentPlayer}
            otherPlayers={otherPlayers}
            gameState={gameState}
            onCardClick={onCardClick}
            needsToRespond={needsToRespond}
            pendingDogmaAction={pendingDogmaAction}
            multiSelectedCards={multiSelectedCards}
            isMobile={isMobile}
            isTablet={isTablet}
          />
        </Box>

        {/* Action Log + Activity Sidebar */}
        <Box sx={{ width: { xs: "100%", lg: "400px" }, flexShrink: 0 }}>
          <Paper
            elevation={1}
            sx={{
              p: 2,
              position: { lg: "sticky" },
              top: { lg: 16 },
              maxHeight: { lg: "calc(100vh - 32px)" },
              overflow: "auto",
            }}
          >
            <ActionLog actionLog={gameState?.action_log || []} gameState={gameState} />
          </Paper>
        </Box>
      </Box>

      {/* Fixed Actions Panel at bottom */}
      {(isMyTurn || needsToRespond) && (
        <Paper
          elevation={3}
          sx={{
            position: "fixed",
            bottom: 0,
            left: 0,
            right: 0,
            p: needsToRespond ? { xs: 0.5, sm: 0.75 } : { xs: 1, sm: 1.5 },
            bgcolor: "background.paper",
            borderTop: "2px solid",
            borderColor: "primary.main",
            zIndex: 1200,
            maxWidth: "100vw",
            boxShadow: "0 -4px 20px rgba(0,0,0,0.15)",
            backdropFilter: "blur(10px)",
            backgroundColor: "rgba(255, 255, 255, 0.95)",
          }}
        >
          <Container maxWidth="lg" sx={{ px: { xs: 1, sm: 2 } }}>
            <ActionsPanel
              selectedCard={selectedCard}
              selectedCardLocation={selectedCardLocation}
              playerDrawAge={playerDrawAge}
              actualDrawAge={actualDrawAge}
              actionsRemaining={gameState.state?.actions_remaining || 0}
              canMeld={!!currentPlayer.hand?.length}
              currentPlayer={currentPlayer}
              ageDeckSizes={ageDeckSizes}
              achievementCards={gameState.achievement_cards}
              onDraw={onDraw}
              onMeld={handleMeld}
              onDogma={handleDogma}
              onAchieve={handleAchieve}
              needsToRespond={needsToRespond}
              pendingDogmaAction={pendingDogmaAction}
              multiSelectedCards={multiSelectedCards}
              onSubmitMultiCard={submitMultiCardSelection}
              onSubmitCardOrder={submitCardOrder}
              onDecline={handleDeclineDogma}
              onCancelSelection={cancelAction}
            />
          </Container>
        </Paper>
      )}

      {/* AI Cost Monitor - shows if any AI players in game */}
      {gameState?.players?.some((p) => p.is_ai) && <AICostMonitor gameId={gameId} />}

      {/* Unseen expansion: Meld source modal */}
      <MeldSourceModal
        open={meldSourceModalOpen}
        onClose={handleMeldSourceModalClose}
        onConfirm={handleMeldSourceConfirm}
        handCards={currentPlayer?.hand || []}
        safe={currentPlayer?.safe || null}
        targetColor={pendingMeldCard?.color || null}
        loading={meldSourceModalLoading}
        error={meldSourceModalError}
      />

      {/* Victory Banner - shown when game is finished */}
      {gameState?.phase === "finished" && (
        <Backdrop
          open={true}
          sx={{
            zIndex: 1400,
            backgroundColor: "rgba(0, 0, 0, 0.7)",
          }}
        >
          <Paper
            elevation={8}
            sx={{
              p: 4,
              textAlign: "center",
              maxWidth: 500,
              background: "linear-gradient(135deg, #1a237e 0%, #4a148c 100%)",
              color: "white",
              borderRadius: 3,
            }}
          >
            <EmojiEventsIcon sx={{ fontSize: 80, color: "#ffd700", mb: 2 }} />
            <Typography variant="h3" component="h1" sx={{ fontWeight: "bold", mb: 2 }}>
              Game Over!
            </Typography>
            <Typography variant="h4" sx={{ mb: 1 }}>
              {gameState?.winner?.name || "Unknown"} Wins!
            </Typography>
            <Typography variant="h6" sx={{ mb: 3, opacity: 0.9 }}>
              {(() => {
                const winner = gameState?.winner;
                if (!winner) return "";
                const achievements = winner.achievements?.length || 0;
                const score = winner.score || winner.score_pile_value || 0;
                if (achievements >= 6) {
                  return `Victory by ${achievements} Achievements`;
                }
                return `Score: ${score} points | ${achievements} Achievements`;
              })()}
            </Typography>
            <Button
              variant="contained"
              size="large"
              onClick={handleLeaveGame}
              sx={{
                bgcolor: "#ffd700",
                color: "#1a237e",
                fontWeight: "bold",
                "&:hover": { bgcolor: "#ffeb3b" },
              }}
            >
              Return to Lobby
            </Button>
          </Paper>
        </Backdrop>
      )}
    </Container>
  );
}

export default GameLayout;
