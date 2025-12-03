"""
MCP (Model Context Protocol) Server for Vaulty
Exposes vaulty functionality through the MCP protocol for AI assistants

SECURITY: This server is configured in SAFE MODE by default.
- Secret VALUES are NEVER returned to prevent exposure to LLM servers
- Only secret keys and metadata are exposed
- All operations go through the REST API for consistency and automatic activity logging
- Set MCP_SAFE_MODE=0 to disable (NOT RECOMMENDED)
"""

import asyncio
import json
import sys
from typing import Any, Optional
from datetime import datetime
from dataclasses import dataclass

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
    from mcp.server.models import InitializationOptions
except ImportError:
    print("MCP SDK not installed. Install with: pip install mcp")
    sys.exit(1)

import httpx
import os
import time
import secrets
import uuid
import base64

# Security: Never expose secret values to LLMs
# Set MCP_SAFE_MODE=1 to prevent any secret values from being returned
MCP_SAFE_MODE = os.getenv("MCP_SAFE_MODE", "1").lower() in ("1", "true", "yes")

# API base URL - defaults to localhost:8000
API_BASE_URL = os.getenv("VAULTY_API_URL", "http://localhost:8000")

# Initialize MCP server
server = Server("vaulty")

# HTTP client for API calls
http_client = httpx.AsyncClient(timeout=30.0)

# Store client info from initialization
# Note: Lifespan handlers may not be the right place to capture client info
# We'll rely on extracting it from the request context during tool calls

# Note: MCP clients send clientInfo (name, title) during initialization.
# The current MCP Python SDK may not expose this directly, so we try to
# access it from the request context. If the SDK is updated to provide
# better access, this can be enhanced.


# Global storage for client info (keyed by session/connection)
# This is a fallback if request context doesn't expose it directly
_client_info_cache: dict[str, dict] = {}

def get_mcp_client_info() -> Optional[dict]:
    """
    Get MCP client information from request context.
    Returns client info if available, None otherwise.
    
    MCP clients send clientInfo during initialization with 'name' and 'title'.
    This must be called within a request context (e.g., inside call_tool).
    
    The client info is sent in the initialize request and may be stored in:
    - The request context's session
    - The request context's meta field
    - Or accessed through the server's session management
    """
    try:
        # Access request context through the server instance
        # This only works within an active request context
        ctx = server.request_context()
        if ctx:
            # Debug: Print all available attributes
            # print(f"DEBUG: Context attributes: {[attr for attr in dir(ctx) if not attr.startswith('_')]}")
            
            # Try to get client info from session
            if hasattr(ctx, 'session') and ctx.session:
                session = ctx.session
                # print(f"DEBUG: Session type: {type(session)}, attributes: {[attr for attr in dir(session) if not attr.startswith('_')]}")
                
                # Check if session has client_info attribute
                if hasattr(session, 'client_info'):
                    client_info = session.client_info
                    if client_info:
                        result = {
                            "name": getattr(client_info, 'name', None),
                            "title": getattr(client_info, 'title', None),
                        }
                        if result.get("name") or result.get("title"):
                            return result
                
                # Check if session is a dict-like object with client_info
                if isinstance(session, dict) and 'client_info' in session:
                    client_info = session['client_info']
                    result = {
                        "name": client_info.get('name') if isinstance(client_info, dict) else getattr(client_info, 'name', None),
                        "title": client_info.get('title') if isinstance(client_info, dict) else getattr(client_info, 'title', None),
                    }
                    if result.get("name") or result.get("title"):
                        return result
                
                # Try to access session ID and check cache
                session_id = getattr(session, 'id', None) or (session.get('id') if isinstance(session, dict) else None)
                if session_id and session_id in _client_info_cache:
                    cached_info = _client_info_cache[session_id]
                    if cached_info.get("name") or cached_info.get("title"):
                        return cached_info
            
            # Try meta field
            if hasattr(ctx, 'meta') and ctx.meta:
                meta = ctx.meta
                # print(f"DEBUG: Meta type: {type(meta)}, attributes: {[attr for attr in dir(meta) if not attr.startswith('_')]}")
                
                if hasattr(meta, 'client_info'):
                    client_info = meta.client_info
                    if client_info:
                        result = {
                            "name": getattr(client_info, 'name', None),
                            "title": getattr(client_info, 'title', None),
                        }
                        if result.get("name") or result.get("title"):
                            return result
                
                # Check if meta is dict-like
                if isinstance(meta, dict) and 'client_info' in meta:
                    client_info = meta['client_info']
                    result = {
                        "name": client_info.get('name') if isinstance(client_info, dict) else getattr(client_info, 'name', None),
                        "title": client_info.get('title') if isinstance(client_info, dict) else getattr(client_info, 'title', None),
                    }
                    if result.get("name") or result.get("title"):
                        return result
            
            # Try accessing client_info directly from context
            if hasattr(ctx, 'client_info'):
                client_info = ctx.client_info
                if client_info:
                    result = {
                        "name": getattr(client_info, 'name', None) if hasattr(client_info, 'name') else (client_info.get('name') if isinstance(client_info, dict) else None),
                        "title": getattr(client_info, 'title', None) if hasattr(client_info, 'title') else (client_info.get('title') if isinstance(client_info, dict) else None),
                    }
                    if result.get("name") or result.get("title"):
                        return result
            
            # Try to get all attributes and search for client-related fields
            for attr_name in dir(ctx):
                if 'client' in attr_name.lower() and not attr_name.startswith('_'):
                    try:
                        attr_value = getattr(ctx, attr_name)
                        if attr_value and (hasattr(attr_value, 'name') or (isinstance(attr_value, dict) and 'name' in attr_value)):
                            if hasattr(attr_value, 'name'):
                                name = getattr(attr_value, 'name', None)
                                title = getattr(attr_value, 'title', None)
                            elif isinstance(attr_value, dict):
                                name = attr_value.get('name')
                                title = attr_value.get('title')
                            else:
                                continue
                            
                            if name or title:
                                return {"name": name, "title": title}
                    except:
                        continue
                        
    except (LookupError, AttributeError, RuntimeError) as e:
        # Request context not available - this is normal outside of requests
        # print(f"DEBUG: Context error: {type(e).__name__}: {e}")
        pass
    except Exception as e:
        # Any other error - fail silently but log for debugging
        # print(f"DEBUG: Unexpected error getting client info: {type(e).__name__}: {e}")
        pass
    
    return None


