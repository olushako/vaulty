"""
Local configuration management for Vaulty client
Stores project name and API URL per working directory
"""

import os
import json
from typing import Optional, Dict


VAULTY_CONFIG_FILE = '.vaulty'


def get_config_path() -> str:
    """Get path to the Vaulty config file in current directory"""
    return os.path.join(os.getcwd(), VAULTY_CONFIG_FILE)


def _load_config() -> Dict:
    """Load config from file, return empty dict if not found or error"""
    config_path = get_config_path()
    
    if not os.path.exists(config_path):
        return {}
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(config: Dict):
    """Save config to file"""
    config_path = get_config_path()
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception:
        # Don't fail if we can't write config
        pass


def save_project_name(project_name: str):
    """
    Save project name to local config file
    
    Args:
        project_name: Name of the project for this working directory
    """
    config = _load_config()
    config['project_name'] = project_name
    _save_config(config)


def get_project_name() -> Optional[str]:
    """
    Get project name from local config file
    
    Returns:
        Project name if found, None otherwise
    """
    config = _load_config()
    return config.get('project_name')


def save_api_url(api_url: str):
    """
    Save API URL to local config file
    
    Args:
        api_url: API URL to save
    """
    config = _load_config()
    config['api_url'] = api_url
    _save_config(config)


def get_api_url() -> Optional[str]:
    """
    Get API URL from local config file
    
    Returns:
        API URL if found, None otherwise
    """
    config = _load_config()
    return config.get('api_url')


def clear_project_name():
    """Clear project name from local config file"""
    config = _load_config()
    if 'project_name' in config:
        del config['project_name']
        _save_config(config)


def clear_api_url():
    """Clear API URL from local config file"""
    config = _load_config()
    if 'api_url' in config:
        del config['api_url']
        _save_config(config)


def clear_config():
    """Clear entire config file"""
    config_path = get_config_path()
    try:
        if os.path.exists(config_path):
            os.remove(config_path)
    except Exception:
        pass


