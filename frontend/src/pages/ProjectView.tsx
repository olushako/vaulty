import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { projectApi, secretApi, tokenApi, activityApi, deviceApi } from '../lib/api';
import { Plus, Eye, EyeOff, Trash2, ArrowLeft, Save, X, Shuffle, Copy, Check, Key, Clock, Monitor, XCircle, ChevronRight, ChevronDown, Trash, CheckCircle, AlertCircle, Terminal } from 'lucide-react';
import type { Project, Secret, SecretCreate, Token, TokenCreate, Activity, Device } from '../types';
import { useToastContext } from '../contexts/ToastContext';
import { useClipboard } from '../hooks/useClipboard';
import { extractErrorMessage, logError } from '../lib/utils/errorHandler';
import { formatRelativeTime } from '../lib/utils/dateFormat';

type TabType = 'secrets' | 'tokens' | 'devices' | 'activity';

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

const ProjectView = () => {
  const { id: projectName } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const toast = useToastContext();
  const { copyToClipboard: copyToClipboardUtil } = useClipboard();

  // Get active tab from URL, default to 'secrets'
  const getTabFromUrl = (): TabType => {
    const tabFromUrl = searchParams.get('tab') as TabType | null;
    if (tabFromUrl && ['secrets', 'tokens', 'devices', 'activity'].includes(tabFromUrl)) {
      return tabFromUrl;
    }
    return 'secrets';
  };

  const [activeTab, setActiveTab] = useState<TabType>(getTabFromUrl());

  // Update URL when tab changes
  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab);
    setSearchParams({ tab }, { replace: true });
  };

  // Sync tab from URL on mount or when URL changes (e.g., browser back/forward)
  useEffect(() => {
    const tabFromUrl = getTabFromUrl();
    setActiveTab(tabFromUrl);
    // If no tab in URL, set default
    if (!searchParams.get('tab')) {
      setSearchParams({ tab: 'secrets' }, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [secretsLoading, setSecretsLoading] = useState(false);
  const [tokensLoading, setTokensLoading] = useState(false);
  const [devicesLoading, setDevicesLoading] = useState(false);
  const [autoApprovalPatterns, setAutoApprovalPatterns] = useState<string[]>([]);
  const [newPatternInput, setNewPatternInput] = useState<string>('');
  const [savingAutoApproval, setSavingAutoApproval] = useState(false);
  const [, setNow] = useState(new Date()); // Force re-render for relative time updates
  
  // Secrets state
  const [secrets, setSecrets] = useState<Secret[]>([]);
  const [showCreateSecret, setShowCreateSecret] = useState(false);
  const [formData, setFormData] = useState<SecretCreate>({ key: '', value: '' });
  const [revealed, setRevealed] = useState<Map<string, string>>(new Map());
  const [editing, setEditing] = useState<Map<string, string>>(new Map());
  const [saving, setSaving] = useState<string | null>(null);
  const [copiedSecretKey, setCopiedSecretKey] = useState<string | null>(null);
  
  // Tokens state
  const [tokens, setTokens] = useState<Token[]>([]);
  const [newToken, setNewToken] = useState<string | null>(null);
  const [tokenCopied, setTokenCopied] = useState(false);
  
    // Activities state
    const [activities, setActivities] = useState<Activity[]>([]);
    const [activitiesLoading, setActivitiesLoading] = useState(false);
    const [activitiesLoadingMore, setActivitiesLoadingMore] = useState(false);
    const [activitiesHasMore, setActivitiesHasMore] = useState(false);
    const [activitiesOffset, setActivitiesOffset] = useState(0);
    const [selectedActivity, setSelectedActivity] = useState<Activity | null>(null);
    // Activity filter: 'all', 'exclude_ui', or 'mcp_only'
    const [activityFilter, setActivityFilter] = useState<'all' | 'exclude_ui' | 'mcp_only'>(() => {
      const saved = localStorage.getItem('vaulty_activity_filter');
      return (saved === 'all' || saved === 'exclude_ui' || saved === 'mcp_only') ? saved : 'all';
    });
    const activitiesContainerRef = useRef<HTMLDivElement>(null);
    
    // Save filter preferences to localStorage when they change
    useEffect(() => {
      localStorage.setItem('vaulty_activity_filter', activityFilter);
    }, [activityFilter]);
    
  
  // Devices state
  const [devices, setDevices] = useState<Device[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);

  useEffect(() => {
    if (projectName) {
      loadProject();
      loadSecrets();
      loadTokens();
    }
  }, [projectName]);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    if (!projectName) return;
    
    const refreshCurrentTab = () => {
      // Always refresh project info
      loadProject();
      
      // Refresh data based on active tab
      switch (activeTab) {
        case 'secrets':
          loadSecrets();
          break;
        case 'tokens':
          loadTokens();
          break;
        case 'devices':
          loadDevices();
          break;
        case 'activity':
          // For activity tab, reload from current offset
          loadActivities(activitiesOffset, false);
          break;
        default:
          // For default tab (secrets), load secrets
          loadSecrets();
          break;
      }
    };
    
    const interval = setInterval(() => {
      refreshCurrentTab();
    }, 60000);
    
    return () => clearInterval(interval);
  }, [projectName, activeTab, activitiesOffset]);

  // Update time periodically to refresh relative time displays
  useEffect(() => {
    const interval = setInterval(() => {
      setNow(new Date());
    }, 60000); // Update every minute for relative time

    return () => clearInterval(interval);
  }, []);

  // Reload tokens when switching to tokens tab
  useEffect(() => {
    if (activeTab === 'tokens' && projectName) {
      loadTokens();
    }
  }, [activeTab, projectName]);

  // Reload activities when switching to activity tab or when filter changes
  useEffect(() => {
    if (activeTab === 'activity' && projectName) {
      // Reset state and load initial activities
      setActivities([]);
      setActivitiesOffset(0);
      setActivitiesHasMore(false);
      loadActivities(0, true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, projectName, activityFilter]);

  // Reload devices when switching to devices tab
  useEffect(() => {
    if (activeTab === 'devices' && projectName) {
      loadDevices();
    }
  }, [activeTab, projectName]);

  const loadProject = () => {
    if (!projectName) return;
    setLoading(true);
    projectApi.get(projectName)
      .then((projectData) => {
        setProject(projectData);
        // Parse patterns from comma-separated string or JSON array
        if (projectData.auto_approval_tag_pattern) {
          try {
            const parsed = JSON.parse(projectData.auto_approval_tag_pattern);
            if (Array.isArray(parsed)) {
              setAutoApprovalPatterns(parsed);
            } else {
              setAutoApprovalPatterns([projectData.auto_approval_tag_pattern]);
            }
          } catch {
            // If not JSON, treat as comma-separated or single value
            const patterns = projectData.auto_approval_tag_pattern.split(',').map(p => p.trim()).filter(p => p);
            setAutoApprovalPatterns(patterns);
          }
        } else {
          setAutoApprovalPatterns([]);
        }
        setLoading(false);
      })
      .catch((error) => {
        logError(error, 'ProjectView: Load project');
        setLoading(false);
        navigate('/projects');
      });
  };

  const handleSaveAutoApproval = async (patterns: string[]) => {
    if (!projectName) return;
    setSavingAutoApproval(true);
    try {
      // Store as JSON array
      const patternValue = patterns.length > 0 
        ? JSON.stringify(patterns) 
        : null;
      const updatedProject = await projectApi.update(projectName, {
        auto_approval_tag_pattern: patternValue
      });
      setProject(updatedProject);
      // Update local state to match saved data
      if (updatedProject.auto_approval_tag_pattern) {
        try {
          const parsed = JSON.parse(updatedProject.auto_approval_tag_pattern);
          if (Array.isArray(parsed)) {
            setAutoApprovalPatterns(parsed);
          } else {
            setAutoApprovalPatterns([updatedProject.auto_approval_tag_pattern]);
          }
        } catch {
          const patterns = updatedProject.auto_approval_tag_pattern.split(',').map(p => p.trim()).filter(p => p);
          setAutoApprovalPatterns(patterns);
        }
      } else {
        setAutoApprovalPatterns([]);
      }
      toast.success('Auto-approval policy updated');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to update auto-approval policy');
      toast.error(message);
      // Reload project to get correct state
      loadProject();
    } finally {
      setSavingAutoApproval(false);
    }
  };

  const handleAddPattern = async () => {
    const trimmed = newPatternInput.trim();
    if (trimmed && !autoApprovalPatterns.includes(trimmed)) {
      const newPatterns = [...autoApprovalPatterns, trimmed];
      setAutoApprovalPatterns(newPatterns);
      setNewPatternInput('');
      await handleSaveAutoApproval(newPatterns);
    }
  };

  const handleRemovePattern = async (patternToRemove: string) => {
    const newPatterns = autoApprovalPatterns.filter(p => p !== patternToRemove);
    setAutoApprovalPatterns(newPatterns);
    await handleSaveAutoApproval(newPatterns);
  };

  const loadSecrets = () => {
    if (!projectName) return;
    setSecretsLoading(true);
    secretApi.list(projectName)
      .then(setSecrets)
      .catch((error) => logError(error, 'ProjectView: Load secrets'))
      .finally(() => setSecretsLoading(false));
  };

  const loadTokens = () => {
    if (!projectName) {
      console.log('loadTokens: No projectName');
      return;
    }
    console.log('loadTokens: Loading tokens for project', projectName);
    setTokensLoading(true);
    tokenApi.list(projectName)
      .then((tokensData) => {
        console.log('loadTokens: Received tokens', tokensData);
        setTokens(tokensData);
        setTokensLoading(false);
      })
      .catch((error) => {
        logError(error, 'ProjectView: Load tokens');
        setTokens([]);
        setTokensLoading(false);
      });
  };

  const loadActivities = (offset: number = 0, isInitial: boolean = false) => {
    if (!projectName) return;
    
    if (isInitial) {
      setActivitiesLoading(true);
    } else {
      setActivitiesLoadingMore(true);
    }
    
    // Pass filters based on activity filter
    const method = activityFilter === 'mcp_only' ? 'MCP' : undefined;
    const excludeUi = activityFilter === 'exclude_ui';
    
    // Debug logging
    console.log('ProjectView: Loading activities', {
      projectName,
      offset,
      isInitial,
      method,
      excludeUi,
      activityFilter
    });
    
    activityApi.list(projectName, 25, offset, method, excludeUi)
      .then((response) => {
        console.log('ProjectView: Activities response', {
          activitiesCount: response.activities?.length || 0,
          total: response.total,
          hasMore: response.has_more,
          activities: response.activities
        });
        
        if (isInitial) {
          setActivities(response.activities);
          setActivitiesOffset(25);
        } else {
          setActivities(prev => [...prev, ...response.activities]);
          setActivitiesOffset(prev => prev + 25);
        }
        setActivitiesHasMore(response.has_more);
      })
      .catch((error) => {
        console.error('ProjectView: Error loading activities', error);
        logError(error, 'ProjectView: Load activities');
        if (isInitial) {
          setActivities([]);
        }
      })
      .finally(() => {
        setActivitiesLoading(false);
        setActivitiesLoadingMore(false);
      });
  };

  // Infinite scroll handler
  useEffect(() => {
    if (activeTab !== 'activity' || !activitiesContainerRef.current) return;

    const container = activitiesContainerRef.current;
    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      // Load more when scrolled to within 100px of bottom
      if (scrollHeight - scrollTop - clientHeight < 100) {
        if (!activitiesLoadingMore && activitiesHasMore && projectName) {
          loadActivities(activitiesOffset, false);
        }
      }
    };

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, activitiesOffset, activitiesHasMore, activitiesLoadingMore, projectName]);

  // Secrets handlers
  const handleCreateSecret = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName) return;
    try {
      await secretApi.create(projectName, formData);
      setFormData({ key: '', value: '' });
      setShowCreateSecret(false);
      loadSecrets();
      toast.success('Secret created successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to create secret');
      toast.error(message);
    }
  };

  const handleDeleteSecret = async (key: string) => {
    if (!projectName) return;
    if (!confirm(`Are you sure you want to delete secret "${key}"?`)) return;
    try {
      await secretApi.delete(projectName, key);
      loadSecrets();
      toast.success('Secret deleted successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to delete secret');
      toast.error(message);
    }
  };

  const toggleReveal = async (key: string) => {
    if (!projectName) return;
    if (revealed.has(key)) {
      const newRevealed = new Map(revealed);
      newRevealed.delete(key);
      setRevealed(newRevealed);
      if (editing.has(key)) {
        const newEditing = new Map(editing);
        newEditing.delete(key);
        setEditing(newEditing);
      }
    } else {
      try {
        const secret = await secretApi.get(projectName, key);
        setRevealed(new Map(revealed).set(key, secret.value));
      } catch (error) {
        const message = extractErrorMessage(error, 'Failed to retrieve secret');
        toast.error(message);
      }
    }
  };

  const handleEditChange = (key: string, value: string) => {
    setEditing(new Map(editing).set(key, value));
  };

  const handleGenerateRandom = (key: string) => {
    const uuid = crypto.randomUUID();
    setEditing(new Map(editing).set(key, uuid));
  };

  const handleSave = async (key: string) => {
    if (!projectName) return;
    const editedValue = editing.get(key);
    if (editedValue === undefined) return;

    setSaving(key);
    try {
      await secretApi.create(projectName, { key, value: editedValue });
      const newEditing = new Map(editing);
      newEditing.delete(key);
      setEditing(newEditing);
      const newRevealed = new Map(revealed);
      newRevealed.delete(key);
      setRevealed(newRevealed);
      loadSecrets();
      toast.success('Secret updated successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to update secret');
      toast.error(message);
    } finally {
      setSaving(null);
    }
  };

  const handleCancelEdit = (key: string) => {
    const newEditing = new Map(editing);
    newEditing.delete(key);
    setEditing(newEditing);
  };

  const handleCopySecret = async (key: string) => {
    let value = revealed.get(key);
    
    if (!value && projectName) {
      try {
        const secret = await secretApi.get(projectName, key);
        value = secret.value;
      } catch (error) {
        const message = extractErrorMessage(error, 'Failed to retrieve secret');
        toast.error(message);
        return;
      }
    }
    
    if (value) {
      const success = await copyToClipboardUtil(value);
      if (success) {
      setCopiedSecretKey(key);
        toast.success('Secret copied to clipboard!');
      setTimeout(() => {
        setCopiedSecretKey(null);
      }, 2000);
      } else {
        toast.error('Failed to copy to clipboard');
      }
    }
  };

  const handleCopyAllExportCommands = async () => {
    if (!projectName || secrets.length === 0) return;
    
    try {
      // Fetch all secret values
      const exportCommands: string[] = [];
      
      for (const secret of secrets) {
        let value = revealed.get(secret.key);
        
        if (!value) {
          try {
            const secretData = await secretApi.get(projectName, secret.key);
            value = secretData.value;
            // Cache it in revealed state
            setRevealed(new Map(revealed).set(secret.key, value));
          } catch (error) {
            logError(error, `Failed to retrieve secret: ${secret.key}`);
            continue; // Skip this secret if we can't retrieve it
          }
        }
        
        if (value) {
          // Escape the value for shell use (escape quotes and backslashes)
          const escapedValue = value.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
          exportCommands.push(`export ${secret.key}="${escapedValue}"`);
        }
      }
      
      if (exportCommands.length > 0) {
        const allCommands = exportCommands.join('\n');
        const success = await copyToClipboardUtil(allCommands);
        if (success) {
          toast.success(`Copied ${exportCommands.length} export command(s) to clipboard!`);
        } else {
          toast.error('Failed to copy export commands');
        }
      } else {
        toast.error('No secrets to export');
      }
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to generate export commands');
      toast.error(message);
    }
  };

  // Tokens handlers
  const handleCreateToken = async () => {
    if (!projectName) return;
    try {
      // Create token - API will generate the name from masked token value
      const tokenData = await tokenApi.create(projectName, { name: '' });
      if (tokenData.token) {
        setNewToken(tokenData.token);
        setTokenCopied(false); // Reset copied state when new token is created
      }
      loadTokens();
      toast.success('Token created successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to create token');
      toast.error(message);
    }
  };

  const handleCopyToken = async (text: string) => {
    const success = await copyToClipboardUtil(text);
    if (success) {
    setTokenCopied(true);
      toast.success('Token copied to clipboard!');
      setTimeout(() => {
        setTokenCopied(false);
      }, 2000);
    } else {
      toast.error('Failed to copy to clipboard');
    }
  };

  const handleRevokeToken = async (tokenId: string) => {
    if (!confirm('Are you sure you want to revoke this token?')) return;
    try {
      await tokenApi.revoke(tokenId);
      loadTokens();
      toast.success('Token revoked successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to revoke token');
      toast.error(message);
    }
  };


  // Devices handlers
  const loadDevices = () => {
    if (!projectName) return;
    setDevicesLoading(true);
    
    // Fetch both pending and authorized devices, then combine
    // (rejected devices are hard-deleted, so they won't appear)
    Promise.all([
      deviceApi.list(projectName, 'pending').catch(() => []),
      deviceApi.list(projectName, 'authorized').catch(() => [])
    ])
      .then(([pending, authorized]) => {
        setDevices([...pending, ...authorized]);
      })
      .catch((error) => {
        logError(error, 'ProjectView: Load devices');
        setDevices([]);
      })
      .finally(() => {
        setDevicesLoading(false);
      });
  };


  const handleAuthorizeDevice = async (deviceId: string) => {
    if (!projectName) return;
    
    // Check current device status before authorizing
    const currentDevice = devices.find(d => d.id === deviceId);
    const wasAlreadyAuthorized = currentDevice?.status === 'authorized';
    
    if (!confirm('Are you sure you want to authorize this device?')) return;
    try {
      const device = await deviceApi.authorize(projectName, deviceId);
      loadDevices();
      
      if (wasAlreadyAuthorized) {
        toast.info('Device is already authorized');
      } else {
        toast.success('Device authorized successfully');
      }
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to authorize device');
      toast.error(message);
    }
  };

  const handleRejectDevice = async (deviceId: string) => {
    if (!projectName) return;
    if (!confirm('Are you sure you want to reject this device?')) return;
    try {
      await deviceApi.reject(projectName, deviceId);
      loadDevices();
      toast.success('Device rejected successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to reject device');
      toast.error(message);
    }
  };

  const handleDeleteDevice = async (deviceId: string) => {
    if (!projectName) return;
    if (!confirm('Are you sure you want to delete this device?')) return;
    try {
      await deviceApi.delete(projectName, deviceId);
      loadDevices();
      toast.success('Device deleted successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to delete device');
      toast.error(message);
    }
  };

  if (loading) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
      </div>
    );
  }

  if (!project) {
    return null;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={() => navigate('/projects')}
          className="p-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{project.name}</h1>
          {project.description && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{project.description}</p>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-6">
        <div className="border-b border-gray-200 dark:border-gray-700">
          <nav className="flex gap-1">
            <button
              onClick={() => handleTabChange('secrets')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'secrets'
                  ? 'border-primary-600 text-primary-600 dark:text-primary-400 dark:border-primary-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
              }`}
            >
              Secrets
            </button>
            <button
              onClick={() => handleTabChange('tokens')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'tokens'
                  ? 'border-primary-600 text-primary-600 dark:text-primary-400 dark:border-primary-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
              }`}
            >
              <div className="flex items-center gap-2">
                <Key className="w-4 h-4" />
                Tokens
              </div>
            </button>
            <button
              onClick={() => handleTabChange('devices')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'devices'
                  ? 'border-primary-600 text-primary-600 dark:text-primary-400 dark:border-primary-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
              }`}
            >
              <div className="flex items-center gap-2">
                <Monitor className="w-4 h-4" />
                Devices
              </div>
            </button>
            <button
              onClick={() => handleTabChange('activity')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'activity'
                  ? 'border-primary-600 text-primary-600 dark:text-primary-400 dark:border-primary-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
              }`}
            >
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Activity
              </div>
            </button>
          </nav>
        </div>
      </div>

      {/* Secrets Tab */}
      {activeTab === 'secrets' && (
        <>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Secrets</h2>
            <div className="flex items-center gap-2">
              <button
                onClick={handleCopyAllExportCommands}
                className="btn btn-secondary flex items-center gap-2 text-sm py-1.5 px-3"
                title="Copy export commands for all secrets"
              >
                <Terminal className="w-3.5 h-3.5" />
                Export All
              </button>
              <button
                onClick={() => setShowCreateSecret(!showCreateSecret)}
                className="btn btn-primary flex items-center gap-2 text-sm py-1.5 px-3"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Secret
              </button>
            </div>
          </div>

          {showCreateSecret && (
            <div className="card p-6 mb-6">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Create New Secret</h2>
              <form onSubmit={handleCreateSecret} className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Key
                  </label>
                  <input
                    type="text"
                    required
                    className="input text-sm py-1.5"
                    value={formData.key}
                    onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Value
                  </label>
                  <textarea
                    className="input text-sm py-1.5"
                    rows={3}
                    required
                    value={formData.value}
                    onChange={(e) => setFormData({ ...formData, value: e.target.value })}
                  />
                </div>
                <div className="flex gap-2">
                  <button type="submit" className="btn btn-primary text-sm py-1.5 px-3">
                    Create
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowCreateSecret(false)}
                    className="btn btn-secondary text-sm py-1.5 px-3"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          <div className="card">
            {secrets.length === 0 ? (
              <div className="p-12 text-center">
                <p className="text-gray-500 dark:text-gray-400">No secrets yet. Add your first secret to get started.</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {secrets.map((secret) => (
                  <div key={secret.key} className="px-3 py-1 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                    {editing.has(secret.key) ? (
                      <div className="space-y-2">
                        <textarea
                          className="input text-xs py-1.5 font-mono min-h-[60px]"
                          value={editing.get(secret.key) || ''}
                          onChange={(e) => handleEditChange(secret.key, e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          onFocus={(e) => e.stopPropagation()}
                          autoFocus
                        />
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleGenerateRandom(secret.key);
                            }}
                            className="btn btn-secondary text-xs py-1 px-2 flex items-center gap-1"
                            title="Generate random UUID"
                          >
                            <Shuffle className="w-3 h-3" />
                            Random
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSave(secret.key);
                            }}
                            disabled={saving === secret.key}
                            className="btn btn-primary text-xs py-1 px-2 flex items-center gap-1"
                          >
                            <Save className="w-3 h-3" />
                            {saving === secret.key ? 'Saving...' : 'Save'}
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCancelEdit(secret.key);
                            }}
                            className="btn btn-secondary text-xs py-1 px-2 flex items-center gap-1"
                          >
                            <X className="w-3 h-3" />
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-xs text-gray-900 dark:text-gray-100">{secret.key}</span>
                        {revealed.has(secret.key) ? (
                          <span 
                            className="text-xs text-gray-500 dark:text-gray-400 font-mono truncate max-w-xs cursor-text hover:text-gray-700 dark:hover:text-gray-300"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (!editing.has(secret.key)) {
                                setEditing(new Map(editing).set(secret.key, revealed.get(secret.key) || ''));
                              }
                            }}
                            title="Click to edit"
                          >
                            {revealed.get(secret.key)}
                          </span>
                        ) : (
                          <span 
                            className="text-xs text-gray-400 dark:text-gray-500 cursor-text hover:text-gray-600 dark:hover:text-gray-400"
                            onClick={(e) => {
                              e.stopPropagation();
                              // First reveal, then edit
                              if (!revealed.has(secret.key)) {
                                toggleReveal(secret.key);
                                // After revealing, set edit mode
                                setTimeout(() => {
                                  if (projectName) {
                                    secretApi.get(projectName, secret.key)
                                      .then((secretData) => {
                                        setRevealed(new Map(revealed).set(secret.key, secretData.value));
                                        setEditing(new Map(editing).set(secret.key, secretData.value));
                                      })
                                      .catch((error) => logError(error, 'ProjectView: Reveal secret'));
                                  }
                                }, 100);
                              }
                            }}
                            title="Click to reveal and edit"
                          >
                            ••••••••••••••••
                          </span>
                        )}
                        <div className="flex items-center gap-1 ml-auto" onClick={(e) => e.stopPropagation()}>
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
                            Updated {formatRelativeTime(secret.updated_at)}
                          </span>
                          <button
                            onClick={() => toggleReveal(secret.key)}
                            className={`p-1.5 rounded transition-all ${
                              revealed.has(secret.key)
                                ? 'text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 hover:bg-primary-50 dark:hover:bg-primary-900/20'
                                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700'
                            }`}
                            title={revealed.has(secret.key) ? 'Hide value' : 'Reveal value'}
                          >
                            {revealed.has(secret.key) ? (
                              <EyeOff className="w-3.5 h-3.5" />
                            ) : (
                              <Eye className="w-3.5 h-3.5" />
                            )}
                          </button>
                          <button
                            onClick={() => handleCopySecret(secret.key)}
                            className={`p-1.5 rounded transition-all flex-shrink-0 ${
                              copiedSecretKey === secret.key
                                ? 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 scale-110'
                                : 'text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 hover:bg-primary-50 dark:hover:bg-primary-900/20'
                            }`}
                            title={copiedSecretKey === secret.key ? 'Copied!' : 'Copy secret value'}
                          >
                            {copiedSecretKey === secret.key ? (
                              <Check className="w-3.5 h-3.5" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                          <button
                            onClick={() => handleDeleteSecret(secret.key)}
                            className="p-1.5 text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                            title="Delete secret"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* Tokens Tab */}
      {activeTab === 'tokens' && (
        <>
          {newToken && (
            <div className="card p-6 mb-6 bg-primary-50 dark:bg-primary-900/20 border-primary-200 dark:border-primary-800">
              <h3 className="font-semibold text-primary-900 dark:text-primary-300 mb-2">New Project Token Created</h3>
              <p className="text-sm text-primary-700 dark:text-primary-400 mb-3">
                Save this token now. You won't be able to see it again!
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 px-3 py-2 bg-white dark:bg-gray-800 border border-primary-200 dark:border-primary-800 rounded text-sm text-gray-900 dark:text-gray-100">
                  {newToken}
                </code>
                <button
                  onClick={() => handleCopyToken(newToken)}
                  className={`btn flex items-center gap-2 ${
                    tokenCopied
                      ? 'bg-green-600 hover:bg-green-700 text-white'
                      : 'btn-primary'
                  }`}
                >
                  {tokenCopied ? (
                    <>
                      <Check className="w-4 h-4" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4" />
                      Copy
                    </>
                  )}
                </button>
                <button
                  onClick={() => setNewToken(null)}
                  className="btn btn-secondary"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Project Tokens</h2>
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
            ) : !tokens || tokens.length === 0 ? (
              <div className="p-12 text-center">
                <p className="text-gray-500 dark:text-gray-400">No tokens yet. Create your first token to get started.</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {tokens.map((token) => {
                  try {
                    return (
                      <div key={token.id} className="px-3 py-1 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-medium text-xs font-mono text-gray-900 dark:text-gray-100">
                            {token.name || '••••••••'}
                          </span>
                          <div className="flex items-center gap-1 ml-auto" onClick={(e) => e.stopPropagation()}>
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
                              {token.last_used ? `Last used ${formatRelativeTime(token.last_used)}` : 'Never used'}
                            </span>
                            <button
                              onClick={() => handleRevokeToken(token.id)}
                              className="p-1.5 text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                              title="Revoke token"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  } catch (error) {
                    logError(error, 'ProjectView: Render token');
                    return (
                      <div key={token.id} className="px-4 py-3">
                        <p className="text-red-500 text-sm">Error displaying token {token.id}</p>
                      </div>
                    );
                  }
                })}
              </div>
            )}
          </div>
        </>
      )}

      {/* Devices Tab */}
      {activeTab === 'devices' && (
        <>
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Devices</h2>
            </div>
            <div className="text-xs text-gray-400 dark:text-gray-500">
              {devices.length} device{devices.length !== 1 ? 's' : ''}
            </div>
          </div>

          {/* Auto-Approval Policy */}
          <div className="card mb-4">
            <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <div>
                <h3 className="text-xs font-semibold text-gray-900 dark:text-gray-100">Auto-Approval Policy</h3>
                <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
                  Devices with tags containing any of these patterns will be automatically approved
                </p>
              </div>
            </div>
            <div className="p-2.5">
              {/* Existing patterns as badges */}
              {autoApprovalPatterns.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {autoApprovalPatterns.map((pattern) => (
                    <span
                      key={pattern}
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300"
                    >
                      {pattern}
                      <button
                        onClick={() => handleRemovePattern(pattern)}
                        disabled={savingAutoApproval}
                        className="hover:bg-blue-200 dark:hover:bg-blue-800/50 rounded p-0.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Remove pattern"
                      >
                        <X className="w-2.5 h-2.5" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
              
              {/* Add new pattern */}
              <div className="flex items-center gap-1.5">
                <input
                  type="text"
                  value={newPatternInput}
                  onChange={(e) => setNewPatternInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddPattern();
                    }
                  }}
                  placeholder="Enter tag pattern"
                  className="input text-xs py-1 px-2 flex-1 h-7"
                  disabled={savingAutoApproval}
                />
                <button
                  onClick={handleAddPattern}
                  disabled={!newPatternInput.trim() || autoApprovalPatterns.includes(newPatternInput.trim()) || savingAutoApproval}
                  className="btn btn-secondary text-xs py-1 px-2 h-7 flex items-center gap-1"
                >
                  {savingAutoApproval ? (
                    <span className="animate-spin text-[10px]">⏳</span>
                  ) : (
                    <Plus className="w-3 h-3" />
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Devices List */}
          <div className="card">
            {devicesLoading ? (
              <div className="p-12 text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
                <p className="text-gray-500 dark:text-gray-400 mt-4">Loading devices...</p>
              </div>
            ) : devices.length === 0 ? (
              <div className="p-12 text-center">
                <Monitor className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
              <p className="text-gray-500 dark:text-gray-400 mb-2">
                No devices registered yet.
              </p>
              <p className="text-xs text-gray-400 dark:text-gray-500">
                Devices register by calling POST /api/devices with project_name. They start as pending and require manual approval.
              </p>
              </div>
            ) : (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {devices.map((device) => {
                  let deviceInfo = null;
                  try {
                    if (device.device_info) {
                      deviceInfo = JSON.parse(device.device_info);
                    }
                  } catch (e) {
                    // Ignore parse errors
                  }

                  const getStatusBadge = () => {
                    switch (device.status) {
                      case 'authorized':
                        return (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
                            <CheckCircle className="w-3 h-3" />
                            Authorized
                          </span>
                        );
                      case 'pending':
                        return (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">
                            <AlertCircle className="w-3 h-3" />
                            Pending
                          </span>
                        );
                      default:
                        return null;
                    }
                  };

                  return (
                    <div 
                      key={device.id} 
                      className="px-3 py-1 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer"
                      onClick={() => setSelectedDevice(device)}
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        {/* Device Name */}
                        <span className="font-semibold text-xs text-gray-900 dark:text-gray-100">
                          {device.name}
                        </span>
                        
                        {/* IP Address */}
                        <span className="font-medium text-xs text-gray-900 dark:text-gray-100">
                          {deviceInfo?.ip || 'N/A'}
                        </span>
                        
                        {/* User Agent */}
                        <span className="text-xs text-gray-600 dark:text-gray-400">
                          {deviceInfo?.user_agent || 'Unknown'}
                        </span>
                        
                        {/* Working Directory */}
                        <span className="text-xs text-gray-500 dark:text-gray-500 font-mono">
                          {deviceInfo?.working_directory || 'N/A'}
                        </span>
                        
                        {/* Last Active Badge and Status Badge - Right Aligned */}
                        <div className="ml-auto flex items-center gap-2">
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
                            Last active {formatRelativeTime(device.updated_at)}
                          </span>
                          {getStatusBadge()}
                        </div>
                        
                        {/* Actions */}
                        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                          {device.status === 'pending' && (
                            <>
                              <button
                                onClick={() => handleAuthorizeDevice(device.id)}
                                className="p-1.5 text-green-600 dark:text-green-400 hover:text-green-700 dark:hover:text-green-300 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors"
                                title="Authorize"
                              >
                                <CheckCircle className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleRejectDevice(device.id)}
                                className="p-1.5 text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                                title="Reject"
                              >
                                <XCircle className="w-3.5 h-3.5" />
                              </button>
                            </>
                          )}
                          <button
                            onClick={() => handleDeleteDevice(device.id)}
                            className="p-1.5 text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}

      {/* Activity Tab */}
      {activeTab === 'activity' && (
        <>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Activity History</h2>
            <div className="flex items-center gap-4">
              {/* Activity Filter: All / Remote & MCP / MCP Only - 3-state toggle */}
              <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-700 rounded-md p-1">
                <button
                  onClick={() => setActivityFilter('all')}
                  className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                    activityFilter === 'all'
                      ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-gray-100 shadow-sm'
                      : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                  }`}
                >
                  All
                </button>
                <button
                  onClick={() => setActivityFilter('exclude_ui')}
                  className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                    activityFilter === 'exclude_ui'
                      ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-gray-100 shadow-sm'
                      : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                  }`}
                >
                  Remote & MCP
                </button>
                <button
                  onClick={() => setActivityFilter('mcp_only')}
                  className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                    activityFilter === 'mcp_only'
                      ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-gray-100 shadow-sm'
                      : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                  }`}
                >
                  MCP Only
                </button>
              </div>
            </div>
          </div>

          <div className="card">
            {activitiesLoading ? (
              <div className="p-12 text-center">
                <p className="text-gray-500 dark:text-gray-400">Loading activities...</p>
              </div>
            ) : !activities || activities.length === 0 ? (
              <div className="p-12 text-center">
                <Clock className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
                <p className="text-gray-500 dark:text-gray-400">
                  {activityFilter === 'mcp_only' 
                    ? 'No MCP activities in the last 7 days.' 
                    : activityFilter === 'exclude_ui'
                    ? 'No Remote or MCP activities in the last 7 days.'
                    : 'No activities in the last 7 days.'}
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
                  let mcpClient = null; // MCP client info (name/title)
                  let source = null;
                  let exposedConfidentialData = false;
                  if (activity.request_data) {
                    try {
                      const requestData = JSON.parse(activity.request_data);
                      clientIp = requestData.client_ip || null;
                      source = requestData.source || null;
                      // Extract MCP tool information
                      if (requestData.mcp) {
                        mcpTool = requestData.mcp.tool || null;
                        mcpArguments = requestData.mcp.arguments || null;
                        // Extract MCP client info (name or title)
                        if (requestData.mcp.client) {
                          mcpClient = requestData.mcp.client.name || requestData.mcp.client.title || null;
                        }
                      }
                    } catch {
                      // Ignore parse errors
                    }
                  }
                  // Fallback: if method is MCP but no client_ip found, use "MCP"
                  if (!clientIp && activity.method === 'MCP') {
                    clientIp = 'MCP';
                  }
                  
                  // Check if confidential data was exposed
                  // Note: _confidential_fields is no longer stored, we only have the flag
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
                        
                        {/* 2. API or MCP Badge */}
                        {activity.method === 'MCP' ? (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-indigo-100 dark:bg-indigo-900/30 text-indigo-800 dark:text-indigo-300">
                            MCP
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300">
                            API
                          </span>
                        )}
                        
                        {/* 3. Client IP / MCP Client / UI Badge */}
                        {activity.method === 'MCP' ? (
                          // MCP activities - show client name if available
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
                        
                        {/* 4. Command: HTTP Method (GET/POST) or MCP Tool */}
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
                        
                        {/* 5. API URL/Path */}
                        <span className="text-xs font-medium text-gray-900 dark:text-gray-100 font-mono">
                          {activity.path}
                        </span>
                        
                        {/* 6. Latency (Execution Time) */}
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
                  {activitiesLoadingMore && (
                    <div className="px-3 py-4 text-center">
                      <p className="text-xs text-gray-500 dark:text-gray-400">Loading more...</p>
                    </div>
                  )}
                  {!activitiesHasMore && activities.length > 0 && (
                    <div className="px-3 py-4 text-center">
                      <p className="text-xs text-gray-400 dark:text-gray-500">No more activities</p>
                    </div>
                  )}
                </div>
            )}
          </div>
        </>
      )}

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

      {/* Device Details Modal */}
      {selectedDevice && (() => {
        let deviceInfo = null;
        try {
          if (selectedDevice.device_info) {
            deviceInfo = JSON.parse(selectedDevice.device_info);
          }
        } catch (e) {
          // Ignore parse errors
        }

        const getStatusBadge = () => {
          switch (selectedDevice.status) {
            case 'authorized':
              return (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
                  <CheckCircle className="w-3 h-3" />
                  Authorized
                </span>
              );
            case 'pending':
              return (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">
                  <AlertCircle className="w-3 h-3" />
                  Pending
                </span>
              );
            default:
              return null;
          }
        };

        return (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setSelectedDevice(null)}>
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
              <div className="sticky top-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-3 py-1.5 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Device Details</h3>
                <button
                  onClick={() => setSelectedDevice(null)}
                  className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded transition-colors"
                >
                  <XCircle className="w-4 h-4" />
                </button>
              </div>
              <div className="p-3 space-y-2">
                {/* Timestamps */}
                <div className="flex items-center gap-3 flex-wrap">
                  <div>
                    <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Registered</label>
                    <div className="mt-0.5 text-xs text-gray-900 dark:text-gray-100">
                      {new Date(selectedDevice.created_at).toLocaleString()}
                    </div>
                  </div>
                  {selectedDevice.authorized_at && (
                    <div>
                      <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Authorized</label>
                      <div className="mt-0.5 text-xs text-gray-900 dark:text-gray-100">
                        {new Date(selectedDevice.authorized_at).toLocaleString()}
                      </div>
                    </div>
                  )}
                  {selectedDevice.rejected_at && (
                    <div>
                      <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Rejected</label>
                      <div className="mt-0.5 text-xs text-gray-900 dark:text-gray-100">
                        {new Date(selectedDevice.rejected_at).toLocaleString()}
                      </div>
                    </div>
                  )}
                </div>

                {/* Raw Device Info */}
                {selectedDevice.device_info && (
                  <div className="border-t border-gray-200 dark:border-gray-700 pt-2">
                    <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-0.5 block">Raw JSON</label>
                    <div className="p-1 bg-gray-50 dark:bg-gray-900 rounded text-xs font-mono overflow-auto max-h-32 border border-gray-200 dark:border-gray-700">
                      {(() => {
                        try {
                          const data = JSON.parse(selectedDevice.device_info);
                          return <JsonTree data={data} defaultExpanded={true} />;
                        } catch {
                          return <span className="text-gray-900 dark:text-gray-100">{selectedDevice.device_info}</span>;
                        }
                      })()}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
};

export default ProjectView;



