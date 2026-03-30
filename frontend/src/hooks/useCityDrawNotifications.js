import { useEffect, useRef } from "react";
import { showCityDrawToast } from "../utils/toast";

/**
 * Custom hook to monitor game activity log and show toast notifications for city draws
 *
 * @param {Array} actionLog - The game's action log
 * @param {Object} gameState - The current game state
 */
export function useCityDrawNotifications(actionLog, gameState) {
  // Track the last processed log entry count to detect new entries
  const lastProcessedCount = useRef(0);

  useEffect(() => {
    if (!actionLog || actionLog.length === 0) {
      return;
    }

    // Only process new log entries
    const newEntries = actionLog.slice(lastProcessedCount.current);

    newEntries.forEach((entry) => {
      // Check if this entry describes a city draw
      const description = entry.description || entry.message || "";
      const lowerDesc = description.toLowerCase();

      // Match patterns like "drew city {cityName} (new color)" or "drew city {cityName} (new splay direction)"
      if (lowerDesc.includes("drew city")) {
        // Extract city name and reason
        const cityMatch = description.match(/drew city (\w+)/i);
        const reasonMatch = description.match(/\((new color|new splay direction)\)/i);

        if (cityMatch) {
          const cityName = cityMatch[1];
          const reason = reasonMatch ? reasonMatch[1] : "trigger";

          // Show toast notification
          showCityDrawToast(cityName, reason === "new color" ? "new_color" : "new_splay");
        }
      }
    });

    // Update last processed count
    lastProcessedCount.current = actionLog.length;
  }, [actionLog, gameState]);
}

export default useCityDrawNotifications;
