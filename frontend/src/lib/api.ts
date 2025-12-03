import axios from 'axios';
import type {
  Project,
  Token,
  Secret,
  SecretValue,
  MasterToken,
  ProjectCreate,
  TokenCreate,
  SecretCreate,
  MasterTokenCreate,
  Activity,
  ActivityListResponse,
  Device,
  DeviceCreate,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

import { CACHE_EXPIRATION_MS } from './utils/constants';

// Token cache management
const AUTH_TOKEN_KEY = 'authToken';
const AUTH_TOKEN_TIMESTAMP_KEY = 'authTokenTimestamp';

export const setAuthToken = (token: string | null) => {
  if (token) {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    localStorage.setItem(AUTH_TOKEN_TIMESTAMP_KEY, Date.now().toString());
  } else {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_TOKEN_TIMESTAMP_KEY);
  }
};

export const getAuthToken = (): string | null => {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  const timestamp = localStorage.getItem(AUTH_TOKEN_TIMESTAMP_KEY);
  
  if (!token || !timestamp) {
    return null;
  }
  
  // Check if token has expired (older than 3 hours)
  const tokenAge = Date.now() - parseInt(timestamp, 10);
  if (tokenAge > CACHE_EXPIRATION_MS) {
    // Token expired, clear it
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_TOKEN_TIMESTAMP_KEY);
    return null;
  }
  
  return token;
};

// Note: clearExpiredAuthToken was removed as it was redundant
// getAuthToken() already handles token expiration checking and clearing

export const logout = (): void => {
  // Clear the auth token and timestamp
  setAuthToken(null);
  // Redirect to auth page
  window.location.href = '/auth';
};

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = getAuthToken(); // Use getAuthToken to check expiration
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle expired/invalid tokens in responses
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // If we get a 401 (Unauthorized), the token is invalid/expired
    if (error.response?.status === 401) {
      // Clear expired token
      setAuthToken(null);
      // Redirect to auth page if we're not already there
      if (window.location.pathname !== '/auth') {
        window.location.href = '/auth';
      }
    }
    return Promise.reject(error);
  }
);

// Master Token APIs
export const masterTokenApi = {
  create: (data: MasterTokenCreate): Promise<MasterToken> =>
    api.post('/master-tokens', data).then((res) => res.data),
  
  list: (): Promise<MasterToken[]> =>
    api.get('/master-tokens').then((res) => res.data),
  
  revoke: (id: string): Promise<void> =>
    api.delete(`/master-tokens/${id}`).then(() => undefined),
  
  rotate: (id: string): Promise<MasterToken> =>
    api.post(`/master-tokens/${id}/rotate`).then((res) => res.data),
};

// Database APIs
export const databaseApi = {
  getInfo: (): Promise<{
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
  }> => api.get('/auth/database/info').then((res) => res.data),
};

// Status APIs
export const statusApi = {
  getSystemStatus: (): Promise<{
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
  }> => api.get('/auth/status').then((res) => res.data),
};

// Project APIs
export const projectApi = {
  create: (data: ProjectCreate): Promise<Project> =>
    api.post('/projects', data).then((res) => res.data),
  
  list: (): Promise<Project[]> =>
    api.get('/projects').then((res) => res.data),
  
  get: (projectName: string): Promise<Project> =>
    api.get(`/projects/${projectName}`).then((res) => res.data),
  
  update: (projectName: string, data: { auto_approval_tag_pattern?: string | null }): Promise<Project> =>
    api.patch(`/projects/${projectName}`, data).then((res) => res.data),
  
  delete: (projectName: string): Promise<void> =>
    api.delete(`/projects/${projectName}`).then(() => undefined),
};

// Token APIs
export const tokenApi = {
  create: (projectName: string, data: TokenCreate): Promise<Token> =>
    api.post(`/projects/${projectName}/tokens`, data).then((res) => res.data),
  
  list: (projectName: string): Promise<Token[]> =>
    api.get(`/projects/${projectName}/tokens`).then((res) => res.data),
  
  revoke: (id: string): Promise<void> =>
    api.delete(`/tokens/${id}`).then(() => undefined),
};

// Secret APIs
export const secretApi = {
  create: (projectName: string, data: SecretCreate): Promise<Secret> =>
    api.post(`/projects/${projectName}/secrets`, data).then((res) => res.data),
  
  get: (projectName: string, key: string): Promise<SecretValue> =>
    api.get(`/projects/${projectName}/secrets/${key}`).then((res) => res.data),
  
  list: (projectName: string): Promise<Secret[]> =>
    api.get(`/projects/${projectName}/secrets`).then((res) => res.data),
  
  delete: (projectName: string, key: string): Promise<void> =>
    api.delete(`/projects/${projectName}/secrets/${key}`).then(() => undefined),
};

