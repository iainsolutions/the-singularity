import { memo } from "react";
import { Snackbar, Alert, Box, Typography } from "@mui/material";
import LockIcon from "@mui/icons-material/Lock";
import styles from "./UnseenDrawNotification.module.css";

/**
 * UnseenDrawNotification Component
 *
 * Toast notification that appears when first draw of turn is replaced with Unseen card.
 *
 * Per official rules: When you draw your first card during a turn (your own turn or
 * another player's turn), you draw an Unseen card of the same age instead, and tuck
 * it unseen into your Safe.
 *
 * Props:
 * - open: Whether notification is visible
 * - onClose: Close handler
 * - age: Age of the Unseen card drawn
 * - isFirstDraw: Whether this was the first draw (should always be true)
 */
const UnseenDrawNotification = memo(({ open, onClose, age, isFirstDraw = true }) => {
  if (!isFirstDraw) {
    return null; // Only show for first draws
  }

  return (
    <Snackbar
      open={open}
      autoHideDuration={4000}
      onClose={onClose}
      anchorOrigin={{ vertical: "top", horizontal: "center" }}
      className={styles.snackbar}
    >
      <Alert
        onClose={onClose}
        severity="info"
        icon={<LockIcon />}
        className={styles.alert}
        sx={{
          background: "linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%)",
          color: "#ffd700",
          border: "2px solid #ffd700",
          boxShadow: "0 4px 12px rgba(255, 215, 0, 0.3)",
        }}
      >
        <Box className={styles.content}>
          <Typography variant="h6" className={styles.title}>
            🔒 Unseen Card Drawn
          </Typography>
          <Typography variant="body2" className={styles.message}>
            First draw of turn: <strong>Age {age} Unseen card</strong> tucked into your Safe
            (hidden from all players, including you).
          </Typography>
          <Typography variant="caption" className={styles.hint}>
            Subsequent draws this turn will use the normal deck.
          </Typography>
        </Box>
      </Alert>
    </Snackbar>
  );
});

UnseenDrawNotification.displayName = "UnseenDrawNotification";

export default UnseenDrawNotification;
