import { memo, useMemo } from "react";
import ScorePileCounter from "./ScorePileCounter";
import styles from "./SymbolCounter.module.css";

// Import symbol images
import castleIcon from "../assets/symbols/castle.png";
import leafIcon from "../assets/symbols/leaf.png";
import lightbulbIcon from "../assets/symbols/lightbulb.png";
import crownIcon from "../assets/symbols/crown.png";
import factoryIcon from "../assets/symbols/factory.png";
import clockIcon from "../assets/symbols/clock.png";

// Move constants outside to prevent recreation on each render
const SYMBOLS = [
  { key: "castle", icon: castleIcon, name: "Castle" },
  { key: "leaf", icon: leafIcon, name: "Leaf" },
  { key: "lightbulb", icon: lightbulbIcon, name: "Lightbulb" },
  { key: "crown", icon: crownIcon, name: "Crown" },
  { key: "factory", icon: factoryIcon, name: "Factory" },
  { key: "clock", icon: clockIcon, name: "Clock" },
];

const STACK_KEYS = ["blue_cards", "red_cards", "green_cards", "yellow_cards", "purple_cards"];

const SymbolCounter = memo(
  function SymbolCounter({
    player,
    compareToPlayer = null,
    position = "above",
    showExtras = true,
    isCurrentPlayer = false,
  }) {
    // Memoize symbol counts calculation to prevent recalculation on each render
    // Phase 2: Use computed_state.visible_symbols from backend (no fallback)
    const symbolCounts = useMemo(() => {
      if (!player) return {};
      return player.computed_state?.visible_symbols || {};
    }, [player?.computed_state?.visible_symbols]);

    // Memoize compare player symbol counts
    // Phase 2: Use computed_state.visible_symbols from backend (no fallback)
    const compareSymbolCounts = useMemo(() => {
      if (!compareToPlayer) return {};
      return compareToPlayer.computed_state?.visible_symbols || {};
    }, [compareToPlayer?.computed_state?.visible_symbols]);

    // Memoize comparison class function
    const getComparisonClass = useMemo(
      () => (myCount, theirCount) => {
        if (!compareToPlayer || theirCount === undefined) return "";

        if (myCount > theirCount) return styles.symbolCount__higher;
        if (myCount === theirCount) return styles.symbolCount__equal;
        return styles.symbolCount__lower;
      },
      [compareToPlayer],
    );

    // Early return after all hooks
    if (!player) return null;

    return (
      <>
        <div className={`${styles.symbolCounter} ${styles[`symbolCounter--${position}`]}`}>
          <div className={styles.symbolGrid}>
            {SYMBOLS.map((symbol) => {
              const myCount = symbolCounts[symbol.key];
              const compareCount = compareSymbolCounts[symbol.key] || 0;

              return (
                <div
                  key={symbol.key}
                  className={`${styles.symbolItem} ${getComparisonClass(myCount, compareCount)}`}
                  title={`${symbol.name}: ${myCount}${
                    compareToPlayer ? ` (vs ${compareCount})` : ""
                  }`}
                >
                  <img src={symbol.icon} alt={symbol.name} className={styles.symbolIcon} />
                  <span className={styles.symbolCount}>{myCount}</span>
                </div>
              );
            })}

            {/* Add hand, score, and achievements with same styling */}
            {showExtras && (
              <>
                {/* Divider */}
                <div className={styles.symbolDivider} />

                {/* Hand Count */}
                <div
                  className={styles.symbolItem}
                  title={`Hand: ${player?.hand?.length || 0} cards`}
                >
                  <span className={styles.symbolText}>🃏</span>
                  <span className={styles.symbolCount}>{player?.hand?.length || 0}</span>
                </div>

                {/* Score Pile - Clickable */}
                <ScorePileCounter player={player} isCurrentPlayer={isCurrentPlayer} />

                {/* Achievements */}
                <div
                  className={styles.symbolItem}
                  title={`Achievements: ${player?.achievements?.length || 0}`}
                >
                  <span className={styles.symbolText}>🏆</span>
                  <span className={styles.symbolCount}>{player?.achievements?.length || 0}</span>
                </div>

                {/* Safe - Unseen Expansion */}
                {player?.safe && (
                  <div
                    className={styles.symbolItem}
                    title={`Safe: ${player.safe.card_count || 0}/${player.safe_limit || 5} secrets`}
                  >
                    <span className={styles.symbolText}>🔒</span>
                    <span className={styles.symbolCount}>{player.safe.card_count || 0}</span>
                  </div>
                )}

                {/* Forecast Zone - Echoes Expansion */}
                {player?.forecast_zone && (
                  <div
                    className={styles.symbolItem}
                    title={`Forecast: ${player.forecast_zone.cards?.length || 0} cards`}
                  >
                    <span className={styles.symbolText}>🔮</span>
                    <span className={styles.symbolCount}>{player.forecast_zone.cards?.length || 0}</span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison function for React.memo
    // Phase 2: Only compare computed_state fields (no board comparison needed)
    return (
      JSON.stringify(prevProps.player?.hand) === JSON.stringify(nextProps.player?.hand) &&
      JSON.stringify(prevProps.player?.score_pile) === JSON.stringify(nextProps.player?.score_pile) &&
      JSON.stringify(prevProps.player?.achievements) ===
        JSON.stringify(nextProps.player?.achievements) &&
      JSON.stringify(prevProps.player?.computed_state?.visible_symbols) ===
        JSON.stringify(nextProps.player?.computed_state?.visible_symbols) &&
      JSON.stringify(prevProps.compareToPlayer?.computed_state?.visible_symbols) ===
        JSON.stringify(nextProps.compareToPlayer?.computed_state?.visible_symbols) &&
      JSON.stringify(prevProps.player?.safe) === JSON.stringify(nextProps.player?.safe) &&
      JSON.stringify(prevProps.player?.forecast_zone) === JSON.stringify(nextProps.player?.forecast_zone) &&
      prevProps.position === nextProps.position &&
      prevProps.isCurrentPlayer === nextProps.isCurrentPlayer
    );
  },
);

export default SymbolCounter;
