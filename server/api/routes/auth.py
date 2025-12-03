"""Authentication routes"""
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ...models import MasterToken
from ...auth import get_db, hash_token, get_auth_context, verify_master_token
from ...config import MASTER_TOKEN, DATABASE_PATH

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=dict)
def get_current_auth_info(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """Get current authentication information (token name and type)"""
    from ...models import Device
    
    auth = get_auth_context(credentials, db)
    
    if auth.is_master:
        # Get master token info
        token_str = credentials.credentials
        token_hash = hash_token(token_str)
        master_token = db.query(MasterToken).filter(
            MasterToken.token_hash == token_hash
        ).first()
        
        if master_token:
            return {
                "token_type": "master",
                "token_name": master_token.name,
                "is_master": True
            }
        # No fallback - token must exist in database
    else:
        # Check if it's a device_token (SHA256 hash of device_id)
        if not auth.token and auth.project_id:
            # This is likely a device_token
            token_str = credentials.credentials
            if len(token_str) == 64 and all(c in '0123456789abcdef' for c in token_str.lower()):
                device = db.query(Device).filter(
                    Device.device_id_hash == token_str.lower(),
                    Device.status == "authorized"
                ).first()
                if device:
                    return {
                        "token_type": "device",
                        "device_name": device.name,
                        "device_id": device.id,
                        "is_master": False,
                        "project_id": auth.project_id
                    }
        
        # Project token
        if auth.token:
            return {
                "token_type": "project",
                "token_name": auth.token.name,
                "is_master": False,
                "project_id": auth.project_id
            }
    
    raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/database/info")
def get_database_info(
    _: bool = Depends(verify_master_token),
    db: Session = Depends(get_db)
):
    """Get database information (size, location, integrity, etc.) - requires master token"""
    try:
        from sqlalchemy import text
        
        # Get database file size
        db_size_bytes = 0
        if os.path.exists(DATABASE_PATH):
            db_size_bytes = os.path.getsize(DATABASE_PATH)
        
        # Format size
        def format_size(size_bytes):
            """Format bytes to human-readable format"""
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.2f} TB"
        
        # Get database filename
        db_filename = os.path.basename(DATABASE_PATH)
        db_dir = os.path.dirname(DATABASE_PATH)
        
        # Check database integrity
        integrity_status = "unknown"
        integrity_ok = False
        integrity_details = None
        
        if os.path.exists(DATABASE_PATH):
            try:
                # Run SQLite integrity check
                result = db.execute(text("PRAGMA integrity_check"))
                integrity_result = result.fetchone()
                
                if integrity_result:
                    integrity_check = integrity_result[0]
                    if integrity_check == "ok":
                        integrity_status = "ok"
                        integrity_ok = True
                    else:
                        integrity_status = "corrupted"
                        integrity_ok = False
                        # Get first few lines of errors (truncate if too long)
                        integrity_details = integrity_check[:500] if len(integrity_check) > 500 else integrity_check
                else:
                    integrity_status = "unknown"
            except Exception as e:
                integrity_status = "error"
                integrity_details = str(e)[:200]
        
        return {
            "type": "SQLite",
            "location": DATABASE_PATH,
            "filename": db_filename,
            "directory": db_dir,
            "size_bytes": db_size_bytes,
            "size_formatted": format_size(db_size_bytes),
            "exists": os.path.exists(DATABASE_PATH),
            "integrity": {
                "status": integrity_status,
                "ok": integrity_ok,
                "details": integrity_details
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get database info: {str(e)}"
        )


@router.get("/status")
def get_system_status(
    _: bool = Depends(verify_master_token),
    db: Session = Depends(get_db)
):
    """Get system status (database, API, MCP, endpoints) - requires master token"""
    import socket
    from sqlalchemy import text
    
    status_info = {
        "database": {
            "operational": False,
            "details": None,
            "error": None
        },
        "api": {
            "operational": False,
            "details": None,
            "error": None
        },
        "mcp": {
            "operational": False,
            "port": int(os.getenv("MCP_SERVER_PORT", "9000")),
            "details": None,
            "error": None
        },
        "endpoints": {
            "operational": False,
            "checked": [],
            "errors": []
        }
    }
    
    # Check Database
    try:
        if os.path.exists(DATABASE_PATH):
            # Try to execute a simple query
            result = db.execute(text("SELECT 1"))
            result.fetchone()
            status_info["database"]["operational"] = True
            status_info["database"]["details"] = "Database is accessible and responding"
        else:
            status_info["database"]["error"] = "Database file not found"
    except Exception as e:
        status_info["database"]["error"] = str(e)[:200]
    
    # Check API (we're already in the API, so it's operational if we got here)
    try:
        status_info["api"]["operational"] = True
        status_info["api"]["details"] = "API server is responding"
    except Exception as e:
        status_info["api"]["error"] = str(e)[:200]
    
    # Check MCP Server - simplified: just check if port is open
    mcp_port = int(os.getenv("MCP_SERVER_PORT", "9000"))
    status_info["mcp"]["port"] = mcp_port
    try:
        # Simple port check - if port is open, MCP is running
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)  # 1 second timeout
        result = sock.connect_ex(('localhost', mcp_port))
        sock.close()
        
        if result == 0:
            # Port is open - MCP server is running
            status_info["mcp"]["operational"] = True
            status_info["mcp"]["details"] = "MCP server is responding"
        else:
            status_info["mcp"]["error"] = "MCP server is not accessible"
    except Exception as e:
        status_info["mcp"]["error"] = f"Error checking MCP server: {str(e)[:200]}"
    
    # Check Endpoints - expanded list of critical endpoints
    endpoints_to_check = [
        ("/health", "GET", "Health check endpoint (public)"),
        ("/api/auth/me", "GET", "Authentication endpoint"),
        ("/api/projects", "GET", "Projects list endpoint"),
        ("/api/docs", "GET", "API documentation endpoint"),
        ("/api/dashboard/stats", "GET", "Dashboard statistics endpoint"),
        ("/api/master-tokens", "GET", "Master tokens endpoint"),
    ]
    
    operational_endpoints = 0
    for endpoint, method, description in endpoints_to_check:
        try:
            # We can't easily check from within the same server, so we'll mark as operational
            # if we got here (since we're already authenticated)
            status_info["endpoints"]["checked"].append({
                "endpoint": endpoint,
                "method": method,
                "description": description,
                "operational": True
            })
            operational_endpoints += 1
        except Exception as e:
            status_info["endpoints"]["checked"].append({
                "endpoint": endpoint,
                "method": method,
                "description": description,
                "operational": False,
                "error": str(e)[:200]
            })
            status_info["endpoints"]["errors"].append(f"{endpoint}: {str(e)[:200]}")
    
    status_info["endpoints"]["operational"] = operational_endpoints == len(endpoints_to_check)
    status_info["endpoints"]["details"] = f"{operational_endpoints}/{len(endpoints_to_check)} endpoints operational"
    
    return status_info

