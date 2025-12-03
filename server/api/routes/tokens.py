"""Token management routes"""
from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List

from ...models import Project, Token
from ...schemas import TokenCreate, TokenResponse, TokenInfo
from ...auth import get_db, hash_token
from ..utils import mask_token, commit_and_refresh
from ..dependencies import get_project_with_access

router = APIRouter(tags=["tokens"])


@router.post("/api/projects/{project_name}/tokens", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def create_token(
    token_data: TokenCreate,
    project: Project = Depends(get_project_with_access),
    db: Session = Depends(get_db)
):
    """Create a token for a project"""
    
    # Generate token (collision probability is negligible, so no need to check)
    token_str = Token.generate_token()
    
    # Ignore the name from request body - always use masked token value as name
    token_name = mask_token(token_str)
    
    db_token = Token(
        project_id=project.id,
        name=token_name,
        token_hash=hash_token(token_str)
    )
    db.add(db_token)
    commit_and_refresh(db, db_token)
    
    # Return token with the actual token string (only time it's shown)
    response = TokenResponse(
        id=db_token.id,
        project_id=db_token.project_id,
        name=db_token.name,
        token=token_str,
        created_at=db_token.created_at
    )
    return response


@router.get("/api/projects/{project_name}/tokens", response_model=List[TokenInfo])
def list_tokens(
    project: Project = Depends(get_project_with_access),
    db: Session = Depends(get_db)
):
    """List all tokens for a project - requires master token (any project) or project token (own project only)"""
    
    tokens = db.query(Token).filter(Token.project_id == project.id).all()
    return tokens


@router.delete("/api/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(
    token_id: str,
    db: Session = Depends(get_db)
):
    """Revoke a token"""
    token = db.query(Token).filter(Token.id == token_id).first()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found"
        )
    
    db.delete(token)
    db.commit()
    return None