def generate_secret_value(
    value_format: str = "random_string",
    value_length: int = 32,
    integer_min: int = 0,
    integer_max: int = 999999999,
    float_min: float = 0.0,
    float_max: float = 999999.99
) -> str:
    """
    Generate a secret value based on the specified format.
    This ensures values are generated server-side, not provided by LLM.
    
    Args:
        value_format: Type of value to generate
            - 'uuid': UUID v4 (36 characters, length ignored)
            - 'random_string': Alphanumeric string (default 32 chars)
            - 'token': URL-safe token (default 32 chars)
            - 'hex': Hexadecimal string (default 64 chars = 32 bytes)
            - 'base64': Base64-encoded string (default 44 chars = 32 bytes)
            - 'integer': Random integer (between integer_min and integer_max)
            - 'float': Random float (between float_min and float_max)
            - 'lowercase': Lowercase letters only (default 32 chars)
            - 'uppercase': Uppercase letters only (default 32 chars)
            - 'numeric': Digits only (default 32 chars)
            - 'alphanumeric_lower': Lowercase alphanumeric (default 32 chars)
        value_length: Length for string-based formats (ignored for uuid, integer, float)
        integer_min: Minimum value for integer format
        integer_max: Maximum value for integer format
        float_min: Minimum value for float format
        float_max: Maximum value for float format
    
    Returns:
        Generated secret value as string
    """
    import random
    
    if value_format == "uuid":
        return str(uuid.uuid4())
    
    elif value_format == "random_string":
        # Alphanumeric string (mixed case)
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return ''.join(secrets.choice(alphabet) for _ in range(value_length))
    
    elif value_format == "token":
        # URL-safe token
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        return ''.join(secrets.choice(alphabet) for _ in range(value_length))
    
    elif value_format == "hex":
        # Hexadecimal string (length in bytes, output is 2x length)
        bytes_length = value_length // 2 if value_length >= 2 else 1
        return secrets.token_hex(bytes_length)[:value_length] if value_length % 2 == 0 else secrets.token_hex((bytes_length + 1))[:value_length]
    
    elif value_format == "base64":
        # Base64-encoded string
        bytes_length = (value_length * 3) // 4  # Approximate bytes needed
        if bytes_length < 1:
            bytes_length = 1
        encoded = base64.urlsafe_b64encode(secrets.token_bytes(bytes_length)).decode('utf-8').rstrip('=')
        return encoded[:value_length] if len(encoded) >= value_length else encoded
    
    elif value_format == "integer":
        # Random integer
        if integer_min >= integer_max:
            integer_max = integer_min + 1
        return str(secrets.randbelow(integer_max - integer_min + 1) + integer_min)
    
    elif value_format == "float":
        # Random float
        if float_min >= float_max:
            float_max = float_min + 1.0
        random_float = random.uniform(float_min, float_max)
        # Format with reasonable precision
        return f"{random_float:.6f}".rstrip('0').rstrip('.')
    
    elif value_format == "lowercase":
        # Lowercase letters only
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        return ''.join(secrets.choice(alphabet) for _ in range(value_length))
    
    elif value_format == "uppercase":
        # Uppercase letters only
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return ''.join(secrets.choice(alphabet) for _ in range(value_length))
    
    elif value_format == "numeric":
        # Digits only
        alphabet = "0123456789"
        return ''.join(secrets.choice(alphabet) for _ in range(value_length))
    
    elif value_format == "alphanumeric_lower":
        # Lowercase alphanumeric
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
        return ''.join(secrets.choice(alphabet) for _ in range(value_length))
    
    else:
        # Default to random_string if unknown format
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return ''.join(secrets.choice(alphabet) for _ in range(value_length))


def get_mcp_request_metadata() -> dict:
    """
    Get additional metadata about the MCP request.
    Since MCP uses HTTP/SSE transport, we can capture HTTP request info.
    Returns a dict with available metadata.
    """
    import os
    import sys
    
    metadata = {
        "protocol": "MCP (HTTP/SSE)",
        "process_id": os.getpid(),
    }
    
    # Try to get HTTP request context from context variable
    try:
        from server.mcp.http_server import _http_request_ctx
        # Get the context - if not set, get() returns the default {}
        http_context = _http_request_ctx.get({})
        # Check if context actually has data (not just empty default)
        # An empty dict {} is the default, so check if it has actual keys
        if http_context and isinstance(http_context, dict) and len(http_context) > 0 and http_context.get("client_ip"):
            metadata["client_ip"] = http_context.get("client_ip", "unknown")
            metadata["user_agent"] = http_context.get("user_agent", "unknown")
            # Include key headers if available
            headers = http_context.get("headers", {})
            if headers:
                # Store headers in metadata
                metadata["headers"] = dict(headers)  # Make a copy
                # Include referer if available (helps identify source)
                if "referer" in headers:
                    metadata["referer"] = headers["referer"]
        else:
            # Context not available - might be stdio or context not set
            # This happens when context variable is not set (returns default {})
            metadata["client_ip"] = "unknown"
            metadata["user_agent"] = "unknown"
            metadata["context_status"] = "not_set"  # Debug: indicate context wasn't set
    except Exception as e:
        # If context variable access fails, log but continue
        metadata["client_ip"] = "unknown"
        metadata["user_agent"] = "unknown"
        metadata["context_error"] = str(e)
    
    # Try to get parent process info
    try:
        metadata["parent_process_id"] = os.getppid()
    except:
        pass
    
    # Check for environment variables that might indicate source
    env_vars = ['MCP_CLIENT', 'MCP_SOURCE', 'CLIENT_NAME']
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            metadata[var.lower()] = value
    
    # Get user info if available
    try:
        metadata["user"] = os.environ.get('USER') or os.environ.get('USERNAME')
    except:
        pass
    
    return metadata


