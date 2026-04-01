// Service for fetching and caching lore data (era narratives, domain lore)
import axios from "axios";
import { getApiBase } from "../utils/config";

const API_BASE = getApiBase();

let loreCache = null;
let loreCachePromise = null;

/**
 * Fetches domain and era lore from the backend
 */
export const fetchLore = async () => {
  if (loreCache) return loreCache;
  if (loreCachePromise) return loreCachePromise;

  loreCachePromise = axios
    .get(`${API_BASE}/api/v1/cards/lore`)
    .then((response) => {
      loreCache = response.data;
      loreCachePromise = null;
      return loreCache;
    })
    .catch((error) => {
      console.error("Failed to fetch lore:", error);
      loreCachePromise = null;
      return { domain_lore: {}, era_lore: {} };
    });

  return loreCachePromise;
};

/**
 * Get lore for a specific era
 */
export const getEraLore = async (eraNumber) => {
  const lore = await fetchLore();
  return lore.era_lore?.[String(eraNumber)] || null;
};

/**
 * Get lore for a specific domain (color)
 */
export const getDomainLore = async (color) => {
  const lore = await fetchLore();
  return lore.domain_lore?.[color] || null;
};

export const clearLoreCache = () => {
  loreCache = null;
  loreCachePromise = null;
};
