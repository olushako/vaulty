from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import hashlib

from .models import SessionLocal, Token, MasterToken, Device

security = HTTPBearer()


def hash_token(token: str) -> str:
    """Hash a token for storage"""
    return hashlib.sha256(token.encode()).hexdigest()


def get_db():
    """Dependency for database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_master_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
):
    """Verify master token for administrative operations - only tokens in database are accepted"""
    token_str = credentials.credentials
    token_hash = hash_token(token_str)
    from datetime import datetime
    
    # Check database for master token
    master_token = db.query(MasterToken).filter(
        MasterToken.token_hash == token_hash
    ).first()
    
    if master_token:
        # Update last_used timestamp
        master_token.last_used = datetime.utcnow()
        db.commit()
        return True
    
    # No fallback - token must exist in database
    raise HTTPException(status_code=403, detail="Master token required")


class AuthContext:
    """Authentication context - can be master token or project token"""
    def __init__(self, is_master: bool, project_id: str = None, token: Token = None):
        self.is_master = is_master
        self.project_id = project_id
        self.token = token


def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
) -> AuthContext:
    """Get authentication context - accepts either master token or project token"""
    token_str = credentials.credentials
    token_hash = hash_token(token_str)
    from datetime import datetime
    
    # Check if it's a master token (database first, then fallback to env)
    master_token = db.query(MasterToken).filter(
        MasterToken.token_hash == token_hash
    ).first()
    
    if master_token:
        master_token.last_used = datetime.utcnow()
        db.commit()
        return AuthContext(is_master=True, project_id=None)
    
    # Check if it's a device_token (64 hex characters - SHA256 hash of device_id)
    # Client sends: device_token = SHA256(device_id) in Authorization header
    # Server compares with stored device_id_hash (DB column name, but conceptually it's device_token)
    if len(token_str) == 64 and all(c in '0123456789abcdef' for c in token_str.lower()):
        device = db.query(Device).filter(
            Device.device_id_hash == token_str.lower(),
            Device.status == "authorized"
        ).first()
        
        if device:
            # Device is authorized, grant access to its project
            return AuthContext(is_master=False, project_id=device.project_id, token=None)
    
    # Otherwise, check if it's a project token
    token = db.query(Token).filter(Token.token_hash == token_hash).first()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Update last_used timestamp
    token.last_used = datetime.utcnow()
    db.commit()
    
    return AuthContext(is_master=False, project_id=token.project_id, token=token)


def verify_project_access_by_id(
    project_id: str,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
) -> str:
    """
    Verify access to a specific project by UUID ID.
    - Master token: can access any project
    - Project token: can only access its own project
    - Device token (device_token = SHA256(device_id)): can only access its own project
    Returns the project_id that was verified.
    """
    token_str = credentials.credentials
    token_hash = hash_token(token_str)
    
    # Check if it's a master token (database first, then fallback to env)
    master_token = db.query(MasterToken).filter(
        MasterToken.token_hash == token_hash
    ).first()
    
    if master_token:
        from datetime import datetime
        master_token.last_used = datetime.utcnow()
        db.commit()
        return project_id
    
    # Check if it's a device_token (64 hex characters - SHA256 hash of device_id)
    # Client sends: device_token = SHA256(device_id) in Authorization header
    # Server compares with stored device_id_hash (DB column name, but conceptually it's device_token)
    if len(token_str) == 64 and all(c in '0123456789abcdef' for c in token_str.lower()):
        device = db.query(Device).filter(
            Device.device_id_hash == token_str.lower(),
            Device.status == "authorized"
        ).first()
        
        if device:
            # Device can only access its own project
            if device.project_id != project_id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: device does not have access to this project"
                )
        return project_id
    
    # Otherwise, check if it's a project token
    token = db.query(Token).filter(Token.token_hash == token_hash).first()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Project token can only access its own project
    if token.project_id != project_id:
        raise HTTPException(
            status_code=403, 
            detail="Access denied: token does not have access to this project"
        )
    
    # Update last_used timestamp
    from datetime import datetime
    token.last_used = datetime.utcnow()
    db.commit()
    
    return project_id





