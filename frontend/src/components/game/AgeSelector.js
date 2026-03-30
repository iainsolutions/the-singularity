import { memo, useState } from "react";
import { Box, Typography, useTheme, useMediaQuery } from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import styles from "./AgeSelector.module.css";

// Move constant outside component to prevent recreation
const AGES = Array.from({ length: 11 }, (_, i) => i + 1);

const AgeSelector = memo(
  function AgeSelector({
    selectedAge,
    ageDeckSizes,
    citiesDeckSizes,
    echoesDeckSizes,
    figuresDeckSizes,
    artifactsDeckSizes,
    unseenDeckSizes,
    onSelectAge,
    isMyTurn,
    compact = false,
    junkPile = [],
  }) {
    const [imageErrors, setImageErrors] = useState(new Set());
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down("sm"));

    // Get card back image path for the age
    const getCardBackPath = (age) => {
      return `/cards/CardBacks/InnoUlt_CardBacks_PRODUCTION${age}.png`;
    };

    // Fallback image path for generic age background
    const getFallbackImage = (age) => {
      return `/cards/card_backgrounds/action_1.png`;
    };

    // Handle image load error
    const handleImageError = (age) => {
      setImageErrors((prev) => new Set([...prev, age]));
    };

    return (
      <Box sx={{ display: "flex", gap: 3, alignItems: "flex-start" }}>
        {/* Age Decks Section */}
        <Box>
          <Typography
            variant="body2"
            sx={{
              mb: 0.5,
              fontWeight: 600,
              color: "primary.main",
              fontSize: compact ? "0.6rem" : "0.7rem",
              lineHeight: 1,
            }}
          >
            Age Decks
          </Typography>
          <div className={`${styles.ageRow} ${compact ? styles.ageRowCompact : ""}`}>
            {AGES.map((age) => {
              const cardsRemaining = ageDeckSizes?.[age] || 0;
              const hasCards = cardsRemaining > 0;
              const isSelected = selectedAge === age;

              return (
                <div
                  key={age}
                  className={`${styles.ageOption} ${isSelected ? styles.ageOptionSelected : ""} ${
                    !hasCards ? styles.ageOptionEmpty : ""
                  } ${!isMyTurn ? styles.ageOptionDisabled : ""}`}
                  onClick={() => isMyTurn && hasCards && onSelectAge(age)}
                  title={
                    !hasCards
                      ? `Age ${age} deck is empty`
                      : `Age ${age} deck (${cardsRemaining} cards remaining)`
                  }
                >
                  {hasCards ? (
                    <img
                      src={imageErrors.has(age) ? getFallbackImage(age) : getCardBackPath(age)}
                      alt={`Age ${age} deck`}
                      className={styles.ageCardBack}
                      onError={() => handleImageError(age)}
                      loading="lazy"
                    />
                  ) : (
                    <div className={styles.ageEmpty}>
                      <span className={styles.ageEmptyText}>Empty</span>
                    </div>
                  )}
                  <span className={styles.ageNumber}>{age}</span>
                  <span className={styles.ageCount}>{cardsRemaining}</span>
                </div>
              );
            })}
          </div>
        </Box>

        {/* Expansion Decks Section - Diagonal cascade display */}
        {((citiesDeckSizes && Object.keys(citiesDeckSizes).length > 0) ||
          (echoesDeckSizes && Object.keys(echoesDeckSizes).length > 0) ||
          (figuresDeckSizes && Object.keys(figuresDeckSizes).length > 0) ||
          (artifactsDeckSizes && Object.keys(artifactsDeckSizes).length > 0) ||
          (unseenDeckSizes && Object.keys(unseenDeckSizes).length > 0)) && (
          <Box>
            <Typography
              variant="body2"
              sx={{
                mb: 0.5,
                fontWeight: 600,
                color: "primary.main",
                fontSize: compact ? "0.6rem" : "0.7rem",
                lineHeight: 1,
              }}
            >
              Expansions
            </Typography>
            <div className={`${styles.ageRow} ${compact ? styles.ageRowCompact : ""}`}>
              {AGES.map((age) => {
                const echoesCount = echoesDeckSizes?.[age] || 0;
                const figuresCount = figuresDeckSizes?.[age] || 0;
                const citiesCount = citiesDeckSizes?.[age] || 0;
                const artifactsCount = artifactsDeckSizes?.[age] || 0;
                const unseenCount = unseenDeckSizes?.[age] || 0;

                const totalCount = echoesCount + figuresCount + citiesCount + artifactsCount + unseenCount;

                // Card back numbers: Echoes 13-23, Figures 24-34, Cities 35-45, Artifacts 46-56, Unseen 57-67
                const expansions = [
                  { count: echoesCount, cardBack: 12 + age, name: "Echoes" },
                  { count: figuresCount, cardBack: 23 + age, name: "Figures" },
                  { count: citiesCount, cardBack: 34 + age, name: "Cities" },
                  { count: artifactsCount, cardBack: 45 + age, name: "Artifacts" },
                  { count: unseenCount, cardBack: 56 + age, name: "Unseen" },
                ].filter(exp => exp.count > 0);

                // If no expansions have cards for this age, don't show it
                if (expansions.length === 0) return null;

                return (
                  <div
                    key={`expansion-${age}`}
                    className={styles.ageOption}
                    style={{
                      cursor: "default",
                      position: "relative",
                    }}
                    title={expansions.map(exp => `${exp.name}: ${exp.count}`).join(", ")}
                  >
                    {/* Diagonal cascade display */}
                    <div style={{ position: "relative", width: "100%", height: "100%" }}>
                      {expansions.map((exp, idx) => (
                        <img
                          key={exp.name}
                          src={`/cards/CardBacks/InnoUlt_CardBacks_PRODUCTION${exp.cardBack}.png`}
                          alt={`Age ${age} ${exp.name.toLowerCase()} deck`}
                          className={styles.ageCardBack}
                          style={{
                            position: idx === 0 ? "relative" : "absolute",
                            top: idx === 0 ? 0 : `${idx * 12}%`,
                            left: idx === 0 ? 0 : `${idx * 15}%`,
                            zIndex: idx + 1,
                          }}
                          loading="lazy"
                        />
                      ))}
                    </div>
                    <span className={styles.ageNumber}>{age}</span>
                    <span className={styles.ageCount}>{totalCount}</span>
                  </div>
                );
              })}
            </div>
          </Box>
        )}

        {/* Junk Pile Section */}
        <Box>
          <Typography
            variant="body2"
            sx={{
              mb: 0.5,
              fontWeight: 600,
              color: "primary.main",
              fontSize: compact ? "0.6rem" : "0.7rem",
              lineHeight: 1,
            }}
          >
            Junk
          </Typography>
          <div
            style={{
              position: "relative",
              width: compact ? "60px" : "80px",
              height: compact ? "45px" : "60px",
              cursor: junkPile?.length > 0 ? "pointer" : "default",
              border: junkPile?.length > 0 ? "2px solid #d32f2f" : "2px solid #999",
              borderRadius: "4px",
              opacity: junkPile?.length > 0 ? 1 : 0.5,
              overflow: "hidden",
              transition: "all 0.2s ease",
            }}
            title={
              junkPile?.length > 0
                ? `Junk pile (${junkPile.length} card${junkPile.length !== 1 ? "s" : ""})`
                : "Junk pile is empty"
            }
          >
            <Box
              sx={{
                width: "100%",
                height: "100%",
                background:
                  junkPile?.length > 0
                    ? "linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%)"
                    : "linear-gradient(135deg, #e0e0e0 0%, #c0c0c0 100%)",
                display: "flex",
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "center",
                gap: "4px",
              }}
            >
              <DeleteIcon
                sx={{
                  fontSize: compact ? "16px" : "18px",
                  color: junkPile?.length > 0 ? "#d32f2f" : "#666",
                }}
              />
              <Box
                sx={{
                  fontSize: compact ? "11px" : "13px",
                  fontWeight: "bold",
                  color: junkPile?.length > 0 ? "#d32f2f" : "#666",
                }}
              >
                {junkPile?.length || 0}
              </Box>
            </Box>
          </div>
        </Box>

      </Box>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison function for React.memo
    return (
      prevProps.selectedAge === nextProps.selectedAge &&
      JSON.stringify(prevProps.ageDeckSizes) === JSON.stringify(nextProps.ageDeckSizes) &&
      JSON.stringify(prevProps.citiesDeckSizes) === JSON.stringify(nextProps.citiesDeckSizes) &&
      JSON.stringify(prevProps.echoesDeckSizes) === JSON.stringify(nextProps.echoesDeckSizes) &&
      JSON.stringify(prevProps.figuresDeckSizes) === JSON.stringify(nextProps.figuresDeckSizes) &&
      JSON.stringify(prevProps.artifactsDeckSizes) === JSON.stringify(nextProps.artifactsDeckSizes) &&
      JSON.stringify(prevProps.unseenDeckSizes) === JSON.stringify(nextProps.unseenDeckSizes) &&
      prevProps.onSelectAge === nextProps.onSelectAge &&
      prevProps.isMyTurn === nextProps.isMyTurn &&
      prevProps.compact === nextProps.compact &&
      JSON.stringify(prevProps.junkPile) === JSON.stringify(nextProps.junkPile)
    );
  },
);

export default AgeSelector;