def log_mcp_tool_invocation(
    tool_name: str,
    arguments: dict,
    token: Optional[str] = None,
    status_code: int = 200,
    execution_time_ms: Optional[int] = None,
    response_data: Optional[dict] = None,
    client_info: Optional[dict] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    headers: Optional[dict] = None
):
    """
    Log an MCP tool invocation as a separate activity.
    This represents the LLM calling the MCP tool.
    """
    # Debug: Log that function is being called
    print(f"DEBUG: log_mcp_tool_invocation called for tool: {tool_name}", file=sys.stderr)
    sys.stderr.flush()  # Force flush
    
    try:
        from ..models import SessionLocal, Activity
        from ..auth import hash_token, get_auth_context
        from fastapi.security import HTTPAuthorizationCredentials
        from fastapi import HTTPException
        print(f"DEBUG: Imports successful", file=sys.stderr)
        sys.stderr.flush()
    except (Exception, SystemExit) as import_error:
        # Catch both Exception and SystemExit (config.py calls sys.exit(1) if MASTER_TOKEN not set)
        # MCP server doesn't need MASTER_TOKEN - it just proxies to API
        print(f"DEBUG: Import error: {import_error}", file=sys.stderr)
        sys.stderr.flush()
        return  # Exit early if imports fail
    
    # If no token provided, skip logging (for tools like register_device, get_documentation)
    # These tools don't require authentication, so we can't log them with a token
    if not token or token == "anonymous":
        print(f"DEBUG: No token provided for tool {tool_name}, skipping activity logging", file=sys.stderr)
        sys.stderr.flush()
        return
    
    db = SessionLocal()
    print(f"DEBUG: Database session created", file=sys.stderr)
    sys.stderr.flush()
    try:
        # Determine token type
        print(f"DEBUG: Hashing token...", file=sys.stderr)
        token_hash = hash_token(token)
        print(f"DEBUG: Token hashed, checking token type...", file=sys.stderr)
        from ..models import MasterToken, Token
        # Try to get MASTER_TOKEN from config, but don't fail if it's not set
        try:
            from ..config import MASTER_TOKEN
        except SystemExit:
            # config.py exits if MASTER_TOKEN not set - that's OK for MCP server
            MASTER_TOKEN = None
        
        token_type = "unknown"
        project_name = None
        
        # Check if it's a master token
        master_token = db.query(MasterToken).filter(
            MasterToken.token_hash == token_hash
        ).first()
        
        if master_token:
            token_type = "master"
        else:
            # Check if it's a device_token (64 hex characters - SHA256 hash of device_id)
            if len(token) == 64 and all(c in '0123456789abcdef' for c in token.lower()):
                from ..models import Device
                device = db.query(Device).filter(
                    Device.device_id_hash == token.lower(),  # DB column name, but conceptually it's device_token
                    Device.status == "authorized"
                ).first()
                if device:
                    token_type = "device"
                    # Get project name from device's project
                    from ..models import Project
                    project = db.query(Project).filter(Project.id == device.project_id).first()
                    if project:
                        project_name = project.name
            
            # Check if it's a project token
            if token_type == "unknown":
                project_token = db.query(Token).filter(Token.token_hash == token_hash).first()
                if project_token:
                    token_type = "project"
                    # Get project name from token's project
                    from ..models import Project
                    project = db.query(Project).filter(Project.id == project_token.project_id).first()
                    if project:
                        project_name = project.name
        
        # Extract project name from arguments if not found from token
        if not project_name:
            project_name = arguments.get("project_name")
        
        # Mask sensitive arguments
        safe_args = {}
        for key, value in arguments.items():
            if key == "auth_token":
                if isinstance(value, str) and len(value) > 8:
                    safe_args[key] = f"{value[:4]}...{value[-4:]}"
                else:
                    safe_args[key] = "***"
            elif key == "value_format" and tool_name == "create_secret":
                # value_format is safe to include (it's just a format specifier)
                safe_args[key] = value
            else:
                safe_args[key] = value
        
        # Prepare request data
        # Get HTTP request metadata (client IP, user agent, etc.)
        # If client_ip, user_agent, headers are passed directly, use them
        # Otherwise, try to get from context variable
        if client_ip is None or user_agent is None:
            request_metadata = get_mcp_request_metadata()
            if client_ip is None:
                client_ip = request_metadata.get("client_ip", "unknown")
            if user_agent is None:
                user_agent = request_metadata.get("user_agent", "unknown")
            if headers is None:
                headers = request_metadata.get("headers", {})
        else:
            # Build metadata from passed parameters
            request_metadata = {
                "protocol": "MCP (HTTP/SSE)",
                "client_ip": client_ip,
                "user_agent": user_agent,
            }
            if headers:
                request_metadata["headers"] = headers
        
        # Determine client display: prefer client name, then IP, then "MCP"
        client_display = "MCP"
        
        if client_info and client_info.get("name"):
            client_display = f"MCP ({client_info.get('name')})"
            # Include IP in metadata
            if client_ip != "unknown":
                client_display += f" @ {client_ip}"
        elif client_info and client_info.get("title"):
            client_display = f"MCP ({client_info.get('title')})"
            if client_ip != "unknown":
                client_display += f" @ {client_ip}"
        elif client_ip != "unknown":
            # Use IP address if available
            client_display = f"MCP @ {client_ip}"
        
        request_data = {
            "client_ip": client_display,  # Show client identification with IP if available
            "source": "mcp",  # Top-level source field for filtering (3-state system: ui, api, mcp)
            "mcp": {
                "tool": tool_name,
                "arguments": safe_args,
                "source": "mcp_llm",  # Nested source for MCP-specific metadata
                "metadata": request_metadata  # Includes client_ip, user_agent, etc.
            }
        }
        
        # Add client information if available
        if client_info:
            request_data["mcp"]["client"] = client_info
        
        # Prepare response data
        import json
        response_data_json = None
        if response_data:
            from ..activity_logger import redact_exposed_values
            
            # Check if response_data has metadata (from internal API call)
            confidential_fields = []
            exposed_confidential_data = False
            
            if isinstance(response_data, dict) and "_confidential_fields" in response_data:
                # Use metadata from internal API response
                confidential_fields = response_data["_confidential_fields"]
                # Check if any confidential fields actually contain data
                for field in confidential_fields:
                    path_parts = field.get("path", "").split('.')
                    current = response_data
                    try:
                        for part in path_parts:
                            if part == "body" and "body" in current:
                                current = current["body"]
                            elif part in current:
                                current = current[part]
                            else:
                                current = None
                                break
                        
                        if current is not None and isinstance(current, str) and current != "***EXPOSED***":
                            exposed_confidential_data = True
                            break
                    except:
                        continue
            else:
                # Fallback to DB scan if no metadata
                from ..exposure_detector import check_for_exposed_data
                exposure_report = check_for_exposed_data(
                    request_data=json.dumps(request_data, default=str),
                    response_data=json.dumps(response_data, default=str),
                    db=db,
                    original_token=token
                )
                exposed_confidential_data = exposure_report.has_exposure
                # Convert to confidential_fields format
                if exposure_report.has_exposure:
                    confidential_fields = [
                        {
                            "path": f.field_path.replace("response.", "").replace("request.", ""),
                            "type": f.type,
                            "details": f.details
                        }
                        for f in exposure_report.findings
                    ]
            
            # CRITICAL: Redact exposed values BEFORE storing in database
            if exposed_confidential_data and confidential_fields:
                response_data = redact_exposed_values(response_data, confidential_fields, "response")
            
            # Remove _confidential_fields from response_data if present (we only need it for detection/redaction)
            if isinstance(response_data, dict) and "_confidential_fields" in response_data:
                response_data_clean = response_data.copy()
                del response_data_clean["_confidential_fields"]
            else:
                response_data_clean = response_data
            
            response_data_dict = {
                "body": response_data_clean,
                "exposed_confidential_data": exposed_confidential_data
            }
            
            response_data_json = json.dumps(response_data_dict, default=str)
        
        # Create activity
        print(f"DEBUG: Creating Activity object...", file=sys.stderr)
        activity = Activity(
            method="MCP",
            path=f"/mcp/tools/{tool_name}",
            action=f"mcp_{tool_name}",
            project_name=project_name,
            token_type=token_type,
            status_code=status_code,
            execution_time_ms=execution_time_ms,
            request_data=json.dumps(request_data, default=str),
            response_data=response_data_json
        )
        
        db.add(activity)
        print(f"DEBUG: Activity object created, committing to database...", file=sys.stderr)
        db.commit()
        print(f"DEBUG: Activity committed successfully! ID: {activity.id}", file=sys.stderr)
    except Exception as e:
        db.rollback()
        # Don't fail the tool call if logging fails, but log the error prominently
        import traceback
        error_msg = f"Failed to log MCP tool invocation: {e}"
        traceback_str = traceback.format_exc()
        # Print to stderr so it's visible in logs
        print(f"ERROR: {error_msg}", file=sys.stderr)
        print(f"ERROR TRACEBACK: {traceback_str}", file=sys.stderr)
        # Also log to a file for debugging (optional)
        try:
            with open("/tmp/vaulty_mcp_logging_errors.log", "a") as f:
                f.write(f"\n{datetime.now().isoformat()}: {error_msg}\n{traceback_str}\n")
        except:
            pass  # Don't fail if we can't write to log file
    finally:
        db.close()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    tools_list = [
        Tool(
            name="list-projects",
            description="List all projects in vaulty",
            inputSchema={
                "type": "object",
                "properties": {
                    "auth_token": {
                        "type": "string",
                        "description": "Authentication token: master token, project token, or device_token (64 hex chars, calculated as SHA256(device_id)) for authentication"
                    }
                },
                "required": ["auth_token"]
            }
        ),
        Tool(
            name="check-secret",
            description="Check if a secret exists in a project (returns existence status only, never the value).",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project"
                    },
                    "key": {
                        "type": "string",
                        "description": "Secret key to check"
                    },
                    "auth_token": {
                        "type": "string",
                        "description": "Authentication token: master token, project token, or device_token (64 hex chars, calculated as SHA256(device_id)) for authentication"
                    }
                },
                "required": ["project_name", "key", "auth_token"]
            }
        ),
        Tool(
            name="list-secrets",
            description="List all secrets in a project (keys only, not values)",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project"
                    },
                    "auth_token": {
                        "type": "string",
                        "description": "Authentication token: master token, project token, or device_token (64 hex chars, calculated as SHA256(device_id)) for authentication"
                    }
                },
                "required": ["project_name", "auth_token"]
            }
        ),
        Tool(
            name="create-secret",
            description="Create or update a secret in a project. The secret value will be automatically generated by the server. You can specify the format/type of value to generate (uuid, random_string, token, etc.). The generated value will NEVER be returned to prevent exposure.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project"
                    },
                    "key": {
                        "type": "string",
                        "description": "Secret key"
                    },
                    "value_format": {
                        "type": "string",
                        "description": "Format/type of value to generate. Options: 'uuid' (UUID v4), 'random_string' (32-char alphanumeric), 'token' (32-char URL-safe token), 'hex' (64-char hex string), 'base64' (44-char base64 string), 'integer' (random integer), 'float' (random float), 'lowercase' (32-char lowercase), 'uppercase' (32-char uppercase), 'numeric' (32-char digits only), 'alphanumeric_lower' (32-char lowercase alphanumeric). Default: 'random_string'",
                        "enum": ["uuid", "random_string", "token", "hex", "base64", "integer", "float", "lowercase", "uppercase", "numeric", "alphanumeric_lower"],
                        "default": "random_string"
                    },
                    "value_length": {
                        "type": "integer",
                        "description": "Optional: Length for string-based formats (default: 32 for strings, 64 for hex). Ignored for uuid, integer, float.",
                        "minimum": 1,
                        "maximum": 256,
                        "default": 32
                    },
                    "integer_min": {
                        "type": "integer",
                        "description": "Optional: Minimum value for integer format (default: 0)",
                        "default": 0
                    },
                    "integer_max": {
                        "type": "integer",
                        "description": "Optional: Maximum value for integer format (default: 999999999)",
                        "default": 999999999
                    },
                    "float_min": {
                        "type": "number",
                        "description": "Optional: Minimum value for float format (default: 0.0)",
                        "default": 0.0
                    },
                    "float_max": {
                        "type": "number",
                        "description": "Optional: Maximum value for float format (default: 999999.99)",
                        "default": 999999.99
                    },
                    "auth_token": {
                        "type": "string",
                        "description": "Authentication token: master token, project token, or device_token (64 hex chars, calculated as SHA256(device_id)) for authentication"
                    }
                },
                "required": ["project_name", "key", "auth_token"]
            }
        ),
        Tool(
            name="delete-secret",
            description="Delete a secret from a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project"
                    },
                    "key": {
                        "type": "string",
                        "description": "Secret key to delete"
                    },
                    "auth_token": {
                        "type": "string",
                        "description": "Authentication token: master token, project token, or device_token (64 hex chars, calculated as SHA256(device_id)) for authentication"
                    }
                },
                "required": ["project_name", "key", "auth_token"]
            }
        ),
        Tool(
            name="list-tokens",
            description="List all project tokens for a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project"
                    },
                    "auth_token": {
                        "type": "string",
                        "description": "Authentication token: master token, project token, or device_token (64 hex chars, calculated as SHA256(device_id)) for authentication"
                    }
                },
                "required": ["project_name", "auth_token"]
            }
        ),
        Tool(
            name="get-project",
            description="Get information about a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project"
                    },
                    "auth_token": {
                        "type": "string",
                        "description": "Authentication token: master token, project token, or device_token (64 hex chars, calculated as SHA256(device_id)) for authentication"
                    }
                },
                "required": ["project_name", "auth_token"]
            }
        ),
        Tool(
            name="get-docs",
            description="Get comprehensive API and MCP documentation. Returns complete documentation including all API endpoints, MCP tools, authentication methods, examples, and usage instructions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "auth_token": {
                        "type": "string",
                        "description": "Authentication token (optional, documentation endpoint doesn't require auth but token is used for activity logging)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="device-status",
            description="Check device registration status in a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project"
                    },
                    "device_name": {
                        "type": "string",
                        "description": "Optional device name to check. If not provided, uses device_id from working_directory"
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory path to generate device_id (defaults to current directory)"
                    },
                    "auth_token": {
                        "type": "string",
                        "description": "Authentication token: master token, project token, or device_token (64 hex chars, calculated as SHA256(device_id)) for authentication"
                    }
                },
                "required": ["project_name", "auth_token"]
            }
        ),
        Tool(
            name="list-devices",
            description="List all devices in a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project"
                    },
                    "status": {
                        "type": "string",
                        "description": "Optional status filter: pending, authorized, or rejected",
                        "enum": ["pending", "authorized", "rejected"]
                    },
                    "auth_token": {
                        "type": "string",
                        "description": "Authentication token: master token, project token, or device_token (64 hex chars, calculated as SHA256(device_id)) for authentication"
                    }
                },
                "required": ["project_name", "auth_token"]
            }
        ),
        Tool(
            name="list-activities",
            description="List activity history for a project. Returns activities from the last 7 days with pagination support.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of activities to return (1-100, default: 25)",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 25
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of activities to skip (default: 0)",
                        "minimum": 0,
                        "default": 0
                    },
                    "method": {
                        "type": "string",
                        "description": "Filter by HTTP method (e.g., 'MCP', 'GET', 'POST'). Optional."
                    },
                    "exclude_ui": {
                        "type": "boolean",
                        "description": "Exclude UI-initiated requests (default: false)",
                        "default": False
                    },
                    "auth_token": {
                        "type": "string",
                        "description": "Authentication token: master token, project token, or device_token (64 hex chars, calculated as SHA256(device_id)) for authentication"
                    }
                },
                "required": ["project_name", "auth_token"]
            }
        ),
        Tool(
            name="register",
            description="Register a new device in a project. Devices are registered as 'pending' and require manual approval (unless auto-approval tags match). After approval, devices authenticate using device_token (SHA256 hash of device_id). The device_id must be provided by the client. No authentication token required.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project to register the device in"
                    },
                    "name": {
                        "type": "string",
                        "description": "Device name/identifier"
                    },
                    "user_agent": {
                        "type": "string",
                        "description": "User agent string (used to detect OS server-side)"
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Current working directory of the device"
                },
                    "device_id": {
                        "type": "string",
                        "description": "Required: 32-character hex device ID. Generate it client-side using: hash(pwd) + hash(hostname) + MAC. Then hash it locally (SHA256) to get device_token (64 hex chars) for authentication: device_token = SHA256(device_id)."
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for categorization. Devices with tags matching project's auto_approval_tag_pattern will be automatically approved."
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description of the device"
                    },
                    "auth_token": {
                        "type": "string",
                        "description": "Optional: Authentication token (master token, project token, or device_token) for activity logging and automatic rejection on timeout (not required for registration itself)"
                    }
                },
                "required": ["project_name", "name", "user_agent", "working_directory", "device_id"]
            }
        ),
    ]
    
    # In safe mode, don't expose tools that could leak secret values
    # delete-secret is excluded in safe mode (prevents accidental deletion)
    # create-secret is handled in call_tool with a check
    # get-secret is not available (safe mode blocks secret value exposure)
    # check-secret is allowed in safe mode (only returns true/false, not values)
    
    # Filter out delete-secret in safe mode
    if MCP_SAFE_MODE:
        tools_list = [tool for tool in tools_list if tool.name not in ["delete-secret"]]
    
    return tools_list


