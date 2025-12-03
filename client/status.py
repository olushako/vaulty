"""
Device status checking client
Check device registration status in Vaulty
"""

import requests
from typing import Optional, Dict, Any
from .device_token import get_device_id


def check_device_status(
    api_url: str,
    project_name: str,
    device_id: Optional[str] = None,
    device_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check device registration status in a Vaulty project.
    Automatically uses device_token for authentication.
    
    Args:
        api_url: Base URL of the Vaulty API (e.g., "http://localhost:8000")
        project_name: Name of the project
        device_id: Device ID (32-char hex) to check. If None, uses current device_id.
        device_name: Device name to check (alternative to device_id)
    
    Returns:
        Dictionary with device status information or error details
    """
    from .device_token import get_device_id, get_device_token
    
    # If device_id not provided, use current device_id
    if device_id is None:
        device_id = get_device_id()
    
    # Automatically use device_token for authentication
    device_token = get_device_token(device_id)
    headers = {"Authorization": f"Bearer {device_token}"}
    
    # If device_name is provided, we need to list devices and find by name
    if device_name:
        try:
            # List devices in project (using device_token for auth)
            response = requests.get(
                f"{api_url}/api/projects/{project_name}/devices",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 401:
                return {
                    "success": False,
                    "error": "Authentication failed",
                    "message": "Invalid or expired authentication token"
                }
            
            if response.status_code == 404:
                return {
                    "success": False,
                    "error": "Project not found",
                    "message": f"Project '{project_name}' does not exist"
                }
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"API error (HTTP {response.status_code})",
                    "message": response.text
                }
            
            devices = response.json()
            
            # Find device by name
            matching_device = None
            for device in devices:
                if device.get("name") == device_name:
                    matching_device = device
                    break
            
            if not matching_device:
                return {
                    "success": False,
                    "error": "Device not found",
                    "message": f"Device '{device_name}' not found in project '{project_name}'"
                }
            
            return {
                "success": True,
                "device": matching_device,
                "status": matching_device.get("status"),
                "message": f"Device '{device_name}' found in project '{project_name}'"
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Failed to connect to API: {str(e)}",
                "message": f"Could not reach Vaulty API at {api_url}"
            }
    
    # Check by device_token - use /api/auth/me to get device info
    try:
        # Get device info from auth endpoint
        auth_response = requests.get(
            f"{api_url}/api/auth/me",
            headers=headers,
            timeout=10
        )
        
        if auth_response.status_code == 401:
            return {
                "success": False,
                "error": "Authentication failed",
                "message": "Invalid or expired device_token. Device may not be registered or authorized."
            }
        
        if auth_response.status_code == 200:
            auth_info = auth_response.json()
            if auth_info.get("token_type") == "device":
                # Device is registered and authorized
                device_id_db = auth_info.get("device_id")
                device_name_from_auth = auth_info.get("device_name")
                
                # Get full device details by listing devices and finding by database ID
                devices_response = requests.get(
                    f"{api_url}/api/projects/{project_name}/devices",
                    headers=headers,
                    timeout=10
                )
                
                if devices_response.status_code == 200:
                    devices = devices_response.json()
                    # Find device by database ID
                    matching_device = None
                    for device in devices:
                        if device.get("id") == device_id_db:
                            matching_device = device
                            break
                    
                    if matching_device:
                        return {
                            "success": True,
                            "device": matching_device,
                            "status": matching_device.get("status"),
                            "message": f"Device '{matching_device.get('name')}' is registered and authorized"
                        }
                    else:
                        # Device exists (auth works) but not in list (shouldn't happen)
                        return {
                            "success": True,
                            "device": {
                                "id": device_id_db,
                                "name": device_name_from_auth,
                                "status": "authorized"
                            },
                            "status": "authorized",
                            "message": f"Device '{device_name_from_auth}' is registered and authorized"
                        }
        
        # Fallback: if auth works, device is registered
        # Try to access project to verify
        project_response = requests.get(
            f"{api_url}/api/projects/{project_name}",
            headers=headers,
            timeout=10
        )
        
        if project_response.status_code == 200:
            return {
                "success": True,
                "device": {
                    "status": "authorized"
                },
                "status": "authorized",
                "message": f"Device is registered and authorized in project '{project_name}'"
            }
        else:
            return {
                "success": False,
                "error": "Device not found",
                "message": f"Device not found or not authorized in project '{project_name}'"
            }
        
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to connect to API: {str(e)}",
            "message": f"Could not reach Vaulty API at {api_url}"
        }


def list_devices(
    api_url: str,
    project_name: str,
    status_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    List all devices in a project.
    Automatically uses device_token for authentication.
    
    Args:
        api_url: Base URL of the Vaulty API
        project_name: Name of the project
        status_filter: Optional filter by status: 'pending', 'authorized', 'rejected'
    
    Returns:
        Dictionary with list of devices or error details
    """
    from .device_token import get_device_token
    
    # Automatically use device_token for authentication
    device_token = get_device_token()
    headers = {"Authorization": f"Bearer {device_token}"}
    
    params = {}
    if status_filter:
        params["status_filter"] = status_filter
    
    try:
        response = requests.get(
            f"{api_url}/api/projects/{project_name}/devices",
            headers=headers,
            params=params,
            timeout=10
        )
        
        if response.status_code == 401:
            return {
                "success": False,
                "error": "Authentication failed",
                "message": "Invalid or expired authentication token"
            }
        
        if response.status_code == 404:
            return {
                "success": False,
                "error": "Project not found",
                "message": f"Project '{project_name}' does not exist"
            }
        
        if response.status_code != 200:
            try:
                error_detail = response.json()
            except:
                error_detail = {"detail": response.text}
            return {
                "success": False,
                "error": f"API error (HTTP {response.status_code})",
                "message": error_detail.get("detail", "Unknown error")
            }
        
        devices = response.json()
        
        return {
            "success": True,
            "devices": devices,
            "count": len(devices),
            "message": f"Found {len(devices)} device(s) in project '{project_name}'"
        }
        
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to connect to API: {str(e)}",
            "message": f"Could not reach Vaulty API at {api_url}"
        }

