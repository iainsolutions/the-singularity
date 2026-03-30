import { memo } from "react";
import { Box, Typography, Tooltip } from "@mui/material";
import LockIcon from "@mui/icons-material/Lock";
import SecretCardBack from "./SecretCardBack";
import styles from "./SafeDisplay.module.css";

/**
 * SafeDisplay Component
 *
 * Displays a player's Safe (hidden card storage from Unseen expansion).
 *
 * Per official rules: Secrets are face-down. NO ONE can see which specific
 * Unseen cards they are (including the owner). Owner can track order and age.
 *
 * Props:
 * - safe: Safe object { player_id, card_count, secret_ages, cards }
 * - isOwner: Whether viewing player owns this Safe
 * - onSecretClick: Callback when clicking a secret (for achieving)
 * - currentLimit: Current Safe capacity limit (based on splay)
 */
const SafeDisplay = memo(({ safe, isOwner, onSecretClick, currentLimit }) => {
  if (!safe) {
    return null;
  }

  const cardCount = safe.card_count || 0;
  const secretAges = isOwner ? safe.secret_ages : null;
  const limit = currentLimit || 5;

  // Determine if Safe is at/over limit
  const isAtLimit = cardCount >= limit;
  const limitColor = isAtLimit ? "#ff5252" : "#4caf50";

  return (
    <Box className={styles.safeContainer}>
      {/* Header */}
      <Box className={styles.safeHeader}>
        <Box className={styles.safeTitle}>
          <LockIcon className={styles.lockIcon} />
          <Typography variant="h6" className={styles.titleText}>
            The Safe
          </Typography>
        </Box>
        <Tooltip title={`Safe capacity: ${cardCount}/${limit} (based on splay)`}>
          <Typography
            variant="body2"
            className={styles.limitIndicator}
            style={{ color: limitColor }}
          >
            {cardCount}/{limit}
          </Typography>
        </Tooltip>
      </Box>

      {/* Safe Contents */}
      <Box className={styles.safeContents}>
        {cardCount === 0 ? (
          <Typography variant="body2" className={styles.emptyMessage}>
            No secrets in Safe
          </Typography>
        ) : isOwner && secretAges ? (
          // Owner sees card backs with age labels (for achievement tracking)
          secretAges.map((age, index) => (
            <SecretCardBack
              key={index}
              secretIndex={index}
              age={age}
              onClick={onSecretClick ? () => onSecretClick(index, age) : null}
              isClickable={!!onSecretClick}
            />
          ))
        ) : (
          // Opponents see generic card backs (no ages)
          Array(cardCount).fill(0).map((_, index) => (
            <SecretCardBack
              key={index}
              secretIndex={index}
              age={null}
              onClick={null}
              isClickable={false}
            />
          ))
        )}
      </Box>

      {/* Safe Limit Warning */}
      {isOwner && isAtLimit && (
        <Box className={styles.limitWarning}>
          <Typography variant="caption" color="error">
            ⚠️ Safe is at capacity. Improve splays to increase limit.
          </Typography>
        </Box>
      )}
    </Box>
  );
});

SafeDisplay.displayName = "SafeDisplay";

export default SafeDisplay;
