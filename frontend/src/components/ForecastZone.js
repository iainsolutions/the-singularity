import { Box, Typography, Paper } from "@mui/material";
import ForecastCard from "./game/echoes/ForecastCard";
import ForecastLimitIndicator from "./game/echoes/ForecastLimitIndicator";
import { calculateForecastLimit } from "../utils/echoesUtils";

/**
 * ForecastZone component for Echoes expansion
 * Displays forecasted cards with capacity indicator
 */
const ForecastZone = ({
  forecastZone,
  player,
  playerName,
  isCurrentPlayer,
  onCardClick,
}) => {
  if (!forecastZone) return null;

  // Extract cards and calculate limit
  const cards = forecastZone.cards || [];
  const limit = calculateForecastLimit(player);

  return (
    <Paper
      elevation={2}
      sx={{
        p: 2,
        backgroundColor: "background.paper",
        borderRadius: 2,
        border: "2px solid",
        borderColor: isCurrentPlayer ? "primary.main" : "divider",
      }}
    >
      {/* Header with title and limit indicator */}
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 2,
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: "bold" }}>
          Forecast Zone
          {!isCurrentPlayer && (
            <Typography
              component="span"
              variant="body2"
              sx={{ ml: 1, color: "text.secondary" }}
            >
              ({playerName})
            </Typography>
          )}
        </Typography>

        <ForecastLimitIndicator current={cards.length} max={limit} />
      </Box>

      {/* Cards display */}
      {cards.length === 0 ? (
        <Box
          sx={{
            textAlign: "center",
            py: 4,
            color: "text.secondary",
          }}
        >
          <Typography variant="body2">No forecasted cards</Typography>
          {isCurrentPlayer && (
            <Typography variant="caption" sx={{ mt: 0.5, display: "block" }}>
              Use cards with "Foreshadow" effects to add cards here
            </Typography>
          )}
        </Box>
      ) : (
        <Box
          sx={{
            display: "flex",
            flexWrap: "wrap",
            gap: 1.5,
            alignItems: "flex-start",
          }}
        >
          {cards.map((card, idx) => (
            <ForecastCard
              key={`forecast-${idx}`}
              card={card}
              position={idx}
              isOwner={isCurrentPlayer}
              onClick={onCardClick}
            />
          ))}
        </Box>
      )}

      {/* Available slots indicator */}
      {cards.length < limit && cards.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="caption" color="text.secondary">
            {limit - cards.length} slot{limit - cards.length !== 1 ? "s" : ""}{" "}
            available
          </Typography>
        </Box>
      )}
    </Paper>
  );
};

export default ForecastZone;
