import { memo, useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Alert,
  CircularProgress,
} from "@mui/material";
import SecretCardBack from "./SecretCardBack";
import styles from "./AchieveFromSafeModal.module.css";

/**
 * AchieveFromSafeModal Component
 *
 * Modal for selecting which secret from Safe to use for achieving.
 *
 * Per official rules: Player must choose a secret by index (position in Safe).
 * The secret's age must match an available achievement age, and player must
 * meet all achievement requirements (score and board age).
 *
 * Props:
 * - open: Whether modal is open
 * - onClose: Close handler
 * - onConfirm: Confirm handler (secretIndex, age)
 * - safe: Player's Safe object
 * - availableAchievements: Array of achievement ages player can claim
 * - currentPlayerScore: Player's current score
 * - currentPlayerHighestAge: Highest age card on player's board
 * - loading: Whether achievement request is in progress
 * - error: Error message if achievement failed
 */
const AchieveFromSafeModal = memo(({
  open,
  onClose,
  onConfirm,
  safe,
  availableAchievements = [],
  currentPlayerScore = 0,
  currentPlayerHighestAge = 0,
  loading = false,
  error = null,
}) => {
  const [selectedIndex, setSelectedIndex] = useState(null);

  if (!safe) {
    return null;
  }

  const secretAges = safe.secret_ages || [];
  const secretCount = safe.card_count || secretAges.length;

  // Determine which secrets are eligible (age matches available achievement)
  const eligibleSecrets = secretAges.map((age, index) => {
    const hasMatchingAchievement = availableAchievements.includes(age);
    return hasMatchingAchievement;
  });

  const handleSecretClick = (index) => {
    if (eligibleSecrets[index]) {
      setSelectedIndex(index);
    }
  };

  const handleConfirm = () => {
    if (selectedIndex !== null) {
      const age = secretAges[selectedIndex];
      onConfirm(selectedIndex, age);
      setSelectedIndex(null);
      onClose();
    }
  };

  const handleClose = () => {
    setSelectedIndex(null);
    onClose();
  };

  const hasEligibleSecrets = eligibleSecrets.some(e => e);

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      className={styles.modal}
    >
      <DialogTitle className={styles.title}>
        <Box display="flex" alignItems="center" gap={1}>
          <span>🔒</span>
          <Typography variant="h6">Achieve Using Secret from Safe</Typography>
        </Box>
      </DialogTitle>

      <DialogContent className={styles.content}>
        {/* Error Alert */}
        {error && (
          <Alert severity="error" className={styles.errorAlert} sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* Instructions */}
        <Alert severity="info" className={styles.instructions}>
          Select a secret from your Safe to use for achieving. The secret's age must
          match an available achievement.
        </Alert>

        {/* Player Status */}
        <Box className={styles.statusBox}>
          <Typography variant="body2">
            <strong>Your Score:</strong> {currentPlayerScore}
          </Typography>
          <Typography variant="body2">
            <strong>Highest Board Age:</strong> {currentPlayerHighestAge}
          </Typography>
          <Typography variant="body2">
            <strong>Available Achievements:</strong>{" "}
            {availableAchievements.length > 0
              ? availableAchievements.map(a => `Age ${a}`).join(", ")
              : "None"}
          </Typography>
        </Box>

        {/* Secrets Grid */}
        {secretCount === 0 ? (
          <Alert severity="warning">Your Safe is empty. No secrets to use for achieving.</Alert>
        ) : !hasEligibleSecrets ? (
          <Alert severity="warning">
            No eligible secrets in Safe. None of your secrets match available achievements.
          </Alert>
        ) : (
          <Box className={styles.secretsGrid}>
            {secretAges.map((age, index) => {
              const isEligible = eligibleSecrets[index];
              const isSelected = selectedIndex === index;

              return (
                <Box
                  key={index}
                  className={`${styles.secretWrapper} ${
                    isEligible ? styles.eligible : styles.ineligible
                  } ${isSelected ? styles.selected : ""}`}
                  onClick={() => handleSecretClick(index)}
                >
                  <SecretCardBack
                    secretIndex={index}
                    age={age}
                    onClick={isEligible ? () => handleSecretClick(index) : null}
                    isClickable={isEligible}
                  />
                  {!isEligible && (
                    <Box className={styles.ineligibleOverlay}>
                      <Typography variant="caption" className={styles.ineligibleText}>
                        No Age {age} achievement available
                      </Typography>
                    </Box>
                  )}
                  {isEligible && !isSelected && (
                    <Box className={styles.eligibleBadge}>
                      ✓ Eligible
                    </Box>
                  )}
                  {isSelected && (
                    <Box className={styles.selectedBadge}>
                      ✓ Selected
                    </Box>
                  )}
                </Box>
              );
            })}
          </Box>
        )}
      </DialogContent>

      <DialogActions className={styles.actions}>
        <Button onClick={handleClose} color="secondary" disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleConfirm}
          color="primary"
          variant="contained"
          disabled={selectedIndex === null || loading}
          startIcon={loading ? <CircularProgress size={20} /> : null}
        >
          {loading ? "Achieving..." : "Achieve with Selected Secret"}
        </Button>
      </DialogActions>
    </Dialog>
  );
});

AchieveFromSafeModal.displayName = "AchieveFromSafeModal";

export default AchieveFromSafeModal;
