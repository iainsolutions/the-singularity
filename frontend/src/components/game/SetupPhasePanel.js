import { memo } from "react";
import Card from "../Card";
import styles from "./SetupPhasePanel.module.css";

const SetupPhasePanel = memo(
  function SetupPhasePanel({ cards, onCardSelect }) {
    return (
      <div className={styles.setupPanel}>
        <h3 className={styles.setupPanel__title}>Choose Your Starting Card</h3>
        <p className={styles.setupPanel__description}>
          Select one card to meld to your board. The other will remain in your hand.
        </p>
        <div className={styles.setupPanel__cards}>
          {cards.map((card) => (
            <Card
              key={card.card_id || card.name}
              card={card}
              isClickable
              onClick={() => onCardSelect(card)}
            />
          ))}
        </div>
      </div>
    );
  },
  (prevProps, nextProps) => {
    // Efficient shallow comparison instead of expensive JSON.stringify
    if (prevProps.onCardSelect !== nextProps.onCardSelect) {
      return false;
    }

    // Check array length first (fast)
    if (prevProps.cards?.length !== nextProps.cards?.length) {
      return false;
    }

    // If both are null/undefined, they're equal
    if (!prevProps.cards && !nextProps.cards) {
      return true;
    }

    // If one is null/undefined and the other isn't, they're different
    if (!prevProps.cards || !nextProps.cards) {
      return false;
    }

    // Compare each card by reference and key properties
    return prevProps.cards.every((card, index) => {
      const nextCard = nextProps.cards[index];
      return (
        card === nextCard || // Same reference (most common case)
        (card?.name === nextCard?.name &&
          card?.age === nextCard?.age &&
          card?.color === nextCard?.color)
      );
    });
  },
);

export default SetupPhasePanel;
