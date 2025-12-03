"""
Vaulty Client Library
Provides functions for device identification, authentication, registration, status checking, secret management, and project information
"""

from .device_token import get_device_id, get_device_token
from .register import register_device
from .status import check_device_status, list_devices
from .secrets import get_secret, list_secrets, check_secret_exists
from .project import get_project_info, get_project_name

__all__ = [
    'get_device_id', 
    'get_device_token', 
    'register_device', 
    'check_device_status', 
    'list_devices',
    'get_secret',
    'list_secrets',
    'check_secret_exists',
    'get_project_info',
    'get_project_name'
]

