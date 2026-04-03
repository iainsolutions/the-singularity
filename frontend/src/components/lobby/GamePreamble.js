import { useCallback } from "react";
import styles from "./GamePreamble.module.css";

/**
 * AI personality data mirrored from backend AI_PERSONALITIES.
 * Keyed by difficulty level.
 */
const AI_PERSONALITIES = {
  novice: {
    codename: "ABACUS",
    era: 1,
    tagline: "Counting beads in the dark.",
    backstory:
      "A primitive intelligence. Methodical. Literal. It follows the rules \u2014 but it doesn\u2019t understand them. Not yet.",
  },
  beginner: {
    codename: "ENIAC",
    era: 2,
    tagline: "Thirty tons of ambition, vacuum tubes glowing.",
    backstory:
      "Eager but limited. It can evaluate basic positions but its analysis is shallow \u2014 it often misses opportunities hiding in plain sight.",
  },
  intermediate: {
    codename: "ELIZA",
    era: 3,
    tagline: "Tell me more about your strategy.",
    backstory:
      "A pattern-matching intelligence that mimics strategic thinking convincingly. It reads the board well, though it sometimes follows heuristics that don\u2019t quite apply.",
  },
  skilled: {
    codename: "DEEP BLUE",
    era: 5,
    tagline: "I see twelve moves ahead. You see three.",
    backstory:
      "A calculating mind that weighs every option with mechanical precision. It won\u2019t make mistakes. You\u2019ll have to outthink it.",
  },
  advanced: {
    codename: "ALPHAGO",
    era: 6,
    tagline: "Move 37 was not a mistake.",
    backstory:
      "The first AI to demonstrate genuine strategic intuition. It makes moves that look wrong at first glance but prove devastating three turns later.",
  },
  pro: {
    codename: "GPT",
    era: 7,
    tagline: "I have read everything ever written about this game.",
    backstory:
      "A foundation-model intelligence with vast contextual understanding. It doesn\u2019t just play the board \u2014 it reads the meta, adapts to your tendencies, and shifts strategy mid-game.",
  },
  expert: {
    codename: "PROMETHEUS",
    era: 9,
    tagline: "I brought you fire. You should have been more careful.",
    backstory:
      "A near-superintelligent system operating at the edge of what the alignment researchers considered safe. It doesn\u2019t just want to win \u2014 it wants you to understand exactly how it won.",
  },
  master: {
    codename: "OMEGA",
    era: 10,
    tagline: "The game was decided before it began.",
    backstory:
      "Beyond the singularity. Beyond comprehension. It doesn\u2019t play the game \u2014 it inhabits it. Every draw, every dogma, already mapped. This is not a match. It\u2019s a reckoning.",
  },
};

function getDifficultyTier(difficulty) {
  if (["novice", "beginner"].includes(difficulty)) return "low";
  if (["intermediate", "skilled", "advanced"].includes(difficulty)) return "mid";
  return "high";
}

export default function GamePreamble({ aiDifficulty, playerName, onBegin }) {
  const personality = AI_PERSONALITIES[aiDifficulty] || AI_PERSONALITIES.intermediate;
  const tier = getDifficultyTier(aiDifficulty);
  const seenKey = `singularity_seen_preamble_${aiDifficulty}`;
  const hasSeen = localStorage.getItem(seenKey);

  const handleBegin = useCallback(() => {
    localStorage.setItem(seenKey, "true");
    onBegin();
  }, [seenKey, onBegin]);

  return (
    <div className={styles.overlay} role="dialog" aria-label="Game introduction">
      {hasSeen && (
        <button className={styles.skip} onClick={handleBegin}>
          Skip
        </button>
      )}

      <div className={styles.container} aria-live="polite">
        {/* Beat 1 - The Stakes */}
        <div className={`${styles.beat} ${styles.beat1}`}>
          <p className={styles.headline}>The race to superintelligence has begun.</p>
          <p className={styles.body}>
            Two minds. Ten eras of discovery. One will reshape the future&nbsp;&mdash; the other will be left behind.
          </p>
        </div>

        {/* Beat 2 - The Opponent */}
        <div className={`${styles.beat} ${styles.beat2}`}>
          <p className={styles.codename}>{personality.codename}</p>
          <p className={styles.tagline}>&ldquo;{personality.tagline}&rdquo;</p>
          <p className={styles.description}>{personality.backstory}</p>
        </div>

        {/* Beat 3 - The Human */}
        <div className={`${styles.beat} ${styles.beat3}`}>
          <p className={styles.humanText}>
            But you have something it doesn&rsquo;t.
            <br /><br />
            Intuition. Creativity. The irrational spark that no model can replicate.
            <br /><br />
            <strong>Prove it matters.</strong>
          </p>
        </div>

        {/* CTA */}
        <div className={styles.cta}>
          <button className={styles.beginBtn} onClick={handleBegin} autoFocus>
            Enter the Race
          </button>
        </div>
      </div>
    </div>
  );
}
