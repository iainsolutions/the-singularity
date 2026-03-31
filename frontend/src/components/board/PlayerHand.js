import { Box, Chip, Typography } from "@mui/material";
import Card from "../Card";

const PlayerHand = ({
  hand,
  isCurrentPlayer,
  needsToRespond,
  dogmaResponse,
  currentPendingAction,
  isCardEligibleForDogmaResponse,
  onCardClick,
  compact = false,
  hideBoard = false,
}) => {
  // Determine if hand should be shown
  // Hide if selecting from score pile
  const isScorePileSelection =
    dogmaResponse?.pendingAction?.context?.interaction_data?.data?.source === "score_pile" ||
    dogmaResponse?.pendingAction?.source === "score_pile" ||
    dogmaResponse?.pendingAction?.context?.source === "score_pile";

  if (hideBoard || isScorePileSelection) {
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
        }}
      >
        🃏 Hand ({hand?.length || 0} cards)
      </Typography>
      <Box
        sx={{
          display: "flex",
          gap: compact ? 0.5 : 1,
          flexWrap: "wrap",
          p: compact ? 0.5 : 1,
          bgcolor: "background.paper",
          borderRadius: 2,
          border: "1px solid",
          borderColor: "divider",
          justifyContent: compact ? "center" : "flex-start",
        }}
      >
        {hand && hand.length > 0 ? (
          hand.map((card, index) => {
            const isEligible = isCardEligibleForDogmaResponse(card);
            const isClickable = isCurrentPlayer && (!dogmaResponse || isEligible);
            const isSelected = dogmaResponse?.multiSelectedCards?.some((c) => c.name === card.name);

            // Check if this is a multi-card selection scenario
            const context = dogmaResponse?.pendingAction?.context || {};
            const interactionData = context.interaction_data?.data || context;
            const maxCount = interactionData.max_count ?? interactionData.count ?? 1;
            const minCount =
              interactionData.min_count ??
              (interactionData.is_optional ? 0 : interactionData.count) ??
              1;
            const isMultiCardSelection = dogmaResponse && (maxCount > 1 || minCount > 1);

            return (
              <Box
                key={`${card.name}-${index}`}
                sx={{
                  position: "relative",
                  ...(dogmaResponse &&
                    isEligible &&
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
                  ...(dogmaResponse &&
                    !isEligible && {
                      opacity: 0.4,
                      filter: "grayscale(70%)",
                      cursor: "not-allowed",
                    }),
                }}
              >
                <Card
                  card={card}
                  size={compact ? "small" : "normal"}
                  isClickable={isClickable}
                  isSelected={isSelected}
                  isSelecting={!!dogmaResponse}
                  showCheckbox={isMultiCardSelection && isEligible}
                  onClick={(clickedCard) => {
                    const effectivePendingAction =
                      currentPendingAction || dogmaResponse?.pendingAction;
                    onCardClick &&
                      onCardClick(
                        clickedCard,
                        needsToRespond,
                        effectivePendingAction,
                        true,
                        "hand",
                      );
                  }}
                />
                {dogmaResponse && isEligible && !isSelected && (
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
          })
        ) : (
          <Box
            sx={{
              padding: 3,
              textAlign: "center",
              border: "2px dashed",
              borderColor: "divider",
              borderRadius: 2,
              color: "text.secondary",
              width: "100%",
            }}
          >
            <Typography>No cards in hand</Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default PlayerHand;
