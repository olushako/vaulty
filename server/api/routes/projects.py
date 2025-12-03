"""Project management routes"""
from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List

from ...models import Project
from ...schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from ...auth import get_db, verify_master_token, get_auth_context
from ..utils import get_project_by_name, commit_and_refresh
from ..dependencies import get_project_with_access

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_master_token)
):
    """Create a new project (requires master token)"""
    # Check if project name already exists
    existing = db.query(Project).filter(Project.name == project.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project with this name already exists"
        )
    
    db_project = Project(name=project.name, description=project.description)
    db.add(db_project)
    return commit_and_refresh(db, db_project)


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """List projects accessible with the current token - master token sees all, project token sees only its project"""
    auth = get_auth_context(credentials, db)
    
    if auth.is_master:
        # Master token: return all projects
        projects = db.query(Project).all()
    else:
        # Project token: return only the project this token belongs to
        project = db.query(Project).filter(Project.id == auth.project_id).first()
        projects = [project] if project else []
    
    return projects


@router.get("/{project_name}", response_model=ProjectResponse)
def get_project(
    project: Project = Depends(get_project_with_access)
):
    """Get project details - requires master token or project token (own project only)"""
    return project


@router.patch("/{project_name}", response_model=ProjectResponse)
def update_project(
    project_update: ProjectUpdate,
    project: Project = Depends(get_project_with_access),
    db: Session = Depends(get_db)
):
    """Update project settings - requires master token (any project) or project token (own project only)"""
    # Update auto_approval_tag_pattern if provided (including None to clear it)
    # Use model_dump to check if the field was explicitly set in the request
    update_data = project_update.model_dump(exclude_unset=True)
    if 'auto_approval_tag_pattern' in update_data:
        project.auto_approval_tag_pattern = update_data['auto_approval_tag_pattern']
    
    return commit_and_refresh(db, project)


@router.delete("/{project_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_name: str,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_master_token)
):
    """Delete a project and all its secrets and tokens (requires master token)"""
    project = db.query(Project).filter(Project.name == project_name).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Delete from database (cascade will handle tokens and secrets)
    db.delete(project)
    db.commit()
    return None

