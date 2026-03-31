/**
 * Card Image Mapping Utility
 * Maps cards to their corresponding images using card_id
 *
 * Singularity cards: S001 - S105
 * Currently no card images exist — cards render as text.
 */

/**
 * Get the full image path for a card using its card_id
 * Returns null since Singularity cards don't have images yet.
 */
export function getCardImagePath(card, side = "front") {
  return null;
}

/**
 * Check if a card has an associated image
 */
export function hasCardImage(card) {
  return false;
}

/**
 * Get the card back image path for a given age
 */
export function getCardBackImagePath(age) {
  return null;
}

/**
 * Get a fallback image based on card color
 */
export function getFallbackImagePath(color) {
  return null;
}

/**
 * Validate that a card and side combination is valid
 */
export function isValidCardImage(card, side = "front") {
  return false;
}

export default {
  getCardImagePath,
  hasCardImage,
  getCardBackImagePath,
  getFallbackImagePath,
  isValidCardImage,
};
