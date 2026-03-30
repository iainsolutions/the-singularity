import { useState } from "react";
import PropTypes from "prop-types";
import styles from "./ExpansionSelector.module.css";

const AVAILABLE_EXPANSIONS = [
  {
    id: "cities",
    name: "Cities of Destiny",
    description: "Special icons, Endorse action, and city cards",
    enabled: true,
  },
  {
    id: "artifacts",
    name: "Artifacts of History",
    description: "Dig events, museums, and compel effects",
    enabled: true,
  },
  {
    id: "echoes",
    name: "Echoes of the Past",
    description: "Echo effects and forecast zone",
    enabled: true,
  },
  {
    id: "figures",
    name: "Figures of History",
    description: "Figure cards with karma effects and decrees",
    enabled: true,
  },
  {
    id: "unseen",
    name: "The Unseen",
    description: "Hidden information and safeguard mechanics",
    enabled: true,
  },
];

function ExpansionSelector({ selectedExpansions, onExpansionsChange, disabled }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const handleToggle = (expansionId) => {
    const expansion = AVAILABLE_EXPANSIONS.find((exp) => exp.id === expansionId);
    if (!expansion.enabled) {
      // Show message that expansion is not yet implemented
      return;
    }

    if (selectedExpansions.includes(expansionId)) {
      onExpansionsChange(selectedExpansions.filter((id) => id !== expansionId));
    } else {
      onExpansionsChange([...selectedExpansions, expansionId]);
    }
  };

  const selectedCount = selectedExpansions.length;

  return (
    <div className={styles.expansionSelector}>
      <button
        className={styles.toggleButton}
        onClick={() => setIsExpanded(!isExpanded)}
        disabled={disabled}
        type="button"
      >
        <span className={styles.toggleIcon}>{isExpanded ? "▼" : "▶"}</span>
        <span className={styles.toggleText}>
          Expansions {selectedCount > 0 && `(${selectedCount} selected)`}
        </span>
      </button>

      {isExpanded && (
        <div className={styles.expansionList}>
          {AVAILABLE_EXPANSIONS.map((expansion) => (
            <div
              key={expansion.id}
              className={`${styles.expansionItem} ${
                !expansion.enabled ? styles.disabled : ""
              }`}
            >
              <label className={styles.expansionLabel}>
                <input
                  type="checkbox"
                  checked={selectedExpansions.includes(expansion.id)}
                  onChange={() => handleToggle(expansion.id)}
                  disabled={disabled || !expansion.enabled}
                  className={styles.checkbox}
                />
                <div className={styles.expansionInfo}>
                  <div className={styles.expansionName}>
                    {expansion.name}
                    {!expansion.enabled && (
                      <span className={styles.comingSoon}>(Coming Soon)</span>
                    )}
                  </div>
                  <div className={styles.expansionDescription}>
                    {expansion.description}
                  </div>
                </div>
              </label>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

ExpansionSelector.propTypes = {
  selectedExpansions: PropTypes.arrayOf(PropTypes.string).isRequired,
  onExpansionsChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};

ExpansionSelector.defaultProps = {
  disabled: false,
};

export default ExpansionSelector;
