/**
 * Application constants
 */

// Time constants (in milliseconds)
export const TIME = {
  SECOND: 1000,
  MINUTE: 60 * 1000,
  HOUR: 60 * 60 * 1000,
  DAY: 24 * 60 * 60 * 1000,
} as const;

// Cache expiration
export const CACHE_EXPIRATION_MS = 3 * TIME.HOUR; // 3 hours

// Activity limits
export const ACTIVITY_LIMIT = 100;
export const ACTIVITY_DEFAULT_LIMIT = 25;

// Refresh intervals
export const REFRESH_INTERVAL_MS = 60 * TIME.SECOND; // 60 seconds
export const TOKEN_CHECK_INTERVAL_MS = 5 * TIME.MINUTE; // 5 minutes

// Toast notification duration
export const TOAST_DURATION_MS = 3000; // 3 seconds

