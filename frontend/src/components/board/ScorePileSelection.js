import { Box, Chip, Typography } from "@mui/material";
import Card from "../Card";

const ScorePileSelection = ({
  scorePile,
  dogmaResponse,
  currentPendingAction,
  isCardEligibleForDogmaResponse,
  onCardClick,
  needsToRespond,
  compact = false,
  isCurrentPlayer = false,
}) => {
  // Check if we should show score pile selection
  // Check multiple possible paths due to varying message structures
  const pendingAction = currentPendingAction || dogmaResponse?.pendingAction;
  const isScorePileSelection =
    pendingAction?.context?.interaction_data?.data?.source === "score_pile" ||
    pendingAction?.context?.interaction_data?.source === "score_pile" ||
    pendingAction?.context?.selection_source === "score_pile" ||
    pendingAction?.context?.source === "score_pile" ||
    pendingAction?.source === "score_pile";

  // CRITICAL FIX: Only show score pile selection on the current player's board
  // when selecting from your own score pile (e.g., Education card).
  // Without this check, opponent's score pile would also show as selectable.
  // Note: For cards that select from opponent's score pile (if any), source_player
  // would need to be checked. Currently "score_pile" source means current player's pile.
  if (!isScorePileSelection || !scorePile || scorePile.length === 0 || !isCurrentPlayer) {
    return null;
  }

  return (
    <Box sx={{ mt: compact ? 1.5 : 3 }}>
      <Typography
        variant={compact ? "subtitle1" : "h6"}
        gutterBottom={!compact}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1,
          mb: compact ? 0.25 : 0.5,
          color: "warning.main",
        }}
      >
        📊 Select from Score Pile ({scorePile.length} cards)
      </Typography>
      <Box
        sx={{
          display: "flex",
          gap: compact ? 0.5 : 1,
          flexWrap: "wrap",
          p: compact ? 0.5 : 1,
          bgcolor: "background.paper",
          borderRadius: 2,
          border: "2px solid",
          borderColor: "warning.main",
          justifyContent: compact ? "center" : "flex-start",
        }}
      >
        {scorePile.map((card, index) => {
          const isEligible = isCardEligibleForDogmaResponse(card);
          const isSelected = dogmaResponse?.multiSelectedCards?.some((c) => c.name === card.name);

          return (
            <Box
              key={`score-${card.name}-${index}`}
              sx={{
                position: "relative",
                ...(isEligible &&
                  !isSelected && {
                    boxShadow: "0 0 12px rgba(76, 175, 80, 0.5)",
                    border: "2px solid",
                    borderColor: "success.main",
                    borderRadius: 1,
                    transform: "translateY(-4px)",
                    transition: "all 0.2s ease",
                  }),
                ...(isSelected && {
                  boxShadow: "0 0 20px rgba(25, 118, 210, 0.8)",
                  border: "3px solid",
                  borderColor: "primary.main",
                  borderRadius: 1,
                  transform: "translateY(-8px) scale(1.05)",
                  transition: "all 0.2s ease",
                }),
                ...(!isEligible && {
                  opacity: 0.4,
                  filter: "grayscale(70%)",
                  cursor: "not-allowed",
                }),
              }}
            >
              <Card
                card={card}
                size={compact ? "small" : "normal"}
                isClickable={isEligible}
                isSelected={isSelected}
                isSelecting={!!dogmaResponse}
                onClick={(clickedCard) => {
                  const effectivePendingAction =
                    currentPendingAction || dogmaResponse?.pendingAction;
                  onCardClick &&
                    onCardClick(
                      clickedCard,
                      needsToRespond,
                      effectivePendingAction,
                      true,
                      "score_pile",
                    );
                }}
              />
              {isEligible && !isSelected && (
                <Chip
                  label="✓ Eligible"
                  color="success"
                  size="small"
                  sx={{
                    position: "absolute",
                    top: -8,
                    right: -8,
                    fontSize: "0.75rem",
                    fontWeight: "bold",
                  }}
                />
              )}
              {isSelected && (
                <Chip
                  label="✓ Selected"
                  color="primary"
                  size="small"
                  sx={{
                    position: "absolute",
                    top: -8,
                    right: -8,
                    fontSize: "0.75rem",
                    fontWeight: "bold",
                    bgcolor: "primary.main",
                    color: "white",
                  }}
                />
              )}
            </Box>
          );
        })}
      </Box>
    </Box>
  );
};

export default ScorePileSelection;
