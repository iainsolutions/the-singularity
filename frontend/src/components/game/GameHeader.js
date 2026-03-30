import { memo, useState } from "react";
import {
  Button,
  Typography,
  Box,
  Chip,
  IconButton,
  Tooltip,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import {
  ContentCopy as CopyIcon,
  Check as CheckIcon,
  ExitToApp as LeaveIcon,
} from "@mui/icons-material";
import ExpansionIndicator from "./ExpansionIndicator";

const GameHeader = memo(
  function GameHeader({ gameId, gameState, onLeaveGame }) {
    const [copiedGameId, setCopiedGameId] = useState(false);
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down("md"));

    const handleCopyGameId = async () => {
      try {
        await navigator.clipboard.writeText(gameId);
        setCopiedGameId(true);
        setTimeout(() => setCopiedGameId(false), 2000);
      } catch (err) {
        // Fallback for older browsers
        const textArea = document.createElement("textarea");
        textArea.value = gameId;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        document.body.removeChild(textArea);
        setCopiedGameId(true);
        setTimeout(() => setCopiedGameId(false), 2000);
      }
    };

    const getPhaseColor = (phase) => {
      switch (phase) {
        case "playing":
          return "success";
        case "setup_card_selection":
          return "warning";
        case "finished":
          return "error";
        default:
          return "default";
      }
    };

    const getCurrentPlayerColor = (currentPlayer, actionsRemaining) => {
      if (!currentPlayer) return "default";
      if (actionsRemaining === 0) return "warning";
      return "primary";
    };

    return (
      <Box
        sx={{
          display: "flex",
          flexDirection: isMobile ? "column" : "row",
          justifyContent: "space-between",
          alignItems: isMobile ? "stretch" : "center",
          gap: 2,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap" }}>
          <Typography
            variant={isMobile ? "h5" : "h4"}
            sx={{ fontWeight: 600, color: "primary.main" }}
          >
            Innovation
          </Typography>

          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Game: {gameId?.slice(0, 8)}
            </Typography>

            <Tooltip title={copiedGameId ? "Copied!" : "Copy full Game ID"}>
              <IconButton
                onClick={handleCopyGameId}
                size="small"
                sx={{
                  color: copiedGameId ? "success.main" : "text.secondary",
                  "&:hover": {
                    bgcolor: copiedGameId ? "success.50" : "action.hover",
                  },
                  transition: "all 0.2s ease-in-out",
                }}
              >
                {copiedGameId ? <CheckIcon fontSize="small" /> : <CopyIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        <Box
          sx={{
            display: "flex",
            flexDirection: isMobile ? "column" : "row",
            alignItems: isMobile ? "stretch" : "center",
            gap: isMobile ? 1 : 2,
            flexWrap: "wrap",
          }}
        >
          <Box
            sx={{
              display: "flex",
              gap: 1,
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: isMobile ? "center" : "flex-end",
              minHeight: "32px",
            }}
          >
            <Chip
              label={`Phase: ${gameState.phase}`}
              color={getPhaseColor(gameState.phase)}
              size="small"
              variant="outlined"
            />

            {gameState.current_player && (
              <Chip
                label={`Turn: ${gameState.current_player.name}`}
                color={getCurrentPlayerColor(
                  gameState.current_player,
                  gameState.state?.actions_remaining,
                )}
                size="small"
                variant="filled"
              />
            )}

            <Chip
              label={`Actions: ${gameState.state?.actions_remaining || 0}`}
              color={gameState.state?.actions_remaining > 0 ? "primary" : "default"}
              size="small"
              variant="outlined"
            />
          </Box>

          <ExpansionIndicator gameState={gameState} />

          <Button
            variant={isMobile ? "text" : "outlined"}
            color="error"
            startIcon={<LeaveIcon />}
            onClick={onLeaveGame}
            size={isMobile ? "small" : "medium"}
            sx={{
              minWidth: isMobile ? "auto" : "120px",
              fontSize: isMobile ? "0.75rem" : "0.875rem",
              "&:hover": {
                bgcolor: "error.50",
                transform: isMobile ? "none" : "translateY(-1px)",
                boxShadow: isMobile ? "none" : "0 4px 12px rgba(244, 67, 54, 0.2)",
              },
              transition: "all 0.2s ease-in-out",
            }}
          >
            {isMobile ? "Leave" : "Leave Game"}
          </Button>
        </Box>
      </Box>
    );
  },
  (prevProps, nextProps) => {
    return (
      prevProps.gameId === nextProps.gameId &&
      prevProps.gameState?.phase === nextProps.gameState?.phase &&
      prevProps.gameState?.current_player?.name === nextProps.gameState?.current_player?.name &&
      prevProps.gameState?.state?.actions_remaining ===
        nextProps.gameState?.state?.actions_remaining &&
      prevProps.onLeaveGame === nextProps.onLeaveGame
    );
  },
);

export default GameHeader;
