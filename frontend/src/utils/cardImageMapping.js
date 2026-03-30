/**
 * Card Image Mapping Utility
 * Maps Innovation cards to their corresponding PNG images using card_id
 *
 * Card images are organized by expansion:
 * - Base cards: B 001 - B 115 -> /cards/Base/Base1.png - Base115.png
 * - Artifacts: A 001 - A 115 -> /cards/Artifacts/Artifacts1.png - Artifacts115.png
 * - Cities: C 001 - C 115 -> /cards/Cities/Cities1.png - Cities115.png
 * - Echoes: E 001 - E 115 -> /cards/Echoes/Echoes1.png - Echoes115.png
 * - Figures: F 001 - F 130 -> /cards/Figures/Figures1.png - Figures130.png
 * - Unseen: U 001 - U 115 -> /cards/Unseen/Unseen1.png - Unseen115.png
 */

/**
 * Parse card_id to get expansion and number
 * @param {string} cardId - The card_id from the card data (e.g., "B 001")
 * @returns {object|null} - Object with expansion and number, or null if invalid
 */
function parseCardId(cardId) {
  if (!cardId || typeof cardId !== "string") return null;

  // Parse format like "B 001" or "B001"
  const match = cardId.match(/^([BACEFSU])\s*(\d{3})$/);
  if (!match) return null;

  const [, expansion, number] = match;

  // Map expansion codes to folder names
  const expansionMap = {
    B: "Base",
    A: "Artifacts",
    C: "Cities",
    E: "Echoes",
    F: "Figures",
    U: "Unseen",
    S: "Specials",
  };

  const expansionName = expansionMap[expansion];
  if (!expansionName) return null;

  // Convert "001" to "1" for the filename
  const imageNumber = parseInt(number, 10);

  return {
    expansion: expansionName,
    number: imageNumber,
    paddedNumber: number, // Keep padded for display if needed
  };
}

/**
 * Get the full image path for a card using its card_id
 * @param {object} card - The card object containing card_id
 * @param {string} side - "front" or "back" (currently only front images exist for Ultimate)
 * @returns {string|null} - The full path to the image or null if not found
 */
export function getCardImagePath(card, side = "front") {
  // Check if we have a card with card_id
  if (!card || !card.card_id) {
    // Fallback to name-based mapping for old Print_BaseCards images if needed
    if (card && card.name && !card.card_id) {
      return getOldCardImagePath(card.name, side);
    }
    return null;
  }

  const parsed = parseCardId(card.card_id);
  if (!parsed) return null;

  // For Ultimate cards, we only have front images in expansion folders
  // Format: /cards/Base/Base1.png
  const path = `/cards/${parsed.expansion}/${parsed.expansion}${parsed.number}.png`;
  return path;
}

/**
 * Legacy function to get image path using card name (for old Print_BaseCards images)
 * @param {string} cardName - The name of the card
 * @param {string} side - "front" or "back"
 * @returns {string|null} - The full path to the image or null
 */
function getOldCardImagePath(cardName, side = "front") {
  // This is the old mapping for Print_BaseCards images
  // We'll keep this as a fallback but it shouldn't be used with Ultimate cards
  const OLD_MAPPING = {
    Agriculture: "001",
    Archery: "002",
    // ... etc (keeping old mapping as fallback)
  };

  const imageNumber = OLD_MAPPING[cardName];
  if (!imageNumber) return null;

  return `/cards/${side}/Print_BaseCards_${side}-${imageNumber}.png`;
}

/**
 * Check if a card has an associated image
 * @param {object} card - The card object
 * @returns {boolean} - True if the card has an associated image
 */
export function hasCardImage(card) {
  if (!card) return false;

  // Check for card_id first (Ultimate cards)
  if (card.card_id) {
    const parsed = parseCardId(card.card_id);
    return parsed !== null;
  }

  // Fallback to name-based check for old cards
  return false; // We're only using Ultimate cards now
}

/**
 * Get the card back image path for a given age
 * @param {number} age - The age of the card (1-11)
 * @returns {string} - The path to the card back image
 */
export function getCardBackImagePath(age) {
  // Ultimate card backs are in /cards/CardBacks/
  // They're numbered by age: InnoUlt_CardBacks_PRODUCTION1.png through PRODUCTION67.png
  // We'll need to map ages to the appropriate back image
  // For now, return a generic back or age-specific if we have the mapping
  return `/cards/CardBacks/InnoUlt_CardBacks_PRODUCTION${age}.png`;
}

/**
 * Get a fallback image based on card color
 * @param {string} color - The card color
 * @returns {string} - The path to the fallback image
 */
export function getFallbackImagePath(color) {
  const validColors = ["red", "yellow", "green", "blue", "purple"];
  const cardColor = validColors.includes(color) ? color : "blue";
  return `/cards/card_backgrounds/${cardColor}.png`;
}

/**
 * Validate that a card and side combination is valid
 * @param {object} card - The card object
 * @param {string} side - "front" or "back"
 * @returns {boolean} - True if valid
 */
export function isValidCardImage(card, side = "front") {
  return hasCardImage(card) && ["front", "back"].includes(side);
}

export default {
  getCardImagePath,
  hasCardImage,
  getCardBackImagePath,
  getFallbackImagePath,
  isValidCardImage,
};
