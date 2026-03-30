/**
 * Centralized configuration for API and WebSocket endpoints.
 *
 * This utility ensures consistent access to environment variables across
 * the application, supporting both build-time (Vite) and runtime configuration.
 *
 * Environment Variables:
 * - VITE_API_BASE: Base URL for HTTP API calls (default: http://localhost:8000)
 * - VITE_WS_BASE: Base URL for WebSocket connections (default: derived from API_BASE)
 *
 * Runtime Configuration (via window object):
 * - window.RUNTIME_CONFIG.API_BASE: Override for API base URL
 * - window.RUNTIME_CONFIG.WS_BASE: Override for WebSocket base URL
 */

/**
 * Get the API base URL.
 * Checks runtime config first, then falls back to build-time env vars.
 *
 * @returns {string} The API base URL
 */
export function getApiBase() {
  // Check runtime config (for production deployments)
  if (typeof window !== "undefined" && window.RUNTIME_CONFIG?.API_BASE) {
    return window.RUNTIME_CONFIG.API_BASE;
  }

  // Fall back to Vite build-time env vars
  return import.meta.env.VITE_API_BASE || "http://localhost:8000";
}

/**
 * Get the WebSocket base URL.
 * Checks runtime config first, then falls back to build-time env vars,
 * and finally derives from API base URL if not set.
 *
 * @returns {string} The WebSocket base URL
 */
export function getWsBase() {
  // Check runtime config (for production deployments)
  if (typeof window !== "undefined" && window.RUNTIME_CONFIG?.WS_BASE) {
    return window.RUNTIME_CONFIG.WS_BASE;
  }

  // Fall back to Vite build-time env vars
  if (import.meta.env.VITE_WS_BASE) {
    return import.meta.env.VITE_WS_BASE;
  }

  // Derive from API base URL (http -> ws, https -> wss)
  const apiBase = getApiBase();
  return apiBase.replace(/^http/, "ws");
}

/**
 * Get all configuration values.
 *
 * @returns {object} Configuration object with API_BASE and WS_BASE
 */
export function getConfig() {
  return {
    API_BASE: getApiBase(),
    WS_BASE: getWsBase(),
  };
}
