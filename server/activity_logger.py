"""
Activity logging middleware and utilities for tracking API activities.
"""
from fastapi import Request, Response
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Any

from .models import Activity, SessionLocal, Token, MasterToken
from .auth import hash_token
from .exposure_detector import check_for_exposed_data, ExposureReport
from .confidential_tracker import check_exposure_from_metadata


def mask_tokens_in_data(data: dict) -> dict:
    """
    Mask Bearer tokens, token fields, and secret values in request/response data.
    Returns a deep copy with sensitive data masked.
    """
    import copy
    
    if not isinstance(data, dict):
        return data
    
    masked_data = copy.deepcopy(data)
    
    # Mask Authorization header (Bearer token)
    # Format: Bearer {first4}{asterisks}{last4} (matching UI display exactly)
    if 'headers' in masked_data and isinstance(masked_data['headers'], dict):
        # Find authorization header (case-insensitive) and preserve original key case
        auth_key = None
        auth_value = None
        for key in masked_data['headers'].keys():
            if key.lower() == 'authorization':
                auth_key = key
                auth_value = masked_data['headers'][key]
                break
        
        if auth_key and isinstance(auth_value, str):
            # Extract token from Bearer header (handle various formats)
            token = None
            auth_lower = auth_value.lower().strip()
            
            if auth_lower.startswith('bearer '):
                # Standard format: "Bearer <token>"
                token = auth_value[7:].strip()
            elif auth_lower.startswith('bearer'):
                # Format without space: "Bearer<token>" (uncommon but possible)
                token = auth_value[6:].strip()
            else:
                # Try to extract token if it looks like a Bearer token format
                import re
                match = re.match(r'bearer\s+(.+)', auth_lower)
                if match:
                    token = match.group(1).strip()
            
            if token and len(token) > 0:
                # Skip if token is already masked (starts with asterisks)
                is_already_masked = (token.startswith('*') and len(token) > 8 and 
                                   not any(c.isalnum() for c in token[:4]))
                
                if not is_already_masked:
                    if len(token) > 8:
                        # Show first 4, asterisks for middle, last 4
                        start = token[:4]
                        end = token[-4:]
                        asterisks = '*' * max(8, len(token) - 8)
                        masked_data['headers'][auth_key] = f"Bearer {start}{asterisks}{end}"
                    elif len(token) > 0:
                        # For tokens 8 chars or less, mask completely
                        masked_data['headers'][auth_key] = f"Bearer {'*' * len(token)}"
                # If already masked, leave it as is
    
    # Mask token fields in body
    if 'body' in masked_data and isinstance(masked_data['body'], dict):
        masked_data['body'] = _mask_tokens_in_dict(masked_data['body'])
    
    return masked_data


def redact_exposed_values(data: Any, confidential_fields: list, location: str) -> Any:
    """
    Redact exposed values in data based on confidential fields metadata.
    Replaces exposed values with "***EXPOSED***" to ensure they're never stored.
    """
    import copy
    import json
    
    if not confidential_fields:
        return data
    
    # Convert to JSON and back to get a clean copy
    try:
        data_json = json.dumps(data, default=str)
        redacted = json.loads(data_json)
    except:
        redacted = copy.deepcopy(data)
    
    # For each confidential field, navigate to it and redact it
    for field in confidential_fields:
        # Parse field path (e.g., "body.value" or "body.token")
        path_parts = field.get("path", "").split('.')
        
        if not path_parts:
            continue
        
        # Navigate to the field and redact it
        current = redacted
        for i, part in enumerate(path_parts):
            # Handle array indices like "secrets[0]"
            if '[' in part and ']' in part:
                key = part.split('[')[0]
                index = int(part.split('[')[1].split(']')[0])
                if key in current and isinstance(current[key], list) and index < len(current[key]):
                    if i == len(path_parts) - 1:
                        # Last part - redact this array element
                        current[key][index] = "***EXPOSED***"
                        break
                    else:
                        current = current[key][index]
                else:
                    break
            else:
                # Regular dict key
                if part in current:
                    if i == len(path_parts) - 1:
                        # Last part - this is the field to redact
                        current[part] = "***EXPOSED***"
                        break
                    else:
                        # Navigate deeper
                        if isinstance(current[part], (dict, list)):
                            current = current[part]
                        else:
                            break
                else:
                    break
    
    return redacted


