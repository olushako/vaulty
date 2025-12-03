import os
from pathlib import Path

# Master encryption key (32 bytes = 64 hex characters)
MASTER_KEY = os.getenv("MASTER_KEY", None)
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

if MASTER_KEY:
    if len(MASTER_KEY) != 64:
        raise ValueError("MASTER_KEY must be 64 hex characters (32 bytes)")
    MASTER_KEY = bytes.fromhex(MASTER_KEY)
else:
    # Default key for development (NOT for production!)
    if ENVIRONMENT == "production":
        print("=" * 80)
        print("ERROR: MASTER_KEY environment variable is REQUIRED in production!")
        print("=" * 80)
        print("\nThe server cannot start in production without a MASTER_KEY.")
        print("Please set MASTER_KEY environment variable before starting the server.")
        print("\nGenerate a secure 64-character hex key (32 bytes):")
        print("  python3 -c 'import secrets; print(secrets.token_hex(32))'")
        print("\nSet it and start the server:")
        print("  export MASTER_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')")
        print("  export ENVIRONMENT=production")
        print("  python3 -m uvicorn server.main:app --host 0.0.0.0 --port 8000")
        print("=" * 80)
        import sys
        sys.exit(1)
    # Only allow default in development
    MASTER_KEY = b"default_key_32_bytes_long_for_dev_only!!"

# Database path (relative to server directory)
DATABASE_PATH = os.getenv("DATABASE_PATH", None)
if not DATABASE_PATH:
    # Default to data directory in server directory
    server_dir = Path(__file__).parent
    data_dir = server_dir / "data"
    # Create data directory if it doesn't exist
    data_dir.mkdir(exist_ok=True)
    DATABASE_PATH = str(data_dir / "vaulty.db")
else:
    DATABASE_PATH = os.path.abspath(DATABASE_PATH)

# Master token for administrative operations (project creation/deletion)
# MASTER_TOKEN is MANDATORY - server will not start without it
MASTER_TOKEN = os.getenv("MASTER_TOKEN", None)
if not MASTER_TOKEN:
    print("=" * 80)
    print("ERROR: MASTER_TOKEN environment variable is REQUIRED!")
    print("=" * 80)
    print("\nThe server cannot start without a MASTER_TOKEN.")
    print("Please set MASTER_TOKEN environment variable before starting the server.")
    print("\nGenerate a secure token:")
    print("  python3 -c 'import secrets; print(secrets.token_urlsafe(32))'")
    print("\nSet it and start the server:")
    print("  export MASTER_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')")
    print("  python3 -m uvicorn server.main:app --host 0.0.0.0 --port 8000")
    print("\nOr in docker-compose.yml:")
    print("  environment:")
    print("    - MASTER_TOKEN=your-secure-token-here")
    print("=" * 80)
    import sys
    sys.exit(1)

