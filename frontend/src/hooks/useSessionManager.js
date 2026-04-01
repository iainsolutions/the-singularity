import { useCallback } from "react";

/**
 * Custom hook for managing game session persistence in localStorage
 * Handles saving, loading, and clearing session data
 */
export function useSessionManager() {
  const saveSession = useCallback((gameId, playerId, playerName, token = null) => {
    console.log("💾 [SessionManager] saveSession called:", {
      gameId,
      playerId,
      playerName,
      hasToken: !!token,
    });
    const sessionData = { gameId, playerId, playerName, token };
    localStorage.setItem("singularity-session", JSON.stringify(sessionData));
    console.log("✅ [SessionManager] Session saved successfully");
  }, []);

  const loadSession = useCallback(() => {
    try {
      // Debug: Log all localStorage keys to understand what's available
      console.log("🔍 [SessionManager] All localStorage keys:", Object.keys(localStorage));

      // First try the new key
      let sessionData = localStorage.getItem("singularity-session");
      console.log("🔍 [SessionManager] New key data:", sessionData ? "found" : "not found");

      // Migration: Check for old key format and migrate
      if (!sessionData) {
        const oldSessionData = localStorage.getItem("singularity_game_session");
        console.log("🔍 [SessionManager] Old key data:", oldSessionData ? "found" : "not found");
        if (oldSessionData) {
          console.log("🔄 [SessionManager] Migrating session from old key format");
          // Migrate to new key
          localStorage.setItem("singularity-session", oldSessionData);
          localStorage.removeItem("singularity_game_session");
          sessionData = oldSessionData;
        }
      }

      return sessionData ? JSON.parse(sessionData) : null;
    } catch (error) {
      console.error("Failed to load session:", error);
      return null;
    }
  }, []);

  const clearSession = useCallback(() => {
    localStorage.removeItem("singularity-session");
  }, []);

  return {
    saveSession,
    loadSession,
    clearSession,
  };
}
