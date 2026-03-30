import React, { useState, useEffect, memo, useCallback } from "react";
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Button,
  Chip,
  LinearProgress,
} from "@mui/material";
import {
  Psychology as AIIcon,
  Refresh as RetryIcon,
  Warning as WarningIcon,
  CheckCircle as SuccessIcon,
} from "@mui/icons-material";

/**
 * AITurnIndicator - Shows AI player status during their turn
 *
 * States:
 * - thinking: AI is making a decision (shows spinner)
 * - slow: AI is taking longer than expected (shows warning)
 * - error: AI encountered an error (shows error with retry button)
 * - success: AI completed action (brief flash)
 */
const AITurnIndicator = memo(function AITurnIndicator({
  isAITurn,
  aiPlayerName = "AI",
  onRetryAITurn,
  turnStartTime,
  lastActionTime,
}) {
  const [status, setStatus] = useState("idle"); // idle, thinking, slow, error
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [showSuccess, setShowSuccess] = useState(false);

  // Thresholds in seconds
  const SLOW_THRESHOLD = 30; // Show warning after 30s
  const ERROR_THRESHOLD = 90; // Show error after 90s

  // Track elapsed time during AI turn
  useEffect(() => {
    if (!isAITurn) {
      setStatus("idle");
      setElapsedSeconds(0);
      return;
    }

    setStatus("thinking");
    const startTime = turnStartTime || Date.now();

    const interval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      setElapsedSeconds(elapsed);

      if (elapsed >= ERROR_THRESHOLD) {
        setStatus("error");
      } else if (elapsed >= SLOW_THRESHOLD) {
        setStatus("slow");
        // Auto-retry once at slow threshold
        if (elapsed === SLOW_THRESHOLD && onRetryAITurn) {
          console.log("🔄 Auto-retrying AI turn after slow threshold");
          onRetryAITurn();
        }
      } else {
        setStatus("thinking");
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isAITurn, turnStartTime, onRetryAITurn]);

  // Show brief success indicator when action completes
  useEffect(() => {
    if (lastActionTime && isAITurn) {
      setShowSuccess(true);
      const timeout = setTimeout(() => setShowSuccess(false), 1500);
      return () => clearTimeout(timeout);
    }
  }, [lastActionTime, isAITurn]);

  const handleRetry = useCallback(() => {
    if (onRetryAITurn) {
      setStatus("thinking");
      setElapsedSeconds(0);
      onRetryAITurn();
    }
  }, [onRetryAITurn]);

  // Don't render if not AI's turn
  if (!isAITurn) {
    return null;
  }

  const getStatusContent = () => {
    if (showSuccess) {
      return (
        <Alert
          severity="success"
          icon={<SuccessIcon />}
          sx={{ py: 0.5 }}
        >
          <Typography variant="body2">
            {aiPlayerName} completed action
          </Typography>
        </Alert>
      );
    }

    switch (status) {
      case "thinking":
        return (
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 2,
              p: 1.5,
              bgcolor: "info.50",
              borderRadius: 1,
              border: "1px solid",
              borderColor: "info.200",
            }}
          >
            <CircularProgress size={24} color="info" />
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 600, color: "info.dark" }}>
                {aiPlayerName} is thinking...
              </Typography>
              {elapsedSeconds > 3 && (
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  {elapsedSeconds}s elapsed
                </Typography>
              )}
            </Box>
            <Chip
              icon={<AIIcon />}
              label="AI Turn"
              size="small"
              color="info"
              variant="outlined"
            />
          </Box>
        );

      case "slow":
        return (
          <Alert
            severity="warning"
            icon={<WarningIcon />}
            sx={{ py: 0.5 }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
              <Box sx={{ flex: 1 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {aiPlayerName} is taking longer than usual...
                </Typography>
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  {elapsedSeconds}s elapsed - Please wait
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={Math.min((elapsedSeconds / ERROR_THRESHOLD) * 100, 100)}
                  sx={{ mt: 1, height: 4, borderRadius: 2 }}
                  color="warning"
                />
              </Box>
              <CircularProgress size={20} color="warning" />
            </Box>
          </Alert>
        );

      case "error":
        return (
          <Alert
            severity="error"
            icon={<WarningIcon />}
            sx={{ py: 0.5 }}
            action={
              onRetryAITurn && (
                <Button
                  color="error"
                  size="small"
                  startIcon={<RetryIcon />}
                  onClick={handleRetry}
                  sx={{
                    textTransform: "none",
                    "&:hover": {
                      bgcolor: "error.dark",
                      color: "white",
                    },
                  }}
                >
                  Retry
                </Button>
              )
            }
          >
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {aiPlayerName} appears to be stuck
              </Typography>
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                {elapsedSeconds}s without response - Click Retry to continue
              </Typography>
            </Box>
          </Alert>
        );

      default:
        return null;
    }
  };

  return (
    <Box
      sx={{
        mb: 2,
        animation: status === "error" ? "pulse 1.5s infinite" : "none",
        "@keyframes pulse": {
          "0%": { opacity: 1 },
          "50%": { opacity: 0.7 },
          "100%": { opacity: 1 },
        },
      }}
    >
      {getStatusContent()}
    </Box>
  );
});

export default AITurnIndicator;
