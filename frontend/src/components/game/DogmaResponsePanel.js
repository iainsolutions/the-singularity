import {
  Check as CheckIcon,
  Block as DeclineIcon,
  Warning as WarningIcon,
  ArrowUpward as ArrowUpIcon,
  ArrowDownward as ArrowDownIcon,
} from "@mui/icons-material";
import { Box, Button, Chip, Typography, Card, CardContent } from "@mui/material";
import { memo, useState, useEffect } from "react";
import {
  canDeclineDogmaResponse,
  getDeclineButtonText,
  getDogmaResponseMessage,
} from "../../utils/gameLogic";

const DogmaResponsePanel = memo(
  function DogmaResponsePanel({
    pendingDogmaAction,
    onDecline,
    multiSelectedCards = [],
    onSubmitMultiCard,
    onSelectColor, // NEW: Color selection handler
    onSubmitCardOrder, // NEW: Card ordering handler (Cities expansion: Search icon)
  }) {
    const message = getDogmaResponseMessage(pendingDogmaAction);
    const showDeclineButton = canDeclineDogmaResponse(pendingDogmaAction);
    const declineButtonText = getDeclineButtonText(pendingDogmaAction);

    // Check if this is a color selection interaction
    const interactionData = pendingDogmaAction?.context?.interaction_data?.data;
    const interactionType = interactionData?.type;
    const isColorSelection = interactionType === "select_color";
    const availableColors = interactionData?.available_colors || [];

    // Cities expansion: Check if this is a card ordering interaction (Search icon)
    const isCardOrdering = interactionType === "order_cards";
    const cardsToOrder = interactionData?.cards_to_order || [];
    const orderingInstruction = interactionData?.instruction || "Choose the order for these cards";

    // Card ordering state
    const [orderedCards, setOrderedCards] = useState([]);

    // Initialize ordered cards when interaction changes
    useEffect(() => {
      if (isCardOrdering && cardsToOrder.length > 0) {
        setOrderedCards([...cardsToOrder]);
      }
    }, [isCardOrdering, cardsToOrder]);

    // Move card up in order
    const moveCardUp = (index) => {
      if (index === 0) return;
      const newOrder = [...orderedCards];
      [newOrder[index - 1], newOrder[index]] = [newOrder[index], newOrder[index - 1]];
      setOrderedCards(newOrder);
    };

    // Move card down in order
    const moveCardDown = (index) => {
      if (index === orderedCards.length - 1) return;
      const newOrder = [...orderedCards];
      [newOrder[index], newOrder[index + 1]] = [newOrder[index + 1], newOrder[index]];
      setOrderedCards(newOrder);
    };

    // Submit card order
    const handleSubmitOrder = () => {
      const cardIds = orderedCards.map(card => card.card_id);
      onSubmitCardOrder(cardIds);
    };

    // Check if this is a multi-card selection
    const context = pendingDogmaAction?.context || {};
    const maxCount = Number(context.max_count ?? context.count ?? 1);
    const minCount = Number(context.min_count ?? (context.is_optional ? 0 : context.count) ?? 1);
    const isMultiCardSelection = maxCount > 1 || minCount > 1;
    const canSubmit =
      multiSelectedCards.length >= minCount && multiSelectedCards.length <= maxCount;

    // Color button styles
    const colorStyles = {
      red: { bgcolor: "#d32f2f", "&:hover": { bgcolor: "#b71c1c" } },
      blue: { bgcolor: "#1976d2", "&:hover": { bgcolor: "#0d47a1" } },
      green: { bgcolor: "#388e3c", "&:hover": { bgcolor: "#1b5e20" } },
      yellow: { bgcolor: "#f57c00", "&:hover": { bgcolor: "#e65100" } },
      purple: { bgcolor: "#7b1fa2", "&:hover": { bgcolor: "#4a148c" } },
    };

    return (
      <Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
          <WarningIcon color="warning" />
          <Typography variant="h6" sx={{ fontWeight: 600, color: "warning.main" }}>
            Dogma Action Required
          </Typography>
        </Box>

        <Typography
          variant="body1"
          sx={{
            mb: 2,
            p: 2,
            bgcolor: "warning.50",
            border: "1px solid",
            borderColor: "warning.200",
            borderRadius: 1,
            fontWeight: 500,
          }}
        >
          {message}
        </Typography>

        {/* Color selection UI */}
        {isColorSelection && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" sx={{ mb: 2, fontWeight: 600, color: "primary.main" }}>
              Select a color:
            </Typography>
            <Box sx={{ display: "flex", gap: 2, justifyContent: "center", flexWrap: "wrap" }}>
              {availableColors.map((color) => (
                <Button
                  key={color}
                  variant="contained"
                  size="large"
                  onClick={() => onSelectColor(color)}
                  sx={{
                    ...colorStyles[color],
                    color: "white",
                    minWidth: 120,
                    textTransform: "capitalize",
                    fontWeight: 600,
                    "&:hover": {
                      ...colorStyles[color]["&:hover"],
                      transform: "translateY(-2px)",
                      boxShadow: "0 6px 16px rgba(0, 0, 0, 0.3)",
                    },
                    transition: "all 0.2s ease-in-out",
                  }}
                >
                  {color}
                </Button>
              ))}
            </Box>
          </Box>
        )}

        {/* Cities expansion: Card ordering UI (Search icon) */}
        {isCardOrdering && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" sx={{ mb: 2, fontWeight: 600, color: "primary.main" }}>
              {orderingInstruction}
            </Typography>
            <Typography variant="caption" sx={{ mb: 2, display: "block", color: "text.secondary" }}>
              Use the arrow buttons to arrange cards in your preferred order (top card will be returned first)
            </Typography>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
              {orderedCards.map((card, index) => (
                <Card key={card.card_id || card.name} variant="outlined" sx={{ bgcolor: "background.paper" }}>
                  <CardContent sx={{ display: "flex", alignItems: "center", gap: 2, p: 1.5, "&:last-child": { pb: 1.5 } }}>
                    <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}>
                      <Button
                        size="small"
                        onClick={() => moveCardUp(index)}
                        disabled={index === 0}
                        sx={{ minWidth: 36, p: 0.5 }}
                      >
                        <ArrowUpIcon fontSize="small" />
                      </Button>
                      <Button
                        size="small"
                        onClick={() => moveCardDown(index)}
                        disabled={index === orderedCards.length - 1}
                        sx={{ minWidth: 36, p: 0.5 }}
                      >
                        <ArrowDownIcon fontSize="small" />
                      </Button>
                    </Box>
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {index + 1}. {card.name}
                      </Typography>
                      <Typography variant="caption" sx={{ color: "text.secondary" }}>
                        Age {card.age} • {card.color?.charAt(0).toUpperCase() + card.color?.slice(1)}
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              ))}
            </Box>
            <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
              <Button
                variant="contained"
                color="primary"
                size="large"
                startIcon={<CheckIcon />}
                onClick={handleSubmitOrder}
                sx={{
                  minWidth: 200,
                  "&:hover": {
                    transform: "translateY(-1px)",
                    boxShadow: "0 4px 12px rgba(25, 118, 210, 0.3)",
                  },
                  transition: "all 0.2s ease-in-out",
                }}
              >
                Confirm Order
              </Button>
            </Box>
          </Box>
        )}

        {/* Show selection status and selected cards for multi-card selection */}
        {isMultiCardSelection && (
          <Box sx={{ mb: 2 }}>
            <Box
              sx={{
                mb: 2,
                p: 1.5,
                bgcolor: "primary.50",
                borderRadius: 1,
                border: "1px solid",
                borderColor: "primary.200",
              }}
            >
              <Typography variant="body2" sx={{ fontWeight: 600, color: "primary.main" }}>
                Selection: {multiSelectedCards.length} of{" "}
                {minCount === maxCount ? minCount : `${minCount}-${maxCount}`} cards
              </Typography>
              {multiSelectedCards.length < minCount && (
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  Select {minCount - multiSelectedCards.length} more card
                  {minCount - multiSelectedCards.length !== 1 ? "s" : ""} to continue
                </Typography>
              )}
            </Box>

            {multiSelectedCards.length > 0 && (
              <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                {multiSelectedCards.map((card) => (
                  <Chip
                    key={card.name}
                    label={`${card.name} (Age ${card.age})`}
                    color="primary"
                    variant="filled"
                    size="small"
                    onDelete={null} // Could add removal functionality here
                  />
                ))}
              </Box>
            )}
          </Box>
        )}

        {/* Submit button for multi-card selection */}
        {isMultiCardSelection && (
          <Box
            sx={{
              display: "flex",
              justifyContent: "center",
              gap: 2,
              mb: showDeclineButton ? 0 : 2,
            }}
          >
            <Button
              variant="contained"
              color="primary"
              size="large"
              startIcon={<CheckIcon />}
              onClick={onSubmitMultiCard}
              disabled={!canSubmit}
              sx={{
                minWidth: 200,
                "&:hover": {
                  transform: "translateY(-1px)",
                  boxShadow: "0 4px 12px rgba(25, 118, 210, 0.3)",
                },
                transition: "all 0.2s ease-in-out",
              }}
            >
              {multiSelectedCards.length === 0
                ? `Select ${minCount === maxCount ? minCount : `${minCount}-${maxCount}`} Card${
                    minCount !== 1 ? "s" : ""
                  }`
                : `Accept Selection (${multiSelectedCards.length} Card${
                    multiSelectedCards.length !== 1 ? "s" : ""
                  })`}
            </Button>
          </Box>
        )}

        {showDeclineButton && (
          <Box sx={{ display: "flex", justifyContent: "center" }}>
            <Button
              variant="outlined"
              color="warning"
              startIcon={<DeclineIcon />}
              onClick={onDecline}
              sx={{
                "&:hover": {
                  bgcolor: "warning.50",
                  transform: "translateY(-1px)",
                  boxShadow: "0 4px 12px rgba(255, 152, 0, 0.2)",
                },
                transition: "all 0.2s ease-in-out",
              }}
            >
              {declineButtonText}
            </Button>
          </Box>
        )}
      </Box>
    );
  },
  (prevProps, nextProps) => {
    return (
      JSON.stringify(prevProps.pendingDogmaAction) ===
        JSON.stringify(nextProps.pendingDogmaAction) &&
      prevProps.onDecline === nextProps.onDecline &&
      JSON.stringify(prevProps.multiSelectedCards) ===
        JSON.stringify(nextProps.multiSelectedCards) &&
      prevProps.onSubmitMultiCard === nextProps.onSubmitMultiCard &&
      prevProps.onSelectColor === nextProps.onSelectColor
    );
  },
);

export default DogmaResponsePanel;
