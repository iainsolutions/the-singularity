// Centralized card database for the Innovation game
// This mirrors the backend BaseCards.json for frontend components that only have card names
// (like ActionLog when parsing log text)

export const CARD_DATABASE = {
  // Age 1
  Archery: { age: 1, color: "red", card_id: "B 001" },
  Metalworking: { age: 1, color: "red", card_id: "B 002" },
  Oars: { age: 1, color: "red", card_id: "B 003" },
  Agriculture: { age: 1, color: "yellow", card_id: "B 004" },
  Domestication: { age: 1, color: "yellow", card_id: "B 005" },
  Masonry: { age: 1, color: "yellow", card_id: "B 006" },
  Clothing: { age: 1, color: "green", card_id: "B 007" },
  Sailing: { age: 1, color: "green", card_id: "B 008" },
  "The Wheel": { age: 1, color: "green", card_id: "B 009" },
  Pottery: { age: 1, color: "blue", card_id: "B 010" },
  Tools: { age: 1, color: "blue", card_id: "B 011" },
  Writing: { age: 1, color: "blue", card_id: "B 012" },
  "City States": { age: 1, color: "purple", card_id: "B 013" },
  "Code of Laws": { age: 1, color: "purple", card_id: "B 014" },
  Mysticism: { age: 1, color: "purple", card_id: "B 015" },

  // Age 2
  Construction: { age: 2, color: "red", card_id: "B 016" },
  "Road Building": { age: 2, color: "red", card_id: "B 017" },
  "Canal Building": { age: 2, color: "yellow", card_id: "B 018" },
  Fermenting: { age: 2, color: "yellow", card_id: "B 019" },
  Currency: { age: 2, color: "green", card_id: "B 020" },
  Mapmaking: { age: 2, color: "green", card_id: "B 021" },
  Calendar: { age: 2, color: "blue", card_id: "B 022" },
  Mathematics: { age: 2, color: "blue", card_id: "B 023" },
  Monotheism: { age: 2, color: "purple", card_id: "B 024" },
  Philosophy: { age: 2, color: "purple", card_id: "B 025" },

  // Age 3
  Engineering: { age: 3, color: "red", card_id: "B 026" },
  Optics: { age: 3, color: "red", card_id: "B 027" },
  Machinery: { age: 3, color: "yellow", card_id: "B 028" },
  Medicine: { age: 3, color: "yellow", card_id: "B 029" },
  Compass: { age: 3, color: "green", card_id: "B 030" },
  Paper: { age: 3, color: "green", card_id: "B 031" },
  Alchemy: { age: 3, color: "blue", card_id: "B 032" },
  Translation: { age: 3, color: "blue", card_id: "B 033" },
  Education: { age: 3, color: "purple", card_id: "B 034" },
  Feudalism: { age: 3, color: "purple", card_id: "B 035" },

  // Age 4
  Colonialism: { age: 4, color: "red", card_id: "B 036" },
  Gunpowder: { age: 4, color: "red", card_id: "B 037" },
  Anatomy: { age: 4, color: "yellow", card_id: "B 038" },
  Perspective: { age: 4, color: "yellow", card_id: "B 039" },
  Invention: { age: 4, color: "green", card_id: "B 040" },
  Navigation: { age: 4, color: "green", card_id: "B 041" },
  Experimentation: { age: 4, color: "blue", card_id: "B 042" },
  "Printing Press": { age: 4, color: "blue", card_id: "B 043" },
  Enterprise: { age: 4, color: "purple", card_id: "B 044" },
  Reformation: { age: 4, color: "purple", card_id: "B 045" },

  // Age 5
  Coal: { age: 5, color: "red", card_id: "B 046" },
  "The Pirate Code": { age: 5, color: "red", card_id: "B 047" },
  Statistics: { age: 5, color: "yellow", card_id: "B 048" },
  "Steam Engine": { age: 5, color: "yellow", card_id: "B 049" },
  Banking: { age: 5, color: "green", card_id: "B 050" },
  Measurement: { age: 5, color: "green", card_id: "B 051" },
  Chemistry: { age: 5, color: "blue", card_id: "B 052" },
  Physics: { age: 5, color: "blue", card_id: "B 053" },
  Astronomy: { age: 5, color: "purple", card_id: "B 054" },
  Societies: { age: 5, color: "purple", card_id: "B 055" },

  // Age 6
  Industrialization: { age: 6, color: "red", card_id: "B 056" },
  "Machine Tools": { age: 6, color: "red", card_id: "B 057" },
  Canning: { age: 6, color: "yellow", card_id: "B 058" },
  Vaccination: { age: 6, color: "green", card_id: "B 059" },
  Classification: { age: 6, color: "green", card_id: "B 060" },
  "Metric System": { age: 6, color: "green", card_id: "B 061" },
  "Atomic Theory": { age: 6, color: "blue", card_id: "B 062" },
  Encyclopedia: { age: 6, color: "blue", card_id: "B 063" },
  Democracy: { age: 6, color: "purple", card_id: "B 064" },
  Emancipation: { age: 6, color: "purple", card_id: "B 065" },

  // Age 7
  Combustion: { age: 7, color: "red", card_id: "B 066" },
  Explosives: { age: 7, color: "red", card_id: "B 067" },
  Refrigeration: { age: 7, color: "yellow", card_id: "B 068" },
  Sanitation: { age: 7, color: "yellow", card_id: "B 069" },
  Bicycle: { age: 7, color: "green", card_id: "B 070" },
  Electricity: { age: 7, color: "green", card_id: "B 071" },
  Evolution: { age: 7, color: "blue", card_id: "B 072" },
  Publications: { age: 7, color: "blue", card_id: "B 073" },
  Lighting: { age: 7, color: "purple", card_id: "B 074" },
  Railroad: { age: 7, color: "purple", card_id: "B 075" },

  // Age 8
  Flight: { age: 8, color: "red", card_id: "B 076" },
  Mobility: { age: 8, color: "red", card_id: "B 077" },
  Antibiotics: { age: 8, color: "green", card_id: "B 078" },
  Skyscrapers: { age: 8, color: "yellow", card_id: "B 079" },
  Corporations: { age: 8, color: "green", card_id: "B 080" },
  "Mass Media": { age: 8, color: "green", card_id: "B 081" },
  "Quantum Theory": { age: 8, color: "blue", card_id: "B 082" },
  Rocketry: { age: 8, color: "blue", card_id: "B 083" },
  Empiricism: { age: 8, color: "purple", card_id: "B 084" },
  Socialism: { age: 8, color: "purple", card_id: "B 085" },

  // Age 9
  Composites: { age: 9, color: "red", card_id: "B 086" },
  Fission: { age: 9, color: "red", card_id: "B 087" },
  Ecology: { age: 9, color: "yellow", card_id: "B 088" },
  Suburbia: { age: 9, color: "yellow", card_id: "B 089" },
  Collaboration: { age: 9, color: "green", card_id: "B 090" },
  Satellites: { age: 9, color: "green", card_id: "B 091" },
  Computers: { age: 9, color: "blue", card_id: "B 092" },
  Genetics: { age: 9, color: "blue", card_id: "B 093" },
  Services: { age: 9, color: "purple", card_id: "B 094" },
  Specialization: { age: 9, color: "purple", card_id: "B 095" },

  // Age 10
  Miniaturization: { age: 10, color: "red", card_id: "B 096" },
  Robotics: { age: 10, color: "red", card_id: "B 097" },
  Globalization: { age: 10, color: "yellow", card_id: "B 098" },
  "Stem Cells": { age: 10, color: "yellow", card_id: "B 099" },
  Databases: { age: 10, color: "green", card_id: "B 100" },
  "Self Service": { age: 10, color: "green", card_id: "B 101" },
  Bioengineering: { age: 10, color: "blue", card_id: "B 102" },
  Software: { age: 10, color: "blue", card_id: "B 103" },
  "A.I.": { age: 10, color: "purple", card_id: "B 104" },
  "The Internet": { age: 10, color: "purple", card_id: "B 105" },

  // Age 11
  Astrogeology: { age: 11, color: "red", card_id: "B 106" },
  Fusion: { age: 11, color: "red", card_id: "B 107" },
  "Near-field Comm": { age: 11, color: "yellow", card_id: "B 108" },
  Reclamation: { age: 11, color: "yellow", card_id: "B 109" },
  Hypersonics: { age: 11, color: "green", card_id: "B 110" },
  "Space Traffic": { age: 11, color: "green", card_id: "B 111" },
  Climatology: { age: 11, color: "blue", card_id: "B 112" },
  "Solar Sailing": { age: 11, color: "blue", card_id: "B 113" },
  Escapism: { age: 11, color: "purple", card_id: "B 114" },
  Whataboutism: { age: 11, color: "purple", card_id: "B 115" },
};

