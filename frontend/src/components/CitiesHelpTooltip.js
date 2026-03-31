import { memo } from "react";
import { Tooltip, Box, Typography, Divider } from "@mui/material";
import styles from "./CitiesHelpTooltip.module.css";

/**
 * CitiesHelpTooltip provides detailed explanations for Cities expansion features
 *
 * Features:
 * - Special icon descriptions
 * - Endorse action guide
 * - Flag/Fountain achievement info
 * - Quick reference for players
 */

export const SpecialIconTooltip = memo(function SpecialIconTooltip({ icon, children }) {
  const tooltipContent = getIconTooltipContent(icon);

  return (
    <Tooltip
      title={
        <Box className={styles.tooltipContent}>
          <Typography variant="subtitle2" className={styles.tooltipTitle}>
            {tooltipContent.title}
          </Typography>
          <Divider className={styles.divider} />
          <Typography variant="body2" className={styles.tooltipDescription}>
            {tooltipContent.description}
          </Typography>
          {tooltipContent.example && (
            <>
              <Typography variant="caption" className={styles.exampleLabel}>
                Example:
              </Typography>
              <Typography variant="caption" className={styles.tooltipExample}>
                {tooltipContent.example}
              </Typography>
            </>
          )}
        </Box>
      }
      arrow
      placement="top"
      enterDelay={300}
      leaveDelay={200}
    >
      {children}
    </Tooltip>
  );
});

export const EndorseTooltip = memo(function EndorseTooltip({ children }) {
  return (
    <Tooltip
      title={
        <Box className={styles.tooltipContent}>
          <Typography variant="subtitle2" className={styles.tooltipTitle}>
            🎯 Endorse Action
          </Typography>
          <Divider className={styles.divider} />
          <Typography variant="body2" className={styles.tooltipDescription}>
            Double your dogma effects!
          </Typography>
          <Box className={styles.requirementsList}>
            <Typography variant="caption" className={styles.requirement}>
              ✓ City with dogma's featured icon
            </Typography>
            <Typography variant="caption" className={styles.requirement}>
              ✓ Card to junk (age ≤ city age)
            </Typography>
            <Typography variant="caption" className={styles.requirement}>
              ✓ Once per turn only
            </Typography>
          </Box>
          <Typography variant="caption" className={styles.tooltipExample}>
            <strong>Example:</strong> Endorse Tools → Return 2 cards, draw 6 (instead of
            return 1, draw 3)
          </Typography>
        </Box>
      }
      arrow
      placement="top"
      enterDelay={300}
      leaveDelay={200}
    >
      {children}
    </Tooltip>
  );
});

export const FlagAchievementTooltip = memo(function FlagAchievementTooltip({
  color,
  children,
}) {
  return (
    <Tooltip
      title={
        <Box className={styles.tooltipContent}>
          <Typography variant="subtitle2" className={styles.tooltipTitle}>
            🚩 {color.charAt(0).toUpperCase() + color.slice(1)} Flag Achievement
          </Typography>
          <Divider className={styles.divider} />
          <Typography variant="body2" className={styles.tooltipDescription}>
            Gain this achievement by having ≥ visible {color} cards than all opponents.
          </Typography>
          <Typography variant="caption" className={styles.warning}>
            ⚠️ You can LOSE this flag if an opponent surpasses your visible card count!
          </Typography>
          <Typography variant="caption" className={styles.tooltipExample}>
            <strong>Strategy:</strong> Splay {color} aggressively and keep melding {color}{" "}
            cards to maintain dominance.
          </Typography>
        </Box>
      }
      arrow
      placement="top"
      enterDelay={300}
      leaveDelay={200}
    >
      {children}
    </Tooltip>
  );
});

export const FountainAchievementTooltip = memo(function FountainAchievementTooltip({
  icon,
  children,
}) {
  return (
    <Tooltip
      title={
        <Box className={styles.tooltipContent}>
          <Typography variant="subtitle2" className={styles.tooltipTitle}>
            ⛲ {icon.charAt(0).toUpperCase() + icon.slice(1)} Fountain Achievement
          </Typography>
          <Divider className={styles.divider} />
          <Typography variant="body2" className={styles.tooltipDescription}>
            Gain this achievement by having this fountain city visible on your board.
          </Typography>
          <Typography variant="caption" className={styles.success}>
            ✓ Simple and reliable - no competition with opponents!
          </Typography>
          <Typography variant="caption" className={styles.tooltipExample}>
            <strong>Tip:</strong> Keep fountain cities on top of your stacks to maintain
            the achievement.
          </Typography>
        </Box>
      }
      arrow
      placement="top"
      enterDelay={300}
      leaveDelay={200}
    >
      {children}
    </Tooltip>
  );
});

