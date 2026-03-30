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
  Radio,
  RadioGroup,
  FormControlLabel,
  FormControl,
  CircularProgress,
} from "@mui/material";
import SecretCardBack from "./SecretCardBack";
import styles from "./MeldSourceModal.module.css";

/**
 * MeldSourceModal Component
 *
 * Modal for choosing where to meld a card from (hand or Safe) when Unseen expansion is enabled.
 *
 * Per official rules: When melding, players can choose to meld from their hand OR
 * from their Safe (if they have secrets). Melding from Safe reveals the secret.
 *
 * Props:
 * - open: Whether modal is open
 * - onClose: Close handler
 * - onConfirm: Confirm handler (source: 'hand' | 'safe', safeIndex?: number)
 * - handCards: Array of cards in player's hand
 * - safe: Player's Safe object
 * - targetColor: Color stack where card will be melded (optional)
 * - loading: Whether meld request is in progress
 * - error: Error message if meld failed
 */
const MeldSourceModal = memo(({
  open,
  onClose,
  onConfirm,
  handCards = [],
  safe,
  targetColor = null,
  loading = false,
  error = null,
}) => {
  const [source, setSource] = useState("hand"); // 'hand' or 'safe'
  const [selectedSafeIndex, setSelectedSafeIndex] = useState(null);

  if (!safe) {
    return null;
  }

  const secretAges = safe.secret_ages || [];
  const secretCount = safe.card_count || secretAges.length;
  const hasSecrets = secretCount > 0;

  const handleSourceChange = (event) => {
    setSource(event.target.value);
    if (event.target.value === "hand") {
      setSelectedSafeIndex(null);
    }
  };

  const handleSecretClick = (index) => {
    setSource("safe");
    setSelectedSafeIndex(index);
  };

  const handleConfirm = () => {
    if (source === "hand") {
      onConfirm("hand");
      handleClose();
    } else if (source === "safe" && selectedSafeIndex !== null) {
      onConfirm("safe", selectedSafeIndex);
      handleClose();
    }
  };

  const handleClose = () => {
    setSource("hand");
    setSelectedSafeIndex(null);
    onClose();
  };

  const isConfirmDisabled =
    loading || (source === "safe" && selectedSafeIndex === null);

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
          <span>📥</span>
          <Typography variant="h6">Choose Meld Source</Typography>
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
          Choose whether to meld a card from your hand or reveal a secret from your Safe.
          {targetColor && ` Melding to ${targetColor} stack.`}
        </Alert>

        {/* Source Selection */}
        <FormControl component="fieldset" className={styles.sourceSelector}>
          <RadioGroup value={source} onChange={handleSourceChange}>
            {/* Hand Option */}
            <FormControlLabel
              value="hand"
              control={<Radio />}
              label={
                <Box>
                  <Typography variant="body1" fontWeight="bold">
                    Meld from Hand
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {handCards.length > 0
                      ? `${handCards.length} card${handCards.length !== 1 ? "s" : ""} in hand`
                      : "No cards in hand"}
                  </Typography>
                </Box>
              }
              disabled={handCards.length === 0}
            />

            {/* Safe Option */}
            <FormControlLabel
              value="safe"
              control={<Radio />}
              label={
                <Box>
                  <Typography variant="body1" fontWeight="bold">
                    Meld from Safe (Reveal Secret)
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {hasSecrets
                      ? `${secretCount} secret${secretCount !== 1 ? "s" : ""} in Safe`
                      : "No secrets in Safe"}
                  </Typography>
                </Box>
              }
              disabled={!hasSecrets}
            />
          </RadioGroup>
        </FormControl>

        {/* Safe Secrets Grid (shown when Safe is selected) */}
        {source === "safe" && hasSecrets && (
          <Box className={styles.secretsSection}>
            <Typography variant="subtitle2" className={styles.sectionTitle}>
              Select Secret to Reveal:
            </Typography>
            <Box className={styles.secretsGrid}>
              {secretAges.map((age, index) => {
                const isSelected = selectedSafeIndex === index;

                return (
                  <Box
                    key={index}
                    className={`${styles.secretWrapper} ${
                      isSelected ? styles.selected : ""
                    }`}
                    onClick={() => handleSecretClick(index)}
                  >
                    <SecretCardBack
                      secretIndex={index}
                      age={age}
                      onClick={() => handleSecretClick(index)}
                      isClickable={true}
                    />
                    {isSelected && (
                      <Box className={styles.selectedBadge}>
                        ✓ Selected
                      </Box>
                    )}
                  </Box>
                );
              })}
            </Box>
            {selectedSafeIndex === null && (
              <Typography variant="caption" color="text.secondary">
                Click a secret to select it for melding
              </Typography>
            )}
          </Box>
        )}

        {/* Warning when melding from Safe */}
        {source === "safe" && (
          <Alert severity="warning" className={styles.warningAlert}>
            ⚠️ Revealing a secret from your Safe will show the card to all players.
          </Alert>
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
          disabled={isConfirmDisabled}
          startIcon={loading ? <CircularProgress size={20} /> : null}
        >
          {loading
            ? "Melding..."
            : source === "hand"
            ? "Meld from Hand"
            : "Reveal & Meld from Safe"}
        </Button>
      </DialogActions>
    </Dialog>
  );
});

MeldSourceModal.displayName = "MeldSourceModal";

export default MeldSourceModal;