async def call_api(
    method: str,
    endpoint: str,
    token: Optional[str] = None,
    json_data: Optional[dict] = None,
    params: Optional[dict] = None,
    mcp_tool_name: Optional[str] = None,
    mcp_arguments: Optional[dict] = None
) -> tuple[int, dict, str]:
    """
    Make an internal API call to the REST API.
    Returns: (status_code, response_json, response_text)
    Activity logging happens automatically via API middleware.
    This is logged as a regular API call (not MCP), since it's an internal call from MCP server to API.
    
    Args:
        token: Optional authentication token (master token, project token, or device_token).
               If None, request is made without authentication.
    """
    url = f"{API_BASE_URL}{endpoint}"
    headers = {
        "X-Internal-API-Call": "true",  # Identify this as an internal API call from MCP server
        "X-Client-IP": "127.0.0.1"  # Internal call from localhost
    }
    
    # Add Authorization header only if token is provided
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        if method.upper() == "GET":
            response = await http_client.get(url, headers=headers, params=params)
        elif method.upper() == "POST":
            response = await http_client.post(url, headers=headers, json=json_data, params=params)
        elif method.upper() == "PATCH":
            response = await http_client.patch(url, headers=headers, json=json_data, params=params)
        elif method.upper() == "DELETE":
            response = await http_client.delete(url, headers=headers, params=params)
        else:
            return 405, {}, "Method not allowed"
        
        response_text = response.text
        try:
            response_json = response.json()
        except:
            response_json = {}
        
        return response.status_code, response_json, response_text
    except httpx.RequestError as e:
        return 500, {"error": f"API request failed: {str(e)}"}, str(e)


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls - all operations go through the REST API
    
    Authentication: For tools requiring auth (except register_device and get_documentation),
    the 'auth_token' parameter accepts:
    - Master token (from database or environment)
    - Project token (for project-specific access)
    - device_token (64 hex characters, calculated as SHA256(device_id) - for device authentication)
    """
    # Tools that don't require authentication
    no_auth_tools = ["register", "get-docs"]
    
    # Get auth token (can be master token, project token, or device_token)
    auth_token = arguments.get("auth_token")
    
    # For tools that require authentication, check if token is provided
    if name not in no_auth_tools:
        if not auth_token:
            return [TextContent(
                type="text",
                text=json.dumps({"error": "auth_token is required (can be master token, project token, or device_token)"}, indent=2)
            )]
    
    # Debug: Check if HTTP context is accessible
    try:
        from server.mcp.http_server import _http_request_ctx
        http_context = _http_request_ctx.get({})
        if http_context and len(http_context) > 0:
            print(f"DEBUG: HTTP context available in call_tool: {http_context}", file=sys.stderr)
        else:
            print(f"DEBUG: HTTP context NOT available in call_tool (got: {http_context})", file=sys.stderr)
    except Exception as e:
        print(f"DEBUG: Error accessing HTTP context: {e}", file=sys.stderr)
    
    # Get MCP client information from request context
    client_info = get_mcp_client_info()
    
    # Debug: Inspect request context to see what's available
    try:
        ctx = server.request_context()
        if ctx:
            ctx_attrs = [attr for attr in dir(ctx) if not attr.startswith('_')]
            print(f"DEBUG: Request context attributes: {ctx_attrs}", file=sys.stderr)
            if hasattr(ctx, 'session'):
                session = ctx.session
                session_attrs = [attr for attr in dir(session) if not attr.startswith('_')] if session else []
                print(f"DEBUG: Session attributes: {session_attrs}", file=sys.stderr)
                if isinstance(session, dict):
                    print(f"DEBUG: Session dict keys: {list(session.keys())}", file=sys.stderr)
    except Exception as e:
        print(f"DEBUG: Could not inspect context: {e}", file=sys.stderr)
    
    # Debug: Print client info if available
    if client_info:
        print(f"DEBUG: MCP Client Info captured: {client_info}", file=sys.stderr)
    else:
        print(f"DEBUG: No MCP Client Info available", file=sys.stderr)
    
    project_name = None
    response_text = ""
    start_time = time.time()
    
    # Use auth_token variable name for clarity (can be master token, project token, or device_token)
    # Keep using 'master_token' parameter name for API calls to maintain consistency
    master_token = auth_token
    
    try:
        if name == "list-projects":
            status_code, response_json, response_text = await call_api(
                "GET", "/api/projects", auth_token
            )
            execution_time = int((time.time() - start_time) * 1000)
            
            result = response_json if status_code == 200 else response_json
            
            # Try to get HTTP context from context variable
            http_client_ip = None
            http_user_agent = None
            http_headers = None
            try:
                from server.mcp.http_server import _http_request_ctx
                http_context = _http_request_ctx.get({})
                if http_context and len(http_context) > 0:
                    http_client_ip = http_context.get("client_ip")
                    http_user_agent = http_context.get("user_agent")
                    http_headers = http_context.get("headers")
            except:
                pass
            
            # Log MCP tool invocation
            log_mcp_tool_invocation(
                tool_name=name,
                arguments=arguments,
                token=master_token,
                status_code=status_code,
                execution_time_ms=execution_time,
                response_data=result,
                client_info=client_info,
                client_ip=http_client_ip,
                user_agent=http_user_agent,
                headers=http_headers
            )
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "check-secret":
            project_name = arguments.get("project_name")
            key = arguments.get("key")
            
            # Try to get the secret - if 404, it doesn't exist
            status_code, response_json, response_text = await call_api(
                "GET", 
                f"/api/projects/{project_name}/secrets/{key}", 
                auth_token
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            if status_code == 200:
                result = {
                    "exists": True,
                    "project_name": project_name,
                    "key": key,
                    "message": f"Secret '{key}' exists in project '{project_name}'. Use REST API to retrieve the value securely."
                }
            elif status_code == 404:
                result = {
                    "exists": False,
                    "project_name": project_name,
                    "key": key,
                    "message": f"Secret '{key}' does not exist in project '{project_name}'"
                }
            else:
                result = response_json
            
            # Try to get HTTP context from context variable
            http_client_ip = None
            http_user_agent = None
            http_headers = None
            try:
                from server.mcp.http_server import _http_request_ctx
                http_context = _http_request_ctx.get({})
                if http_context and len(http_context) > 0:
                    http_client_ip = http_context.get("client_ip")
                    http_user_agent = http_context.get("user_agent")
                    http_headers = http_context.get("headers")
            except:
                pass
            
            # Log MCP tool invocation
            log_mcp_tool_invocation(
                tool_name=name,
                arguments=arguments,
                token=master_token,
                status_code=status_code,
                execution_time_ms=execution_time,
                response_data=result,
                client_info=client_info,
                client_ip=http_client_ip,
                user_agent=http_user_agent,
                headers=http_headers
            )
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "list-secrets":
            project_name = arguments.get("project_name")
            status_code, response_json, response_text = await call_api(
                "GET", 
                f"/api/projects/{project_name}/secrets", 
                auth_token
            )
            execution_time = int((time.time() - start_time) * 1000)
            
            if status_code == 200:
                # SECURITY: Only return keys and metadata, NEVER secret values
                result = [
                    {
                        "key": s.get("key"),
                        "created_at": s.get("created_at"),
                        "updated_at": s.get("updated_at"),
                        "note": "Use REST API to retrieve secret values securely"
                    }
                    for s in response_json
                ]
            else:
                result = response_json
            
            # Try to get HTTP context from context variable
            http_client_ip = None
            http_user_agent = None
            http_headers = None
            try:
                from server.mcp.http_server import _http_request_ctx
                http_context = _http_request_ctx.get({})
                if http_context and len(http_context) > 0:
                    http_client_ip = http_context.get("client_ip")
                    http_user_agent = http_context.get("user_agent")
                    http_headers = http_context.get("headers")
            except:
                pass
            
            # Log MCP tool invocation
            log_mcp_tool_invocation(
                tool_name=name,
                arguments=arguments,
                token=master_token,
                status_code=status_code,
                execution_time_ms=execution_time,
                response_data=result,
                client_info=client_info,
                client_ip=http_client_ip,
                user_agent=http_user_agent,
                headers=http_headers
            )
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "create-secret":
            project_name = arguments.get("project_name")
            key = arguments.get("key")
            value_format = arguments.get("value_format", "random_string")
            value_length = arguments.get("value_length", 32)
            integer_min = arguments.get("integer_min", 0)
            integer_max = arguments.get("integer_max", 999999999)
            float_min = arguments.get("float_min", 0.0)
            float_max = arguments.get("float_max", 999999.99)
            
            # SECURITY: Generate value on server side - LLM never provides the value
            # This prevents the value from being in tool call parameters (which may be logged)
            generated_value = generate_secret_value(
                value_format=value_format,
                value_length=value_length,
                integer_min=integer_min,
                integer_max=integer_max,
                float_min=float_min,
                float_max=float_max
            )
            
            status_code, response_json, response_text = await call_api(
                "POST",
                f"/api/projects/{project_name}/secrets",
                auth_token,
                json_data={"key": key, "value": generated_value}
            )
            execution_time = int((time.time() - start_time) * 1000)
            
            if status_code in [200, 201]:
                # SECURITY: Response NEVER includes the secret value
                result = {
                    "success": True,
                    "message": f"Secret '{key}' created/updated successfully in project '{project_name}' with {value_format} format. The generated value has been stored securely.",
                    "project_name": project_name,
                    "key": key,
                    "value_format": value_format,
                    "value_length": value_length if value_format not in ["uuid", "integer", "float"] else None,
                    "security_note": "Secret value was generated server-side and stored securely. Value is NOT included in this response. Use REST API to retrieve the value if needed."
                }
                # Remove None values
                result = {k: v for k, v in result.items() if v is not None}
            else:
                result = response_json
            
            # Try to get HTTP context from context variable
            http_client_ip = None
            http_user_agent = None
            http_headers = None
            try:
                from server.mcp.http_server import _http_request_ctx
                http_context = _http_request_ctx.get({})
                if http_context and len(http_context) > 0:
                    http_client_ip = http_context.get("client_ip")
                    http_user_agent = http_context.get("user_agent")
                    http_headers = http_context.get("headers")
            except:
                pass
            
            # Log MCP tool invocation
            log_mcp_tool_invocation(
                tool_name=name,
                arguments=arguments,
                token=master_token,
                status_code=status_code,
                execution_time_ms=execution_time,
                response_data=result,
                client_info=client_info,
                client_ip=http_client_ip,
                user_agent=http_user_agent,
                headers=http_headers
            )
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "delete-secret":
            # Block delete-secret in safe mode
            if MCP_SAFE_MODE:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "delete-secret is disabled in safe mode",
                        "message": "delete-secret tool is not available when MCP_SAFE_MODE is enabled. This prevents accidental deletion of secrets through the MCP interface."
                    }, indent=2)
                )]
            
            project_name = arguments.get("project_name")
            key = arguments.get("key")
            
            status_code, response_json, response_text = await call_api(
                "DELETE",
                f"/api/projects/{project_name}/secrets/{key}",
                auth_token
            )
            execution_time = int((time.time() - start_time) * 1000)
            
            if status_code == 204:
                result = {
                    "message": f"Secret '{key}' deleted successfully from project '{project_name}'",
                    "project_name": project_name,
                    "key": key
                }
            else:
                result = response_json
            
            # Try to get HTTP context from context variable
            http_client_ip = None
            http_user_agent = None
            http_headers = None
            try:
                from server.mcp.http_server import _http_request_ctx
                http_context = _http_request_ctx.get({})
                if http_context and len(http_context) > 0:
                    http_client_ip = http_context.get("client_ip")
                    http_user_agent = http_context.get("user_agent")
                    http_headers = http_context.get("headers")
            except:
                pass
            
            # Log MCP tool invocation
            log_mcp_tool_invocation(
                tool_name=name,
                arguments=arguments,
                token=master_token,
                status_code=status_code,
                execution_time_ms=execution_time,
                response_data=result,
                client_info=client_info,
                client_ip=http_client_ip,
                user_agent=http_user_agent,
                headers=http_headers
            )
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "list-tokens":
            project_name = arguments.get("project_name")
            status_code, response_json, response_text = await call_api(
                "GET",
                f"/api/projects/{project_name}/tokens",
                auth_token
            )
            execution_time = int((time.time() - start_time) * 1000)
            
            result = response_json
            
            # Try to get HTTP context from context variable
            http_client_ip = None
            http_user_agent = None
            http_headers = None
            try:
                from server.mcp.http_server import _http_request_ctx
                http_context = _http_request_ctx.get({})
                if http_context and len(http_context) > 0:
                    http_client_ip = http_context.get("client_ip")
                    http_user_agent = http_context.get("user_agent")
                    http_headers = http_context.get("headers")
            except:
                pass
            
            # Log MCP tool invocation
            log_mcp_tool_invocation(
                tool_name=name,
                arguments=arguments,
                token=master_token,
                status_code=status_code,
                execution_time_ms=execution_time,
                response_data=result,
                client_info=client_info,
                client_ip=http_client_ip,
                user_agent=http_user_agent,
                headers=http_headers
            )
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "list-activities":
            project_name = arguments.get("project_name")
            limit = arguments.get("limit", 25)
            offset = arguments.get("offset", 0)
            method = arguments.get("method")
            exclude_ui = arguments.get("exclude_ui", False)
            
            # Build query parameters
            params = {
                "limit": limit,
                "offset": offset,
                "exclude_ui": exclude_ui
            }
            if method:
                params["method"] = method
            
            # List activities
            status_code, response_json, response_text = await call_api(
                "GET",
                f"/api/projects/{project_name}/activities",
                auth_token,
                params=params
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            if status_code == 200:
                result = response_json
            else:
                result = response_json
            
            # Log MCP tool invocation
            http_client_ip = None
            http_user_agent = None
            http_headers = None
            try:
                from server.mcp.http_server import _http_request_ctx
                http_context = _http_request_ctx.get({})
                if http_context and len(http_context) > 0:
                    http_client_ip = http_context.get("client_ip")
                    http_user_agent = http_context.get("user_agent")
                    http_headers = http_context.get("headers")
            except:
                pass
            
            if master_token:
                log_mcp_tool_invocation(
                    tool_name=name,
                    arguments=arguments,
                    token=master_token,
                    status_code=status_code,
                    execution_time_ms=execution_time,
                    response_data=result,
                    client_info=client_info,
                    client_ip=http_client_ip,
                    user_agent=http_user_agent,
                    headers=http_headers
                )
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "get-project":
            project_name = arguments.get("project_name")
            status_code, response_json, response_text = await call_api(
                "GET",
                f"/api/projects/{project_name}",
                auth_token
            )
            
            if status_code == 200:
                # Get secrets and tokens counts via API
                secrets_status, secrets_json, _ = await call_api(
                    "GET",
                    f"/api/projects/{project_name}/secrets",
                    auth_token
                )
                tokens_status, tokens_json, _ = await call_api(
                    "GET",
                    f"/api/projects/{project_name}/tokens",
                    auth_token
                )
                devices_status, devices_json, _ = await call_api(
                    "GET",
                    f"/api/projects/{project_name}/devices",
                    auth_token
                )
                
                # Devices API returns a list directly, not a dict
                devices_count = 0
                if devices_status == 200:
                    if isinstance(devices_json, list):
                        devices_count = len(devices_json)
                    elif isinstance(devices_json, dict) and "devices" in devices_json:
                        devices_count = len(devices_json["devices"])
                    elif isinstance(devices_json, dict) and "count" in devices_json:
                        devices_count = devices_json["count"]
                
                result = {
                    **response_json,
                    "stats": {
                        "secrets_count": len(secrets_json) if secrets_status == 200 else 0,
                        "tokens_count": len(tokens_json) if tokens_status == 200 else 0,
                        "devices_count": devices_count
                    }
                }
            else:
                result = response_json
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # Try to get HTTP context from context variable
            http_client_ip = None
            http_user_agent = None
            http_headers = None
            try:
                from server.mcp.http_server import _http_request_ctx
                http_context = _http_request_ctx.get({})
                if http_context and len(http_context) > 0:
                    http_client_ip = http_context.get("client_ip")
                    http_user_agent = http_context.get("user_agent")
                    http_headers = http_context.get("headers")
            except:
                pass
            
            # Log MCP tool invocation (only if token provided)
            if master_token:
                log_mcp_tool_invocation(
                tool_name=name,
                arguments=arguments,
                token=master_token,
                status_code=status_code,
                execution_time_ms=execution_time,
                response_data=result,
                client_info=client_info,
                client_ip=http_client_ip,
                user_agent=http_user_agent,
                headers=http_headers
            )
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "device-status":
            project_name = arguments.get("project_name")
            device_name = arguments.get("device_name")
            working_directory = arguments.get("working_directory")
            
            # Get device status
            if device_name:
                # Find device by name
                status_code, devices_json, _ = await call_api(
                "GET",
                    f"/api/projects/{project_name}/devices",
                    auth_token
                )
                
                if status_code == 200:
                    device = next((d for d in devices_json if d.get("name") == device_name), None)
                    if device:
                        result = {
                            "success": True,
                            "device": device,
                            "status": device.get("status"),
                            "message": f"Device '{device_name}' status: {device.get('status')}"
                        }
                    else:
                        result = {
                            "success": False,
                            "error": "Device not found",
                            "message": f"Device '{device_name}' not found in project '{project_name}'"
                        }
                else:
                    result = devices_json
            else:
                # Would need device_id from working_directory - simplified for now
                result = {
                    "error": "device_name or device_id required",
                    "message": "Please provide device_name or device_id to check status"
                }
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # Log MCP tool invocation
            http_client_ip = None
            http_user_agent = None
            http_headers = None
            try:
                from server.mcp.http_server import _http_request_ctx
                http_context = _http_request_ctx.get({})
                if http_context and len(http_context) > 0:
                    http_client_ip = http_context.get("client_ip")
                    http_user_agent = http_context.get("user_agent")
                    http_headers = http_context.get("headers")
            except:
                pass
            
                log_mcp_tool_invocation(
                    tool_name=name,
                    arguments=arguments,
                    token=master_token,
                status_code=200 if result.get("success") else 404,
                    execution_time_ms=execution_time,
                    response_data=result,
                    client_info=client_info,
                    client_ip=http_client_ip,
                    user_agent=http_user_agent,
                    headers=http_headers
            )
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "list-devices":
            project_name = arguments.get("project_name")
            status_filter = arguments.get("status")
            
            # List devices
            status_code, response_json, response_text = await call_api(
                "GET",
                f"/api/projects/{project_name}/devices",
                auth_token
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            if status_code == 200:
                devices = response_json
                
                # Filter by status if provided
                if status_filter:
                    devices = [d for d in devices if d.get("status") == status_filter]
                
            result = {
                "success": True,
                "devices": devices,
                "count": len(devices),
                "message": f"Found {len(devices)} device(s) in project '{project_name}'"
            }
            if status_filter:
                result["filter"] = status_filter
            else:
                result = response_json
            
            # Log MCP tool invocation
            http_client_ip = None
            http_user_agent = None
            http_headers = None
            try:
                from server.mcp.http_server import _http_request_ctx
                http_context = _http_request_ctx.get({})
                if http_context and len(http_context) > 0:
                    http_client_ip = http_context.get("client_ip")
                    http_user_agent = http_context.get("user_agent")
                    http_headers = http_context.get("headers")
            except:
                pass
            
            log_mcp_tool_invocation(
                tool_name=name,
                arguments=arguments,
                token=master_token,
                status_code=status_code,
                execution_time_ms=execution_time,
                response_data=result,
                client_info=client_info,
                client_ip=http_client_ip,
                user_agent=http_user_agent,
                headers=http_headers
            )
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "register":
            project_name = arguments.get("project_name")
            device_name = arguments.get("name")
            user_agent = arguments.get("user_agent")
            working_directory = arguments.get("working_directory")
            device_id = arguments.get("device_id")
            tags = arguments.get("tags")
            description = arguments.get("description")
            
            # Validate required fields
            if not device_id:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "device_id is required",
                        "message": "device_id must be provided. Generate it client-side using: hash(pwd) + hash(hostname) + MAC (32 hex chars). Then hash it locally (SHA256) to get device_token for authentication: device_token = SHA256(device_id)."
                    }, indent=2)
                )]
            
            # Build request payload
            payload = {
                "project_name": project_name,
                "name": device_name,
                "user_agent": user_agent,
                "working_directory": working_directory,
                "device_id": device_id  # Required - generated client-side
            }
            
            # Add optional fields if provided
            if tags:
                payload["tags"] = tags
            if description:
                payload["description"] = description
            
            # Device registration doesn't require authentication
            # But we can use token for activity logging and rejection if provided
            status_code, response_json, response_text = await call_api(
                "POST",
                "/api/devices",
                token=auth_token,  # Optional - for activity logging and rejection
                json_data=payload
            )
            
            # Check if project doesn't exist
            if status_code == 404:
                result = {
                    "error": "Project not found",
                    "message": f"Project '{project_name}' does not exist. Please create the project first.",
                    "project_name": project_name,
                    "suggestion": "Use the create_project API endpoint or MCP tool to create the project before registering devices."
                }
            elif status_code in [200, 201]:
                device_status = response_json.get("status")
                device_id_value = response_json.get("id")
                
                # If device was auto-approved, return success immediately
                if device_status == "authorized":
                    result = {
                        "success": True,
                        "message": f"Device '{device_name}' registered and auto-approved in project '{project_name}'",
                        "device": {
                            "id": device_id_value,
                            "name": response_json.get("name"),
                            "status": device_status,
                            "created_at": response_json.get("created_at"),
                            "authorized_at": response_json.get("authorized_at"),
                            "authorized_by": response_json.get("authorized_by")
                        },
                        "note": "Device was auto-approved based on tag patterns. Ready to use. Hash your device_id locally (SHA256) to get device_token for authentication: device_token = SHA256(device_id)."
                    }
                else:
                    # Device is pending - wait for authorization for up to 5 minutes
                    result = {
                        "success": True,
                        "message": f"Device '{device_name}' registered successfully in project '{project_name}'. Waiting for authorization...",
                        "device": {
                            "id": device_id_value,
                            "name": response_json.get("name"),
                            "status": device_status,
                            "created_at": response_json.get("created_at")
                        },
                        "waiting_for_authorization": True,
                        "note": "Device is pending authorization. Please authorize the device within 5 minutes."
                    }
                    
                    # Poll device status for up to 5 minutes (300 seconds)
                    # Wait for server response: authorized, rejected, or timeout
                    max_wait_time = 300  # 5 minutes
                    poll_interval = 1  # Check every 1 second
                    elapsed_time = 0
                    final_status = None
                    device_status_json = None
                    
                    while elapsed_time < max_wait_time:
                        await asyncio.sleep(poll_interval)
                        elapsed_time += poll_interval
                        
                        # Check device status (no auth required now)
                        device_status_code, device_status_json, _ = await call_api(
                            "GET",
                            f"/api/projects/{project_name}/devices/{device_id_value}",
                            token=None  # No auth required for device status check
                        )
                        
                        if device_status_code == 200:
                            current_status = device_status_json.get("status")
                            
                            if current_status == "authorized":
                                # Device was authorized - return success
                                final_status = "authorized"
                                result = {
                                    "success": True,
                                    "message": f"Device '{device_name}' authorized successfully in project '{project_name}'",
                                    "device": {
                                        "id": device_id_value,
                                        "name": device_status_json.get("name"),
                                        "status": current_status,
                                        "created_at": device_status_json.get("created_at"),
                                        "authorized_at": device_status_json.get("authorized_at"),
                                        "authorized_by": device_status_json.get("authorized_by")
                                    },
                                    "wait_time_seconds": elapsed_time,
                                    "note": "Device is now authorized and ready to use. Hash your device_id locally (SHA256) to get device_token for authentication: device_token = SHA256(device_id)."
                                }
                                break
                            elif current_status == "rejected":
                                # Device was rejected - return rejection
                                final_status = "rejected"
                                result = {
                                    "success": False,
                                    "message": f"Device '{device_name}' was rejected in project '{project_name}'",
                                    "device": {
                                        "id": device_id_value,
                                        "name": device_status_json.get("name"),
                                        "status": current_status,
                                        "created_at": device_status_json.get("created_at"),
                                        "rejected_at": device_status_json.get("rejected_at"),
                                        "rejected_by": device_status_json.get("rejected_by")
                                    },
                                    "wait_time_seconds": elapsed_time,
                                    "note": "Device registration was rejected."
                                }
                                break
                            # If still "pending", continue polling
                        elif device_status_code == 404:
                            # Device was deleted/rejected (hard delete)
                            final_status = "rejected"
                            result = {
                                "success": False,
                                "message": f"Device '{device_name}' was rejected/deleted in project '{project_name}'",
                                "device_id": device_id_value,
                                "wait_time_seconds": elapsed_time,
                                "note": "Device registration was rejected and device was removed."
                            }
                            break
                    
                    # If timeout reached and still pending, reject the device
                    if final_status is None:
                        # Timeout - device was not authorized or rejected within 5 minutes
                        # Try to reject the device (requires auth token for rejection)
                        if auth_token:
                            reject_status, _, _ = await call_api(
                                "PATCH",
                                f"/api/projects/{project_name}/devices/{device_id_value}/reject",
                                token=auth_token
                            )
                            if reject_status == 204:
                                result = {
                                    "success": False,
                                    "message": f"Device '{device_name}' was not authorized within 5 minutes and has been rejected",
                                    "device_id": device_id_value,
                                    "wait_time_seconds": elapsed_time,
                                    "status": "rejected",
                                    "reason": "timeout",
                                    "note": "Device registration timed out after 5 minutes. Please try again and authorize the device promptly."
                                }
                            else:
                                # Couldn't reject (maybe already rejected/deleted)
                                result = {
                                    "success": False,
                                    "message": f"Device '{device_name}' was not authorized within 5 minutes",
                                    "device_id": device_id_value,
                                    "wait_time_seconds": elapsed_time,
                                    "status": "timeout",
                                    "note": "Device registration timed out. Device may have been manually rejected or deleted."
                                }
                        else:
                            # No auth token - can't auto-reject, but return timeout
                            result = {
                                "success": False,
                                "message": f"Device '{device_name}' was not authorized within 5 minutes",
                                "device_id": device_id_value,
                                "wait_time_seconds": elapsed_time,
                                "status": "timeout",
                                "note": "Device registration timed out. No authentication token provided, so device could not be automatically rejected. Please manually reject or authorize the device."
                }
            else:
                result = response_json
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # Try to get HTTP context from context variable
            http_client_ip = None
            http_user_agent = None
            http_headers = None
            try:
                from server.mcp.http_server import _http_request_ctx
                http_context = _http_request_ctx.get({})
                if http_context and len(http_context) > 0:
                    http_client_ip = http_context.get("client_ip")
                    http_user_agent = http_context.get("user_agent")
                    http_headers = http_context.get("headers")
            except:
                pass
            
            # Log MCP tool invocation (only if token provided for activity logging)
            if master_token:
                log_mcp_tool_invocation(
                tool_name=name,
                arguments=arguments,
                token=master_token,
                status_code=status_code,
                execution_time_ms=execution_time,
                response_data=result,
                client_info=client_info,
                client_ip=http_client_ip,
                user_agent=http_user_agent,
                headers=http_headers
            )
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "get-docs":
            # Get documentation from API (doesn't require auth, but we use token for activity logging)
            # If no token provided, we'll still fetch the docs but log it differently
            status_code, response_json, response_text = await call_api(
                "GET",
                "/api/docs",
                token=auth_token  # Optional - for activity logging only
            )
            execution_time = int((time.time() - start_time) * 1000)
            
            result = response_json if status_code == 200 else response_json
            
            # Try to get HTTP context from context variable
            http_client_ip = None
            http_user_agent = None
            http_headers = None
            try:
                from server.mcp.http_server import _http_request_ctx
                http_context = _http_request_ctx.get({})
                if http_context and len(http_context) > 0:
                    http_client_ip = http_context.get("client_ip")
                    http_user_agent = http_context.get("user_agent")
                    http_headers = http_context.get("headers")
            except:
                pass
            
            # Log MCP tool invocation (use provided token or "anonymous" for logging)
            if master_token:
                log_mcp_tool_invocation(
                tool_name=name,
                arguments=arguments,
                token=master_token,
                    status_code=status_code,
                execution_time_ms=execution_time,
                    response_data=result,
                    client_info=client_info,
                    client_ip=http_client_ip,
                    user_agent=http_user_agent,
                    headers=http_headers
            )
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        else:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"}, indent=2)
            )]
    
    except Exception as e:
        execution_time = int((time.time() - start_time) * 1000)
        error_result = {"error": f"Error: {str(e)}"}
        
        # Log MCP tool invocation even on error (only if token provided)
        try:
            if master_token:
                log_mcp_tool_invocation(
                tool_name=name,
                arguments=arguments,
                    token=master_token,
                status_code=500,
                execution_time_ms=execution_time,
                response_data=error_result
            )
        except:
            pass  # Don't fail if logging fails
        
        return [TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]


@dataclass
class NotificationOptions:
    """Notification options for MCP server capabilities"""
    tools_changed: bool = False


# Export server and NotificationOptions for use in HTTP/SSE endpoints
__all__ = ['server', 'NotificationOptions', 'http_client']

