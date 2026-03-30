import { memo } from "react";
import { Box, Typography, Tooltip } from "@mui/material";
import styles from "./SecretCardBack.module.css";

/**
 * SecretCardBack Component
 *
 * Displays a face-down card back for Unseen secrets in the Safe.
 *
 * Per official rules: Card fronts are HIDDEN from ALL players (including owner).
 * Owner can see age labels for achievement tracking.
 *
 * Props:
 * - secretIndex: Position in Safe (0-based)
 * - age: Age of secret (only visible to owner, null for opponents)
 * - onClick: Click handler (for achieving from Safe)
 * - isClickable: Whether card can be clicked
 */
const SecretCardBack = memo(({ secretIndex, age, onClick, isClickable }) => {
  const cardContent = (
    <Box
      className={`${styles.cardBack} ${isClickable ? styles.clickable : ""}`}
      onClick={isClickable ? onClick : null}
    >
      {/* Card Back Pattern */}
      <Box className={styles.cardPattern}>
        <Box className={styles.diagonalLines} />
      </Box>

      {/* Position Badge */}
      <Box className={styles.positionBadge}>
        <Typography variant="caption">#{secretIndex + 1}</Typography>
      </Box>

      {/* Age Label (only for owner) */}
      {age !== null && age !== undefined && (
        <Box className={styles.ageBadge}>
          <Typography variant="body2" className={styles.ageText}>
            Age {age}
          </Typography>
        </Box>
      )}

      {/* Lock Icon Overlay */}
      <Box className={styles.lockOverlay}>🔒</Box>
    </Box>
  );

  // Add tooltip for owner explaining what they can do
  if (isClickable && age !== null) {
    return (
      <Tooltip
        title={`Secret #${secretIndex + 1} (Age ${age}) - Click to achieve using this secret`}
        arrow
      >
        {cardContent}
      </Tooltip>
    );
  }

  // Simple tooltip for owner (non-clickable)
  if (age !== null) {
    return (
      <Tooltip title={`Secret #${secretIndex + 1} (Age ${age})`} arrow>
        {cardContent}
      </Tooltip>
    );
  }

  // No tooltip for opponents (they only see card backs)
  return cardContent;
});

SecretCardBack.displayName = "SecretCardBack";

export default SecretCardBack;
