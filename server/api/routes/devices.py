"""Device management routes"""
import json
from fastapi import APIRouter, Depends, HTTPException, status, Security, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ...models import Project, Device, MasterToken
from ...schemas import DeviceCreate, DeviceResponse
from ...auth import get_db, hash_token, get_auth_context
from ...device_id import get_device_id
from ..utils import get_client_ip, detect_os_from_user_agent, get_project_by_name, commit_and_refresh
from ..dependencies import get_project_with_access, get_device_by_id, get_device_by_id_no_auth

router = APIRouter(tags=["devices"])


@router.post("/api/devices", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def register_device(
    device_data: DeviceCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Register a new device.
    
    Devices are always registered as 'pending' and require manual approval.
    After approval, devices authenticate using device_token = SHA256(device_id) (not project tokens).
    Project tokens are for services/applications only, not for devices.
    
    Requires project_name in request body.
    """
    # Require project_name for device registration
    if not device_data.project_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_name is required for device registration."
        )
    
    # Look up project by name
    project = db.query(Project).filter(Project.name == device_data.project_name).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{device_data.project_name}' not found"
        )
    
    # All devices start as pending - require manual approval
    project_id = project.id
    status_value = "pending"
    
    # Device ID must be provided by the client (generated client-side)
    # Device ID is: hash(pwd) + hash(hostname) + MAC
    # Client generates device_id locally and sends it, then hashes it locally to get device_token for auth
    if not device_data.device_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="device_id is required. Generate it client-side using hash(pwd) + hash(hostname) + MAC, then hash it to get device_token (SHA256) for authentication."
        )
    
        # Use provided device ID (generated client-side with actual pwd/hostname/MAC)
        device_id = device_data.device_id.lower().strip()
        # Validate format (32 hex chars)
        if len(device_id) != 32 or not all(c in '0123456789abcdef' for c in device_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid device_id format. Must be 32-character hex string."
            )
    
    # Hash the device_id to create device_token (for security)
    # Client will send device_token = SHA256(device_id) in Authorization header
    device_token = hash_token(device_id)  # SHA256 = 64 hex chars (stored as device_id_hash in DB)
    
    # Check if device already exists (by device_token, stored as device_id_hash in DB)
    existing_device = db.query(Device).filter(
        Device.device_id_hash == device_token
    ).first()
    
    if existing_device:
        # Device already registered - update if needed or return existing
        if existing_device.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device already registered for a different project"
            )
        # Device exists for this project - return it
        db.refresh(existing_device)
        return existing_device
    
    # Detect IP and OS from the request (server-side)
    detected_ip = get_client_ip(request)
    detected_os = detect_os_from_user_agent(device_data.user_agent)
    
    # Build device info from mandatory and optional fields
    device_info_dict = {
        "os": detected_os,  # Detected server-side from user agent
        "ip": detected_ip,  # Detected server-side from request
        "user_agent": device_data.user_agent,
        "working_directory": device_data.working_directory,
    }
    
    # Add optional fields if provided
    if device_data.tags:
        device_info_dict["tags"] = device_data.tags
    if device_data.description:
        device_info_dict["description"] = device_data.description
    
    device_info_json = json.dumps(device_info_dict)
    
    # Check auto-approval policy: if device has tags matching any pattern, auto-approve
    should_auto_approve = False
    if project.auto_approval_tag_pattern and device_data.tags:
        try:
            # Try to parse as JSON array
            patterns = json.loads(project.auto_approval_tag_pattern)
            if not isinstance(patterns, list):
                patterns = [project.auto_approval_tag_pattern]
        except (json.JSONDecodeError, TypeError):
            # If not JSON, treat as comma-separated or single value
            patterns = [p.strip() for p in project.auto_approval_tag_pattern.split(',') if p.strip()]
        
        # Check if any device tag contains any pattern
        for tag in device_data.tags:
            tag_lower = tag.lower()
            for pattern in patterns:
                if pattern.lower() in tag_lower:
                    should_auto_approve = True
                    break
            if should_auto_approve:
                break
    
    if should_auto_approve:
        status_value = "authorized"
        authorized_at = datetime.utcnow()
        authorized_by = "auto_approval_policy"
    else:
        status_value = "pending"
        authorized_at = None
        authorized_by = None
    
    # Create device
    device = Device(
        project_id=project_id,
        device_id_hash=device_token,  # Store device_token (SHA256 of device_id) in DB column device_id_hash
        name=device_data.name,
        token_hash=None,  # Devices don't use project tokens - they use device_token
        status=status_value,
        device_info=device_info_json,
        authorized_at=authorized_at,
        authorized_by=authorized_by
    )
    
    db.add(device)
    device = commit_and_refresh(db, device)
    
    # Device already knows its device_id (provided during registration)
    # Device can hash device_id locally to get device_token for authentication
    # No need to return device_token - device calculates it: device_token = SHA256(device_id)
    return device


@router.get("/api/projects/{project_name}/devices", response_model=List[DeviceResponse])
def list_devices(
    project: Project = Depends(get_project_with_access),
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(None, description="Filter by status: pending, authorized, rejected")
):
    """List devices for a project - requires master token (any project) or project token (own project only)"""
    query = db.query(Device).filter(Device.project_id == project.id)
    
    if status_filter:
        if status_filter not in ["pending", "authorized", "rejected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status filter. Must be: pending, authorized, or rejected"
            )
        query = query.filter(Device.status == status_filter)
    
    devices = query.order_by(Device.created_at.desc()).all()
    return devices


@router.get("/api/projects/{project_name}/devices/{device_id}", response_model=DeviceResponse)
def get_device(
    device: Device = Depends(get_device_by_id_no_auth)
):
    """Get device details - no authentication required (for device status checks during registration)"""
    return device


@router.patch("/api/projects/{project_name}/devices/{device_id}/authorize", response_model=DeviceResponse)
def authorize_device(
    device: Device = Depends(get_device_by_id),
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """Authorize a pending device - requires master token (any project) or project token (own project only)"""
    # If device is already authorized, return it as-is (idempotent)
    if device.status == "authorized":
        db.refresh(device)
        return device
    
    # Get token info for authorized_by
    auth = get_auth_context(credentials, db)
    token_str = credentials.credentials
    
    if auth.is_master:
        master_token = db.query(MasterToken).filter(
            MasterToken.token_hash == hash_token(token_str)
        ).first()
        authorized_by_name = f"master_token:{master_token.id}" if master_token else "master_token:env"
    else:
        authorized_by_name = f"project_token:{auth.token.id}" if auth.token else "project_token"
    
    device.status = "authorized"
    device.authorized_at = datetime.utcnow()
    device.authorized_by = authorized_by_name
    device.rejected_at = None
    device.rejected_by = None
    device.updated_at = datetime.utcnow()
    
    return commit_and_refresh(db, device)


@router.patch("/api/projects/{project_name}/devices/{device_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_device(
    device: Device = Depends(get_device_by_id),
    db: Session = Depends(get_db)
):
    """Reject a pending device - hard deletes it from database but keeps activity log.
    
    Requires master token (any project) or project token (own project only).
    The rejection action will be logged in activities before deletion.
    """
    # Hard delete the device (activity will be logged by middleware)
    db.delete(device)
    db.commit()
    
    return None


@router.delete("/api/projects/{project_name}/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device: Device = Depends(get_device_by_id),
    db: Session = Depends(get_db)
):
    """Delete a device - requires master token (any project) or project token (own project only)"""
    db.delete(device)
    db.commit()
    return None