def _mask_tokens_in_dict(data: Any) -> Any:
    """Recursively mask token fields and secret values in a dictionary or nested structure"""
    import copy
    
    if isinstance(data, dict):
        masked = copy.deepcopy(data)
        for key, value in masked.items():
            # Mask fields that commonly contain tokens
            # Format: {first4}{asterisks}{last4} (matching UI display exactly)
            # BUT: Don't mask if already redacted as exposed
            if key.lower() in ['token', 'master_token', 'api_token', 'access_token', 'bearer_token', 'auth_token']:
                if value == '***EXPOSED***':
                    # Already redacted as exposed, preserve it
                    masked[key] = '***EXPOSED***'
                elif isinstance(value, str) and len(value) > 8:
                    # Show first 4, asterisks for middle, last 4
                    start = value[:4]
                    end = value[-4:]
                    asterisks = '*' * max(8, len(value) - 8)
                    masked[key] = f"{start}{asterisks}{end}"
                elif isinstance(value, str) and len(value) <= 8:
                    # For tokens 8 chars or less, mask completely
                    masked[key] = '*' * len(value)
            # Mask secret values (value field in secret creation/update requests)
            # But don't overwrite if already marked as exposed
            elif key.lower() == 'value' and isinstance(value, str) and len(value) > 0:
                # If already marked as exposed, keep it
                if value == '***EXPOSED***':
                    masked[key] = '***EXPOSED***'
                else:
                    # Only mask if not exposed (for request data or non-exposed responses)
                    # In responses, if it's not "***EXPOSED***", it shouldn't be there at all
                    # But for safety, mask it anyway
                    masked[key] = '***REDACTED***'
            elif isinstance(value, (dict, list)):
                masked[key] = _mask_tokens_in_dict(value)
        return masked
    elif isinstance(data, list):
        return [_mask_tokens_in_dict(item) for item in data]
    else:
        return data


def get_action_from_path(method: str, path: str) -> str:
    """Extract a human-readable action from the API path"""
    # Remove /api prefix
    if path.startswith('/api'):
        path = path[4:]
    
    # Remove query parameters
    if '?' in path:
        path = path.split('?')[0]
    
    # Map common patterns (check more specific patterns first)
    
    # Master tokens
    if path == '/master-tokens' and method == 'POST':
        return 'create_master_token'
    elif path == '/master-tokens' and method == 'GET':
        return 'list_master_tokens'
    elif path.startswith('/master-tokens/') and '/rotate' in path and method == 'POST':
        return 'rotate_master_token'
    elif path.startswith('/master-tokens/') and method == 'DELETE':
        return 'revoke_master_token'
    
    # Projects
    elif path == '/projects' and method == 'POST':
        return 'create_project'
    elif path == '/projects' and method == 'GET':
        return 'list_projects'
    # Check nested paths first (more specific)
    elif path.startswith('/projects/') and path.endswith('/activities') and method == 'GET':
        return 'get_activities'
    elif path.startswith('/projects/') and path.endswith('/tokens') and method == 'POST':
        return 'create_token'
    elif path.startswith('/projects/') and path.endswith('/tokens') and method == 'GET':
        return 'list_tokens'
    elif path.startswith('/projects/') and '/secrets/' in path and method == 'GET':
        return 'get_secret'
    elif path.startswith('/projects/') and '/secrets/' in path and method == 'DELETE':
        return 'delete_secret'
    elif path.startswith('/projects/') and path.endswith('/secrets') and method == 'POST':
        return 'create_secret'
    elif path.startswith('/projects/') and path.endswith('/secrets') and method == 'GET':
        return 'list_secrets'
    # Then check single project paths (less specific)
    elif path.startswith('/projects/') and method == 'GET':
        # Single project name (no additional path)
        parts = [p for p in path.split('/') if p]  # Remove empty strings
        if len(parts) == 2:  # projects/{name}
            return 'get_project'
    elif path.startswith('/projects/') and method == 'DELETE':
        # Single project name (no additional path)
        parts = [p for p in path.split('/') if p]  # Remove empty strings
        if len(parts) == 2:  # projects/{name}
            return 'delete_project'
    
    # Tokens
    elif path.startswith('/tokens/') and method == 'DELETE':
        return 'revoke_token'
    
    # Fallback
    return f"{method.lower()}_{path.replace('/', '_').strip('_')}"


