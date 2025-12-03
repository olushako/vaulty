"""Utility functions for API"""
import re
from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from ..models import Project


def detect_os_from_user_agent(user_agent: str) -> str:
    """Detect operating system from user agent string."""
    if not user_agent:
        return "Unknown"
    
    user_agent_lower = user_agent.lower()
    
    # Windows
    if 'windows nt 10.0' in user_agent_lower or 'windows 10' in user_agent_lower:
        return "Windows 10"
    elif 'windows nt 6.3' in user_agent_lower:
        return "Windows 8.1"
    elif 'windows nt 6.2' in user_agent_lower:
        return "Windows 8"
    elif 'windows nt 6.1' in user_agent_lower:
        return "Windows 7"
    elif 'windows nt 6.0' in user_agent_lower:
        return "Windows Vista"
    elif 'windows nt 5.1' in user_agent_lower:
        return "Windows XP"
    elif 'windows' in user_agent_lower:
        return "Windows"
    
    # macOS
    if 'mac os x' in user_agent_lower or 'macos' in user_agent_lower:
        # Try to extract version
        match = re.search(r'mac os x (\d+)[._](\d+)', user_agent_lower)
        if match:
            major, minor = match.groups()
            return f"macOS {major}.{minor}"
        return "macOS"
    
    # Linux
    if 'linux' in user_agent_lower:
        # Try to detect specific distributions
        if 'ubuntu' in user_agent_lower:
            return "Linux (Ubuntu)"
        elif 'debian' in user_agent_lower:
            return "Linux (Debian)"
        elif 'fedora' in user_agent_lower:
            return "Linux (Fedora)"
        elif 'centos' in user_agent_lower:
            return "Linux (CentOS)"
        elif 'redhat' in user_agent_lower or 'red hat' in user_agent_lower:
            return "Linux (Red Hat)"
        return "Linux"
    
    # Android
    if 'android' in user_agent_lower:
        match = re.search(r'android ([\d.]+)', user_agent_lower)
        if match:
            return f"Android {match.group(1)}"
        return "Android"
    
    # iOS
    if 'iphone os' in user_agent_lower or 'ipad' in user_agent_lower:
        match = re.search(r'os ([\d_]+)', user_agent_lower)
        if match:
            version = match.group(1).replace('_', '.')
            return f"iOS {version}"
        return "iOS"
    
    return "Unknown"


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request headers."""
    # Check X-Forwarded-For header first (for proxied requests)
    if request.headers.get("x-forwarded-for"):
        # X-Forwarded-For can contain multiple IPs, take the first one
        return request.headers.get("x-forwarded-for").split(",")[0].strip()
    elif request.headers.get("x-real-ip"):
        return request.headers.get("x-real-ip")
    elif request.client:
        return request.client.host
    return "Unknown"


def mask_token(token: str) -> str:
    """Generate name from masked token value: first 4 chars + masked middle + last 4 chars"""
    if len(token) <= 8:
        return '•' * len(token)
    first_chars = token[:4]
    last_chars = token[-4:]
    masked_middle = '•' * (len(token) - 8)
    return f"{first_chars}{masked_middle}{last_chars}"


def get_project_by_name(project_name: str, db: Session) -> Project:
    """
    Get a project by name, raising HTTPException if not found.
    This consolidates the repeated project lookup pattern.
    """
    project = db.query(Project).filter(Project.name == project_name).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return project


def commit_and_refresh(db: Session, obj):
    """
    Helper function to commit and refresh a database object.
    Consolidates the common pattern of db.commit() + db.refresh().
    """
    db.commit()
    db.refresh(obj)
    return obj
