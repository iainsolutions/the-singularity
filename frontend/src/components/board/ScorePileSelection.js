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
  isCurrentPlayer,
}) => {
  // Only render when there's an active score_pile selection interaction
  const pendingAction = currentPendingAction || dogmaResponse?.pendingAction;
  const interactionData =
    pendingAction?.context?.interaction_data?.data ||
    pendingAction?.context ||
    {};
  const source = interactionData.source || pendingAction?.source;

  if (source !== "score_pile" || !dogmaResponse) {
    return null;
  }

  const cards = scorePile || [];
  const maxCount = interactionData.max_count ?? interactionData.count ?? 1;
  const minCount =
    interactionData.min_count ??
    (interactionData.is_optional ? 0 : interactionData.count) ??
    1;
  const isMultiCardSelection = maxCount > 1 || minCount > 1;

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
        📊 Score Pile — Select cards to return ({cards.length} cards)
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
        {cards.length > 0 ? (
          cards.map((card, index) => {
            const isEligible = isCardEligibleForDogmaResponse(card);
            const isClickable = isCurrentPlayer && isEligible;
            const isSelected = dogmaResponse?.multiSelectedCards?.some(
              (c) => c.card_id === card.card_id || c.name === card.name,
            );

            return (
              <Box
                key={`score-${card.card_id || card.name}-${index}`}
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
                  isClickable={isClickable}
                  isSelected={isSelected}
                  isSelecting={true}
                  showCheckbox={isMultiCardSelection && isEligible}
                  onClick={(clickedCard) => {
                    onCardClick &&
                      onCardClick(
                        clickedCard,
                        needsToRespond,
                        pendingAction,
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
            <Typography>No cards in score pile</Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default ScorePileSelection;