def extract_project_name(path: str) -> Optional[str]:
    """Extract project name from API path if applicable"""
    if '/projects/' in path:
        parts = path.split('/projects/')
        if len(parts) > 1:
            # Get the part after /projects/
            project_part = parts[1].split('/')[0]
            # Only return if it's not a UUID (UUIDs have dashes and are 36 chars)
            if len(project_part) != 36 or '-' not in project_part:
                return project_part
    return None


def get_token_type(request, db: Session) -> str:
    """Determine if the request uses a master token, project token, or device token and update last_used"""
    from datetime import datetime
    from .models import Device
    
    # Handle both Request objects and dict-like objects
    if hasattr(request, 'headers'):
        if hasattr(request.headers, 'get'):
            auth_header = request.headers.get('Authorization', '')
        else:
            auth_header = request.headers.get('Authorization', '') if isinstance(request.headers, dict) else ''
    else:
        auth_header = ''
    if not auth_header.startswith('Bearer '):
        return 'none'
    
    token_str = auth_header[7:]
    token_hash = hash_token(token_str)
    
    # Check if it's a master token
    master_token = db.query(MasterToken).filter(
        MasterToken.token_hash == token_hash
    ).first()
    
    if master_token:
        # Update last_used timestamp
        master_token.last_used = datetime.utcnow()
        db.commit()
        return 'master'
    
    # Check if it's a project token
    project_token = db.query(Token).filter(Token.token_hash == token_hash).first()
    if project_token:
        # Update last_used timestamp
        project_token.last_used = datetime.utcnow()
        db.commit()
        return 'project'
    
    # Check if it's a device_token (64 hex characters - SHA256 hash of device_id)
    if len(token_str) == 64 and all(c in '0123456789abcdef' for c in token_str.lower()):
        device = db.query(Device).filter(
            Device.device_id_hash == token_str.lower(),  # DB column name, but conceptually it's device_token
            Device.status == "authorized"
        ).first()
        if device:
            # Device tokens don't have last_used, but we can update device.updated_at if needed
            # For now, just return 'device'
            return 'device'
    
    # No fallback - token must exist in database
    return 'unknown'


