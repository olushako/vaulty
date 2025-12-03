"""Main FastAPI application"""
import os
import time
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models import init_db, MasterToken
from .auth import hash_token
from .activity_logger import cleanup_old_activities
from .config import MASTER_TOKEN
from .api.middleware import ActivityLoggingMiddleware
from .api.routes import (
    master_tokens,
    projects,
    tokens,
    secrets,
    activities,
    auth,
    devices,
    docs
)

app = FastAPI(title="Vaulty Secrets Manager", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add activity logging middleware
app.add_middleware(ActivityLoggingMiddleware)

# Register all route routers
app.include_router(master_tokens.router)
app.include_router(projects.router)
app.include_router(tokens.router)
app.include_router(secrets.router)
app.include_router(activities.router)
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(docs.router)


def run_periodic_cleanup():
    """Run cleanup every 24 hours"""
    while True:
        try:
            time.sleep(86400)  # 24 hours
            deleted = cleanup_old_activities(days=7)
            if deleted > 0:
                print(f"Cleaned up {deleted} old activities")
        except Exception as e:
            print(f"Error in periodic cleanup: {e}")


def init_master_token():
    """Initialize master token from environment variable if database is newly created"""
    from .models import SessionLocal
    from .api.utils import mask_token
    
    db = SessionLocal()
    try:
        # Check if any master tokens exist
        existing_tokens = db.query(MasterToken).count()
        
        if existing_tokens == 0:
            # Database is newly created, store the master token from env var
            token_hash = hash_token(MASTER_TOKEN)
            token_name = mask_token(MASTER_TOKEN)
            master_token = MasterToken(
                name=token_name,
                token_hash=token_hash,
                is_init_token=1  # Mark as initialization token
            )
            db.add(master_token)
            db.commit()
            print(f"✅ Initialized master token from MASTER_TOKEN environment variable (marked as init token)")
        else:
            # Master tokens already exist - don't inject the MASTER_TOKEN env var
            print(f"ℹ️  Master tokens already exist in database. Skipping MASTER_TOKEN environment variable injection.")
    except Exception as e:
        db.rollback()
        print(f"⚠️  Failed to initialize master token: {e}")
    finally:
        db.close()


@app.on_event("startup")
def startup_event():
    """Initialize database on startup and cleanup old activities"""
    # MASTER_TOKEN is validated in config.py - if not set, server won't start
    init_db()
    
    # Initialize master token from environment variable
    # MASTER_TOKEN is guaranteed to exist at this point (config.py validates it)
    init_master_token()
    
    # Cleanup activities older than 7 days on startup
    deleted = cleanup_old_activities(days=7)
    if deleted > 0:
        print(f"Cleaned up {deleted} old activities on startup")
    
    # Start background thread for periodic cleanup
    cleanup_thread = threading.Thread(target=run_periodic_cleanup, daemon=True)
    cleanup_thread.start()


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "service": "Vaulty Secrets Manager",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """Public health check endpoint (no authentication required) - for load balancers and monitoring"""
    import socket
    from .config import DATABASE_PATH
    from sqlalchemy import text
    from .models import SessionLocal
    
    health_status = {
        "status": "healthy",
        "service": "Vaulty Secrets Manager",
        "version": "1.0.0",
        "checks": {
            "api": {"status": "ok"},
            "database": {"status": "unknown"},
            "mcp": {"status": "unknown"}
        }
    }
    
    # Check database
    try:
        db = SessionLocal()
        try:
            result = db.execute(text("SELECT 1"))
            result.fetchone()
            health_status["checks"]["database"]["status"] = "ok"
        except Exception as e:
            health_status["checks"]["database"]["status"] = "error"
            health_status["checks"]["database"]["error"] = str(e)[:100]
        finally:
            db.close()
    except Exception as e:
        health_status["checks"]["database"]["status"] = "error"
        health_status["checks"]["database"]["error"] = str(e)[:100]
    
    # Check MCP server
    try:
        mcp_port = int(os.getenv("MCP_SERVER_PORT", "9000"))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', mcp_port))
        sock.close()
        if result == 0:
            health_status["checks"]["mcp"]["status"] = "ok"
        else:
            health_status["checks"]["mcp"]["status"] = "error"
            health_status["checks"]["mcp"]["error"] = f"Port {mcp_port} not accessible"
    except Exception as e:
        health_status["checks"]["mcp"]["status"] = "error"
        health_status["checks"]["mcp"]["error"] = str(e)[:100]
    
    # Determine overall status
    if any(check["status"] == "error" for check in health_status["checks"].values()):
        health_status["status"] = "degraded"
    
    return health_status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
