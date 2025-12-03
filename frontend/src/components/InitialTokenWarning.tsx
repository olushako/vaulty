import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AlertTriangle, Shield } from 'lucide-react';
import { masterTokenApi } from '../lib/api';
import { logError } from '../lib/utils/errorHandler';
import { REFRESH_INTERVAL_MS } from '../lib/utils/constants';

const InitialTokenWarning = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [hasInitialToken, setHasInitialToken] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check if user is on the master tokens settings page
  const isOnMasterTokensPage = location.pathname === '/settings' && 
    new URLSearchParams(location.search).get('tab') === 'master-tokens';

  const checkInitialToken = async () => {
    try {
      const tokens = await masterTokenApi.list();
      // Check if any token has is_init_token flag set to true
      // If no initial tokens exist, hasInitial will be false and warning won't show
      const hasInitial = tokens.some(token => token.is_init_token === true);
      setHasInitialToken(hasInitial);
    } catch (error) {
      // If we can't check (e.g., not authenticated), assume no warning needed
      logError(error, 'InitialTokenWarning: Check');
      setHasInitialToken(false);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Check immediately
    checkInitialToken();

    // Check periodically to detect when initial token is removed
    const interval = setInterval(() => {
      checkInitialToken();
    }, REFRESH_INTERVAL_MS);

    return () => clearInterval(interval);
  }, []);

  // Don't show anything while loading, if no initial token, or if user is on master tokens page
  if (isLoading || !hasInitialToken || isOnMasterTokensPage) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full mx-4 p-6 border-2 border-red-500">
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0">
            <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-red-600 dark:text-red-400" />
            </div>
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <Shield className="w-5 h-5" />
                Security Warning: Default Master Token Detected
              </h2>
            </div>
            <div className="space-y-3 text-gray-700 dark:text-gray-300">
              <p className="text-sm">
                Your Vaulty instance is using the default master token from the <code className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs font-mono">MASTER_TOKEN</code> environment variable.
              </p>
              <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3">
                <p className="text-sm font-medium text-yellow-900 dark:text-yellow-100 mb-1">
                  ⚠️ This is a security risk in production!
                </p>
                <ul className="text-xs text-yellow-800 dark:text-yellow-200 list-disc list-inside space-y-1">
                  <li>The default token is predictable and can be compromised</li>
                  <li>Anyone with access to your environment variables can access your secrets</li>
                  <li>This warning will persist until you remove the initial token</li>
                </ul>
              </div>
              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
                <p className="text-sm font-medium text-blue-900 dark:text-blue-100 mb-1">
                  📋 What to do:
                </p>
                <ol className="text-xs text-blue-800 dark:text-blue-200 list-decimal list-inside space-y-1">
                  <li>Go to <strong>Settings → Master Tokens</strong></li>
                  <li>Create a new master token</li>
                  <li>Revoke the initial token (marked with "initial" indicator)</li>
                  <li>Update your <code className="px-1 py-0.5 bg-blue-100 dark:bg-blue-800 rounded text-xs font-mono">MASTER_TOKEN</code> environment variable with the new token</li>
                  <li>Restart your server</li>
                </ol>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 italic">
                This warning will automatically disappear once the initial token is removed.
              </p>
            </div>
            <div className="mt-6 flex justify-end">
              <button
                onClick={() => navigate('/settings?tab=master-tokens')}
                className="btn btn-primary px-6 py-2 text-sm font-medium"
              >
                Go to Master Tokens
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InitialTokenWarning;

