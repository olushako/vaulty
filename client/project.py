"""
Project information client
Get project information using device_token
"""

import requests
from typing import Optional, Dict, Any
from .device_token import get_device_token


def get_project_info(api_url: str) -> Dict[str, Any]:
    """
    Get project information for the current device_token.
    Since device_token is tied to a specific project, this returns that project.
    Automatically uses device_token for authentication.
    
    Args:
        api_url: Base URL of the Vaulty API (e.g., "http://localhost:8000")
    
    Returns:
        Dictionary with project information or error details
    """
    # Automatically use device_token for authentication
    device_token = get_device_token()
    headers = {"Authorization": f"Bearer {device_token}"}
    
    try:
        # List projects - device_token will only return its own project
        response = requests.get(
            f"{api_url}/api/projects",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 401:
            return {
                "success": False,
                "error": "Authentication failed",
                "message": "Invalid or expired device_token. Device may not be authorized."
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
        
        projects = response.json()
        
        # Device token should only have access to one project
        if len(projects) == 0:
            return {
                "success": False,
                "error": "No project found",
                "message": "Device is not associated with any project. Please register the device first."
            }
        
        if len(projects) > 1:
            # This shouldn't happen, but handle it
            return {
                "success": False,
                "error": "Multiple projects found",
                "message": f"Device has access to multiple projects: {[p.get('name') for p in projects]}"
            }
        
        project = projects[0]
        project_name = project.get("name")
        
        # Get stats (secrets_count, tokens_count, devices_count) to match MCP output
        stats = {
            "secrets_count": 0,
            "tokens_count": 0,
            "devices_count": 0
        }
        
        # Get secrets count
        try:
            secrets_response = requests.get(
                f"{api_url}/api/projects/{project_name}/secrets",
                headers=headers,
                timeout=10
            )
            if secrets_response.status_code == 200:
                stats["secrets_count"] = len(secrets_response.json())
        except:
            pass
        
        # Get tokens count
        try:
            tokens_response = requests.get(
                f"{api_url}/api/projects/{project_name}/tokens",
                headers=headers,
                timeout=10
            )
            if tokens_response.status_code == 200:
                stats["tokens_count"] = len(tokens_response.json())
        except:
            pass
        
        # Get devices count
        try:
            devices_response = requests.get(
                f"{api_url}/api/projects/{project_name}/devices",
                headers=headers,
                timeout=10
            )
            if devices_response.status_code == 200:
                stats["devices_count"] = len(devices_response.json())
        except:
            pass
        
        # Add stats to project dict to match MCP output structure
        project_with_stats = {
            **project,
            "stats": stats
        }
        
        return {
            "success": True,
            "project": project_with_stats,
            "project_name": project_name,
            "project_id": project.get("id"),
            "message": f"Project '{project_name}' found"
        }
        
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to connect to API: {str(e)}",
            "message": f"Could not reach Vaulty API at {api_url}"
        }


def get_project_name(api_url: str) -> Optional[str]:
    """
    Get project name for the current device_token.
    Convenience function that returns just the project name.
    
    Args:
        api_url: Base URL of the Vaulty API
    
    Returns:
        Project name if found, None otherwise
    """
    result = get_project_info(api_url)
    if result.get('success'):
        return result.get('project_name')
    return None

