export interface Project {
  id: string; // 16-char hex ID
  name: string;
  description: string | null;
  auto_approval_tag_pattern: string | null; // Tag pattern for auto-approving devices
  created_at: string;
}

export interface Token {
  id: string; // 16-char hex ID
  project_id: string; // 16-char hex ID
  name: string;
  token?: string; // Only present on creation
  created_at: string;
  last_used: string | null;
}

export interface Secret {
  key: string;
  created_at: string;
  updated_at: string;
}

export interface SecretValue {
  key: string;
  value: string;
}

export interface MasterToken {
  id: string; // 16-char hex ID
  name: string;
  token?: string; // Only present on creation
  created_at: string;
  last_used: string | null;
  is_init_token: boolean; // True if this is the initialization token (from MASTER_TOKEN env)
  is_current_token: boolean; // True if this is the token currently being used for authentication
}

export interface ProjectCreate {
  name: string;
  description?: string;
}

export interface TokenCreate {
  name: string;
}

export interface SecretCreate {
  key: string;
  value: string;
}

export interface MasterTokenCreate {
  name: string;
}

export interface Activity {
  id: string; // 16-char hex ID
  method: string;
  path: string;
  action: string;
  project_name: string | null;
  token_type: string;
  status_code: number;
  execution_time_ms: number | null;
  request_data: string | null;
  response_data: string | null;
  created_at: string;
}

export interface ActivityListResponse {
  activities: Activity[];
  total: number;
  has_more: boolean;
}

export interface Device {
  id: string; // 16-char hex ID
  name: string;
  status: 'pending' | 'authorized' | 'rejected';
  device_info: string | null; // JSON string
  created_at: string;
  updated_at: string;
  authorized_at: string | null;
  authorized_by: string | null;
  rejected_at: string | null;
  rejected_by: string | null;
}

export interface DeviceCreate {
  name: string;
  device_id?: string;
  project_name: string; // Required
  
  // Mandatory fields (from client)
  user_agent: string; // Used to detect OS server-side
  working_directory: string;
  
  // Optional fields
  tags?: string[];
  description?: string;
  
  // Note: IP and OS are detected server-side from the request
}








