import { memo } from "react";
import { Box, Typography, Tooltip, Chip } from "@mui/material";
import ShieldIcon from "@mui/icons-material/Shield";
import styles from "./SafeguardBadge.module.css";

/**
 * SafeguardBadge Component
 *
 * Displays Safeguard indicator on achievements (Unseen expansion).
 *
 * Safeguard keyword reserves achievements for exclusive claiming by the card owner.
 * Multiple players can Safeguard the same achievement (creating a deadlock).
 *
 * Props:
 * - achievementAge: Age of the achievement (for display)
 * - safeguardOwners: Array of player names who have Safeguarded this achievement
 * - currentPlayerId: ID of viewing player
 * - currentPlayerName: Name of viewing player
 * - canClaim: Whether current player can claim (true if they own a Safeguard)
 */
const SafeguardBadge = memo(({
  achievementAge,
  safeguardOwners = [],
  currentPlayerId,
  currentPlayerName,
  canClaim
}) => {
  if (!safeguardOwners || safeguardOwners.length === 0) {
    return null; // No Safeguards active
  }

  // Determine if current player owns a Safeguard
  const playerOwnsSafeguard = safeguardOwners.includes(currentPlayerName);

  // Determine badge color and message
  const isBlocked = !canClaim && !playerOwnsSafeguard;
  const badgeColor = playerOwnsSafeguard ? "#4caf50" : "#ff5252";
  const badgeLabel = playerOwnsSafeguard ? "You" : safeguardOwners.join(", ");

  // Tooltip text
  let tooltipText;
  if (playerOwnsSafeguard && safeguardOwners.length === 1) {
    tooltipText = `You have Safeguarded Age ${achievementAge} - only you can claim it`;
  } else if (playerOwnsSafeguard && safeguardOwners.length > 1) {
    tooltipText = `Multiple Safeguards (You, ${safeguardOwners.filter(n => n !== currentPlayerName).join(", ")}) - only Safeguard owners can claim`;
  } else if (safeguardOwners.length === 1) {
    tooltipText = `Safeguarded by ${safeguardOwners[0]} - you cannot claim this achievement`;
  } else {
    tooltipText = `Safeguarded by ${safeguardOwners.join(", ")} - deadlocked (only they can claim)`;
  }

  return (
    <Tooltip title={tooltipText} arrow placement="top">
      <Box className={styles.safeguardContainer}>
        <Chip
          icon={<ShieldIcon className={styles.shieldIcon} />}
          label={badgeLabel}
          size="small"
          className={`${styles.safeguardBadge} ${isBlocked ? styles.blocked : styles.owned}`}
          style={{
            backgroundColor: badgeColor,
            color: "#fff",
            fontWeight: "bold"
          }}
        />
        {safeguardOwners.length > 1 && (
          <Typography variant="caption" className={styles.deadlockWarning}>
            ⚠️ Deadlock
          </Typography>
        )}
      </Box>
    </Tooltip>
  );
});

SafeguardBadge.displayName = "SafeguardBadge";

export default SafeguardBadge;