// Helper functions
export const getCardColor = (cardName) => {
  return CARD_DATABASE[cardName]?.color || "blue";
};

export const getCardAge = (cardName) => {
  return CARD_DATABASE[cardName]?.age || 1;
};

export const getCardInfo = (cardName) => {
  return CARD_DATABASE[cardName] || { age: 1, color: "blue" };
};

// Get all card names as an array for regex matching
export const getAllCardNames = () => {
  return Object.keys(CARD_DATABASE);
};

// Color helper functions for UI
export const getCardBackgroundColor = (cardColor) => {
  switch (cardColor) {
    case "blue":
      return "#e3f2fd";
    case "red":
      return "#ffebee";
    case "green":
      return "#e8f5e9";
    case "yellow":
      return "#fffde7";
    case "purple":
      return "#f3e5f5";
    default:
      return "#f5f5f5";
  }
};

export const getCardTextColor = (cardColor) => {
  switch (cardColor) {
    case "blue":
      return "#1565c0";
    case "red":
      return "#c62828";
    case "green":
      return "#2e7d32";
    case "yellow":
      return "#f9a825";
    case "purple":
      return "#6a1b9a";
    default:
      return "#424242";
  }
};

// Full card data cache (populated from backend)
let fullCardDataCache = null;

/**
 * Set the full card data cache
 * Used to update the database with complete card information from backend
 */
export const setFullCardDataCache = (cardData) => {
  fullCardDataCache = cardData;
};

/**
 * Get full card data including symbols and dogma effects
 * Falls back to basic info if full data not available
 */
export const getFullCardInfo = (cardName) => {
  if (fullCardDataCache && fullCardDataCache[cardName]) {
    return fullCardDataCache[cardName];
  }
  // Fallback to basic info
  return CARD_DATABASE[cardName] || { age: 1, color: "blue" };
};
