/**
 * Debug control utilities for browser console
 * Allows runtime control of debug logging without rebuilding
 */

import { enableDebug, disableDebug, isDebugEnabled } from "./logger";

// Expose debug control to window object for browser console access
if (typeof window !== "undefined") {
  window.SingularityDebug = {
    /**
     * Enable debug logging
     * Usage: SingularityDebug.enable()
     */
    enable: () => {
      enableDebug();
      console.log("🔍 Debug mode enabled. Page will reload...");
    },

    /**
     * Disable debug logging
     * Usage: SingularityDebug.disable()
     */
    disable: () => {
      disableDebug();
      console.log("🔕 Debug mode disabled. Page will reload...");
    },

    /**
     * Check current debug status
     * Usage: SingularityDebug.status()
     */
    status: () => {
      const enabled = isDebugEnabled();
      console.log(`Debug mode is ${enabled ? "✅ ENABLED" : "❌ DISABLED"}`);
      return enabled;
    },

    /**
     * Help information
     * Usage: SingularityDebug.help()
     */
    help: () => {
      console.log(`
🎮 The Singularity Debug Control
=================================
Available commands:
  SingularityDebug.enable()  - Turn on debug logging
  SingularityDebug.disable() - Turn off debug logging
  SingularityDebug.status()  - Check current status
  SingularityDebug.help()    - Show this help

Debug mode persists across page reloads until disabled.
      `);
    },
  };

  // Show status on initial load in development
  if (import.meta.env.MODE === "development") {
    console.log('💡 Debug controls available. Type "SingularityDebug.help()" for info.');
  }
}

export default {};
