import { useState, useCallback } from 'react';

/**
 * Hook for managing loading state
 */
export const useLoading = (initialState: boolean = false) => {
  const [loading, setLoading] = useState(initialState);

  const startLoading = useCallback(() => setLoading(true), []);
  const stopLoading = useCallback(() => setLoading(false), []);
  const withLoading = useCallback(async <T,>(asyncFn: () => Promise<T>): Promise<T> => {
    try {
      setLoading(true);
      return await asyncFn();
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, startLoading, stopLoading, withLoading };
};