export const CityDrawTriggerTooltip = memo(function CityDrawTriggerTooltip({ children }) {
  return (
    <Tooltip
      title={
        <Box className={styles.tooltipContent}>
          <Typography variant="subtitle2" className={styles.tooltipTitle}>
            🏙️ City Draw Triggers
          </Typography>
          <Divider className={styles.divider} />
          <Typography variant="body2" className={styles.tooltipDescription}>
            Cities are drawn automatically when:
          </Typography>
          <Box className={styles.triggerList}>
            <Typography variant="caption" className={styles.trigger}>
              1. You meld a card that adds a <strong>new color</strong> to your board
            </Typography>
            <Typography variant="caption" className={styles.trigger}>
              2. You splay a color in a <strong>new direction</strong>
            </Typography>
          </Box>
          <Typography variant="caption" className={styles.info}>
            ℹ️ You can only hold one city in hand at a time.
          </Typography>
        </Box>
      }
      arrow
      placement="top"
      enterDelay={300}
      leaveDelay={200}
    >
      {children}
    </Tooltip>
  );
});

// Helper function to get tooltip content for each icon type
function getIconTooltipContent(icon) {
  const iconType = typeof icon === "string" ? icon : icon?.type;

  const content = {
    search: {
      title: "🔍 Search Icon",
      description:
        "Reveal the top X cards of the base Age-X deck. Take all cards with the target icon into your hand. Return the rest in any order.",
      example: "Search for neural_net cards → Reveal Age 1 deck, take all neural_net cards.",
    },
    plus: {
      title: "➕ Plus Icon",
      description: "Draw a card of age+1 (one age higher than this city).",
      example: "Age 2 city with Plus → Draw an Age 3 card.",
    },
    arrow: {
      title: "➡️ Arrow Icon",
      description:
        "Splay the city's color in the indicated direction (left, right, or up). Can trigger a new city draw if the direction changes!",
      example:
        "Red city with Arrow Right → Splay Red right. If Red wasn't splayed right before, draw another city!",
    },
    junk: {
      title: "🗑️ Junk Icon",
      description:
        "Remove an available achievement of this city's age from the game. No one can claim it anymore.",
      example: "Age 3 city with Junk → Age 3 achievement is junked permanently.",
    },
    uplift: {
      title: "⬆️ Uplift Icon",
      description:
        "Junk the entire deck of age+1, then draw a card from age+2. Major age acceleration!",
      example:
        "Age 1 city with Uplift → Junk all Age 2 cards, draw an Age 3 card. Skip an entire age!",
    },
    unsplay: {
      title: "🔄 Unsplay Icon",
      description:
        "Remove the splay from this city's color on all opponents' boards. Reduces their visible symbols.",
      example: "Red city with Unsplay → All opponents' Red stacks lose their splay.",
    },
    flag: {
      title: "🚩 Flag Icon (Constant)",
      description:
        "While this city is visible, you gain a special achievement if you have ≥ visible cards of this color than all opponents. Can be lost if surpassed!",
      example:
        "Red Flag + 5 visible red cards vs opponent's 4 → Gain Red Flag achievement. Opponent melds more red → Lose flag!",
    },
    fountain: {
      title: "⛲ Fountain Icon (Constant)",
      description:
        "While this city is visible, you have this fountain achievement. Simple and reliable!",
      example:
        "Neural Net Fountain city on top of stack → Gain Neural Net Fountain achievement. Keep it visible to maintain it.",
    },
  };

  return (
    content[iconType] || {
      title: "❓ Unknown Icon",
      description: "Special icon effect",
      example: null,
    }
  );
}

export default {
  SpecialIconTooltip,
  EndorseTooltip,
  FlagAchievementTooltip,
  FountainAchievementTooltip,
  CityDrawTriggerTooltip,
};