def _log_activity_sync_safe(safe_request_data: dict, safe_response_data: dict, execution_time_ms: float = None, request_data: dict = None, response_data: dict = None):
    """Synchronous logging function (runs in background thread) - uses safe request data"""
    import json
    from starlette.requests import Request
    from starlette.responses import Response
    
    # Skip logging for health checks or non-API endpoints
    path = safe_request_data.get('path', '')
    if not path.startswith('/api'):
        return
    
    # Log ALL API and MCP events - no exclusions
    # Extract path for logging
    method = safe_request_data.get('method', 'GET')
    
    # Remove /api prefix for action detection
    if path.startswith('/api'):
        path = path[4:]
    
    # Remove query parameters
    if '?' in path:
        path = path.split('?')[0]
    
    db = SessionLocal()
    try:
        headers = safe_request_data.get('headers', {})
        
        # Check if this is an MCP-initiated call (for method detection)
        # Note: source is already determined by middleware and stored in request_data["source"]
        # We only need to check for MCP calls to set method = "MCP" for direct MCP tool calls
        is_mcp_call = headers.get("X-MCP-Source") == "true" and not headers.get("X-Internal-API-Call") == "true"
        
        # For direct MCP calls (not internal), set method to "MCP"
        # Internal API calls from MCP server keep their original HTTP method
        method = "MCP" if is_mcp_call else method
        status_code = safe_response_data.get('status_code', 200)
        
        # For MCP calls (legacy direct calls), use MCP tool name if available
        if is_mcp_call:
            http_method = method
            # Get MCP tool name from header (available before request_data processing)
            mcp_tool = headers.get("X-MCP-Tool")
            
            if mcp_tool:
                # Use the actual MCP tool name (e.g., "get_secret", "list_projects")
                action = f"mcp_{mcp_tool}"
            else:
                # Fallback to path-based action
                action = f"mcp_{get_action_from_path(http_method, path)}"
            # Update path to show MCP source
            path = f"/mcp{path}"
        else:
            # Regular API call (including internal calls from MCP server)
            action = get_action_from_path(method, path)
        
        project_name = extract_project_name(path)
        # Create a minimal request-like object for get_token_type
        class MinimalRequest:
            def __init__(self, headers_dict):
                class Headers:
                    def get(self, key, default=None):
                        return headers_dict.get(key, default)
                self.headers = Headers()
        
        minimal_request = MinimalRequest(headers)
        token_type = get_token_type(minimal_request, db)
        
        # Convert execution time to milliseconds (round to integer)
        execution_time = int(execution_time_ms) if execution_time_ms is not None else None
        
        # Serialize request and response data to JSON strings
        # Limit size to prevent database bloat (max 10KB per field)
        MAX_DATA_SIZE = 10 * 1024  # 10KB
        
        request_data_json = None
        response_data_json = None
        
        if request_data:
            try:
                # Mask tokens in requests (they're expected, not exposed, but we mask for security)
                masked_request_data = mask_tokens_in_data(request_data)
                request_data_json = json.dumps(masked_request_data, default=str)
                # Truncate if too large
                if len(request_data_json) > MAX_DATA_SIZE:
                    request_data_json = request_data_json[:MAX_DATA_SIZE] + '... (truncated)'
            except Exception as e:
                request_data_json = json.dumps({"error": f"Failed to serialize request data: {str(e)}"})
        
        # Extract original token for exposure detection
        original_token = None
        auth_header = headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            original_token = auth_header[7:]
        
        # Check for exposed confidential data using metadata
        # V2: Use fast metadata-based detection (O(1))
        exposed_confidential_data = False
        confidential_fields = []
        
        if response_data and isinstance(response_data, dict):
            # Check for confidential fields metadata
            confidential_fields = response_data.get("_confidential_fields", [])
            if confidential_fields:
                # Check if any confidential fields actually contain data (not already redacted)
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
                        
                        # If field exists and has actual data (not already redacted), it's exposed
                        if current is not None and isinstance(current, str) and current != "***EXPOSED***":
                            exposed_confidential_data = True
                            break
                    except:
                        continue
            
            # Fallback to DB scan only if no metadata available
            if not confidential_fields:
                # For exposure detection, use original unmasked data
                original_request_json = json.dumps(request_data, default=str) if request_data else None
                response_data_for_check = response_data.copy() if response_data else {}
                from .exposure_detector import check_for_exposed_data
                exposure_report = check_for_exposed_data(
                    request_data=original_request_json,
                    response_data=json.dumps(response_data_for_check, default=str) if response_data_for_check else None,
                    db=db,
                    original_token=original_token
                )
                exposed_confidential_data = exposure_report.has_exposure
                # Convert exposure_report findings to confidential_fields format for redaction
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
                # Redact exposed values in response data
                if response_data:
                    response_data = redact_exposed_values(response_data, confidential_fields, "response")
        
        if response_data:
            try:
                # For large responses (like lists), only store summary
                if response_data.get("body"):
                    body = response_data["body"]
                    # If it's a list and too large, summarize it
                    if isinstance(body, list) and len(body) > 10:
                        response_data["body"] = {
                            "_summary": f"List with {len(body)} items",
                            "_preview": body[:5] if len(body) > 5 else body
                        }
                    # If it's a dict with large arrays, truncate arrays
                    elif isinstance(body, dict):
                        for key, value in body.items():
                            if isinstance(value, list) and len(value) > 10:
                                body[key] = value[:5] + [f"... ({len(value) - 5} more items)"]
                
                # Add exposure information to response data
                if not isinstance(response_data, dict):
                    response_data = {"body": response_data}
                response_data["exposed_confidential_data"] = exposed_confidential_data
                # Remove _confidential_fields metadata - we only need it for detection/redaction, not storage
                if "_confidential_fields" in response_data:
                    del response_data["_confidential_fields"]
                
                # No masking needed for responses - exposed values are already redacted to "***EXPOSED***"
                # Non-exposed responses shouldn't contain sensitive data anyway
                masked_response_data = response_data
                
                response_data_json = json.dumps(masked_response_data, default=str)
                # Truncate if still too large
                if len(response_data_json) > MAX_DATA_SIZE:
                    response_data_json = response_data_json[:MAX_DATA_SIZE] + '... (truncated)'
            except Exception as e:
                response_data_json = json.dumps({
                    "error": f"Failed to serialize response data: {str(e)}",
                    "exposed_confidential_data": exposed_confidential_data
                })
        else:
            # Even if no response_data, store the exposure flag
            response_data_json = json.dumps({
                "exposed_confidential_data": exposed_confidential_data
            })
        
        activity = Activity(
            method=method,
            path=path,
            action=action,
            project_name=project_name,
            token_type=token_type,
            status_code=status_code,
            execution_time_ms=execution_time,
            request_data=request_data_json,
            response_data=response_data_json
        )
        
        db.add(activity)
        db.commit()
    except Exception as e:
        # Don't fail the request if logging fails
        db.rollback()
        import traceback
        import sys
        error_msg = f"ERROR: Failed to log activity: {e}"
        traceback_str = traceback.format_exc()
        print(error_msg, file=sys.stderr)
        print(f"ERROR Traceback: {traceback_str}", file=sys.stderr)
        sys.stderr.flush()
        # Also log to file for debugging
        try:
            with open("/tmp/vaulty_activity_logging_errors.log", "a") as f:
                from datetime import datetime
                f.write(f"\n{datetime.now().isoformat()}: Failed to log activity\n")
                f.write(f"Error: {e}\n")
                f.write(f"Traceback: {traceback_str}\n")
                f.write(f"Method: {safe_request_data.get('method', 'unknown')}\n")
                f.write(f"Path: {safe_request_data.get('path', 'unknown')}\n")
        except:
            pass
    finally:
        db.close()


