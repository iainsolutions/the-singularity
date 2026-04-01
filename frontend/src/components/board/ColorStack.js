import { Box, Chip, Typography } from "@mui/material";
import Card from "../Card";
import styles from "../PlayerBoard.module.css";

const ColorStack = ({
  color,
  cards,
  splayDirection,
  isEligibleForColorSelection,
  onStackClick,
  onCardClick,
  isCurrentPlayer,
  needsToRespond,
  dogmaResponse,
  currentPendingAction,
  isCardEligibleForDogmaResponse,
  canActivateDogma,
  shouldShowClickableBoardCards,
  compact = false,
}) => {
  // Color mapping for visual feedback
  const colorMap = {
    red: "#d32f2f",
    blue: "#1976d2",
    green: "#388e3c",
    yellow: "#f57c00",
    purple: "#7b1fa2",
  };

  const splayClass = splayDirection
    ? styles[`splay${splayDirection.charAt(0).toUpperCase() + splayDirection.slice(1)}`]
    : styles.splayNone;

  // Calculate container dimensions based on splay and card count
  const cardCount = cards.length;
  const baseWidth = compact ? 100 : 180;
  const baseHeight = compact ? 80 : 230;

  // Limit visible cards to prevent excessive spreading
  const maxVisibleCards = 10;
  const visibleCardCount = Math.min(cardCount, maxVisibleCards);

  let containerWidth = baseWidth;
  let containerHeight = baseHeight;

  if (visibleCardCount > 0 && splayDirection) {
    const offset = compact ? 20 : 40;

    switch (splayDirection) {
      case "left":
        // Width increases as cards shift left (negative offset)
        containerWidth = baseWidth + Math.max(0, (visibleCardCount - 1) * offset);
        break;
      case "right":
        // Width increases as cards shift right
        containerWidth = baseWidth + (visibleCardCount - 1) * offset;
        break;
      case "up":
        // Height increases as cards shift up (negative offset)
        containerHeight = baseHeight + Math.max(0, (visibleCardCount - 1) * offset);
        break;
      case "aslant":
        // Both width and height increase for diagonal
        containerWidth = baseWidth + (visibleCardCount - 1) * (compact ? 30 : 60);
        containerHeight = baseHeight + (visibleCardCount - 1) * (compact ? 15 : 30);
        break;
    }
  }

  return (
    <Box
      className={styles.colorStack}
      onClick={() => isEligibleForColorSelection && onStackClick(color)}
      sx={{
        minHeight: containerHeight + "px",
        width: containerWidth + "px",
        position: "relative",
        marginRight: "15px",
        marginBottom: cards.length > maxVisibleCards && splayDirection ? "40px" : "15px",
        // Add visual feedback for clickable colors
        cursor: isEligibleForColorSelection ? "pointer" : "default",
        borderRadius: isEligibleForColorSelection ? "8px" : "0px",
        border: isEligibleForColorSelection ? `3px solid ${colorMap[color]}` : "none",
        boxShadow: isEligibleForColorSelection
          ? `0 0 20px ${colorMap[color]}80, 0 0 40px ${colorMap[color]}40`
          : "none",
        transition: "all 0.3s ease-in-out",
        "&:hover": isEligibleForColorSelection
          ? {
              transform: "scale(1.05)",
              boxShadow: `0 0 30px ${colorMap[color]}CC, 0 0 60px ${colorMap[color]}66`,
              border: `4px solid ${colorMap[color]}`,
            }
          : {},
      }}
    >
      {/* Splay Indicator */}
      {splayDirection && cards.length > 1 && (
        <div className={`${styles.splayIndicator} ${styles[splayDirection]}`} />
      )}

      {/* Card Count Badge for Non-Splayed Stacks */}
      {!splayDirection && cards.length > 1 && (
        <Chip
          label={cards.length}
          size="small"
          color="primary"
          sx={{
            position: "absolute",
            top: -8,
            right: -8,
            height: 20,
            minWidth: 20,
            fontSize: "0.7rem",
            fontWeight: "bold",
            zIndex: 150,
            bgcolor: "primary.main",
            color: "white",
            border: "2px solid white",
            boxShadow: "0 2px 4px rgba(0,0,0,0.3)",
            "& .MuiChip-label": {
              px: 0.5,
            },
          }}
        />
      )}

      {/* Symbol count summary when stack exceeds max visible */}
      {cards.length > maxVisibleCards && splayDirection && (
        <Box
          sx={{
            position: "absolute",
            bottom: -25,
            left: 0,
            right: 0,
            display: "flex",
            gap: "8px",
            justifyContent: "center",
            alignItems: "center",
            fontSize: "12px",
            backgroundColor: "rgba(255, 255, 255, 0.95)",
            padding: "2px 8px",
            borderRadius: "4px",
            border: "1px solid rgba(0, 0, 0, 0.1)",
            zIndex: 100,
          }}
        >
          <Typography variant="caption" sx={{ fontWeight: "bold", mr: 1 }}>
            Stack: {cards.length} cards
          </Typography>
          {(() => {
            // Calculate visible symbols based on splay direction
            const symbolCounts = {
              castle: 0,
              leaf: 0,
              lightbulb: 0,
              crown: 0,
              factory: 0,
              clock: 0,
            };

            // Count symbols from all cards considering splay
            cards.forEach((card, index) => {
              if (index === cards.length - 1) {
                // Top card is fully visible
                card.symbols?.forEach((symbol) => {
                  if (symbolCounts[symbol] !== undefined) {
                    symbolCounts[symbol]++;
                  }
                });
              } else if (splayDirection) {
                // Other cards show partial symbols based on splay
                const visiblePositions =
                  {
                    left: [3], // Right symbol
                    right: [0, 1], // Left symbols
                    up: [1, 2, 3], // Bottom symbols
                    aslant: [0, 1, 2, 3], // All symbols
                  }[splayDirection] || [];

                visiblePositions.forEach((pos) => {
                  if (card.symbol_positions && card.symbol_positions[pos]) {
                    const symbol = card.symbol_positions[pos].toLowerCase();
                    if (symbolCounts[symbol] !== undefined) {
                      symbolCounts[symbol]++;
                    }
                  }
                });
              }
            });

            // Display non-zero counts
            return Object.entries(symbolCounts)
              .filter(([_, count]) => count > 0)
              .map(([symbol, count]) => (
                <Box key={symbol} sx={{ display: "flex", alignItems: "center", gap: "2px" }}>
                  <span>{count}</span>
                  <span style={{ fontSize: "14px" }}>
                    {symbol === "castle" && "🏰"}
                    {symbol === "leaf" && "🍃"}
                    {symbol === "lightbulb" && "💡"}
                    {symbol === "crown" && "👑"}
                    {symbol === "factory" && "🏭"}
                    {symbol === "clock" && "⏰"}
                  </span>
                </Box>
              ));
          })()}
        </Box>
      )}

      {/* Stack Cards with Splay */}
      <Box
        className={`${styles.splayContainer} ${compact ? styles.splayContainerCompact : ""} ${splayClass}`}
        sx={{
          width: containerWidth + "px",
          height: containerHeight + "px",
        }}
      >
        {cards.map((card, index) => {
          // For cards beyond max visible, cluster them together
          const displayIndex = index >= maxVisibleCards ? maxVisibleCards - 1 : index;

          return (
            <Box
              key={`${card.name}-${index}`}
              className={styles.splayedCard}
              sx={{
                "--card-index": displayIndex,
                // Add slight offset for clustered cards
                ...(index >= maxVisibleCards && {
                  transform: `translate(${(index - maxVisibleCards + 1) * 2}px, ${
                    (index - maxVisibleCards + 1) * 2
                  }px)`,
                }),
              }}
            >
              <Card
                card={card}
                size={compact ? "tiny" : "normal"}
                isClickable={
                  index === cards.length - 1 &&
                  ((shouldShowClickableBoardCards &&
                    needsToRespond &&
                    (isCardEligibleForDogmaResponse(card) || isEligibleForColorSelection)) ||
                    (isCurrentPlayer && !needsToRespond))
                }
                isSelecting={!!dogmaResponse && index === cards.length - 1}
                isEligible={
                  needsToRespond &&
                  index === cards.length - 1 &&
                  isCardEligibleForDogmaResponse(card)
                }
                isActivatable={
                  index === cards.length - 1 &&
                  isCurrentPlayer &&
                  !needsToRespond &&
                  canActivateDogma.includes(card.name)
                }
                onClick={(card) => {
                  if (index === cards.length - 1) {
                    // Use currentPendingAction (enhanced) over dogmaResponse.pendingAction (stale)
                    const effectivePendingAction =
                      currentPendingAction || dogmaResponse?.pendingAction;

                    try {
                      if (onCardClick) {
                        onCardClick(card, needsToRespond, effectivePendingAction, true, "board");
                      }
                    } catch (error) {
                      console.error("💥 [ColorStack] Error in card click handler:", error);
                    }
                  }
                }}
              />
            </Box>
          );
        })}
      </Box>

      {/* Empty stack placeholder */}
      {cards.length === 0 && (
        <Box
          sx={{
            minHeight: containerHeight + "px",
            width: containerWidth + "px",
          }}
        />
      )}
    </Box>
  );
};

export default ColorStack;
