/**
 * Structured logger for frontend with environment-aware debug output
 * Reduces console noise in production while maintaining debugging capabilities
 */

// Get debug mode from environment or localStorage
const getDebugMode = () => {
  // Check environment variable (set at build time)
  if (import.meta.env.VITE_DEBUG === "true") {
    return true;
  }

  // Check localStorage for runtime debug toggle
  if (typeof window !== "undefined" && window.localStorage) {
    return window.localStorage.getItem("INNOVATION_DEBUG") === "true";
  }

  // Default to false in production, true in development
  return import.meta.env.MODE === "development";
};

// Log levels
const LogLevel = {
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3,
  NONE: 4,
};

// Get current log level
const getLogLevel = () => {
  const level =
    import.meta.env.VITE_LOG_LEVEL || (import.meta.env.MODE === "production" ? "WARN" : "INFO");
  return LogLevel[level.toUpperCase()] || LogLevel.INFO;
};

class Logger {
  constructor(module) {
    this.module = module;
    this.debugEnabled = getDebugMode();
    this.logLevel = getLogLevel();
  }

  /**
   * Format log message with timestamp and module
   */
  formatMessage(level, message, ...args) {
    const timestamp = new Date().toISOString();
    const prefix = `[${timestamp}] [${this.module}] [${level}]`;
    return [prefix, message, ...args];
  }

  /**
   * Check if should log based on level
   */
  shouldLog(level) {
    return level >= this.logLevel;
  }

  debug(message, ...args) {
    if (this.debugEnabled && this.shouldLog(LogLevel.DEBUG)) {
      console.log(...this.formatMessage("DEBUG", message, ...args));
    }
  }

  info(message, ...args) {
    if (this.shouldLog(LogLevel.INFO)) {
      console.info(...this.formatMessage("INFO", message, ...args));
    }
  }

  warn(message, ...args) {
    if (this.shouldLog(LogLevel.WARN)) {
      console.warn(...this.formatMessage("WARN", message, ...args));
    }
  }

  error(message, ...args) {
    if (this.shouldLog(LogLevel.ERROR)) {
      console.error(...this.formatMessage("ERROR", message, ...args));
    }
  }

  /**
   * Group related logs together (useful for complex operations)
   */
  group(label) {
    if (this.debugEnabled) {
      console.group(`[${this.module}] ${label}`);
    }
  }

  groupEnd() {
    if (this.debugEnabled) {
      console.groupEnd();
    }
  }

  /**
   * Log performance metrics
   */
  time(label) {
    if (this.debugEnabled) {
      console.time(`[${this.module}] ${label}`);
    }
  }

  timeEnd(label) {
    if (this.debugEnabled) {
      console.timeEnd(`[${this.module}] ${label}`);
    }
  }

  /**
   * Log structured data (useful for tracking state changes)
   */
  table(data) {
    if (this.debugEnabled && this.shouldLog(LogLevel.DEBUG)) {
      console.table(data);
    }
  }

  /**
   * Enable/disable debug mode at runtime
   */
  static enableDebug() {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem("INNOVATION_DEBUG", "true");
      window.location.reload();
    }
  }

  static disableDebug() {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.removeItem("INNOVATION_DEBUG");
      window.location.reload();
    }
  }

  /**
   * Get current debug status
   */
  static isDebugEnabled() {
    return getDebugMode();
  }
}

/**
 * Factory function to create a logger for a specific module
 */
export function createLogger(module) {
  return new Logger(module);
}

/**
 * WebSocket-specific logger with additional utilities
 */
export class WebSocketLogger extends Logger {
  constructor() {
    super("WebSocket");
  }

  logConnection(url) {
    this.debug("Connecting to:", url.replace(/token=[^&]*/, "token=***"));
  }

  logMessage(type, data) {
    if (this.debugEnabled) {
      this.group(`Message: ${type}`);
      this.debug("Payload:", data);
      this.groupEnd();
    }
  }

  logError(error, context) {
    this.error(`Error in ${context}:`, error);
  }

  logReconnection(attempt, max) {
    this.info(`Reconnection attempt ${attempt}/${max}`);
  }
}

// Export utility functions for global debug control
export const enableDebug = Logger.enableDebug;
export const disableDebug = Logger.disableDebug;
export const isDebugEnabled = Logger.isDebugEnabled;

// Create default logger instance
const defaultLogger = new Logger("App");
export default defaultLogger;
