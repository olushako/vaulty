"""
Standalone HTTP/SSE server for MCP
Runs separately from the FastAPI API server
Communicates with the API via HTTP
"""

import asyncio
import sys
from mcp.server.sse import SseServerTransport
from server.mcp.server import server, NotificationOptions, http_client
from mcp.server.models import InitializationOptions
import os

# API base URL - defaults to localhost:8000
API_BASE_URL = os.getenv("VAULTY_API_URL", "http://localhost:8000")

# Create SSE transport
transport = SseServerTransport("/mcp/sse")

# Create NotificationOptions
notif_opts = NotificationOptions()

# Store HTTP request context (client IP, headers, etc.) per connection
# Use contextvars to store request info that can be accessed during tool calls
import contextvars

# Context variable to store current HTTP request info
_http_request_ctx: contextvars.ContextVar[dict] = contextvars.ContextVar('http_request_context', default={})

# Global storage for HTTP context per session/connection
# Keyed by session_id or connection identifier
_http_context_store: dict[str, dict] = {}


def extract_client_ip_from_scope(scope: dict) -> str:
    """Extract client IP address from ASGI scope"""
    # Check X-Forwarded-For header first (for proxies)
    headers = dict(scope.get("headers", []))
    x_forwarded_for = None
    x_real_ip = None
    
    for key, value in headers.items():
        if key.lower() == b'x-forwarded-for':
            x_forwarded_for = value.decode('utf-8') if isinstance(value, bytes) else value
        elif key.lower() == b'x-real-ip':
            x_real_ip = value.decode('utf-8') if isinstance(value, bytes) else value
    
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return x_forwarded_for.split(',')[0].strip()
    elif x_real_ip:
        return x_real_ip
    elif "client" in scope and scope["client"]:
        # Direct client connection
        return scope["client"][0]
    else:
        return "unknown"


def extract_headers_from_scope(scope: dict) -> dict:
    """Extract HTTP headers from ASGI scope"""
    headers = {}
    for key, value in scope.get("headers", []):
        key_str = key.decode('utf-8') if isinstance(key, bytes) else key
        value_str = value.decode('utf-8') if isinstance(value, bytes) else value
        headers[key_str] = value_str
    return headers


async def mcp_sse_app(scope, receive, send):
    """ASGI app for MCP SSE endpoint"""
    if scope["type"] != "http":
        return
    
    # CORS headers for cross-origin requests (e.g., from frontend)
    cors_headers = [
        [b"access-control-allow-origin", b"*"],
        [b"access-control-allow-methods", b"GET, POST, OPTIONS"],
        [b"access-control-allow-headers", b"Content-Type, Authorization"],
        [b"access-control-max-age", b"3600"],
    ]
    
    # Handle OPTIONS preflight requests
    method = scope.get("method", "")
    if method == "OPTIONS":
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": cors_headers + [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": b"",
        })
        return
    
    # Only handle /mcp/sse path (with or without query string)
    path = scope.get("path", "")
    # Extract base path without query string for comparison
    base_path = path.split("?")[0] if "?" in path else path
    if base_path != "/mcp/sse":
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": cors_headers + [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"error": "Not found"}',
        })
        return
    
    method = scope["method"]
    
    # Extract HTTP request information
    client_ip = extract_client_ip_from_scope(scope)
    headers = extract_headers_from_scope(scope)
    user_agent = headers.get('user-agent', 'unknown')
    
    # Log HTTP request (for debugging)
    print(f"HTTP Request: {method} {path} from {client_ip} (User-Agent: {user_agent[:50]})", file=sys.stderr)
    sys.stderr.flush()
    
    # Store HTTP context in context variable for access during tool calls
    http_context = {
        "client_ip": client_ip,
        "headers": headers,
        "user_agent": user_agent,
        "method": method,
        "path": path,
    }
    
    # Set context variable for this request
    token = _http_request_ctx.set(http_context)
    
    try:
        if method == "GET":
            # For GET requests, we need to inject CORS headers into the SSE response
            # We'll wrap the send function to add CORS headers
            original_send = send
            
            async def send_with_cors(message):
                if message.get("type") == "http.response.start":
                    # Add CORS headers to the response
                    existing_headers = message.get("headers", [])
                    message["headers"] = cors_headers + existing_headers
                await original_send(message)
            
            # Establish SSE connection with CORS headers
            # Keep context alive for the duration of the SSE connection
            # so tool calls can access it
            async with transport.connect_sse(scope, receive, send_with_cors) as streams:
                # Store connection context in server for access during tool calls
                # The MCP SDK might not expose this directly, so we store it globally
                # and access it via connection_id
                await server.run(
                    streams[0],  # read_stream
                    streams[1],   # write_stream
                    InitializationOptions(
                        server_name="vaulty",
                        server_version="1.0.0",
                        capabilities=server.get_capabilities(notif_opts, None)
                    )
                )
            # Context is reset after SSE connection closes
            _http_request_ctx.reset(token)
        elif method == "POST":
            # Handle POST messages
            # POST messages for tool calls should also have context set
            # (they come from the same client as the GET connection)
            # Set context for POST messages so tool calls can access it
            post_token = _http_request_ctx.set(http_context)
            try:
                await transport.handle_post_message(scope, receive, send)
            finally:
                # Reset context after POST message is handled
                _http_request_ctx.reset(post_token)
        else:
            # Method not allowed
            await send({
                "type": "http.response.start",
                "status": 405,
                "headers": cors_headers + [[b"content-type", b"application/json"]],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"error": "Method not allowed"}',
            })
            _http_request_ctx.reset(token)
    except Exception:
        # Ensure context is reset even on error
        _http_request_ctx.reset(token)
        raise


# Use the ASGI app directly
app = mcp_sse_app


if __name__ == "__main__":
    import uvicorn
    import atexit
    
    # Register cleanup on exit
    def cleanup():
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(http_client.aclose())
            else:
                loop.run_until_complete(http_client.aclose())
        except:
            pass
    
    atexit.register(cleanup)
    
    # Get port from environment or default to 8001
    port = int(os.getenv("MCP_SERVER_PORT", "8001"))
    
    print(f"Starting MCP HTTP/SSE server on port {port}")
    print(f"API server URL: {API_BASE_URL}")
    print(f"MCP endpoint: http://localhost:{port}/mcp/sse")
    
    # Run the ASGI app
    uvicorn.run(app, host="0.0.0.0", port=port)

