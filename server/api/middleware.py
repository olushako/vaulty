"""Middleware for API"""
import time
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..activity_logger import log_activity
from ..confidential_tracker import ConfidentialTracker
from .utils import get_client_ip


class ActivityLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API activities"""
    async def dispatch(self, request: Request, call_next):
        # Record start time
        start_time = time.time()
        
        # Capture request data
        # Get client IP address - check X-Client-IP first (for MCP calls), then X-Forwarded-For, then X-Real-IP, then actual client
        client_ip = None
        if request.headers.get("X-Client-IP"):
            # MCP calls set this to "MCP"
            client_ip = request.headers.get("X-Client-IP")
        elif request.headers.get("x-forwarded-for"):
            # X-Forwarded-For can contain multiple IPs, take the first one
            client_ip = request.headers.get("x-forwarded-for").split(",")[0].strip()
        elif request.headers.get("x-real-ip"):
            client_ip = request.headers.get("x-real-ip")
        elif request.client:
            client_ip = request.client.host
        
        request_data = {
            "client_ip": client_ip,
            "headers": dict(request.headers),
            "query_params": dict(request.query_params),
            "path_params": dict(request.path_params) if hasattr(request, 'path_params') else {},
            "body": None
        }
        
        # Extract MCP tool information if present (only for direct MCP calls, not internal API calls)
        if request.headers.get("X-MCP-Source") == "true" and not request.headers.get("X-Internal-API-Call"):
            mcp_tool = request.headers.get("X-MCP-Tool")
            mcp_args = request.headers.get("X-MCP-Arguments")
            if mcp_tool or mcp_args:
                request_data["mcp"] = {
                    "tool": mcp_tool,
                    "arguments": json.loads(mcp_args) if mcp_args else None,
                    "source": "mcp"
                }
        
        # Determine source: 3-state system (ui, api, mcp)
        # State 1: MCP calls (both direct and internal)
        if request.headers.get("X-Internal-API-Call") == "true" or request.headers.get("X-MCP-Source") == "true":
            # All MCP-related calls (internal server-to-server or direct MCP tool calls)
            request_data["source"] = "mcp"
            if request.headers.get("X-Internal-API-Call") == "true":
                request_data["internal_api_call"] = True
        else:
            # Check if request is from the frontend/UI
            # Frontend requests typically have:
            # - Referer header pointing to the frontend URL
            # - Origin header matching the frontend
            # - Or we can check if it's from the same origin
            referer = request.headers.get("referer", "")
            origin = request.headers.get("origin", "")
            
            # Check if referer or origin indicates it's from the frontend
            # Frontend typically runs on the same host or has a specific pattern
            is_ui_request = False
            user_agent = request.headers.get("user-agent", "").lower()
            
            # Check referer first (most reliable for frontend requests)
            if referer:
                # Check if referer is from the frontend (same origin or localhost)
                if "localhost" in referer.lower() or "127.0.0.1" in referer or referer.startswith("/"):
                    is_ui_request = True
            # Check origin
            if origin:
                # Check if origin is from the frontend
                if "localhost" in origin.lower() or "127.0.0.1" in origin:
                    is_ui_request = True
            # Check Sec-Fetch-Site header (modern browsers set this for same-origin requests)
            if request.headers.get("sec-fetch-site") == "same-origin":
                is_ui_request = True
            # Fallback: Check if it's localhost with browser-like user-agent
            if not is_ui_request and client_ip in ["127.0.0.1", "localhost"]:
                # If it's localhost, check user-agent
                # Exclude curl and other non-browser clients
                if user_agent and "curl" not in user_agent and "wget" not in user_agent and "python" not in user_agent:
                    # If it has a browser-like user-agent, it's likely from UI
                    if "mozilla" in user_agent or "chrome" in user_agent or "safari" in user_agent or "firefox" in user_agent or "electron" in user_agent:
                        is_ui_request = True
            
            if is_ui_request:
                # State 2: UI requests (from frontend)
                request_data["source"] = "ui"
            else:
                # State 3: External API calls (remote clients using tokens)
                request_data["source"] = "api"
        
        # Read request body if present (for POST, PUT, PATCH)
        body_bytes = b""
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body_bytes = await request.body()
                if body_bytes:
                    # Try to parse as JSON, otherwise store as string
                    try:
                        request_data["body"] = json.loads(body_bytes.decode('utf-8'))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        request_data["body"] = body_bytes.decode('utf-8', errors='replace')
            except Exception as e:
                request_data["body_error"] = str(e)
        
        # Recreate request with body if we consumed it
        if body_bytes:
            async def receive():
                return {"type": "http.request", "body": body_bytes}
            request._receive = receive
        
        # Process request
        response = await call_next(request)
        
        # Capture response data
        response_data = {
            "headers": dict(response.headers),
            "body": None
        }
        
        # Read response body
        try:
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk
            
            if response_body:
                # Try to parse as JSON, otherwise store as string
                try:
                    response_data["body"] = json.loads(response_body.decode('utf-8'))
                    
                    # V2: Add confidential metadata based on endpoint and response structure
                    # This allows fast O(1) exposure detection without DB scanning
                    path = str(request.url.path)
                    
                    # Mark secrets returned from get_secret endpoints
                    if "/secrets/" in path and path.endswith("/secrets/" + path.split("/secrets/")[-1]):
                        # This is a get_secret endpoint
                        if isinstance(response_data["body"], dict) and "value" in response_data["body"]:
                            secret_key = response_data["body"].get("key", "unknown")
                            project_name = path.split("/projects/")[1].split("/")[0] if "/projects/" in path else None
                            ConfidentialTracker.mark_secret(
                                response_data,
                                "body.value",
                                secret_key,
                                project_name or "unknown"
                            )
                    
                    # Mark tokens returned from create_token endpoints
                    if path.endswith("/tokens") and request.method == "POST":
                        if isinstance(response_data["body"], dict) and "token" in response_data["body"]:
                            token_type = "project"  # Project tokens
                            project_name = path.split("/projects/")[1].split("/")[0] if "/projects/" in path else None
                            token_name = response_data["body"].get("name", "unknown")
                            token_id = response_data["body"].get("id")
                            ConfidentialTracker.mark_token(
                                response_data,
                                "body.token",
                                token_type,
                                token_name,
                                token_id,
                                project_name
                            )
                    
                    # Mark master tokens
                    if path == "/api/master-tokens" and request.method == "POST":
                        if isinstance(response_data["body"], dict) and "token" in response_data["body"]:
                            ConfidentialTracker.mark_token(
                                response_data,
                                "body.token",
                                "master",
                                response_data["body"].get("name", "unknown"),
                                response_data["body"].get("id")
                            )
                    
                except (json.JSONDecodeError, UnicodeDecodeError):
                    response_data["body"] = response_body.decode('utf-8', errors='replace')
            
            # Create new response with the body (since we consumed it)
            from starlette.responses import Response as StarletteResponse
            new_response = StarletteResponse(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        except Exception as e:
            response_data["body_error"] = str(e)
            new_response = response
        
        # Calculate execution time
        execution_time_ms = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Log activity after response is generated
        await log_activity(request, new_response, execution_time_ms, request_data, response_data)
        return new_response