async def log_activity(request: Request, response: Response, execution_time_ms: float = None, request_data: dict = None, response_data: dict = None):
    """Log an API activity to the database (async wrapper for background thread)"""
    import threading
    import sys
    
    # Extract request data that can be safely passed to background thread
    # Request objects are tied to async context and may not work in threads
    safe_request_data = {
        'method': request.method,
        'path': str(request.url.path),
        'headers': dict(request.headers),
        'query_params': dict(request.query_params),
    }
    
    safe_response_data = {
        'status_code': response.status_code,
        'headers': dict(response.headers),
    }
    
    # Run logging in background thread to avoid blocking request
    thread = threading.Thread(
        target=_log_activity_sync_safe,
        args=(safe_request_data, safe_response_data, execution_time_ms, request_data, response_data),
        daemon=True
    )
    thread.start()
    # Don't wait for completion - let it run in background


def cleanup_old_activities(days: int = 7):
    """Remove activities older than specified days"""
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted_count = db.query(Activity).filter(
            Activity.created_at < cutoff_date
        ).delete()
        db.commit()
        
        # Run VACUUM periodically to reclaim space (every 1000 deletions or so)
        # This helps keep the database size manageable
        if deleted_count > 0 and deleted_count % 1000 == 0:
            try:
                db.execute(text("VACUUM"))
                db.commit()
                print(f"Ran VACUUM after {deleted_count} deletions")
            except Exception as e:
                print(f"VACUUM failed (non-critical): {e}")
        
        return deleted_count
    except Exception as e:
        db.rollback()
        print(f"Failed to cleanup activities: {e}")
        return 0
    finally:
        db.close()
















