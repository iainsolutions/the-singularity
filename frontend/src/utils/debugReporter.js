/**
 * Centralized debugging and validation utility for frontend field name normalization
 * Provides structured logging and error reporting without breaking functionality
 */

class DebugReporter {
  constructor() {
    this.reports = [];
    this.maxReports = 100; // Prevent memory leaks
  }

  /**
   * Report field name normalization events
   */
  reportFieldNormalization(event) {
    const report = {
      type: 'field_normalization',
      timestamp: new Date().toISOString(),
      ...event
    };

    this.addReport(report);

    // Log with appropriate level
    if (event.severity === 'error') {
      console.error('🚨 [DebugReporter] Field normalization error:', event);
    } else if (event.severity === 'warning') {
      console.warn('⚠️ [DebugReporter] Field normalization warning:', event);
    } else {
      console.debug('🔍 [DebugReporter] Field normalization:', event);
    }
  }

  /**
   * Report card interaction validation
   */
  reportCardInteraction(event) {
    const report = {
      type: 'card_interaction',
      timestamp: new Date().toISOString(),
      ...event
    };

    this.addReport(report);

    if (event.severity === 'error') {
      console.error('💥 [DebugReporter] Card interaction error:', event);
    } else if (event.severity === 'warning') {
      console.warn('⚠️ [DebugReporter] Card interaction warning:', event);
    } else {
      console.debug('🎯 [DebugReporter] Card interaction:', event);
    }
  }

  /**
   * Report synchronization issues between state sources
   */
  reportSynchronization(event) {
    const report = {
      type: 'synchronization',
      timestamp: new Date().toISOString(),
      ...event
    };

    this.addReport(report);

    if (event.severity === 'error') {
      console.error('🔄 [DebugReporter] Synchronization error:', event);
    } else if (event.severity === 'warning') {
      console.warn('⚠️ [DebugReporter] Synchronization warning:', event);
    } else {
      console.debug('🔄 [DebugReporter] Synchronization:', event);
    }
  }

  /**
   * Report validation failures with context
   */
  reportValidation(event) {
    const report = {
      type: 'validation',
      timestamp: new Date().toISOString(),
      ...event
    };

    this.addReport(report);

    if (event.severity === 'error') {
      console.error('❌ [DebugReporter] Validation error:', event);
    } else if (event.severity === 'warning') {
      console.warn('⚠️ [DebugReporter] Validation warning:', event);
    } else {
      console.debug('✅ [DebugReporter] Validation:', event);
    }
  }

  /**
   * Add report to internal storage
   */
  addReport(report) {
    this.reports.push(report);

    // Trim old reports to prevent memory leaks
    if (this.reports.length > this.maxReports) {
      this.reports = this.reports.slice(-this.maxReports);
    }
  }

  /**
   * Get recent reports for debugging
   */
  getReports(type = null, limit = 20) {
    let filtered = this.reports;

    if (type) {
      filtered = this.reports.filter(r => r.type === type);
    }

    return filtered.slice(-limit);
  }

  /**
   * Generate summary report for debugging
   */
  generateSummary() {
    const summary = {
      totalReports: this.reports.length,
      byType: {},
      bySeverity: {},
      recentIssues: []
    };

    // Count by type and severity
    this.reports.forEach(report => {
      summary.byType[report.type] = (summary.byType[report.type] || 0) + 1;
      summary.bySeverity[report.severity] = (summary.bySeverity[report.severity] || 0) + 1;

      // Collect recent errors and warnings
      if ((report.severity === 'error' || report.severity === 'warning') &&
          summary.recentIssues.length < 10) {
        summary.recentIssues.push({
          type: report.type,
          severity: report.severity,
          message: report.message,
          timestamp: report.timestamp
        });
      }
    });

    return summary;
  }

  /**
   * Clear all reports
   */
  clear() {
    this.reports = [];
  }

  /**
   * Export reports for external analysis
   */
  export() {
    return {
      timestamp: new Date().toISOString(),
      summary: this.generateSummary(),
      reports: this.reports
    };
  }
}

// Create singleton instance
const debugReporter = new DebugReporter();

// Expose to window for console access
if (typeof window !== 'undefined') {
  window.SingularityDebugReporter = debugReporter;
}

export default debugReporter;

// Convenience functions for common reporting patterns
export const reportFieldNormalization = (details) => {
  debugReporter.reportFieldNormalization({
    severity: 'debug',
    ...details
  });
};

export const reportFieldNormalizationWarning = (details) => {
  debugReporter.reportFieldNormalization({
    severity: 'warning',
    ...details
  });
};

export const reportFieldNormalizationError = (details) => {
  debugReporter.reportFieldNormalization({
    severity: 'error',
    ...details
  });
};

export const reportCardInteraction = (details) => {
  debugReporter.reportCardInteraction({
    severity: 'debug',
    ...details
  });
};

export const reportCardInteractionWarning = (details) => {
  debugReporter.reportCardInteraction({
    severity: 'warning',
    ...details
  });
};

export const reportCardInteractionError = (details) => {
  debugReporter.reportCardInteraction({
    severity: 'error',
    ...details
  });
};

export const reportSynchronization = (details) => {
  debugReporter.reportSynchronization({
    severity: 'debug',
    ...details
  });
};

export const reportSynchronizationWarning = (details) => {
  debugReporter.reportSynchronization({
    severity: 'warning',
    ...details
  });
};

export const reportValidation = (details) => {
  debugReporter.reportValidation({
    severity: 'debug',
    ...details
  });
};

export const reportValidationWarning = (details) => {
  debugReporter.reportValidation({
    severity: 'warning',
    ...details
  });
};

export const reportValidationError = (details) => {
  debugReporter.reportValidation({
    severity: 'error',
    ...details
  });
};