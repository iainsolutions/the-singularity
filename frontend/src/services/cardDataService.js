// Service for fetching and caching full card data from backend
import axios from "axios";
import { getApiBase } from "../utils/config";

const API_BASE = getApiBase();

// Cache for card data
let cardDataCache = null;
let cachePromise = null;

/**
 * Fetches full card database from backend API
 * Includes symbols, dogma effects, and all card metadata
 */
export const fetchCardDatabase = async () => {
  // Return cached data if available
  if (cardDataCache) {
    return cardDataCache;
  }

  // If a fetch is already in progress, wait for it
  if (cachePromise) {
    return cachePromise;
  }

  // Start a new fetch
  cachePromise = axios
    .get(`${API_BASE}/api/v1/cards/database`)
    .then((response) => {
      // Convert array to object keyed by card name for easy lookup
      const cardsMap = {};
      response.data.cards.forEach((card) => {
        cardsMap[card.name] = card;
      });

      cardDataCache = cardsMap;
      cachePromise = null;
      return cardsMap;
    })
    .catch((error) => {
      console.error("Failed to fetch card database:", error);
      cachePromise = null;
      // Return empty object on error to prevent crashes
      return {};
    });

  return cachePromise;
};

/**
 * Get full data for a specific card
 * @param {string} cardName - Name of the card
 * @returns {Object|null} Full card data or null if not found
 */
export const getFullCardData = async (cardName) => {
  const database = await fetchCardDatabase();
  return database[cardName] || null;
};

/**
 * Get card symbols
 * @param {string} cardName - Name of the card
 * @returns {Array} Array of symbol strings
 */
export const getCardSymbols = async (cardName) => {
  const card = await getFullCardData(cardName);
  return card?.symbols || [];
};

/**
 * Get card dogma effects
 * @param {string} cardName - Name of the card
 * @returns {Array} Array of dogma effect objects
 */
export const getCardDogmaEffects = async (cardName) => {
  const card = await getFullCardData(cardName);
  return card?.dogma_effects || [];
};

/**
 * Clear the cache (useful for testing or when data updates)
 */
export const clearCardCache = () => {
  cardDataCache = null;
  cachePromise = null;
};
