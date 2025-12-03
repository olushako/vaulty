"""
Secret management client
Get and manage secrets in Vaulty projects
"""

import requests
from typing import Optional, Dict, Any, List
from .device_token import get_device_token


def get_secret(
    api_url: str,
    project_name: str,
    key: str
) -> Dict[str, Any]:
    """
    Get a secret value by key from a project.
    Automatically uses device_token for authentication.
    
    Args:
        api_url: Base URL of the Vaulty API (e.g., "http://localhost:8000")
        project_name: Name of the project
        key: Secret key to retrieve
    
    Returns:
        Dictionary with secret information or error details
    """
    # Automatically use device_token for authentication
    device_token = get_device_token()
    headers = {"Authorization": f"Bearer {device_token}"}
    
    try:
        response = requests.get(
            f"{api_url}/api/projects/{project_name}/secrets/{key}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 404:
            return {
                "success": False,
                "error": "Secret not found",
                "message": f"Secret '{key}' not found in project '{project_name}'"
            }
        
        if response.status_code == 401:
            return {
                "success": False,
                "error": "Authentication failed",
                "message": "Invalid or expired device_token"
            }
        
        if response.status_code == 403:
            return {
                "success": False,
                "error": "Access denied",
                "message": "Device does not have access to this project"
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
        
        secret_data = response.json()
        
        return {
            "success": True,
            "secret": secret_data,
            "key": secret_data.get("key"),
            "value": secret_data.get("value"),
            "created_at": secret_data.get("created_at"),
            "updated_at": secret_data.get("updated_at"),
            "message": f"Secret '{key}' retrieved successfully"
        }
        
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to connect to API: {str(e)}",
            "message": f"Could not reach Vaulty API at {api_url}"
        }


def list_secrets(
    api_url: str,
    project_name: str
) -> Dict[str, Any]:
    """
    List all secrets in a project (keys only, not values).
    Automatically uses device_token for authentication.
    
    Args:
        api_url: Base URL of the Vaulty API
        project_name: Name of the project
    
    Returns:
        Dictionary with list of secrets or error details
    """
    # Automatically use device_token for authentication
    device_token = get_device_token()
    headers = {"Authorization": f"Bearer {device_token}"}
    
    try:
        response = requests.get(
            f"{api_url}/api/projects/{project_name}/secrets",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 401:
            return {
                "success": False,
                "error": "Authentication failed",
                "message": "Invalid or expired device_token"
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
        
        secrets = response.json()
        
        # SECURITY: Explicitly filter to only return keys and metadata, NEVER values
        # Even though API should only return keys, we filter here as an extra safety measure
        filtered_secrets = [
            {
                "key": s.get("key"),
                "created_at": s.get("created_at"),
                "updated_at": s.get("updated_at")
            }
            for s in secrets
        ]
        
        return {
            "success": True,
            "secrets": filtered_secrets,
            "count": len(filtered_secrets),
            "message": f"Found {len(filtered_secrets)} secret(s) in project '{project_name}'"
        }
        
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to connect to API: {str(e)}",
            "message": f"Could not reach Vaulty API at {api_url}"
        }


def check_secret_exists(
    api_url: str,
    project_name: str,
    key: str
) -> Dict[str, Any]:
    """
    Check if a secret exists in a project (without retrieving the value).
    Automatically uses device_token for authentication.
    
    Args:
        api_url: Base URL of the Vaulty API
        project_name: Name of the project
        key: Secret key to check
    
    Returns:
        Dictionary with existence status or error details
    """
    # Automatically use device_token for authentication
    device_token = get_device_token()
    headers = {"Authorization": f"Bearer {device_token}"}
    
    try:
        response = requests.get(
            f"{api_url}/api/projects/{project_name}/secrets/{key}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 404:
            return {
                "success": True,
                "exists": False,
                "message": f"Secret '{key}' does not exist in project '{project_name}'"
            }
        
        if response.status_code == 200:
            return {
                "success": True,
                "exists": True,
                "message": f"Secret '{key}' exists in project '{project_name}'"
            }
        
        if response.status_code == 401:
            return {
                "success": False,
                "error": "Authentication failed",
                "message": "Invalid or expired device_token"
            }
        
        if response.status_code == 403:
            return {
                "success": False,
                "error": "Access denied",
                "message": "Device does not have access to this project"
            }
        
        try:
            error_detail = response.json()
        except:
            error_detail = {"detail": response.text}
        return {
            "success": False,
            "error": f"API error (HTTP {response.status_code})",
            "message": error_detail.get("detail", "Unknown error")
        }
        
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to connect to API: {str(e)}",
            "message": f"Could not reach Vaulty API at {api_url}"
        }

