import { useEffect, useState, useRef } from 'react';
import { activityApi } from '../lib/api';
import { AlertTriangle, Clock, XCircle, ChevronRight, ChevronDown } from 'lucide-react';
import type { Activity } from '../types';
import { formatRelativeTime } from '../lib/utils/dateFormat';
import { logError } from '../lib/utils/errorHandler';

// JSON Tree Component (same as ProjectView)
const JsonTree = ({ data, level = 0, defaultExpanded = false, parentKey = '' }: { data: any; level?: number; defaultExpanded?: boolean; parentKey?: string }) => {
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
    const key = parentKey || `object-${level}-${Object.keys(data).length}`;
    const isExpanded = expanded.has(key) || defaultExpanded;
    
    return (
      <div className="ml-1">
        <button
          onClick={() => toggle(key)}
          className="flex items-center gap-0.5 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
        >
          {isExpanded ? <ChevronDown className="w-2.5 h-2.5" /> : <ChevronRight className="w-2.5 h-2.5" />}
          <span className="text-gray-500 dark:text-gray-500">{'{'}{Object.keys(data).length}{'}'}</span>
        </button>
        {isExpanded && (
          <div className="ml-3 mt-0.5 space-y-0.5">
            {Object.entries(data).map(([k, value]) => {
              const valueKey = `${key}-${k}`;
              return (
                <div key={k} className="flex items-start gap-1">
                  <span className="text-gray-600 dark:text-gray-400">"{k}":</span>
                  <JsonTree data={value} level={level + 1} defaultExpanded={defaultExpanded} parentKey={valueKey} />
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  return <span className="text-gray-900 dark:text-gray-100">{String(data)}</span>;
};

const Audit = () => {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [selectedActivity, setSelectedActivity] = useState<Activity | null>(null);
  const [offset, setOffset] = useState(0);
  const activitiesContainerRef = useRef<HTMLDivElement>(null);
  const limit = 25;

  const loadActivities = async (reset: boolean = false) => {
    try {
      if (reset) {
        setLoading(true);
        setOffset(0);
      } else {
        setLoadingMore(true);
      }

      const currentOffset = reset ? 0 : offset;
      const response = await activityApi.listAll(limit, currentOffset, undefined, true); // exposed_only = true
      
      if (reset) {
        setActivities(response.activities);
      } else {
        setActivities(prev => [...prev, ...response.activities]);
      }
      
      setHasMore(response.has_more);
      setOffset(currentOffset + response.activities.length);
    } catch (error) {
      logError(error, 'Audit: Load Activities');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    loadActivities(true);
  }, []);

  // Infinite scroll
  useEffect(() => {
    const container = activitiesContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      if (scrollHeight - scrollTop <= clientHeight + 100 && hasMore && !loadingMore) {
        loadActivities(false);
      }
    };

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, [hasMore, loadingMore, offset]);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Audit Log</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Activities with exposed confidential data
          </p>
        </div>
      </div>

      <div className="card">
        {loading ? (
          <div className="p-12 text-center">
            <Clock className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto mb-4 animate-spin" />
            <p className="text-gray-500 dark:text-gray-400">Loading activities...</p>
          </div>
        ) : !activities || activities.length === 0 ? (
          <div className="p-12 text-center">
            <AlertTriangle className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
            <p className="text-gray-500 dark:text-gray-400">
              No activities with exposed data in the last 7 days.
            </p>
          </div>
        ) : (
          <div 
            ref={activitiesContainerRef}
            className="divide-y divide-gray-200 dark:divide-gray-700 max-h-[600px] overflow-y-auto"
          >
            {activities.map((activity) => {
              // Extract client IP, MCP info, and source from request_data
              let clientIp = null;
              let mcpTool = null;
              let mcpArguments = null;
              let mcpClient = null;
              let source = null;
              let exposedConfidentialData = false;
              
              if (activity.request_data) {
                try {
                  const requestData = JSON.parse(activity.request_data);
                  clientIp = requestData.client_ip || null;
                  source = requestData.source || null;
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
                    {/* Status Code */}
                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${
                      activity.status_code >= 200 && activity.status_code < 300
                        ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                        : activity.status_code >= 400
                        ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                    }`}>
                      {activity.status_code}
                    </span>
                    
                    {/* API or MCP Badge */}
                    {activity.method === 'MCP' ? (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-indigo-100 dark:bg-indigo-900/30 text-indigo-800 dark:text-indigo-300">
                        MCP
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300">
                        API
                      </span>
                    )}
                    
                    {/* Client IP / MCP Client / UI Badge */}
                    {activity.method === 'MCP' ? (
                      mcpClient ? (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-indigo-100 dark:bg-indigo-900/30 text-indigo-800 dark:text-indigo-300">
                          {mcpClient}
                        </span>
                      ) : null
                    ) : source === 'ui' ? (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-300">
                        UI
                      </span>
                    ) : source === 'mcp_server' ? (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300">
                        MCP Server
                      </span>
                    ) : clientIp ? (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300 font-mono">
                        {clientIp}
                      </span>
                    ) : null}
                    
                    {/* Command: HTTP Method or MCP Tool */}
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
                    
                    {/* API URL/Path */}
                    <span className="text-xs font-medium text-gray-900 dark:text-gray-100 font-mono">
                      {activity.path}
                    </span>
                    
                    {/* Latency */}
                    {activity.execution_time_ms !== null && (
                      <span className="text-xs text-gray-400 dark:text-gray-500">
                        {activity.execution_time_ms < 1000 
                          ? `${activity.execution_time_ms}ms`
                          : `${(activity.execution_time_ms / 1000).toFixed(2)}s`}
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
              <div className="px-3 py-4 text-center">
                <p className="text-xs text-gray-500 dark:text-gray-400">Loading more...</p>
              </div>
            )}
            {!hasMore && activities.length > 0 && (
              <div className="px-3 py-4 text-center">
                <p className="text-xs text-gray-400 dark:text-gray-500">No more activities</p>
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
            </div>
            <div className="p-4 space-y-4">
              <div>
                <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">Request Data</h4>
                <div className="bg-gray-50 dark:bg-gray-900 rounded p-3 text-xs font-mono overflow-x-auto">
                  {selectedActivity.request_data ? (
                    <JsonTree data={JSON.parse(selectedActivity.request_data)} defaultExpanded={false} />
                  ) : (
                    <span className="text-gray-400 dark:text-gray-500">No request data</span>
                  )}
                </div>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">Response Data</h4>
                <div className="bg-gray-50 dark:bg-gray-900 rounded p-3 text-xs font-mono overflow-x-auto">
                  {selectedActivity.response_data ? (
                    <JsonTree data={JSON.parse(selectedActivity.response_data)} defaultExpanded={false} />
                  ) : (
                    <span className="text-gray-400 dark:text-gray-500">No response data</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Audit;
