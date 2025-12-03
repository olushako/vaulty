from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, LargeBinary, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import secrets
import string
import uuid

from .config import DATABASE_PATH

Base = declarative_base()

engine = create_engine(f"sqlite:///{DATABASE_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def generate_id() -> str:
    """Generate a 16-character hexadecimal ID (8 bytes = 64 bits).
    
    This provides a good balance between:
    - Short length (16 chars vs 36 for UUID)
    - Very low collision probability (2^64 = ~18 quintillion possibilities)
    - URL-safe and easy to work with
    """
    return secrets.token_hex(8)  # 8 bytes = 16 hex characters


class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String(16), primary_key=True, index=True, default=generate_id)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    auto_approval_tag_pattern = Column(String, nullable=True)  # Tag pattern for auto-approving devices (e.g., "test", "dev")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tokens = relationship("Token", back_populates="project", cascade="all, delete-orphan")
    secrets = relationship("Secret", back_populates="project", cascade="all, delete-orphan")
    devices = relationship("Device", back_populates="project", cascade="all, delete-orphan")


class MasterToken(Base):
    __tablename__ = "master_tokens"
    
    id = Column(String(16), primary_key=True, index=True, default=generate_id)
    name = Column(String, nullable=False)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    is_init_token = Column(Integer, default=0)  # 1 = initialization token (from MASTER_TOKEN env), 0 = created via API
    
    @staticmethod
    def generate_token():
        """Generate a secure random alphanumeric token"""
        alphabet = string.ascii_letters + string.digits  # A-Z, a-z, 0-9
        return ''.join(secrets.choice(alphabet) for _ in range(32))


class Token(Base):
    __tablename__ = "tokens"
    
    id = Column(String(16), primary_key=True, index=True, default=generate_id)
    project_id = Column(String(16), ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    
    project = relationship("Project", back_populates="tokens")
    
    @staticmethod
    def generate_token():
        """Generate a secure random alphanumeric token"""
        alphabet = string.ascii_letters + string.digits  # A-Z, a-z, 0-9
        return ''.join(secrets.choice(alphabet) for _ in range(32))


class Secret(Base):
    __tablename__ = "secrets"
    
    id = Column(String(16), primary_key=True, index=True, default=generate_id)
    project_id = Column(String(16), ForeignKey("projects.id"), nullable=False, index=True)
    key = Column(String, nullable=False, index=True)
    encrypted_value = Column(LargeBinary, nullable=False)  # Encrypted secret value
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    project = relationship("Project", back_populates="secrets")
    
    # Unique constraint: each key is unique per project
    __table_args__ = (
        UniqueConstraint('project_id', 'key', name='uq_project_key'),
    )


class Activity(Base):
    __tablename__ = "activities"
    
    id = Column(String(16), primary_key=True, index=True, default=generate_id)
    method = Column(String, nullable=False)  # GET, POST, DELETE, etc.
    path = Column(String, nullable=False)  # API path
    action = Column(String, nullable=False)  # e.g., "create_project", "get_secret", "delete_token"
    project_name = Column(String, nullable=True, index=True)  # Project name if applicable
    token_type = Column(String, nullable=False)  # "master" or "project"
    status_code = Column(Integer, nullable=False)
    execution_time_ms = Column(Integer, nullable=True)  # Execution time in milliseconds
    request_data = Column(Text, nullable=True)  # JSON string with all request data
    response_data = Column(Text, nullable=True)  # JSON string with all response data
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class Device(Base):
    __tablename__ = "devices"
    
    id = Column(String(16), primary_key=True, index=True, default=generate_id)
    project_id = Column(String(16), ForeignKey("projects.id"), nullable=False, index=True)
    device_id_hash = Column(String(64), nullable=True, unique=True, index=True)  # SHA256 hash of device_id (stored as device_id_hash in DB, but referred to as device_token in API)
    name = Column(String, nullable=False)  # Device name/identifier
    token_hash = Column(String, nullable=True, index=True)  # Deprecated: Not used anymore. Devices use device_token (calculated as SHA256(device_id)) for authentication, not project tokens.
    status = Column(String, nullable=False, default="pending")  # pending, authorized, rejected
    device_info = Column(Text, nullable=True)  # JSON string with device metadata (IP, user agent, etc.)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    authorized_at = Column(DateTime, nullable=True)
    authorized_by = Column(String, nullable=True)  # Token identifier (e.g., "master_token:abc123" or "project_token:def456")
    rejected_at = Column(DateTime, nullable=True)
    rejected_by = Column(String, nullable=True)  # Token identifier (e.g., "master_token:abc123" or "project_token:def456")
    
    project = relationship("Project", back_populates="devices")


def init_db():
    """Initialize the database"""
    # Enable auto-vacuum before creating tables (must be done on empty database)
    # Check if database exists and has tables
    import os
    from sqlalchemy import text
    
    db_exists = os.path.exists(DATABASE_PATH)
    if db_exists:
        # Check if database has any tables
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1"))
            has_tables = result.fetchone() is not None
            
            if not has_tables:
                # Database exists but is empty, enable auto-vacuum
                conn.execute(text("PRAGMA auto_vacuum = FULL"))
                conn.commit()
    else:
        # New database, enable auto-vacuum before creating tables
        with engine.connect() as conn:
            conn.execute(text("PRAGMA auto_vacuum = FULL"))
            conn.commit()
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Migrate existing databases
    with engine.connect() as conn:
        try:
            # Check if master_tokens table exists and get its columns
            result = conn.execute(text("PRAGMA table_info(master_tokens)"))
            columns = [row[1] for row in result.fetchall()]
            
            if not columns:
                # Table doesn't exist yet, will be created by create_all above
                pass
            else:
                # Add is_init_token column if it doesn't exist
                if 'is_init_token' not in columns:
                    conn.execute(text("ALTER TABLE master_tokens ADD COLUMN is_init_token INTEGER DEFAULT 0"))
                    conn.commit()
                    print("✅ Added is_init_token column to master_tokens table")
                
                # Remove is_active column if it exists (SQLite doesn't support DROP COLUMN, so recreate table)
                if 'is_active' in columns:
                    print("🔄 Recreating master_tokens table to remove is_active column...")
                    
                    # Create new table without is_active
                    conn.execute(text("""
                        CREATE TABLE master_tokens_new (
                            id VARCHAR(16) PRIMARY KEY,
                            name VARCHAR NOT NULL,
                            token_hash VARCHAR NOT NULL UNIQUE,
                            created_at DATETIME,
                            last_used DATETIME,
                            is_init_token INTEGER DEFAULT 0
                        )
                    """))
                    
                    # Copy data (excluding is_active)
                    conn.execute(text("""
                        INSERT INTO master_tokens_new (id, name, token_hash, created_at, last_used, is_init_token)
                        SELECT id, name, token_hash, created_at, last_used, 
                               COALESCE(is_init_token, 0) as is_init_token
                        FROM master_tokens
                    """))
                    
                    # Drop old table
                    conn.execute(text("DROP TABLE master_tokens"))
                    
                    # Rename new table
                    conn.execute(text("ALTER TABLE master_tokens_new RENAME TO master_tokens"))
                    
                    # Recreate indexes
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_master_tokens_token_hash ON master_tokens(token_hash)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_master_tokens_id ON master_tokens(id)"))
                    
                    conn.commit()
                    print("✅ Recreated master_tokens table without is_active column")
        except Exception as e:
            # Table might not exist yet or migration already completed
            print(f"⚠️  Migration note: {e}")

