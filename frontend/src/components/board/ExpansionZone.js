import { Box, Chip } from "@mui/material";

const ExpansionZone = ({
  player,
  isCurrentPlayer,
  onSafeClick,
  hideBoard = false,
  compact = false,
}) => {
  if ((!player?.safe && !player?.forecast_zone) || hideBoard) {
    return null;
  }

  return (
    <Box
      sx={{
        display: "flex",
        gap: 1,
        mt: compact ? 1 : 1.5,
        flexWrap: "wrap",
      }}
    >
      {/* Safe Indicator - Unseen Expansion */}
      {player?.safe && player.safe.card_count > 0 && (
        <Chip
          icon={<span style={{ fontSize: "14px" }}>🔒</span>}
          label={`Safe: ${player.safe.card_count || 0}/${player.safe_limit || 5}`}
          size="small"
          onClick={isCurrentPlayer && player.safe.card_count > 0 ? onSafeClick : undefined}
          sx={{
            bgcolor: player.safe.card_count > 0 ? "#424242" : "#e0e0e0",
            color: player.safe.card_count > 0 ? "#ffd700" : "#666",
            fontWeight: "bold",
            cursor: isCurrentPlayer && player.safe.card_count > 0 ? "pointer" : "default",
            "&:hover":
              isCurrentPlayer && player.safe.card_count > 0
                ? {
                    bgcolor: "#616161",
                  }
                : {},
          }}
        />
      )}

      {/* Forecast Zone Indicator - Echoes Expansion */}
      {player?.forecast_zone && player.forecast_zone.cards?.length > 0 && (
        <Chip
          icon={<span style={{ fontSize: "14px" }}>🔮</span>}
          label={`Forecast: ${player.forecast_zone.cards?.length || 0}`}
          size="small"
          sx={{
            bgcolor: player.forecast_zone.cards?.length > 0 ? "#9c27b0" : "#e0e0e0",
            color: player.forecast_zone.cards?.length > 0 ? "#fff" : "#666",
            fontWeight: "bold",
          }}
        />
      )}
    </Box>
  );
};

export default ExpansionZone;
