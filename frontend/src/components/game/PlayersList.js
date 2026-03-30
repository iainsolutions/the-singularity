/**
 * PlayersList - Handles rendering of all players (current and others)
 */
import { Box, Paper } from "@mui/material";
import PlayerBoard from "../PlayerBoard";

function PlayersList({
  currentPlayer,
  otherPlayers,
  gameState,
  onCardClick,
  needsToRespond,
  pendingDogmaAction,
  multiSelectedCards,
  isMobile,
  isTablet,
}) {
  const compact = isMobile || isTablet;
  const hideBoard = gameState?.phase === "setup_card_selection";

  // Check if there's a pending dogma action that might require opponent interaction
  const hasPendingDogmaAction = !!pendingDogmaAction;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {/* Other Players */}
      {otherPlayers.map((player) => (
        <Paper key={player.id} elevation={1} sx={{ p: 1.5, mb: 1 }}>
          <PlayerBoard
            player={player}
            isCurrentPlayer={false}
            hideBoard={hideBoard}
            compareToPlayer={currentPlayer}
            compact={compact}
            // CRITICAL FIX: Always enable card clicking for boards to support dogma actions
            // The click handler will determine if the click is valid based on game state
            onCardClick={onCardClick}
            needsToRespond={hasPendingDogmaAction}
            dogmaResponse={
              hasPendingDogmaAction
                ? {
                    pendingAction: pendingDogmaAction,
                    eligibleColors: pendingDogmaAction?.context?.eligible_colors || [],
                    multiSelectedCards: multiSelectedCards,
                  }
                : null
            }
          />
        </Paper>
      ))}

      {/* Current Player */}
      {currentPlayer && (
        <Paper elevation={2} sx={{ p: 1.5, bgcolor: "primary.50" }}>
          <PlayerBoard
            player={currentPlayer}
            isCurrentPlayer={true}
            onCardClick={onCardClick}
            showHand={true}
            hideBoard={hideBoard}
            needsToRespond={needsToRespond}
            dogmaResponse={
              needsToRespond
                ? {
                    pendingAction: pendingDogmaAction,
                    eligibleColors: pendingDogmaAction?.context?.eligible_colors || [],
                    multiSelectedCards: multiSelectedCards,
                  }
                : null
            }
            compareToPlayer={otherPlayers[0]}
            compact={compact}
          />
        </Paper>
      )}
    </Box>
  );
}

export default PlayersList;
