"""Common dependencies for API routes"""
from fastapi import Depends, Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..auth import get_db, verify_project_access_by_id
from ..models import Project, Device, Secret
from .utils import get_project_by_name

security = HTTPBearer()


def get_project_with_access(
    project_name: str,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
) -> Project:
    """
    Dependency that gets a project by name and verifies access.
    Combines get_project_by_name + verify_project_access_by_id pattern.
    Use this as a dependency in route handlers that need project access.
    
    Example:
        @router.get("/{project_name}/something")
        def my_route(project: Project = Depends(get_project_with_access)):
            # project is already verified and accessible
    """
    project = get_project_by_name(project_name, db)
    verify_project_access_by_id(project.id, credentials, db)
    return project


def get_device_by_id(
    device_id: str,
    project_name: str,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
) -> Device:
    """
    Dependency that gets a device by ID within a project.
    Raises 404 if device not found.
    Automatically verifies project access.
    """
    project = get_project_by_name(project_name, db)
    verify_project_access_by_id(project.id, credentials, db)
    
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.project_id == project.id
    ).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    return device


def get_device_by_id_no_auth(
    device_id: str,
    project_name: str,
    db: Session = Depends(get_db)
) -> Device:
    """
    Dependency that gets a device by ID within a project WITHOUT requiring authentication.
    Used for device status checks during registration flow.
    Raises 404 if device or project not found.
    """
    project = get_project_by_name(project_name, db)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_name}' not found"
        )
    
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.project_id == project.id
    ).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    return device


def get_secret_by_key(
    key: str,
    project_name: str,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
) -> Secret:
    """
    Dependency that gets a secret by key within a project.
    Raises 404 if secret not found.
    Automatically verifies project access.
    """
    project = get_project_by_name(project_name, db)
    verify_project_access_by_id(project.id, credentials, db)
    
    secret = db.query(Secret).filter(
        Secret.project_id == project.id,
        Secret.key == key
    ).first()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Secret not found"
        )
    return secret

