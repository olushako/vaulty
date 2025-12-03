import { useEffect, useState } from 'react';
import { masterTokenApi } from '../lib/api';
import { Plus, Copy, Trash2, Check, Shield } from 'lucide-react';
import type { MasterToken } from '../types';
import { useToastContext } from '../contexts/ToastContext';
import { useClipboard } from '../hooks/useClipboard';
import { extractErrorMessage, logError } from '../lib/utils/errorHandler';
import { formatRelativeTime, formatDateTime } from '../lib/utils/dateFormat';
import { REFRESH_INTERVAL_MS } from '../lib/utils/constants';
import { LoadingSpinner } from '../components/LoadingSpinner';

const MasterTokens = () => {
  const toast = useToastContext();
  const { copied, copyToClipboard } = useClipboard();
  const [tokens, setTokens] = useState<MasterToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [, setNow] = useState(new Date()); // Force re-render for time updates

  useEffect(() => {
    loadTokens();
  }, []);

  // Refresh tokens when page becomes visible (user comes back to tab)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        loadTokens();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  // Update time periodically to refresh relative time displays and reload tokens
  useEffect(() => {
    const interval = setInterval(() => {
      setNow(new Date());
      // Reload tokens to get updated last_used timestamps
      loadTokens();
    }, REFRESH_INTERVAL_MS);

    return () => clearInterval(interval);
  }, []);

  const loadTokens = () => {
    setLoading(true);
    masterTokenApi.list()
      .then(setTokens)
      .catch((error) => logError(error, 'MasterTokens: Load'))
      .finally(() => setLoading(false));
  };

  const handleCreate = async () => {
    try {
      // Name will be auto-generated from token value on backend
      const token = await masterTokenApi.create({ name: '' });
      const tokenValue = token.token;
      if (tokenValue) {
        // Copy token to clipboard automatically
        await handleCopy(tokenValue);
        toast.success('Master token created and copied to clipboard!');
      } else {
        toast.success('Master token created successfully');
      }
      loadTokens();
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to create master token');
      toast.error(message);
    }
  };

  const handleRevoke = async (id: string) => {
    const token = tokens.find(t => t.id === id);
    if (token?.is_current_token) {
      toast.error('Cannot revoke the token you are currently using. Please use a different token to revoke this one.');
      return;
    }
    if (!confirm('Are you sure you want to revoke this master token? It will be removed from the list.')) return;
    try {
      await masterTokenApi.revoke(id);
      // Remove from list immediately - backend now only returns active tokens
      setTokens(prevTokens => prevTokens.filter(token => token.id !== id));
      toast.success('Master token revoked successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to revoke token');
      toast.error(message);
      loadTokens(); // Reload on error to sync state
    }
  };

  const handleCopy = async (text: string) => {
    const success = await copyToClipboard(text);
    if (success) {
      toast.success('Copied to clipboard!');
    } else {
      toast.error('Failed to copy to clipboard');
    }
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Master Tokens</h2>
        <div className="text-xs text-gray-400 dark:text-gray-500">
          {tokens.length} token{tokens.length !== 1 ? 's' : ''}
        </div>
        <button
          onClick={() => handleCreate()}
          className="btn btn-primary flex items-center gap-2 text-sm py-1.5 px-3"
        >
          <Plus className="w-3.5 h-3.5" />
          Create Token
        </button>
      </div>

      <div className="card">
        {tokens.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-500 dark:text-gray-400">No master tokens yet. Create your first master token.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {tokens.map((token) => (
              <div key={token.id} className="px-3 py-1 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-xs font-mono text-gray-900 dark:text-gray-100">
                    {token.name}
                  </span>
                  {token.is_current_token && (
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 border border-blue-200 dark:border-blue-800">
                      <Check className="w-3 h-3" />
                      Current Token
                    </span>
                  )}
                  {token.is_init_token && (
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 border border-yellow-200 dark:border-yellow-800">
                      <Shield className="w-3 h-3" />
                      Initial Token
                    </span>
                  )}
                  <span className="text-xs text-gray-400 dark:text-gray-500">
                    Created {formatDateTime(token.created_at)}
                  </span>
                  {token.last_used && (
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      Last used {formatRelativeTime(token.last_used)}
                    </span>
                  )}
                  <button
                    onClick={() => handleRevoke(token.id)}
                    disabled={token.is_current_token}
                    className={`p-1.5 rounded transition-colors ml-auto ${
                      token.is_current_token
                        ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed opacity-50'
                        : 'text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20'
                    }`}
                    title={token.is_current_token ? "Cannot revoke the token you are currently using. Please use a different token to revoke this one." : "Revoke and remove token"}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default MasterTokens;


