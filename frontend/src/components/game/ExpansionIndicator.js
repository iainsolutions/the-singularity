import PropTypes from "prop-types";
import styles from "./ExpansionIndicator.module.css";

const EXPANSION_INFO = {
  cities: { name: "Cities", color: "#FF9800", abbrev: "C" },
  artifacts: { name: "Artifacts", color: "#9C27B0", abbrev: "A" },
  echoes: { name: "Echoes", color: "#2196F3", abbrev: "E" },
  figures: { name: "Figures", color: "#4CAF50", abbrev: "F" },
  unseen: { name: "Unseen", color: "#607D8B", abbrev: "U" },
};

function ExpansionIndicator({ gameState }) {
  // Explicit null checks for safety
  if (!gameState || !gameState.expansion_config) {
    return null;
  }

  const enabledExpansions = gameState.expansion_config.enabled_expansions || [];

  if (enabledExpansions.length === 0) {
    return null;
  }

  return (
    <div className={styles.container}>
      <div className={styles.label}>Active Expansions:</div>
      <div className={styles.badges}>
        {enabledExpansions.map((expId) => {
          const info = EXPANSION_INFO[expId];
          if (!info) return null;

          return (
            <div
              key={expId}
              className={styles.badge}
              style={{ backgroundColor: info.color }}
              title={info.name}
            >
              {info.abbrev}
            </div>
          );
        })}
      </div>
    </div>
  );
}

ExpansionIndicator.propTypes = {
  gameState: PropTypes.shape({
    expansion_config: PropTypes.shape({
      enabled_expansions: PropTypes.arrayOf(PropTypes.string),
    }),
  }),
};

ExpansionIndicator.defaultProps = {
  gameState: null,
};

export default ExpansionIndicator;
