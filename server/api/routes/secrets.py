"""Secret management routes"""
from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from ...models import Project, Secret
from ...schemas import SecretCreate, SecretResponse, SecretValueResponse
from ...auth import get_db, get_auth_context
from ...encryption import encrypt_data, decrypt_data
from ..utils import get_project_by_name, commit_and_refresh
from ..dependencies import get_project_with_access, get_secret_by_key

router = APIRouter(tags=["secrets"])


@router.post("/api/projects/{project_name}/secrets", response_model=SecretResponse, status_code=status.HTTP_201_CREATED)
def create_secret(
    secret: SecretCreate,
    project: Project = Depends(get_project_with_access),
    db: Session = Depends(get_db)
):
    """Store a secret in a project - requires master token (any project) or project token (own project only)"""
    
    # Encrypt the secret value
    encrypted_value = encrypt_data(secret.value)
    
    # Check if secret already exists (unique per project)
    existing = db.query(Secret).filter(
        Secret.project_id == project.id,
        Secret.key == secret.key
    ).first()
    
    if existing:
        # Update existing secret
        existing.encrypted_value = encrypted_value
        existing.updated_at = datetime.utcnow()
        return commit_and_refresh(db, existing)
    else:
        # Create new secret
        db_secret = Secret(
            project_id=project.id,
            key=secret.key,
            encrypted_value=encrypted_value
        )
        db.add(db_secret)
        return commit_and_refresh(db, db_secret)


@router.get("/api/projects/{project_name}/secrets/{key}", response_model=SecretValueResponse)
def get_secret(
    secret: Secret = Depends(get_secret_by_key)
):
    """Get a secret by key from a project - requires master token (any project) or project token (own project only)"""
    
    # Decrypt and return
    value = decrypt_data(secret.encrypted_value)
    return SecretValueResponse(key=secret.key, value=value)


@router.get("/api/projects/{project_name}/secrets", response_model=List[SecretResponse])
def list_secrets(
    project: Project = Depends(get_project_with_access),
    db: Session = Depends(get_db)
):
    """List all secrets in a project - requires master token (any project) or project token (own project only)"""
    
    secrets = db.query(Secret).filter(
        Secret.project_id == project.id
    ).all()
    return secrets


@router.delete("/api/projects/{project_name}/secrets/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_secret(
    secret: Secret = Depends(get_secret_by_key),
    db: Session = Depends(get_db)
):
    """Delete a secret from a project - requires master token (any project) or project token (own project only)"""
    
    db.delete(secret)
    db.commit()
    return None


# Root-level endpoints for project tokens
@router.get("/api/secrets", response_model=List[SecretResponse])
def list_secrets_root(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """List all secrets for the project associated with the token (project token only)"""
    auth = get_auth_context(credentials, db)
    
    if auth.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires a project token. Use /api/projects/{project_name}/secrets with master token."
        )
    
    if not auth.project_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid project token"
        )
    
    secrets = db.query(Secret).filter(Secret.project_id == auth.project_id).all()
    return secrets


@router.get("/api/secrets/{key}", response_model=SecretValueResponse)
def get_secret_root(
    key: str,
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """Get a secret by key for the project associated with the token (project token only)"""
    auth = get_auth_context(credentials, db)
    
    if auth.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires a project token. Use /api/projects/{project_name}/secrets/{key} with master token."
        )
    
    if not auth.project_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid project token"
        )
    
    secret = db.query(Secret).filter(
        Secret.project_id == auth.project_id,
        Secret.key == key
    ).first()
    
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Secret not found"
        )
    
    decrypted_value = decrypt_data(secret.encrypted_value)
    return SecretValueResponse(key=secret.key, value=decrypted_value)


@router.post("/api/secrets", response_model=SecretResponse, status_code=status.HTTP_201_CREATED)
def create_secret_root(
    secret_data: SecretCreate,
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """Create a secret for the project associated with the token (project token only)"""
    auth = get_auth_context(credentials, db)
    
    if auth.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires a project token. Use /api/projects/{project_name}/secrets with master token."
        )
    
    if not auth.project_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid project token"
        )
    
    # Check if secret already exists
    existing = db.query(Secret).filter(
        Secret.project_id == auth.project_id,
        Secret.key == secret_data.key
    ).first()
    
    if existing:
        # Update existing secret
        existing.encrypted_value = encrypt_data(secret_data.value)
        existing.updated_at = datetime.utcnow()
        return commit_and_refresh(db, existing)
    
    # Create new secret
    encrypted_value = encrypt_data(secret_data.value)
    secret = Secret(
        project_id=auth.project_id,
        key=secret_data.key,
        encrypted_value=encrypted_value
    )
    db.add(secret)
    return commit_and_refresh(db, secret)


@router.delete("/api/secrets/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_secret_root(
    key: str,
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """Delete a secret by key for the project associated with the token (project token only)"""
    auth = get_auth_context(credentials, db)
    
    if auth.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires a project token. Use /api/projects/{project_name}/secrets/{key} with master token."
        )
    
    if not auth.project_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid project token"
        )
    
    secret = db.query(Secret).filter(
        Secret.project_id == auth.project_id,
        Secret.key == key
    ).first()
    
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Secret not found"
        )
    
    db.delete(secret)
    db.commit()
    return None

