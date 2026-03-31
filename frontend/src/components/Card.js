import { memo, useMemo } from "react";
import styles from "./Card.module.css";
import circuitIcon from "../assets/icons/circuit.svg";
import neuralNetIcon from "../assets/icons/neural_net.svg";
import dataIcon from "../assets/icons/data.svg";
import algorithmIcon from "../assets/icons/algorithm.svg";
import humanMindIcon from "../assets/icons/human_mind.svg";
import robotIcon from "../assets/icons/robot.svg";

const ICON_SVGS = {
  circuit: circuitIcon,
  neural_net: neuralNetIcon,
  data: dataIcon,
  algorithm: algorithmIcon,
  human_mind: humanMindIcon,
  robot: robotIcon,
};

const Card = memo(
  function Card({
    card,
    isClickable = false,
    isSelected = false,
    onClick,
    size = "normal",
    showBack = false,
    isSelecting = false,
    isEligible = false,
    isActivatable = false,
  }) {
    const cardClasses = useMemo(
      () =>
        [
          styles.card,
          styles[size] || "",
          card?.color ? styles[card.color] : "",
          isClickable ? styles.clickable : "",
          isSelected ? styles.selected : "",
          isSelecting ? styles.selecting : "",
          isEligible ? styles.eligible : "",
          isActivatable ? styles.activatable : "",
        ]
          .filter(Boolean)
          .join(" "),
      [size, card?.color, isClickable, isSelected, isSelecting, isEligible, isActivatable],
    );

    const handleClick = () => {
      if (isClickable && onClick) {
        onClick(card);
      }
    };

    if (!card) {
      return (
        <div className={`${styles.card} ${styles.empty} ${styles[size] || ""}`}>
          <div className={styles.cardPlaceholder}>Empty</div>
        </div>
      );
    }

    if (showBack) {
      return (
        <div className={`${styles.card} ${styles.cardBack} ${styles[size] || ""}`} onClick={handleClick}>
          <div className={styles.backAge}>{card.age}</div>
        </div>
      );
    }

    // Symbol positions: [top_left, bottom_left, bottom_right, top_right]
    const positions = card.symbol_positions || [];
    const renderIcon = (sym) => {
      if (!sym) return null;
      const src = ICON_SVGS[sym];
      return src ? <img src={src} alt={sym} className={styles.iconImg} /> : sym;
    };
    const topLeft = renderIcon(positions[0]);
    const bottomLeft = renderIcon(positions[1]);
    const bottomRight = renderIcon(positions[2]);
    const topRight = renderIcon(positions[3]);

    return (
      <div
        className={cardClasses}
        onClick={handleClick}
        role={isClickable ? "button" : undefined}
        aria-label={`${card.name}, Era ${card.age}`}
        tabIndex={isClickable ? 0 : -1}
        data-achievement={card?.is_achievement ? "true" : "false"}
      >
        <div className={styles.cardContent} data-era={card.age}>
          {/* Header: name + era */}
          <div className={styles.cardHeader}>
            <span className={styles.cardName}>{card.name}</span>
            <span className={styles.cardAge}>{card.age}</span>
          </div>

          {/* Featured icon (dogma resource) — determines sharing/override */}
          {card.dogma_resource && (
            <div className={styles.featuredIcon}>
              {renderIcon(card.dogma_resource)}
            </div>
          )}

          {/* Icons row */}
          <div className={styles.iconRow}>
            <span className={styles.iconSlot}>{topLeft}</span>
            <span className={styles.iconSlot}>{topRight}</span>
          </div>

          {/* Dogma text */}
          {card.dogma_effects && card.dogma_effects.length > 0 && (
            <div className={styles.cardEffects}>
              {card.dogma_effects.map((effect, i) => (
                <div
                  key={i}
                  className={
                    effect.is_demand ? styles.demandEffect : styles.cooperativeEffect
                  }
                >
                  {effect.text}
                </div>
              ))}
            </div>
          )}

          {/* Bottom icons */}
          <div className={styles.iconRow}>
            <span className={styles.iconSlot}>{bottomLeft}</span>
            <span className={styles.iconSlot}>{bottomRight}</span>
          </div>

          {card.dogma_resource && (
            <div className={styles.cardResource}>{card.dogma_resource.replace('_', ' ')}</div>
          )}
        </div>

        {card.is_achievement && (
          <div className={styles.achievementMarker}>Achievement</div>
        )}

        {isSelected && (
          <div className={styles.selectionCheckmark}>
            <div className={styles.checkmarkIcon}>✓</div>
          </div>
        )}
      </div>
    );
  },
  (prevProps, nextProps) => {
    return (
      prevProps.card?.card_id === nextProps.card?.card_id &&
      prevProps.card?.name === nextProps.card?.name &&
      prevProps.isClickable === nextProps.isClickable &&
      prevProps.isSelected === nextProps.isSelected &&
      prevProps.isSelecting === nextProps.isSelecting &&
      prevProps.size === nextProps.size &&
      prevProps.onClick === nextProps.onClick
    );
  },
);

export default Card;
