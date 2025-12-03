import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Settings as SettingsIcon, Shield, Database, Key, Plus, Copy, Trash2, Check, Activity } from 'lucide-react';
import { masterTokenApi, databaseApi } from '../lib/api';
import { getAuthToken } from '../lib/api';
import type { MasterToken } from '../types';
import { useToastContext } from '../contexts/ToastContext';
import { useClipboard } from '../hooks/useClipboard';
import { extractErrorMessage, logError } from '../lib/utils/errorHandler';
import { REFRESH_INTERVAL_MS } from '../lib/utils/constants';
import { formatRelativeTime } from '../lib/utils/dateFormat';

type TabType = 'status' | 'security' | 'database' | 'master-tokens';

const Settings = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab') as TabType | null;
  const [activeTab, setActiveTab] = useState<TabType>(
    tabFromUrl && ['status', 'security', 'database', 'master-tokens'].includes(tabFromUrl)
      ? tabFromUrl
      : 'status'
  );

  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab);
    setSearchParams({ tab }, { replace: true });
  };

  // Sync tab from URL on mount or when URL changes
  useEffect(() => {
    const tabFromUrl = searchParams.get('tab') as TabType | null;
    if (tabFromUrl && ['status', 'security', 'database', 'master-tokens'].includes(tabFromUrl)) {
      setActiveTab(tabFromUrl);
    }
  }, [searchParams]);
  
  // Master Tokens state
  const toast = useToastContext();
  const { copied, copyToClipboard } = useClipboard();
  const [tokens, setTokens] = useState<MasterToken[]>([]);
  const [tokensLoading, setTokensLoading] = useState(false);
  const [, setNow] = useState(new Date()); // Force re-render for relative time updates
  
  // Database info state
  const [dbInfo, setDbInfo] = useState<{
    type: string;
    location: string;
    filename: string;
    directory: string;
    size_bytes: number;
    size_formatted: string;
    exists: boolean;
    integrity?: {
      status: string;
      ok: boolean;
      details?: string;
    };
  } | null>(null);
  const [dbInfoLoading, setDbInfoLoading] = useState(false);

  // System status state
  const [systemStatus, setSystemStatus] = useState<{
    database: {
      operational: boolean;
      details: string | null;
      error: string | null;
    };
    api: {
      operational: boolean;
      details: string | null;
      error: string | null;
    };
    mcp: {
      operational: boolean;
      port: number;
      details: string | null;
      error: string | null;
    };
    endpoints: {
      operational: boolean;
      checked: Array<{
        endpoint: string;
        method: string;
        description: string;
        operational: boolean;
        error?: string;
      }>;
      errors: string[];
      details: string;
    };
  } | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  // Load master tokens when master-tokens tab is active
  useEffect(() => {
    if (activeTab === 'master-tokens') {
      loadTokens();
    }
  }, [activeTab]);
  
  // Load database info when database tab is active
  useEffect(() => {
    if (activeTab === 'database') {
      loadDatabaseInfo();
    }
  }, [activeTab]);

  // Load system status when status tab is active
  useEffect(() => {
    if (activeTab === 'status') {
      loadSystemStatus();
    }
  }, [activeTab]);

  // Refresh status periodically when on status tab
  useEffect(() => {
    if (activeTab !== 'status') return;
    
    const interval = setInterval(() => {
      loadSystemStatus();
    }, REFRESH_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [activeTab]);

  // Refresh tokens periodically when on master-tokens tab
  useEffect(() => {
    if (activeTab !== 'master-tokens') return;
    
    const interval = setInterval(() => {
      loadTokens();
    }, REFRESH_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [activeTab]);

  // Update time periodically to refresh relative time displays
  useEffect(() => {
    const interval = setInterval(() => {
      setNow(new Date());
    }, 60000); // Update every minute for relative time

    return () => clearInterval(interval);
  }, []);

  const loadTokens = () => {
    setTokensLoading(true);
    masterTokenApi.list()
      .then(setTokens)
      .catch((error) => logError(error, 'Settings: Load tokens'))
      .finally(() => setTokensLoading(false));
  };
  
  const loadDatabaseInfo = () => {
    setDbInfoLoading(true);
    databaseApi.getInfo()
      .then(setDbInfo)
      .catch((error) => logError(error, 'Settings: Load database info'))
      .finally(() => setDbInfoLoading(false));
  };

  const loadSystemStatus = async () => {
    setStatusLoading(true);
    
    // Helper function to create a timeout promise
    const timeoutPromise = (ms: number) => new Promise((_, reject) => 
      setTimeout(() => reject(new Error('Request timeout')), ms)
    );

    // Helper function to fetch with timeout
    const fetchWithTimeout = async (url: string, options: RequestInit = {}, timeoutMs: number = 3000) => {
      return Promise.race([
        fetch(url, options),
        timeoutPromise(timeoutMs) as Promise<Response>
      ]);
    };
    
    const status: typeof systemStatus = {
      database: {
        operational: false,
        details: null,
        error: null
      },
      api: {
        operational: false,
        details: null,
        error: null
      },
      mcp: {
        operational: false,
        port: 9000, // Default MCP port
        details: null,
        error: null
      },
      endpoints: {
        operational: false,
        checked: [],
        errors: [],
        details: ''
      }
    };

    // Check API Server
    try {
      const response = await fetchWithTimeout('/api/auth/me', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${getAuthToken() || ''}`
        }
      }, 3000);
      
      if (response.ok || response.status === 401) {
        // 401 is OK - it means API is responding, just not authenticated
        status.api.operational = true;
        status.api.details = 'API server is responding';
      } else {
        status.api.error = `API returned status ${response.status}`;
      }
    } catch (error: any) {
      status.api.error = error.message || 'Could not connect to API server';
    }

    // Check Database (only if API is operational)
    if (status.api.operational) {
      try {
        const dbInfo = await databaseApi.getInfo();
        status.database.operational = dbInfo.exists && (dbInfo.integrity?.ok ?? false);
        status.database.details = dbInfo.integrity?.ok 
          ? 'Database is accessible and healthy'
          : `Database integrity: ${dbInfo.integrity?.status || 'unknown'}`;
        if (!status.database.operational && dbInfo.integrity?.details) {
          status.database.error = dbInfo.integrity.details;
        }
      } catch (error: any) {
        status.database.error = error.message || 'Could not check database status';
      }
    } else {
      status.database.error = 'Cannot check database - API is not operational';
    }

    // Check MCP Server directly (independent of API)
    const mcpPort = 9000; // Default MCP port
    status.mcp.port = mcpPort;
    
    try {
      const mcpUrl = `http://localhost:${mcpPort}/mcp/sse`;
      
      // Try to connect to MCP server - use AbortController for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000); // 2 second timeout
      
      try {
        const response = await fetch(mcpUrl, {
          method: 'GET',
          signal: controller.signal,
          headers: {
            'Accept': 'text/event-stream'
          }
        });
        
        clearTimeout(timeoutId);
        
        // SSE endpoints may return 200, 404, or 405 - any response means server is up
        if (response.status === 200 || response.status === 404 || response.status === 405) {
          status.mcp.operational = true;
          status.mcp.details = `MCP server is responding on port ${mcpPort}`;
        } else {
          status.mcp.error = `MCP server returned status ${response.status}`;
        }
      } catch (fetchError: any) {
        clearTimeout(timeoutId);
        
        // If it's an abort error, it means timeout
        if (fetchError.name === 'AbortError') {
          status.mcp.error = `MCP server connection timeout on port ${mcpPort}`;
        } else if (fetchError.message?.includes('Failed to fetch') || fetchError.message?.includes('NetworkError')) {
          // Connection refused or CORS issue - but we can still detect if port is open
          // For now, mark as not operational
          status.mcp.error = `Could not connect to MCP server on port ${mcpPort} (connection refused or CORS issue)`;
        } else {
          status.mcp.error = fetchError.message || `Could not connect to MCP server on port ${mcpPort}`;
        }
      }
    } catch (error: any) {
      status.mcp.error = error.message || `Could not check MCP server on port ${mcpPort}`;
    }

    // Check Endpoints via API (get the full list from backend)
    if (status.api.operational) {
      try {
        const statusResponse = await fetchWithTimeout('/api/auth/status', {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${getAuthToken() || ''}`
          }
        }, 3000);
        
        if (statusResponse.ok) {
          const statusData = await statusResponse.json();
          if (statusData.endpoints) {
            status.endpoints.operational = statusData.endpoints.operational || false;
            status.endpoints.checked = statusData.endpoints.checked || [];
            status.endpoints.errors = statusData.endpoints.errors || [];
            status.endpoints.details = statusData.endpoints.details || '';
          }
        } else {
          status.endpoints.error = `API returned status ${statusResponse.status}`;
        }
      } catch (error: any) {
        status.endpoints.error = error.message || 'Could not check endpoints via API';
      }
    } else {
      status.endpoints.error = 'Cannot check endpoints - API is not operational';
    }

    setSystemStatus(status);
    setStatusLoading(false);
  };

  const handleCreateToken = async () => {
    try {
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

  const handleRevokeToken = async (id: string) => {
    const token = tokens.find(t => t.id === id);
    if (token?.is_current_token) {
      toast.error('Cannot revoke the token you are currently using. Please use a different token to revoke this one.');
      return;
    }
    if (!confirm('Are you sure you want to revoke this master token? It will be removed from the list.')) return;
    try {
      await masterTokenApi.revoke(id);
      setTokens(prevTokens => prevTokens.filter(token => token.id !== id));
      toast.success('Master token revoked successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to revoke token');
      toast.error(message);
      loadTokens();
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

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Settings</h1>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Manage your application settings and preferences
        </p>
      </div>

      {/* Tabs */}
      <div className="mb-6">
        <div className="border-b border-gray-200 dark:border-[#30363d]">
          <nav className="flex gap-1">
            <button
              onClick={() => handleTabChange('status')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'status'
                  ? 'border-[#f0f6fc] text-[#c9d1d9] dark:border-[#f0f6fc] dark:text-[#c9d1d9]'
                  : 'border-transparent text-gray-500 dark:text-[#8b949e] hover:text-gray-700 dark:hover:text-[#c9d1d9] hover:border-gray-300 dark:hover:border-[#30363d]'
              }`}
            >
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4" />
                Status
              </div>
            </button>
            <button
              onClick={() => handleTabChange('security')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'security'
                  ? 'border-[#f0f6fc] text-[#c9d1d9] dark:border-[#f0f6fc] dark:text-[#c9d1d9]'
                  : 'border-transparent text-gray-500 dark:text-[#8b949e] hover:text-gray-700 dark:hover:text-[#c9d1d9] hover:border-gray-300 dark:hover:border-[#30363d]'
              }`}
            >
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4" />
                Security
              </div>
            </button>
            <button
              onClick={() => handleTabChange('database')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'database'
                  ? 'border-[#f0f6fc] text-[#c9d1d9] dark:border-[#f0f6fc] dark:text-[#c9d1d9]'
                  : 'border-transparent text-gray-500 dark:text-[#8b949e] hover:text-gray-700 dark:hover:text-[#c9d1d9] hover:border-gray-300 dark:hover:border-[#30363d]'
              }`}
            >
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4" />
                Database
              </div>
            </button>
            <button
              onClick={() => handleTabChange('master-tokens')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'master-tokens'
                  ? 'border-[#f0f6fc] text-[#c9d1d9] dark:border-[#f0f6fc] dark:text-[#c9d1d9]'
                  : 'border-transparent text-gray-500 dark:text-[#8b949e] hover:text-gray-700 dark:hover:text-[#c9d1d9] hover:border-gray-300 dark:hover:border-[#30363d]'
              }`}
            >
              <div className="flex items-center gap-2">
                <Key className="w-4 h-4" />
                Master Tokens
              </div>
            </button>
          </nav>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'master-tokens' ? (
        <>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Master Tokens</h2>
            <div className="text-xs text-gray-400 dark:text-gray-500">
              {tokens.length} token{tokens.length !== 1 ? 's' : ''}
            </div>
            <button
              onClick={handleCreateToken}
              className="btn btn-primary flex items-center gap-2 text-sm py-1.5 px-3"
            >
              <Plus className="w-3.5 h-3.5" />
              Create Token
            </button>
          </div>

          <div className="card">
            {tokensLoading ? (
              <div className="p-12 text-center">
                <p className="text-gray-500 dark:text-gray-400">Loading tokens...</p>
              </div>
            ) : tokens.length === 0 ? (
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
                      <div className="flex items-center gap-1 ml-auto" onClick={(e) => e.stopPropagation()}>
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
                          {token.last_used ? `Last used ${formatRelativeTime(token.last_used)}` : 'Never used'}
                        </span>
                        <button
                          onClick={() => handleRevokeToken(token.id)}
                          disabled={token.is_current_token}
                          className={`p-1.5 rounded transition-colors ${
                            token.is_current_token
                              ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed opacity-50'
                              : 'text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20'
                          }`}
                          title={token.is_current_token ? "Cannot revoke the token you are currently using. Please use a different token to revoke this one." : "Revoke token"}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="card">
          {activeTab === 'security' && (
            <div className="p-4 space-y-3">
              <div className="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                <div className="flex items-start gap-2">
                  <Shield className="w-4 h-4 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <h3 className="text-xs font-medium text-blue-900 dark:text-blue-100 mb-1">
                      Security Best Practices
                    </h3>
                    <ul className="text-xs text-blue-800 dark:text-blue-300 space-y-0.5 list-disc list-inside">
                      <li>Rotate master tokens regularly</li>
                      <li>Use project tokens for limited access</li>
                      <li>Never share tokens in plain text</li>
                      <li>Review activity logs regularly</li>
                    </ul>
                  </div>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  Token Cache Duration
                </label>
                <select className="input text-sm py-1.5">
                  <option>3 hours (default)</option>
                  <option>1 hour</option>
                  <option>6 hours</option>
                  <option>12 hours</option>
                  <option>24 hours</option>
                </select>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  How long to cache authentication tokens in the browser
                </p>
              </div>
            </div>
          )}

          {activeTab === 'database' && (
            <div className="p-4 space-y-3">
              <div className="p-3 bg-gray-50 dark:bg-[#161b22] rounded-lg border border-gray-200 dark:border-[#30363d]">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-medium text-gray-700 dark:text-gray-300">Database Type</span>
                  <span className="text-xs text-gray-600 dark:text-gray-400">
                    {dbInfoLoading ? 'Loading...' : (dbInfo?.type || 'SQLite')}
                  </span>
                </div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-medium text-gray-700 dark:text-gray-300">Location</span>
                  <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                    {dbInfoLoading ? 'Loading...' : (dbInfo?.filename || 'vaulty.db')}
                  </span>
                </div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-medium text-gray-700 dark:text-gray-300">Database Size</span>
                  <span className="text-xs text-gray-600 dark:text-gray-400">
                    {dbInfoLoading ? 'Loading...' : (dbInfo?.size_formatted || '-')}
                  </span>
                </div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-medium text-gray-700 dark:text-gray-300">Integrity Status</span>
                  <span className={`text-xs font-medium ${
                    dbInfoLoading 
                      ? 'text-gray-400 dark:text-gray-500' 
                      : dbInfo?.integrity?.ok === true
                      ? 'text-green-600 dark:text-green-400'
                      : dbInfo?.integrity?.status === 'corrupted'
                      ? 'text-red-600 dark:text-red-400'
                      : 'text-yellow-600 dark:text-yellow-400'
                  }`}>
                    {dbInfoLoading 
                      ? 'Checking...' 
                      : dbInfo?.integrity?.ok === true
                      ? '✓ Healthy'
                      : dbInfo?.integrity?.status === 'corrupted'
                      ? '✗ Corrupted'
                      : dbInfo?.integrity?.status === 'error'
                      ? '⚠ Error'
                      : '? Unknown'}
                  </span>
                </div>
                {dbInfo?.integrity?.status === 'corrupted' && dbInfo.integrity.details && (
                  <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-xs text-red-800 dark:text-red-300 font-mono">
                    {dbInfo.integrity.details}
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-700 dark:text-gray-300">Activity Retention</span>
                  <span className="text-xs text-gray-600 dark:text-gray-400">7 days</span>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'status' && (
            <div className="p-4 space-y-1.5">
              {statusLoading ? (
                <div className="p-12 text-center">
                  <p className="text-gray-500 dark:text-gray-400">Loading system status...</p>
                </div>
              ) : systemStatus ? (
                <>
                  {/* Database Status */}
                  <div className="p-2 bg-gray-50 dark:bg-[#161b22] rounded-lg border border-gray-200 dark:border-[#30363d]">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Database className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">Database</span>
                      </div>
                      <span className={`text-xs font-medium ${
                        systemStatus.database.operational
                          ? 'text-green-600 dark:text-green-400'
                          : 'text-red-600 dark:text-red-400'
                      }`}>
                        {systemStatus.database.operational ? (
                          <>
                            <Check className="w-3 h-3 inline mr-1" />
                            Operational
                          </>
                        ) : (
                          <>
                            ✗ Not Operational
                          </>
                        )}
                      </span>
                    </div>
                    {systemStatus.database.details && (
                      <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">{systemStatus.database.details}</p>
                    )}
                    {systemStatus.database.error && (
                      <p className="text-xs text-red-600 dark:text-red-400 mt-0.5">{systemStatus.database.error}</p>
                    )}
                  </div>

                  {/* API Status */}
                  <div className="p-2 bg-gray-50 dark:bg-[#161b22] rounded-lg border border-gray-200 dark:border-[#30363d]">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <SettingsIcon className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">API Server</span>
                      </div>
                      <span className={`text-xs font-medium ${
                        systemStatus.api.operational
                          ? 'text-green-600 dark:text-green-400'
                          : 'text-red-600 dark:text-red-400'
                      }`}>
                        {systemStatus.api.operational ? (
                          <>
                            <Check className="w-3 h-3 inline mr-1" />
                            Operational
                          </>
                        ) : (
                          <>
                            ✗ Not Operational
                          </>
                        )}
                      </span>
                    </div>
                    {systemStatus.api.details && (
                      <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">{systemStatus.api.details}</p>
                    )}
                    {systemStatus.api.error && (
                      <p className="text-xs text-red-600 dark:text-red-400 mt-0.5">{systemStatus.api.error}</p>
                    )}
                  </div>

                  {/* MCP Status */}
                  <div className="p-2 bg-gray-50 dark:bg-[#161b22] rounded-lg border border-gray-200 dark:border-[#30363d]">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Activity className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">MCP Server</span>
                      </div>
                      <span className={`text-xs font-medium ${
                        systemStatus.mcp.operational
                          ? 'text-green-600 dark:text-green-400'
                          : 'text-red-600 dark:text-red-400'
                      }`}>
                        {systemStatus.mcp.operational ? (
                          <>
                            <Check className="w-3 h-3 inline mr-1" />
                            Operational
                          </>
                        ) : (
                          <>
                            ✗ Not Operational
                          </>
                        )}
                      </span>
                    </div>
                    {systemStatus.mcp.details && (
                      <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">{systemStatus.mcp.details}</p>
                    )}
                    {systemStatus.mcp.error && (
                      <p className="text-xs text-red-600 dark:text-red-400 mt-0.5">{systemStatus.mcp.error}</p>
                    )}
                  </div>

                  {/* Endpoints Status */}
                  <div className="p-2 bg-gray-50 dark:bg-[#161b22] rounded-lg border border-gray-200 dark:border-[#30363d]">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Shield className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">API Endpoints</span>
                      </div>
                      <span className={`text-xs font-medium ${
                        systemStatus.endpoints.operational
                          ? 'text-green-600 dark:text-green-400'
                          : 'text-yellow-600 dark:text-yellow-400'
                      }`}>
                        {systemStatus.endpoints.operational ? (
                          <>
                            <Check className="w-3 h-3 inline mr-1" />
                            All Operational
                          </>
                        ) : (
                          <>
                            ⚠ Partial
                          </>
                        )}
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
                      {systemStatus.endpoints.details}
                    </p>
                    <div className="mt-0.5">
                      {systemStatus.endpoints.checked.map((endpoint, idx) => (
                        <div key={idx} className="flex items-center justify-between text-xs py-0.5">
                          <span className="text-gray-700 dark:text-gray-300 font-mono">
                            {endpoint.method} {endpoint.endpoint}
                          </span>
                          <span className={endpoint.operational ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                            {endpoint.operational ? (
                              <Check className="w-3 h-3 inline" />
                            ) : (
                              <span>✗</span>
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                    {systemStatus.endpoints.errors.length > 0 && (
                      <div className="mt-1 p-1.5 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-xs text-red-800 dark:text-red-300">
                        {systemStatus.endpoints.errors.map((error, idx) => (
                          <div key={idx}>{error}</div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="p-12 text-center">
                  <p className="text-gray-500 dark:text-gray-400">Failed to load system status</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Settings;

