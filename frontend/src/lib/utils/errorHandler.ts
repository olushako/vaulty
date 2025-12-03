/**
 * Centralized error handling utilities
 */

export interface ApiError {
  response?: {
    data?: {
      detail?: string;
    };
  };
  message?: string;
}

/**
 * Extracts a user-friendly error message from an API error
 */
export const extractErrorMessage = (error: unknown, defaultMessage: string = 'An error occurred'): string => {
  if (typeof error === 'object' && error !== null) {
    const apiError = error as ApiError;
    if (apiError.response?.data?.detail) {
      return apiError.response.data.detail;
    }
    if (apiError.message) {
      return apiError.message;
    }
  }
  if (typeof error === 'string') {
    return error;
  }
  return defaultMessage;
};

/**
 * Logs an error to the console with context
 */
export const logError = (error: unknown, context?: string): void => {
  const message = extractErrorMessage(error, 'Unknown error');
  if (context) {
    console.error(`[${context}]`, message, error);
  } else {
    console.error(message, error);
  }
};

