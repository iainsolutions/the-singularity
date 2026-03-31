import { memo, useEffect, useState } from "react";
import styles from "./SpecialIconAnimation.module.css";

/**
 * SpecialIconAnimation component renders visual feedback for special icon effects
 *
 * Animations:
 * - Search: Card reveal animation
 * - Plus: Card draw from deck
 * - Arrow: Splay direction indicator
 * - Junk: Achievement destruction
 * - Uplift: Card ascending to higher age
 * - Unsplay: Cards collapsing
 * - Flag: Achievement gain indicator
 * - Fountain: Achievement gain indicator
 */
const SpecialIconAnimation = memo(function SpecialIconAnimation({
  iconType,
  parameters = {},
  onComplete
}) {
  const [isPlaying, setIsPlaying] = useState(true);

  useEffect(() => {
    // Auto-complete animation after duration
    const duration = getAnimationDuration(iconType);
    const timer = setTimeout(() => {
      setIsPlaying(false);
      if (onComplete) onComplete();
    }, duration);

    return () => clearTimeout(timer);
  }, [iconType, onComplete]);

  if (!isPlaying) return null;

  return (
    <div className={styles.animationOverlay}>
      {renderAnimation(iconType, parameters)}
    </div>
  );
});

function getAnimationDuration(iconType) {
  const durations = {
    search: 2000,
    plus: 1500,
    arrow: 1800,
    junk: 1500,
    uplift: 2200,
    unsplay: 1800,
    flag: 1500,
    fountain: 1500
  };
  return durations[iconType] || 1500;
}

function renderAnimation(iconType, parameters) {
  switch (iconType) {
    case "search":
      return <SearchAnimation targetIcon={parameters.target_icon} />;
    case "plus":
      return <PlusAnimation />;
    case "arrow":
      return <ArrowAnimation direction={parameters.direction} />;
    case "junk":
      return <JunkAnimation />;
    case "uplift":
      return <UpliftAnimation />;
    case "unsplay":
      return <UnsplayAnimation />;
    case "flag":
      return <FlagAnimation color={parameters.target_color} />;
    case "fountain":
      return <FountainAnimation icon={parameters.target_icon} />;
    default:
      return null;
  }
}

// Individual animation components
const SearchAnimation = memo(({ targetIcon }) => (
  <div className={styles.searchAnimation}>
    <div className={styles.magnifyingGlass}>🔍</div>
    <div className={styles.revealCards}>
      <div className={styles.card}>📇</div>
      <div className={styles.card}>📇</div>
      <div className={styles.card}>📇</div>
    </div>
    <div className={styles.searchText}>
      Searching for {targetIcon} cards...
    </div>
  </div>
));

const PlusAnimation = memo(() => (
  <div className={styles.plusAnimation}>
    <div className={styles.plusSymbol}>➕</div>
    <div className={styles.drawingCard}>📇</div>
    <div className={styles.plusText}>Drawing +1 age...</div>
  </div>
));

const ArrowAnimation = memo(({ direction = "right" }) => {
  const arrowSymbol = {
    left: "⬅️",
    right: "➡️",
    up: "⬆️"
  }[direction] || "➡️";

  return (
    <div className={styles.arrowAnimation}>
      <div className={styles.arrowSymbol}>{arrowSymbol}</div>
      <div className={styles.splayingCards}>
        <div className={styles.card}>📇</div>
        <div className={styles.card}>📇</div>
        <div className={styles.card}>📇</div>
      </div>
      <div className={styles.arrowText}>Splaying {direction}...</div>
    </div>
  );
});

const JunkAnimation = memo(() => (
  <div className={styles.junkAnimation}>
    <div className={styles.achievement}>🏆</div>
    <div className={styles.trashCan}>🗑️</div>
    <div className={styles.junkText}>Junking achievement...</div>
  </div>
));

const UpliftAnimation = memo(() => (
  <div className={styles.upliftAnimation}>
    <div className={styles.lowerDeck}>
      <div className={styles.deckLabel}>Age +1</div>
      <div className={styles.junkingDeck}>🗑️</div>
    </div>
    <div className={styles.upwardArrow}>⬆️</div>
    <div className={styles.upperDeck}>
      <div className={styles.deckLabel}>Age +2</div>
      <div className={styles.drawingCard}>📇</div>
    </div>
    <div className={styles.upliftText}>Uplifting deck...</div>
  </div>
));

const UnsplayAnimation = memo(() => (
  <div className={styles.unsplayAnimation}>
    <div className={styles.collapsingCards}>
      <div className={styles.card}>📇</div>
      <div className={styles.card}>📇</div>
      <div className={styles.card}>📇</div>
    </div>
    <div className={styles.unsplayText}>Unsplaying opponents...</div>
  </div>
));

const FlagAnimation = memo(({ color = "red" }) => (
  <div className={styles.flagAnimation}>
    <div className={styles.flag}>🚩</div>
    <div className={styles.flagText} style={{ color: getColorHex(color) }}>
      {color.toUpperCase()} FLAG CLAIMED!
    </div>
  </div>
));

const FountainAnimation = memo(({ icon = "neural_net" }) => (
  <div className={styles.fountainAnimation}>
    <div className={styles.fountain}>⛲</div>
    <div className={styles.fountainText}>
      {icon.toUpperCase()} FOUNTAIN ACHIEVED!
    </div>
  </div>
));

function getColorHex(color) {
  const colors = {
    red: "#d32f2f",
    blue: "#1976d2",
    green: "#388e3c",
    yellow: "#f57c00",
    purple: "#7b1fa2"
  };
  return colors[color] || "#666";
}

export default SpecialIconAnimation;
