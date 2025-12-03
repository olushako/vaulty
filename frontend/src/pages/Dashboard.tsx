import { useEffect, useState, useCallback, useRef } from 'react';
import { activityApi } from '../lib/api';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ActivityChart } from '../components/ActivityChart';
import { logError } from '../lib/utils/errorHandler';
import type { Activity } from '../types';
import { formatRelativeTime } from '../lib/utils/dateFormat';
import { Clock, XCircle, ChevronRight, ChevronDown } from 'lucide-react';

// JSON Tree Component
const JsonTree = ({ data, level = 0, defaultExpanded = false, parentKey = '' }: { data: any; level?: number; defaultExpanded?: boolean; parentKey?: string }) => {
  // Build expanded set recursively if defaultExpanded - expand all levels
  const buildExpandedSet = (data: any, currentLevel: number, currentKey: string = ''): Set<string> => {
    const expanded = new Set<string>();
    
    if (Array.isArray(data)) {
      const key = currentKey || `array-${currentLevel}-${data.length}`;
      expanded.add(key);
      data.forEach((item, index) => {
        const itemKey = `${key}-item-${index}`;
        const nested = buildExpandedSet(item, currentLevel + 1, itemKey);
        nested.forEach(k => expanded.add(k));
      });
    } else if (typeof data === 'object' && data !== null) {
      const key = currentKey || `object-${currentLevel}-${Object.keys(data).length}`;
      expanded.add(key);
      Object.entries(data).forEach(([k, value]) => {
        const valueKey = `${key}-${k}`;
        const nested = buildExpandedSet(value, currentLevel + 1, valueKey);
        nested.forEach(nk => expanded.add(nk));
      });
    }
    
    return expanded;
  };
  
  const [expanded, setExpanded] = useState<Set<string>>(
    defaultExpanded ? buildExpandedSet(data, level, parentKey) : new Set()
  );

  const toggle = (key: string) => {
    const newExpanded = new Set(expanded);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpanded(newExpanded);
  };

  if (data === null || data === undefined) {
    return <span className="text-gray-400 dark:text-gray-500">null</span>;
  }

  if (typeof data === 'string') {
    return <span className="text-green-600 dark:text-green-400">"{data}"</span>;
  }

  if (typeof data === 'number') {
    return <span className="text-blue-600 dark:text-blue-400">{data}</span>;
  }

  if (typeof data === 'boolean') {
    return <span className="text-purple-600 dark:text-purple-400">{data.toString()}</span>;
  }

  if (Array.isArray(data)) {
    const key = parentKey || `array-${level}-${data.length}`;
    const isExpanded = expanded.has(key) || defaultExpanded;
    
    return (
      <div className="ml-1">
        <button
          onClick={() => toggle(key)}
          className="flex items-center gap-0.5 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
        >
          {isExpanded ? <ChevronDown className="w-2.5 h-2.5" /> : <ChevronRight className="w-2.5 h-2.5" />}
          <span className="text-gray-500 dark:text-gray-500">[{data.length}]</span>
        </button>
        {isExpanded && (
          <div className="ml-3 mt-0.5 space-y-0.5">
            {data.map((item, index) => {
              const itemKey = `${key}-item-${index}`;
              return (
                <div key={index} className="flex items-start gap-1">
                  <span className="text-gray-400 dark:text-gray-600">{index}:</span>
                  <JsonTree data={item} level={level + 1} defaultExpanded={defaultExpanded} parentKey={itemKey} />
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  if (typeof data === 'object') {
    const keys = Object.keys(data);
    const key = parentKey || `object-${level}-${keys.length}`;
    const isExpanded = expanded.has(key) || defaultExpanded;
    
    return (
      <div className="ml-1">
        <button
          onClick={() => toggle(key)}
          className="flex items-center gap-0.5 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
        >
          {isExpanded ? <ChevronDown className="w-2.5 h-2.5" /> : <ChevronRight className="w-2.5 h-2.5" />}
          <span className="text-gray-500 dark:text-gray-500">{'{'} {keys.length} {')'}</span>
        </button>
        {isExpanded && (
          <div className="ml-3 mt-0.5 space-y-0.5">
            {keys.map((k) => {
              const valueKey = `${key}-${k}`;
              return (
                <div key={k} className="flex items-start gap-1">
                  <span className="text-blue-600 dark:text-blue-400 font-medium">"{k}":</span>
                  <JsonTree data={data[k]} level={level + 1} defaultExpanded={defaultExpanded} parentKey={valueKey} />
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  return <span>{String(data)}</span>;
};

const Dashboard = () => {
  // Removed unused state variables for widgets
  const [dailyStats, setDailyStats] = useState<Array<any>>([]);
  const [chartPaths, setChartPaths] = useState<string[]>([]);
  const [sourceFilter, setSourceFilter] = useState<string | undefined>(() => {
    const saved = localStorage.getItem('vaulty_dashboard_source_filter');
    // Map old values to new format: 'all' -> undefined, 'ui_only' -> 'ui', 'api_only' -> 'api'
    if (saved === 'ui_only') return 'ui';
    if (saved === 'api_only') return 'api';
    if (saved === 'mcp_only') return 'mcp';
    if (saved === 'all' || !saved) return undefined;
    // If it's already a valid filter value, use it
    if (['ui', 'api', 'mcp', 'exposed', 'root', 'project', 'ip', 'token', 'device'].includes(saved)) return saved;
    return undefined;
  });
  const [chartAvgResponseTime, setChartAvgResponseTime] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Activities table state
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loadingActivities, setLoadingActivities] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [activitiesOffset, setActivitiesOffset] = useState(0);
  const [selectedActivity, setSelectedActivity] = useState<Activity | null>(null);
  const activitiesContainerRef = useRef<HTMLDivElement>(null);

  const generateEmptyDailyStats = useCallback(() => {
    const today = new Date();
    const emptyData = [];
    for (let i = 6; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);
      emptyData.push({
        date: date.toISOString().split('T')[0],
        day: date.toLocaleDateString('en-US', { weekday: 'short' }),
        total: 0
      });
    }
    setDailyStats(emptyData);
  }, []);

  const loadDashboardData = useCallback(() => {
    // Load daily stats with selected source filter
    activityApi.getDailyStats(undefined, sourceFilter || undefined)
      .then((daily) => {
        // Debug logging (remove in production)
        console.log('Dashboard: Daily stats response:', {
          hasDaily: !!daily,
          hasDailyStats: !!(daily && daily.daily_stats),
          dailyStatsLength: daily?.daily_stats?.length,
          dailyStats: daily?.daily_stats,
          source: daily?.source,
          paths: daily?.paths
        });
        
        // Check if we have valid data - daily_stats should always have 7 days
        if (daily && daily.daily_stats && Array.isArray(daily.daily_stats)) {
          // Even if all totals are 0, we should still display the chart
          setDailyStats(daily.daily_stats);
          setChartPaths(daily.paths || []);
          setChartAvgResponseTime(daily.avg_response_time_ms || null);
        } else {
          console.warn('Dashboard: Invalid daily stats response, using fallback');
          // Fallback: generate empty structure for last 7 days
          generateEmptyDailyStats();
          setChartAvgResponseTime(null);
        }
        setLoading(false);
      })
      .catch((error) => {
        console.error('Dashboard: Error loading daily stats:', error);
        logError(error, 'Dashboard: Daily Stats');
        // Fallback: generate empty structure for last 7 days
        generateEmptyDailyStats();
        setChartAvgResponseTime(null);
        setLoading(false);
      });
  }, [sourceFilter, generateEmptyDailyStats]);

  const loadActivities = useCallback(async (offset: number = 0, isInitial: boolean = true) => {
    try {
      if (isInitial) {
        setLoadingActivities(true);
      } else {
        setLoadingMore(true);
      }
      
      // Pass source filter to filter activities
      const response = await activityApi.listAll(25, offset, undefined, false, undefined, undefined, sourceFilter || undefined);
      
      if (isInitial) {
        setActivities(response.activities);
        setActivitiesOffset(25);
      } else {
        setActivities(prev => [...prev, ...response.activities]);
        setActivitiesOffset(prev => prev + 25);
      }
      setHasMore(response.has_more || false);
    } catch (error) {
      logError(error, 'Dashboard: Load Activities');
      if (isInitial) {
        setActivities([]);
      }
    } finally {
      setLoadingActivities(false);
      setLoadingMore(false);
    }
  }, [sourceFilter]);

  useEffect(() => {
    loadDashboardData();
    const interval = setInterval(() => {
      loadDashboardData();
    }, 60000);
    return () => clearInterval(interval);
  }, [loadDashboardData]); // Reload when breakdown type changes

  // Load activities when dashboard data is loaded or source filter changes
  useEffect(() => {
    if (!loading) {
      // Reset activities when source filter changes
      setActivities([]);
      setActivitiesOffset(0);
      setHasMore(false);
      loadActivities(0, true);
    }
  }, [loading, sourceFilter, loadActivities]);

  // Infinite scroll handler
  useEffect(() => {
    if (!activitiesContainerRef.current) return;

    const container = activitiesContainerRef.current;
    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      // Load more when scrolled to within 100px of bottom
      if (scrollHeight - scrollTop - clientHeight < 100) {
        if (!loadingMore && hasMore) {
          loadActivities(activitiesOffset, false);
        }
      }
    };

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activitiesOffset, hasMore, loadingMore, loadActivities]);

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="p-4 max-w-7xl mx-auto space-y-4">
      {/* Chart - Full width */}
      <div className="mb-6">
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              Events (Last 7 Days)
            </h3>
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                Filter:
              </label>
              <select
                value={sourceFilter || 'all'}
                onChange={(e) => {
                  const newFilter = e.target.value === 'all' ? undefined : e.target.value;
                  setSourceFilter(newFilter);
                  localStorage.setItem('vaulty_dashboard_source_filter', newFilter || 'all');
                }}
                className="text-xs px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500 dark:focus:ring-primary-400 focus:border-transparent"
              >
                <option value="all">All</option>
                <option value="ui">UI</option>
                <option value="api">API</option>
                <option value="mcp">MCP</option>
                <option value="exposed">EXPOSED</option>
                <option value="root">ROOT</option>
                <option value="project">PROJECT</option>
                <option value="ip">IP</option>
                <option value="token">TOKENS</option>
                <option value="device">DEVICES</option>
              </select>
            </div>
          </div>
          <ActivityChart 
            data={dailyStats} 
            categories={chartPaths}
            avgResponseTime={chartAvgResponseTime}
            isStacked={!!sourceFilter && chartPaths.length > 0}
          />
        </div>
      </div>

      {/* Activities Table */}
      <div className="card">
        {loadingActivities ? (
          <div className="p-12 text-center">
            <Clock className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto mb-4 animate-spin" />
            <p className="text-gray-500 dark:text-gray-400">Loading activities...</p>
          </div>
        ) : activities.length === 0 ? (
          <div className="p-12 text-center">
            <Clock className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
            <p className="text-gray-500 dark:text-gray-400">
              No activities in the last 7 days.
            </p>
          </div>
        ) : (
          <div 
            ref={activitiesContainerRef}
            className="divide-y divide-gray-200 dark:divide-gray-700 max-h-[600px] overflow-y-auto"
          >
            {activities.map((activity) => {
              // Extract client IP, MCP info, source, and masked token from request_data
              let clientIp = null;
              let mcpTool = null;
              let mcpArguments = null;
              let mcpClient = null;
              let source = null;
              let maskedToken = null;
              let exposedConfidentialData = false;
              
              if (activity.request_data) {
                try {
                  const requestData = JSON.parse(activity.request_data);
                  clientIp = requestData.client_ip || null;
                  source = requestData.source || null;
                  
                  // Extract masked Bearer token from Authorization header
                  // Show only 3 asterisks in the middle
                  if (requestData.headers) {
                    const authHeader = requestData.headers.Authorization || requestData.headers.authorization;
                    if (authHeader && typeof authHeader === 'string' && authHeader.startsWith('Bearer ')) {
                      const fullMaskedToken = authHeader.substring(7).trim();
                      // Extract first 4 chars and last 4 chars, replace middle with ***
                      if (fullMaskedToken.length > 8) {
                        const first = fullMaskedToken.substring(0, 4);
                        const last = fullMaskedToken.substring(fullMaskedToken.length - 4);
                        maskedToken = `${first}***${last}`;
                      } else {
                        // If token is too short, just show it as is
                        maskedToken = fullMaskedToken;
                      }
                    }
                  }
                  
                  if (requestData.mcp) {
                    mcpTool = requestData.mcp.tool || null;
                    mcpArguments = requestData.mcp.arguments || null;
                    if (requestData.mcp.client) {
                      mcpClient = requestData.mcp.client.name || requestData.mcp.client.title || null;
                    }
                  }
                } catch {
                  // Ignore parse errors
                }
              }
              
              if (!clientIp && activity.method === 'MCP') {
                clientIp = 'MCP';
              }
              
              // Check if confidential data was exposed
              if (activity.response_data) {
                try {
                  const responseData = JSON.parse(activity.response_data);
                  exposedConfidentialData = responseData.exposed_confidential_data === true;
                } catch {
                  // Ignore parse errors
                }
              }
              
              return (
                <div 
                  key={activity.id} 
                  className="px-3 py-1 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer"
                  onClick={() => setSelectedActivity(activity)}
                >
                  <div className="flex items-center gap-2 flex-wrap">
                    {/* 1. Status Code */}
                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${
                      activity.status_code >= 200 && activity.status_code < 300
                        ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                        : activity.status_code >= 400
                        ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                    }`}>
                      {activity.status_code}
                    </span>
                    
                    {/* 4. Source Badge (UI, API, or MCP) */}
                    {source === 'ui' && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-300">
                        UI
                      </span>
                    )}
                    {source === 'api' && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300">
                        API
                      </span>
                    )}
                    {source === 'mcp' && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-indigo-100 dark:bg-indigo-900/30 text-indigo-800 dark:text-indigo-300">
                        MCP
                      </span>
                    )}
                    
                    {/* 5. IP Badge (only when IP filter is selected) */}
                    {sourceFilter === 'ip' && clientIp && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300">
                        {clientIp}
                      </span>
                    )}
                    
                    {/* 6. Command: HTTP Method (GET/POST) or MCP Tool */}
                    {activity.method === 'MCP' ? (
                      mcpTool && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-cyan-100 dark:bg-cyan-900/30 text-cyan-800 dark:text-cyan-300">
                          {mcpTool}
                        </span>
                      )
                    ) : (
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${
                        activity.method === 'GET' 
                          ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
                          : activity.method === 'POST'
                          ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                          : activity.method === 'DELETE'
                          ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
                          : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                      }`}>
                        {activity.method}
                      </span>
                    )}
                    
                    {/* 8. API URL/Path */}
                    <span className="text-xs font-medium text-gray-900 dark:text-gray-100 font-mono">
                      {activity.path}
                    </span>
                    
                    {/* 9. Latency (Execution Time) */}
                    {activity.execution_time_ms !== null && (
                      <span className="text-xs text-gray-400 dark:text-gray-500">
                        {activity.execution_time_ms < 1000 
                          ? `${activity.execution_time_ms}ms`
                          : `${(activity.execution_time_ms / 1000).toFixed(2)}s`}
                      </span>
                    )}
                    
                    {/* 10. Project Name Badge (only when PROJECT filter is selected) */}
                    {sourceFilter === 'project' && activity.project_name && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300">
                        {activity.project_name}
                      </span>
                    )}
                    
                    {/* 11. Masked Token Badge (only when TOKEN filter is selected) */}
                    {sourceFilter === 'token' && maskedToken && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-indigo-100 dark:bg-indigo-900/30 text-indigo-800 dark:text-indigo-300 font-mono">
                        {maskedToken}
                      </span>
                    )}
                    
                    {/* Right side: EXPOSED badge and Timestamp */}
                    <div className="flex items-center gap-2 ml-auto">
                      {exposedConfidentialData && (
                        <span 
                          className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium font-semibold ${
                            activity.method === 'MCP'
                              ? 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'
                              : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                          }`}
                          title="Confidential data exposed"
                        >
                          EXPOSED
                        </span>
                      )}
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
                        {formatRelativeTime(activity.created_at)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
            {loadingMore && (
              <div className="p-4 text-center">
                <Clock className="w-6 h-6 text-gray-400 dark:text-gray-500 mx-auto mb-2 animate-spin" />
                <p className="text-xs text-gray-500 dark:text-gray-400">Loading more activities...</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Activity Details Modal */}
      {selectedActivity && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setSelectedActivity(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 py-3">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">Activity Details</h3>
                <button
                  onClick={() => setSelectedActivity(null)}
                  className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded transition-colors"
                >
                  <XCircle className="w-5 h-5" />
                </button>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${
                  selectedActivity.status_code >= 200 && selectedActivity.status_code < 300
                    ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                    : selectedActivity.status_code >= 400
                    ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
                    : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                }`}>
                  {selectedActivity.status_code}
                </span>
                <span className="text-xs font-mono text-gray-700 dark:text-gray-300">
                  {selectedActivity.path}
                </span>
                {selectedActivity.execution_time_ms !== null && (
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {selectedActivity.execution_time_ms < 1000 
                      ? `${selectedActivity.execution_time_ms}ms`
                      : `${(selectedActivity.execution_time_ms / 1000).toFixed(2)}s`}
                  </span>
                )}
              </div>
            </div>
            <div className="p-4 space-y-4">
              {/* Exposure Warning Section */}
              {(() => {
                try {
                  if (selectedActivity.response_data) {
                    const responseData = JSON.parse(selectedActivity.response_data);
                    const exposed = responseData.exposed_confidential_data === true;
                    if (exposed) {
                      return (
                        <div className="border-l-4 border-red-500 bg-red-50 dark:bg-red-900/20 p-3 rounded">
                          <label className="text-xs font-semibold text-red-800 dark:text-red-300 uppercase tracking-wide mb-2 block">
                            ⚠️ Confidential Data Exposure Detected
                          </label>
                          <div className="text-xs text-red-700 dark:text-red-400">
                            Confidential data (secrets or tokens) was exposed in this response and has been redacted to <span className="font-mono font-semibold">***EXPOSED***</span>.
                          </div>
                        </div>
                      );
                    }
                  }
                } catch {
                  // Ignore parse errors
                }
                return null;
              })()}

              {selectedActivity.request_data && (
                <div>
                  <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2 block">Request Data</label>
                  <div className="p-3 bg-gray-50 dark:bg-gray-900 rounded text-xs font-mono overflow-auto border border-gray-200 dark:border-gray-700">
                    {(() => {
                      try {
                        const data = JSON.parse(selectedActivity.request_data);
                        // Data is already masked in the database, display as-is
                        return <JsonTree data={data} defaultExpanded={true} />;
                      } catch {
                        // If not JSON, display as plain text (already masked in DB)
                        return <span className="text-gray-900 dark:text-gray-100">{selectedActivity.request_data}</span>;
                      }
                    })()}
                  </div>
                </div>
              )}

              {selectedActivity.response_data && (
                <div>
                  <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2 block">Response Data</label>
                  <div className="p-3 bg-gray-50 dark:bg-gray-900 rounded text-xs font-mono overflow-auto border border-gray-200 dark:border-gray-700">
                    {(() => {
                      try {
                        const data = JSON.parse(selectedActivity.response_data);
                        // Data is already masked in the database, display as-is
                        return <JsonTree data={data} defaultExpanded={true} />;
                      } catch {
                        // If not JSON, display as plain text (already masked in DB)
                        return <span className="text-gray-900 dark:text-gray-100">{selectedActivity.response_data}</span>;
                      }
                    })()}
                  </div>
                </div>
              )}

              {!selectedActivity.request_data && !selectedActivity.response_data && (
                <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                  No request or response data available
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
