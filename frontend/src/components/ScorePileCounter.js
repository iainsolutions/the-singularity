import { memo, useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Grid,
  Box,
  Typography,
} from "@mui/material";
import { Close as CloseIcon } from "@mui/icons-material";
import Card from "./Card";
import styles from "./SymbolCounter.module.css";

const ScorePileCounter = memo(
  function ScorePileCounter({ player, isCurrentPlayer = false }) {
    const [showScorePile, setShowScorePile] = useState(false);

    if (!player) return null;

    // Calculate total score (sum of ages)
    const totalScore = player?.score_pile?.reduce((sum, card) => sum + (card.age || 0), 0) || 0;
    const cardCount = player?.score_pile?.length || 0;

    return (
      <>
        {/* Score Pile Counter - Clickable */}
        <div
          className={styles.symbolItem}
          title={`Score: ${totalScore} points (${cardCount} cards) - click to view`}
          onClick={() => {
            if (cardCount > 0) {
              setShowScorePile(true);
            }
          }}
          style={{ cursor: cardCount > 0 ? "pointer" : "default" }}
        >
          <span className={styles.symbolText}>📊</span>
          <span className={styles.symbolCount}>{totalScore}</span>
        </div>

        {/* Score Pile Modal */}
        <Dialog
          open={showScorePile}
          onClose={() => setShowScorePile(false)}
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
              {player?.name}'s Score Pile ({player?.score_pile?.length || 0} cards,{" "}
              {player?.score_pile?.reduce((sum, card) => sum + (card.age || 0), 0)} points)
            </Typography>
            <IconButton
              onClick={() => setShowScorePile(false)}
              sx={{ color: "white" }}
              size="small"
            >
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
              {player?.score_pile?.map((card, index) => {
                // Show card back for opponent cards unless they're revealed
                const showCardBack = !isCurrentPlayer && !card.is_revealed;

                return (
                  <Grid item xs={6} sm={4} md={3} key={`${card.name}-${index}`}>
                    <Box sx={{ position: "relative" }}>
                      {showCardBack ? (
                        // Show card back for hidden opponent cards
                        <Card
                          card={{
                            ...card,
                            name: "Hidden Card",
                            is_back: true, // This will trigger the card component to show the back
                          }}
                          size="small"
                          lazy={true}
                          showBack={true}
                        />
                      ) : (
                        // Show actual card for current player or revealed cards
                        <Card card={card} size="small" lazy={true} />
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
    // Custom comparison function for React.memo
    return (
      JSON.stringify(prevProps.player?.score_pile) ===
        JSON.stringify(nextProps.player?.score_pile) &&
      prevProps.player?.name === nextProps.player?.name &&
      prevProps.isCurrentPlayer === nextProps.isCurrentPlayer
    );
  },
);

export default ScorePileCounter;
