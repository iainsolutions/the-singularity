import { memo, useMemo } from "react";
import styles from "./SpecialIcon.module.css";
import { SpecialIconTooltip } from "./CitiesHelpTooltip";

/**
 * SpecialIcon component renders a special icon for Cities expansion cards
 *
 * Special icon types:
 * - search: Search base deck for cards with target icon
 * - plus: Draw card of age+1
 * - arrow: Splay color in direction
 * - junk: Junk available achievement
 * - uplift: Junk age+1 deck, draw age+2
 * - unsplay: Unsplay color on opponents
 * - flag: Constant achievement (color-based)
 * - fountain: Constant achievement (visibility-based)
 */
const SpecialIcon = memo(
  function SpecialIcon({ icon, position = 0, size = "normal" }) {
    if (!icon) return null;

    // Generate icon visual based on type and parameters
    const iconContent = useMemo(() => {
      switch (icon.type) {
        case "search":
          return {
            symbol: "🔍",
            label: `Search for ${icon.parameters?.target_icon || "icon"}`,
            color: "#ff9800"
          };
        case "plus":
          return {
            symbol: "➕",
            label: "Draw +1 age",
            color: "#4caf50"
          };
        case "arrow":
          const direction = icon.parameters?.direction || "right";
          const arrowSymbol = {
            left: "⬅️",
            right: "➡️",
            up: "⬆️"
          }[direction] || "➡️";
          return {
            symbol: arrowSymbol,
            label: `Splay ${direction}`,
            color: "#2196f3"
          };
        case "junk":
          return {
            symbol: "🗑️",
            label: "Junk achievement",
            color: "#f44336"
          };
        case "uplift":
          return {
            symbol: "⬆️📚",
            label: "Uplift deck",
            color: "#9c27b0"
          };
        case "unsplay":
          return {
            symbol: "🔄",
            label: "Unsplay opponents",
            color: "#ff5722"
          };
        case "flag":
          const flagColor = icon.parameters?.target_color || "any";
          return {
            symbol: "🚩",
            label: `${flagColor.charAt(0).toUpperCase() + flagColor.slice(1)} Flag`,
            color: "#795548"
          };
        case "fountain":
          const fountainIcon = icon.parameters?.target_icon || "icon";
          return {
            symbol: "⛲",
            label: `${fountainIcon.charAt(0).toUpperCase() + fountainIcon.slice(1)} Fountain`,
            color: "#00bcd4"
          };
        default:
          return {
            symbol: "❓",
            label: "Unknown icon",
            color: "#9e9e9e"
          };
      }
    }, [icon]);

    // Determine if icon is immediate or constant effect
    const isConstant = icon.type === "flag" || icon.type === "fountain";
    const iconClasses = [
      styles.specialIcon,
      styles[size] || "",
      isConstant ? styles.constant : styles.immediate,
      styles[`position${position}`] || ""
    ].filter(Boolean).join(" ");

    return (
      <SpecialIconTooltip icon={icon}>
        <div
          className={iconClasses}
          aria-label={iconContent.label}
          style={{ backgroundColor: iconContent.color }}
          data-icon-type={icon.type}
        >
          <span className={styles.iconSymbol}>{iconContent.symbol}</span>
        </div>
      </SpecialIconTooltip>
    );
  },
  (prevProps, nextProps) => {
    return (
      prevProps.icon?.type === nextProps.icon?.type &&
      prevProps.position === nextProps.position &&
      prevProps.size === nextProps.size
    );
  }
);

export default SpecialIcon;