// Activity APIs
export const activityApi = {
  getDailyStats: (projectName?: string, source?: string): Promise<{ daily_stats: Array<any>; source?: string; avg_response_time_ms?: number | null; paths?: string[] }> => {
    const params: any = {};
    if (projectName) params.project_name = projectName;
    if (source) params.source = source;
    return api.get('/dashboard/daily-stats', { params }).then((res) => res.data);
  },
  getProjectStats: (): Promise<{ project_stats: Array<{ project_name: string; total: number; mcp: number; api: number }> }> =>
    api.get('/dashboard/project-stats').then((res) => res.data),
  getRecent: (limit: number = 25): Promise<ActivityListResponse> =>
    api.get('/activities/recent', { params: { limit } }).then((res) => res.data),
  // Get all activities (master token only)
  listAll: async (limit: number = 25, offset: number = 0, method?: string, exposedOnly?: boolean, breakdown?: string, breakdownValue?: string, source?: string): Promise<ActivityListResponse> => {
    const params: { limit: number; offset: number; method?: string; exposed_only?: boolean; breakdown?: string; breakdown_value?: string; source?: string } = { limit, offset };
    if (method) {
      params.method = method;
    }
    if (exposedOnly) {
      params.exposed_only = true;
    }
    if (breakdown) {
      params.breakdown = breakdown;
    }
    if (breakdownValue) {
      params.breakdown_value = breakdownValue;
    }
    if (source) {
      params.source = source;
    }
    const response = await api.get<ActivityListResponse>('/activities', {
      params,
    });
    return response.data;
  },
  list: (projectName: string, limit: number = 25, offset: number = 0, method?: string, excludeUi?: boolean): Promise<ActivityListResponse> => {
    const params: { limit: number; offset: number; method?: string; exclude_ui?: boolean } = { limit, offset };
    if (method) {
      params.method = method;
    }
    if (excludeUi) {
      params.exclude_ui = true;
    }
    return api.get(`/projects/${projectName}/activities`, {
      params
    }).then((res) => res.data);
  },
  
  flush: (projectName: string): Promise<{ deleted: number; message: string }> =>
    api.delete(`/projects/${projectName}/activities`).then((res) => res.data),
  
  flushAll: (): Promise<{ deleted: number; message: string }> =>
    api.delete('/activities').then((res) => res.data),
  
  getStats: (projectName?: string): Promise<{
    total_activities: number;
    mcp_activities: number;
    exposed_data_count: number;
    mcp_exposed_data_count: number;
  }> => {
    const params = projectName ? { project_name: projectName } : {};
    return api.get('/activities/stats', { params }).then((res) => res.data);
  },
  
  getDashboardStats: (): Promise<{
    projects: number;
    secrets: number;
    tokens: number;
    authorized_devices: number;
    events_last_week: number;
    mcp_activities: number;
    exposed_data_count: number;
    mcp_exposed_data_count: number;
    avg_response_time_ms: number | null;
  }> => {
    return api.get('/dashboard/stats').then((res) => res.data);
  },
};

// Device APIs
export const deviceApi = {
  create: (data: DeviceCreate): Promise<Device> =>
    api.post('/devices', data).then((res) => res.data),
  
  list: (projectName: string, statusFilter?: 'pending' | 'authorized' | 'rejected'): Promise<Device[]> => {
    const params = statusFilter ? { status_filter: statusFilter } : {};
    return api.get(`/projects/${projectName}/devices`, { params }).then((res) => res.data);
  },
  
  get: (projectName: string, deviceId: string): Promise<Device> =>
    api.get(`/projects/${projectName}/devices/${deviceId}`).then((res) => res.data),
  
  authorize: (projectName: string, deviceId: string): Promise<Device> =>
    api.patch(`/projects/${projectName}/devices/${deviceId}/authorize`).then((res) => res.data),
  
  reject: (projectName: string, deviceId: string): Promise<void> =>
    api.patch(`/projects/${projectName}/devices/${deviceId}/reject`).then(() => undefined),
  
  delete: (projectName: string, deviceId: string): Promise<void> =>
    api.delete(`/projects/${projectName}/devices/${deviceId}`).then(() => undefined),
};

// Auth APIs
export interface AuthInfo {
  token_type: 'master' | 'project';
  token_name: string;
  is_master: boolean;
  project_id?: string;
}

export const authApi = {
  getCurrentAuth: (): Promise<AuthInfo> =>
    api.get('/auth/me').then((res) => res.data),
};

export default api;


