import { useState, memo } from "react";
import {
  Box,
  Paper,
  Typography,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Grid,
  useTheme,
} from "@mui/material";
import { Close as CloseIcon } from "@mui/icons-material";
import Card from "./Card";

const ScorePile = memo(
  function ScorePile({
    scorePile = [],
    isClickable = false,
    compact = false,
    isCurrentPlayer = false,
  }) {
    const [showCards, setShowCards] = useState(false);

    // Calculate total score (sum of ages)
    const totalScore = scorePile.reduce((sum, card) => sum + (card.age || 0), 0);
    const cardCount = scorePile.length;

    const handleClick = () => {
      if (isClickable && cardCount > 0) {
        setShowCards(!showCards);
      }
    };

    const handleClose = () => {
      setShowCards(false);
    };

    const theme = useTheme();

    return (
      <>
        <Paper
          elevation={compact ? 0 : cardCount > 0 ? 2 : 1}
          onClick={handleClick}
          sx={{
            p: compact ? "4px 8px" : 2,
            cursor: isClickable && cardCount > 0 ? "pointer" : "default",
            transition: "all 0.2s ease",
            bgcolor: compact
              ? "rgba(255, 255, 255, 0.95)"
              : cardCount > 0
                ? "success.50"
                : "background.paper",
            border: compact ? "1px solid" : "1px solid",
            borderColor: compact ? "#e0e0e0" : cardCount > 0 ? "success.200" : "divider",
            borderRadius: compact ? "6px" : 1,
            boxShadow: compact ? "0 1px 2px rgba(0, 0, 0, 0.1)" : "default",
            "&:hover":
              isClickable && cardCount > 0
                ? {
                    elevation: 3,
                    borderColor: "primary.main",
                    transform: compact ? "none" : "translateY(-2px)",
                  }
                : {},
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            {/* Visual stack representation */}
            <Box
              sx={{ position: "relative", width: compact ? 30 : 80, height: compact ? 30 : 100 }}
            >
              {cardCount > 0 ? (
                <>
                  {/* Show stacked cards effect */}
                  {[...Array(Math.min(3, cardCount))].map((_, index) => (
                    <Paper
                      key={index}
                      elevation={1}
                      sx={{
                        position: "absolute",
                        width: compact ? 24 : 64,
                        height: compact ? 26 : 84,
                        bottom: compact ? index * 1 : index * 2,
                        right: compact ? index * 1 : index * 2,
                        zIndex: index,
                        bgcolor: "background.paper",
                        border: "1px solid",
                        borderColor: "divider",
                      }}
                    />
                  ))}

                  {/* Top card with info */}
                  <Paper
                    elevation={2}
                    sx={{
                      position: "absolute",
                      width: compact ? 24 : 64,
                      height: compact ? 26 : 84,
                      zIndex: 3,
                      bgcolor: "primary.main",
                      color: "white",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                      bottom: 0,
                      right: 0,
                    }}
                  >
                    {!compact ? (
                      <>
                        <Typography variant="h4" component="div">
                          📚
                        </Typography>
                        <Typography variant="h6" component="div" sx={{ fontWeight: "bold" }}>
                          {cardCount}
                        </Typography>
                        <Typography variant="caption" component="div" sx={{ opacity: 0.9 }}>
                          cards
                        </Typography>
                      </>
                    ) : (
                      <Typography
                        variant="caption"
                        component="div"
                        sx={{ fontWeight: "bold", fontSize: "10px" }}
                      >
                        {cardCount}
                      </Typography>
                    )}
                  </Paper>
                </>
              ) : (
                <Paper
                  variant="outlined"
                  sx={{
                    width: "100%",
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    bgcolor: "background.default",
                    color: "text.secondary",
                    borderStyle: "dashed",
                  }}
                >
                  {!compact ? (
                    <>
                      <Typography variant="h4" component="div" sx={{ opacity: 0.5 }}>
                        📚
                      </Typography>
                      <Typography variant="caption">Empty</Typography>
                    </>
                  ) : (
                    <Typography variant="caption" sx={{ fontSize: "8px", opacity: 0.5 }}>
                      0
                    </Typography>
                  )}
                </Paper>
              )}
            </Box>

            {/* Score display */}
            <Box sx={{ textAlign: "center" }}>
              <Typography
                variant={compact ? "body2" : "h3"}
                component="div"
                sx={{
                  fontWeight: "bold",
                  color: cardCount > 0 ? "primary.main" : "text.secondary",
                  lineHeight: 1,
                  fontSize: compact ? "11px" : "inherit",
                }}
              >
                {totalScore}
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ fontSize: compact ? "8px" : "inherit" }}
              >
                Score
              </Typography>
            </Box>

            {/* Cards count chip */}
            {!compact && (
              <Box sx={{ ml: "auto" }}>
                <Chip
                  label={`${cardCount} cards`}
                  color={cardCount > 0 ? "primary" : "default"}
                  variant={cardCount > 0 ? "filled" : "outlined"}
                  size="small"
                />
              </Box>
            )}
          </Box>

          {isClickable && cardCount > 0 && !compact && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ mt: 1, display: "block", textAlign: "center" }}
            >
              Click to view cards
            </Typography>
          )}
        </Paper>

        {/* Dialog to show cards */}
        <Dialog
          open={showCards}
          onClose={handleClose}
          maxWidth="md"
          fullWidth
          PaperProps={{
            sx: {
              minHeight: "60vh",
            },
          }}
        >
          <DialogTitle
            sx={{
              bgcolor: "primary.main",
              color: "white",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <Typography variant="h6">
              Score Pile ({cardCount} cards, {totalScore} points)
            </Typography>
            <IconButton onClick={handleClose} sx={{ color: "white" }} size="small">
              <CloseIcon />
            </IconButton>
          </DialogTitle>

          {!isCurrentPlayer && (
            <Box
              sx={{
                px: 3,
                py: 1,
                bgcolor: "info.50",
                borderBottom: "1px solid",
                borderColor: "divider",
              }}
            >
              <Typography variant="caption" color="text.secondary">
                ℹ️ Opponent's cards are hidden unless they've been revealed
              </Typography>
            </Box>
          )}

          <DialogContent sx={{ p: 3 }}>
            <Grid container spacing={2}>
              {scorePile.map((card, index) => {
                // Show card back for opponent cards unless they're revealed
                const showCardBack = !isCurrentPlayer && !card.is_revealed;

                return (
                  <Grid item xs={6} sm={4} md={3} key={`${card.name}-${index}`}>
                    <Box sx={{ position: "relative" }}>
                      {showCardBack ? (
                        // Show card back for hidden opponent cards
                        <Box
                          sx={{
                            width: "180px",
                            height: "120px",
                            backgroundImage: `url(/cards/back/Print_BaseCards_back-${String(
                              card.card_id?.match(/\d+/)?.[0] || 1,
                            ).padStart(3, "0")}.png)`,
                            backgroundSize: "cover",
                            backgroundPosition: "center",
                            borderRadius: 1,
                            border: "1px solid #333",
                          }}
                        >
                          <Chip
                            label={`Age ${card.age}`}
                            size="small"
                            sx={{
                              position: "absolute",
                              bottom: 4,
                              right: 4,
                              bgcolor: "rgba(0,0,0,0.7)",
                              color: "white",
                              fontSize: "0.7rem",
                            }}
                          />
                        </Box>
                      ) : (
                        // Show actual card for current player or revealed cards
                        <>
                          <Card card={card} size="small" lazy={true} />
                          <Chip
                            label={`Age ${card.age}`}
                            size="small"
                            sx={{
                              position: "absolute",
                              bottom: 4,
                              right: 4,
                              bgcolor: "rgba(0,0,0,0.7)",
                              color: "white",
                              fontSize: "0.7rem",
                            }}
                          />
                        </>
                      )}
                    </Box>
                  </Grid>
                );
              })}
            </Grid>
          </DialogContent>
        </Dialog>
      </>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison for React.memo
    return (
      prevProps.isClickable === nextProps.isClickable &&
      prevProps.compact === nextProps.compact &&
      prevProps.isCurrentPlayer === nextProps.isCurrentPlayer &&
      prevProps.scorePile?.length === nextProps.scorePile?.length &&
      prevProps.scorePile?.reduce((sum, card) => sum + card.age, 0) ===
        nextProps.scorePile?.reduce((sum, card) => sum + card.age, 0)
    );
  },
);

export default ScorePile;
