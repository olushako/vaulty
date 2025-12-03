/**
 * Date formatting utilities
 */

/**
 * Formats a date string to a localized date format
 */
export const formatDate = (dateString: string, options?: Intl.DateTimeFormatOptions): string => {
  const date = new Date(dateString);
  const defaultOptions: Intl.DateTimeFormatOptions = {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  };
  return date.toLocaleDateString('en-US', options || defaultOptions);
};

/**
 * Formats a date string to a full date and time format
 */
export const formatDateTime = (dateString: string): string => {
  const date = new Date(dateString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
};

/**
 * Formats a date string to a relative time (e.g., "2 hours ago")
 * Assumes the date string from the backend is in UTC (without timezone info)
 */
export const formatRelativeTime = (dateString: string): string => {
  // If the date string doesn't have timezone info, treat it as UTC
  // Backend sends dates in UTC format like "2025-11-21T15:41:37.498643"
  let dateStr = dateString.trim();
  
  // Check if it has timezone info (ends with Z, or has +/- with timezone offset)
  const hasTimezone = dateStr.endsWith('Z') || 
                      /[+-]\d{2}:\d{2}$/.test(dateStr) || 
                      /[+-]\d{4}$/.test(dateStr);
  
  if (!hasTimezone) {
    // No timezone indicator, assume UTC and append 'Z'
    dateStr = dateStr + 'Z';
  }
  
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);
  const diffMonths = Math.floor(diffDays / 30);
  const diffYears = Math.floor(diffDays / 365);

  if (diffSeconds < 60) return 'just now';
  if (diffMinutes < 60) return `${diffMinutes} ${diffMinutes === 1 ? 'minute' : 'minutes'} ago`;
  if (diffHours < 24) return `${diffHours} ${diffHours === 1 ? 'hour' : 'hours'} ago`;
  if (diffDays < 30) return `${diffDays} ${diffDays === 1 ? 'day' : 'days'} ago`;
  if (diffMonths < 12) return `${diffMonths} ${diffMonths === 1 ? 'month' : 'months'} ago`;
  return `${diffYears} ${diffYears === 1 ? 'year' : 'years'} ago`;
};

