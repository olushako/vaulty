"""Master token management routes"""
from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List
from datetime import timezone

from ...models import MasterToken
from ...schemas import MasterTokenCreate, MasterTokenResponse, MasterTokenInfo
from ...auth import get_db, hash_token, verify_master_token
from ..utils import mask_token, commit_and_refresh

security = HTTPBearer()

router = APIRouter(prefix="/api/master-tokens", tags=["master-tokens"])


@router.post("", response_model=MasterTokenResponse, status_code=status.HTTP_201_CREATED)
def create_master_token(
    token_data: MasterTokenCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_master_token)
):
    """Create a new master token (requires existing master token)"""
    # Generate token
    token_str = MasterToken.generate_token()
    token_hash = hash_token(token_str)
    
    # Use masked token value as name (ignore name from request if provided)
    token_name = mask_token(token_str)
    
    # Check if this will be the first token (excluding the current one being used)
    # If no tokens exist, mark as initial
    existing_count = db.query(MasterToken).count()
    is_init = 1 if existing_count == 0 else 0
    
    db_master_token = MasterToken(
        name=token_name,
        token_hash=token_hash,
        is_init_token=is_init
    )
    db.add(db_master_token)
    commit_and_refresh(db, db_master_token)
    
    # Return token with the actual token string (only time it's shown)
    response = MasterTokenResponse(
        id=db_master_token.id,
        name=db_master_token.name,
        token=token_str,
        created_at=db_master_token.created_at
    )
    return response


@router.get("", response_model=List[MasterTokenInfo])
def list_master_tokens(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_master_token)
):
    """List all master tokens (requires master token)"""
    # Get current token hash to identify which token is being used
    current_token_str = credentials.credentials
    current_token_hash = hash_token(current_token_str)
    
    # Return all tokens (if token exists, it's active)
    tokens = db.query(MasterToken).all()
    # Ensure timestamps are timezone-aware
    result = []
    for t in tokens:
        # Ensure timestamps are UTC-aware
        created_at = t.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        
        last_used = t.last_used
        if last_used and last_used.tzinfo is None:
            last_used = last_used.replace(tzinfo=timezone.utc)
        
        # Check if this is the current token
        is_current = (t.token_hash == current_token_hash)
        
        result.append(MasterTokenInfo(
            id=t.id,
            name=t.name,
            created_at=created_at,
            last_used=last_used,
            is_init_token=bool(t.is_init_token),
            is_current_token=is_current
        ))
    return result


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_master_token(
    token_id: str,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_master_token)
):
    """Revoke a master token by deleting it from the database (requires master token)"""
    master_token = db.query(MasterToken).filter(MasterToken.id == token_id).first()
    if not master_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Master token not found"
        )
    
    # Prevent revoking the token currently being used
    current_token_str = credentials.credentials
    current_token_hash = hash_token(current_token_str)
    if master_token.token_hash == current_token_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke the token you are currently using. Please use a different token to revoke this one."
        )
    
    # Hard delete - remove from database immediately
    db.delete(master_token)
    db.commit()
    return None


@router.post("/{token_id}/rotate", response_model=MasterTokenResponse, status_code=status.HTTP_200_OK)
def rotate_master_token(
    token_id: str,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_master_token)
):
    """Rotate a master token - revokes old and creates new (requires master token)"""
    old_token = db.query(MasterToken).filter(MasterToken.id == token_id).first()
    if not old_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Master token not found"
        )
    
    # Delete old token immediately
    db.delete(old_token)
    
    # Generate new token
    token_str = MasterToken.generate_token()
    token_hash = hash_token(token_str)
    
    # Use masked token value as name
    token_name = mask_token(token_str)
    
    new_token = MasterToken(
        name=token_name,
        token_hash=token_hash,
        is_init_token=0  # Rotated tokens are not init tokens
    )
    db.add(new_token)
    commit_and_refresh(db, new_token)
    
    # Return new token with the actual token string (only time it's shown)
    response = MasterTokenResponse(
        id=new_token.id,
        name=new_token.name,
        token=token_str,
        created_at=new_token.created_at
    )
    return response

