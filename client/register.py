"""
Device registration client
Registers a device with Vaulty and polls for authorization
"""

import time
import requests
from typing import Optional, Dict, Any
from .device_token import get_device_id, get_device_token


def register_device(
    api_url: str,
    project_name: str,
    name: Optional[str] = None,
    user_agent: Optional[str] = None,
    working_directory: Optional[str] = None,
    tags: Optional[list] = None,
    description: Optional[str] = None,
    auth_token: Optional[str] = None,
    max_wait_time: int = 300,
    poll_interval: int = 1,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Register a device in a Vaulty project and wait for authorization.
    
    Args:
        api_url: Base URL of the Vaulty API (e.g., "http://localhost:8000")
        project_name: Name of the project to register the device in
        name: Device name/identifier (optional, auto-generated from working directory if not provided)
        user_agent: User agent string (defaults to system user agent)
        working_directory: Current working directory (defaults to os.getcwd())
        tags: Optional list of tags for categorization
        description: Optional description of the device
        auth_token: Optional authentication token for activity logging and automatic rejection on timeout
        max_wait_time: Maximum time to wait for authorization in seconds (default: 300 = 5 minutes)
        poll_interval: Interval between status checks in seconds (default: 1)
        verbose: Whether to print status messages (default: True)
    
    Returns:
        Dictionary with registration result containing:
        - success: bool
        - message: str
        - device: dict with device info
        - wait_time_seconds: int (if polling occurred)
        - note: str
    """
    import os
    
    # Get device_id and device_token
    device_id = get_device_id()
    
    # Auto-generate device name from working directory if not provided
    if name is None:
        working_dir = os.getcwd() if working_directory is None else working_directory
        # Use the last directory name as device name
        dir_name = os.path.basename(working_dir.rstrip('/'))
        if not dir_name:
            dir_name = os.path.basename(os.path.dirname(working_dir))
        name = f"{dir_name}-{device_id[:8]}"  # Use directory name + first 8 chars of device_id
    
    # Default values
    if user_agent is None:
        user_agent = f"VaultyClient/1.0 ({os.name})"
    if working_directory is None:
        working_directory = os.getcwd()
    
    # Build request payload
    payload = {
        "project_name": project_name,
        "name": name,
        "user_agent": user_agent,
        "working_directory": working_directory,
        "device_id": device_id
    }
    
    # Add optional fields
    if tags:
        payload["tags"] = tags
    if description:
        payload["description"] = description
    
    # Register device
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    if verbose:
        print(f"Registering device '{name}' in project '{project_name}'...")
        print(f"Device ID: {device_id}")
    
    try:
        response = requests.post(
            f"{api_url}/api/devices",
            json=payload,
            headers=headers,
            timeout=30
        )
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to connect to API: {str(e)}",
            "message": f"Could not reach Vaulty API at {api_url}"
        }
    
    if response.status_code == 404:
        return {
            "success": False,
            "error": "Project not found",
            "message": f"Project '{project_name}' does not exist. Please create the project first.",
            "project_name": project_name,
            "suggestion": "Use the create_project API endpoint to create the project before registering devices."
        }
    
    if response.status_code not in [200, 201]:
        try:
            error_detail = response.json()
        except:
            error_detail = {"detail": response.text}
        return {
            "success": False,
            "error": f"Registration failed (HTTP {response.status_code})",
            "message": error_detail.get("detail", "Unknown error"),
            "status_code": response.status_code
        }
    
    device_data = response.json()
    device_status = device_data.get("status")
    device_id_value = device_data.get("id")
    
    # If device was auto-approved, return success immediately
    if device_status == "authorized":
        if verbose:
            print(f"✓ Device authorized immediately (auto-approved)")
        return {
            "success": True,
            "message": f"Device '{name}' registered and auto-approved in project '{project_name}'",
            "device": {
                "id": device_id_value,
                "name": device_data.get("name"),
                "status": device_status,
                "created_at": device_data.get("created_at"),
                "authorized_at": device_data.get("authorized_at"),
                "authorized_by": device_data.get("authorized_by")
            },
            "note": "Device was auto-approved based on tag patterns. Ready to use."
        }
    
    # Device is pending, poll for status
    if verbose:
        print(f"Device registered as 'pending'. Waiting for authorization...")
        print(f"Polling every {poll_interval} second(s) for up to {max_wait_time} seconds...")
    
    elapsed_time = 0
    final_status = None
    
    while elapsed_time < max_wait_time and final_status is None:
        time.sleep(poll_interval)
        elapsed_time += poll_interval
        
        # Check device status (no auth required for this endpoint)
        try:
            status_response = requests.get(
                f"{api_url}/api/projects/{project_name}/devices/{device_id_value}",
                timeout=10
            )
        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"Warning: Failed to check status: {e}")
            continue
        
        if status_response.status_code == 200:
            current_status = status_response.json().get("status")
            
            if current_status == "authorized":
                # Device was authorized - return success
                final_status = "authorized"
                device_info = status_response.json()
                
                if verbose:
                    print(f"✓ Device authorized after {elapsed_time} seconds")
                return {
                    "success": True,
                    "message": f"Device '{name}' authorized successfully in project '{project_name}'",
                    "device": {
                        "id": device_id_value,
                        "name": device_info.get("name"),
                        "status": current_status,
                        "created_at": device_info.get("created_at"),
                        "authorized_at": device_info.get("authorized_at"),
                        "authorized_by": device_info.get("authorized_by")
                    },
                    "wait_time_seconds": elapsed_time,
                    "note": "Device is now authorized and ready to use."
                }
            elif current_status == "rejected":
                # Device was rejected - return rejection
                final_status = "rejected"
                device_info = status_response.json()
                if verbose:
                    print(f"✗ Device rejected after {elapsed_time} seconds")
                return {
                    "success": False,
                    "message": f"Device '{name}' was rejected in project '{project_name}'",
                    "device": {
                        "id": device_id_value,
                        "name": device_info.get("name"),
                        "status": current_status,
                        "created_at": device_info.get("created_at"),
                        "rejected_at": device_info.get("rejected_at"),
                        "rejected_by": device_info.get("rejected_by")
                    },
                    "wait_time_seconds": elapsed_time,
                    "note": "Device registration was rejected."
                }
            # If still "pending", continue polling
        elif status_response.status_code == 404:
            # Device was deleted/rejected (hard delete)
            final_status = "rejected"
            if verbose:
                print(f"✗ Device was deleted/rejected after {elapsed_time} seconds")
            return {
                "success": False,
                "message": f"Device '{name}' was rejected/deleted in project '{project_name}'",
                "device_id": device_id_value,
                "wait_time_seconds": elapsed_time,
                "status": "rejected",
                "note": "Device was deleted or rejected from the server."
            }
    
    # If timeout reached and still pending, try to reject the device
    if final_status is None:
        if auth_token:
            if verbose:
                print(f"Timeout reached ({elapsed_time} seconds). Attempting to reject device...")
            try:
                reject_response = requests.patch(
                    f"{api_url}/api/projects/{project_name}/devices/{device_id_value}/reject",
                    headers={"Authorization": f"Bearer {auth_token}"},
                    timeout=10
                )
                if reject_response.status_code == 204:
                    if verbose:
                        print(f"✗ Device automatically rejected due to timeout")
                    return {
                        "success": False,
                        "message": f"Device '{name}' was not authorized within {max_wait_time} seconds and has been rejected",
                        "device_id": device_id_value,
                        "wait_time_seconds": elapsed_time,
                        "status": "rejected",
                        "note": "Device registration timed out. Please try again and authorize the device promptly."
                    }
            except:
                pass
        
        if verbose:
            print(f"✗ Timeout: Device not authorized within {max_wait_time} seconds")
        return {
            "success": False,
            "message": f"Device '{name}' was not authorized within {max_wait_time} seconds",
            "device_id": device_id_value,
            "wait_time_seconds": elapsed_time,
            "status": "pending",
            "note": "Device registration timed out. Device is still pending and needs to be manually rejected or authorized." + 
                   ("" if auth_token else " Provide an 'auth_token' to enable automatic rejection on timeout.")
        }

