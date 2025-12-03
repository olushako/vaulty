from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    auto_approval_tag_pattern: Optional[str] = None  # Tag pattern for auto-approving devices


class ProjectResponse(BaseModel):
    id: str  # 16-char hex ID
    name: str
    description: Optional[str] = None
    auto_approval_tag_pattern: Optional[str] = None  # Tag pattern for auto-approving devices
    created_at: datetime
    
    class Config:
        from_attributes = True


class TokenCreate(BaseModel):
    name: str


class TokenResponse(BaseModel):
    id: str  # 16-char hex ID
    project_id: str  # 16-char hex ID
    name: str
    token: str  # Only returned on creation
    created_at: datetime
    
    class Config:
        from_attributes = True


class TokenInfo(BaseModel):
    id: str  # 16-char hex ID
    project_id: str  # 16-char hex ID
    name: str
    created_at: datetime
    last_used: Optional[datetime]
    
    class Config:
        from_attributes = True


class SecretCreate(BaseModel):
    key: str
    value: str


class SecretResponse(BaseModel):
    key: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SecretValueResponse(BaseModel):
    key: str
    value: str


class MasterTokenCreate(BaseModel):
    # Name is optional - will be auto-generated from token value if not provided
    name: Optional[str] = None


class MasterTokenResponse(BaseModel):
    id: str  # 16-char hex ID
    name: str
    token: str  # Only returned on creation
    created_at: datetime
    
    class Config:
        from_attributes = True


class MasterTokenInfo(BaseModel):
    id: str  # 16-char hex ID
    name: str
    created_at: datetime
    last_used: Optional[datetime]
    is_init_token: bool  # True if this is the initialization token (from MASTER_TOKEN env)
    is_current_token: bool  # True if this is the token currently being used for authentication
    
    class Config:
        from_attributes = True


class ActivityResponse(BaseModel):
    id: str  # 16-char hex ID
    method: str
    path: str
    action: str
    project_name: Optional[str]
    token_type: str
    status_code: int
    execution_time_ms: Optional[int]
    request_data: Optional[str] = None  # JSON string
    response_data: Optional[str] = None  # JSON string
    created_at: datetime
    
    class Config:
        from_attributes = True


class ActivityListResponse(BaseModel):
    activities: List[ActivityResponse]
    total: int
    has_more: bool


class DeviceCreate(BaseModel):
    name: str
    device_id: Optional[str] = None  # Optional: deterministic device ID (hash of pwd + hostname + MAC)
    project_name: str  # Required: project name for device registration
    
    # Mandatory device information (from client)
    user_agent: str  # User agent string (used to detect OS server-side)
    working_directory: str  # Current working directory
    
    # Optional device information
    tags: Optional[List[str]] = None  # Optional tags for categorization
    description: Optional[str] = None  # Optional description
    
    # Note: IP and OS are detected server-side from the request


class DeviceResponse(BaseModel):
    id: str  # 16-char hex ID
    name: str
    status: str  # pending, authorized, rejected
    device_info: Optional[str] = None  # JSON string
    created_at: datetime
    updated_at: datetime
    authorized_at: Optional[datetime] = None
    authorized_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejected_by: Optional[str] = None
    # Note: device_token is not returned - device knows its device_id and can hash it locally: device_token = SHA256(device_id)
    
    class Config:
        from_attributes = True











