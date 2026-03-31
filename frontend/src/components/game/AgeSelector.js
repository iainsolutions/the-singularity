import { memo } from "react";
import { Box, Typography } from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import styles from "./AgeSelector.module.css";

const ERAS = Array.from({ length: 10 }, (_, i) => i + 1);

// Domain colors for era-based theming
const ERA_COLORS = {
  1: "#0066CC", 2: "#0066CC",
  3: "#339933", 4: "#339933",
  5: "#CC9900", 6: "#CC9900",
  7: "#7733AA", 8: "#7733AA",
  9: "#CC3333", 10: "#CC3333",
};

const AgeSelector = memo(
  function AgeSelector({
    selectedAge,
    ageDeckSizes,
    onSelectAge,
    isMyTurn,
    compact = false,
    junkPile = [],
  }) {
    return (
      <Box sx={{ display: "flex", gap: 3, alignItems: "flex-start" }}>
        <Box>
          <Typography
            variant="body2"
            sx={{
              mb: 0.5, fontWeight: 600, color: "primary.main",
              fontSize: compact ? "0.6rem" : "0.7rem", lineHeight: 1,
              fontFamily: "'Orbitron', sans-serif",
            }}
          >
            Supply Piles
          </Typography>
          <div className={`${styles.ageRow} ${compact ? styles.ageRowCompact : ""}`}>
            {ERAS.map((era) => {
              const cardsRemaining = ageDeckSizes?.[era] || 0;
              const hasCards = cardsRemaining > 0;
              const isSelected = selectedAge === era;

              return (
                <div
                  key={era}
                  className={`${styles.ageOption} ${isSelected ? styles.ageOptionSelected : ""} ${
                    !hasCards ? styles.ageOptionEmpty : ""
                  } ${!isMyTurn ? styles.ageOptionDisabled : ""}`}
                  onClick={() => isMyTurn && hasCards && onSelectAge(era)}
                  title={
                    !hasCards
                      ? `Era ${era} supply is empty`
                      : `Era ${era} supply (${cardsRemaining} cards)`
                  }
                >
                  {hasCards ? (
                    <div
                      className={styles.eraDeck}
                      style={{
                        background: `linear-gradient(135deg, #1B2A4A 0%, ${ERA_COLORS[era]}33 100%)`,
                        borderColor: ERA_COLORS[era],
                      }}
                    >
                      <span className={styles.eraNumber}>{era}</span>
                    </div>
                  ) : (
                    <div className={styles.ageEmpty}>
                      <span className={styles.ageEmptyText}>Empty</span>
                    </div>
                  )}
                  <span className={styles.ageCount}>{cardsRemaining}</span>
                </div>
              );
            })}
          </div>
        </Box>

        {/* Junk Pile */}
        <Box>
          <Typography
            variant="body2"
            sx={{
              mb: 0.5, fontWeight: 600, color: "primary.main",
              fontSize: compact ? "0.6rem" : "0.7rem", lineHeight: 1,
            }}
          >
            Junk
          </Typography>
          <div
            style={{
              width: compact ? "60px" : "80px",
              height: compact ? "45px" : "60px",
              border: junkPile?.length > 0 ? "2px solid #d32f2f" : "2px solid #999",
              borderRadius: "4px",
              opacity: junkPile?.length > 0 ? 1 : 0.5,
              overflow: "hidden",
            }}
            title={junkPile?.length > 0 ? `Junk pile (${junkPile.length} cards)` : "Junk pile is empty"}
          >
            <Box
              sx={{
                width: "100%", height: "100%",
                background: junkPile?.length > 0
                  ? "linear-gradient(135deg, #ffebee, #ffcdd2)"
                  : "linear-gradient(135deg, #e0e0e0, #c0c0c0)",
                display: "flex", alignItems: "center", justifyContent: "center", gap: "4px",
              }}
            >
              <DeleteIcon sx={{ fontSize: compact ? "16px" : "18px", color: junkPile?.length > 0 ? "#d32f2f" : "#666" }} />
              <Box sx={{ fontSize: compact ? "11px" : "13px", fontWeight: "bold", color: junkPile?.length > 0 ? "#d32f2f" : "#666" }}>
                {junkPile?.length || 0}
              </Box>
            </Box>
          </div>
        </Box>
      </Box>
    );
  },
  (prevProps, nextProps) => {
    return (
      prevProps.selectedAge === nextProps.selectedAge &&
      JSON.stringify(prevProps.ageDeckSizes) === JSON.stringify(nextProps.ageDeckSizes) &&
      prevProps.onSelectAge === nextProps.onSelectAge &&
      prevProps.isMyTurn === nextProps.isMyTurn &&
      prevProps.compact === nextProps.compact &&
      JSON.stringify(prevProps.junkPile) === JSON.stringify(nextProps.junkPile)
    );
  },
);

export default AgeSelector;
