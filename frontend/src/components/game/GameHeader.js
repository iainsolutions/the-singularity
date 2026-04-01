import { memo, useState } from "react";
import {
  Button,
  Typography,
  Box,
  Chip,
  IconButton,
  Tooltip,
  Popover,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import {
  ContentCopy as CopyIcon,
  Check as CheckIcon,
  ExitToApp as LeaveIcon,
  Info as InfoIcon,
} from "@mui/icons-material";
import circuitIcon from "../../assets/icons/circuit.svg";
import neuralNetIcon from "../../assets/icons/neural_net.svg";
import dataIcon from "../../assets/icons/data.svg";
import algorithmIcon from "../../assets/icons/algorithm.svg";
import humanMindIcon from "../../assets/icons/human_mind.svg";
import robotIcon from "../../assets/icons/robot.svg";


const GameHeader = memo(
  function GameHeader({ gameId, gameState, onLeaveGame }) {
    const [copiedGameId, setCopiedGameId] = useState(false);
    const [legendAnchor, setLegendAnchor] = useState(null);
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
            The Singularity
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

          {/* Legend popout */}
          <Tooltip title="Game Reference">
            <IconButton
              size="small"
              onClick={(e) => setLegendAnchor(e.currentTarget)}
              sx={{ color: "text.secondary" }}
            >
              <InfoIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Popover
            open={Boolean(legendAnchor)}
            anchorEl={legendAnchor}
            onClose={() => setLegendAnchor(null)}
            anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
            transformOrigin={{ vertical: "top", horizontal: "center" }}
          >
            <Box sx={{ p: 2, minWidth: 280 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>Domains</Typography>
              <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5, mb: 1.5 }}>
                {[
                  { label: "Processing", color: "#0066CC", lore: "The race to harness raw computational power — from mechanical wheels to quantum lattices." },
                  { label: "Labor", color: "#CC3333", lore: "Where machines learned to move, build, and eventually replace the human hand." },
                  { label: "Ethics", color: "#339933", lore: "Humanity's desperate attempt to encode conscience into silicon." },
                  { label: "Creativity", color: "#7733AA", lore: "The domain where machines learned to dream, and their dreams were stranger and more beautiful than ours." },
                  { label: "Connection", color: "#CC9900", lore: "The networks that bound minds together — first human to human, then human to machine, then machine to machine." },
                ].map(({ label, color, lore }) => (
                  <Box key={label} sx={{ display: "flex", alignItems: "flex-start", gap: 1 }}>
                    <Chip label={label} size="small"
                      sx={{ bgcolor: color, color: "white", fontSize: "0.65rem", height: 20, fontWeight: 600, flexShrink: 0 }}
                    />
                    <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.6rem", lineHeight: 1.3 }}>
                      {lore}
                    </Typography>
                  </Box>
                ))}
              </Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>Icons</Typography>
              <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0.5 }}>
                {[
                  { icon: circuitIcon, label: "Circuit", desc: "Hardware" },
                  { icon: neuralNetIcon, label: "Neural Net", desc: "Intelligence" },
                  { icon: dataIcon, label: "Data", desc: "Information" },
                  { icon: algorithmIcon, label: "Algorithm", desc: "Methods" },
                  { icon: humanMindIcon, label: "Human Mind", desc: "Consciousness" },
                  { icon: robotIcon, label: "Robot", desc: "Automation" },
                ].map(({ icon, label, desc }) => (
                  <Box key={label} sx={{ display: "flex", alignItems: "center", gap: 0.5, py: 0.3 }}>
                    <img src={icon} alt={label} style={{ width: 18, height: 18 }} />
                    <Box>
                      <Box sx={{ fontSize: "0.75rem", fontWeight: 600 }}>{label}</Box>
                      <Box sx={{ fontSize: "0.6rem", color: "text.secondary" }}>{desc}</Box>
                    </Box>
                  </Box>
                ))}
              </Box>
            </Box>
          </Popover>

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
