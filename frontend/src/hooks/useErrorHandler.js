import { useState, useCallback } from "react";

/**
 * Custom hook for handling errors in functional components
 * Provides error state management and error handling utilities
 */
export function useErrorHandler() {
  const [error, setError] = useState(null);
  const [isError, setIsError] = useState(false);

  const resetError = useCallback(() => {
    setError(null);
    setIsError(false);
  }, []);

  const handleError = useCallback((error) => {
    console.error("Error caught by useErrorHandler:", error);
    setError(error);
    setIsError(true);

    // You could also log to an error reporting service here
    // logErrorToService(error);
  }, []);

  const wrapAsync = useCallback(
    (asyncFunction) => {
      return async (...args) => {
        try {
          const result = await asyncFunction(...args);
          return result;
        } catch (error) {
          handleError(error);
          throw error; // Re-throw to allow caller to handle if needed
        }
      };
    },
    [handleError],
  );

  return {
    error,
    isError,
    resetError,
    handleError,
    wrapAsync,
  };
}

/**
 * Higher-order component to wrap async operations with error handling
 */
export function withErrorHandling(asyncOperation, errorHandler) {
  return async (...args) => {
    try {
      return await asyncOperation(...args);
    } catch (error) {
      if (errorHandler) {
        errorHandler(error);
      } else {
        console.error("Unhandled error in async operation:", error);
      }
      throw error;
    }
  };
}
