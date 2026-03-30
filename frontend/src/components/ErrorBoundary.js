import React from "react";
import styles from "./ErrorBoundary.module.css";
import { createLogger } from "../utils/logger";

const logger = createLogger("ErrorBoundary");

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0,
    };
    this.handleReset = this.handleReset.bind(this);
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI.
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log error to console in development
    console.error("ErrorBoundary caught an error:", error, errorInfo);

    // Log to our custom logger with full details
    logger.error("Component tree crash detected", {
      error: error.toString(),
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      props: this.props.name || "Unknown",
      errorCount: this.state.errorCount + 1,
    });

    // Update state with error details
    this.setState((prevState) => ({
      error,
      errorInfo,
      errorCount: prevState.errorCount + 1,
    }));

    // You could also log the error to an error reporting service here
    // logErrorToService(error, errorInfo);
  }

  handleReset() {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  }

  render() {
    if (this.state.hasError) {
      // Custom fallback UI
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.handleReset);
      }

      // Default fallback UI
      return (
        <div className={styles.errorBoundary}>
          <div className={styles.errorBoundary__content}>
            <h2 className={styles.errorBoundary__title}>Something went wrong</h2>
            <p className={styles.errorBoundary__message}>
              {this.props.message ||
                "An unexpected error occurred. Please try refreshing the page."}
            </p>

            {import.meta.env.MODE === "development" && this.state.error && (
              <details className={styles.errorBoundary__details}>
                <summary>Error Details (Development Only)</summary>
                <pre className={styles.errorBoundary__stack}>
                  {this.state.error.toString()}
                  {this.state.errorInfo && this.state.errorInfo.componentStack}
                </pre>
              </details>
            )}

            <div className={styles.errorBoundary__actions}>
              <button onClick={this.handleReset} className={styles.errorBoundary__button}>
                Try Again
              </button>
              <button
                onClick={() => window.location.reload()}
                className={`${styles.errorBoundary__button} ${styles.errorBoundary__buttonSecondary}`}
              >
                Refresh Page
              </button>
            </div>

            {this.state.errorCount > 2 && (
              <p className={styles.errorBoundary__warning}>
                Multiple errors detected. If the problem persists, please contact support.
              </p>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
