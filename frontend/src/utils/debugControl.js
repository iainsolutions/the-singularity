/**
 * Debug control utilities for browser console
 * Allows runtime control of debug logging without rebuilding
 */

import { enableDebug, disableDebug, isDebugEnabled } from "./logger";

// Expose debug control to window object for browser console access
if (typeof window !== "undefined") {
  window.InnovationDebug = {
    /**
     * Enable debug logging
     * Usage: InnovationDebug.enable()
     */
    enable: () => {
      enableDebug();
      console.log("🔍 Debug mode enabled. Page will reload...");
    },

    /**
     * Disable debug logging
     * Usage: InnovationDebug.disable()
     */
    disable: () => {
      disableDebug();
      console.log("🔕 Debug mode disabled. Page will reload...");
    },

    /**
     * Check current debug status
     * Usage: InnovationDebug.status()
     */
    status: () => {
      const enabled = isDebugEnabled();
      console.log(`Debug mode is ${enabled ? "✅ ENABLED" : "❌ DISABLED"}`);
      return enabled;
    },

    /**
     * Help information
     * Usage: InnovationDebug.help()
     */
    help: () => {
      console.log(`
🎮 Innovation Debug Control
===========================
Available commands:
  InnovationDebug.enable()  - Turn on debug logging
  InnovationDebug.disable() - Turn off debug logging
  InnovationDebug.status()  - Check current status
  InnovationDebug.help()    - Show this help

Debug mode persists across page reloads until disabled.
      `);
    },
  };

  // Show status on initial load in development
  if (import.meta.env.MODE === "development") {
    console.log('💡 Debug controls available. Type "InnovationDebug.help()" for info.');
  }
}

export default {};
