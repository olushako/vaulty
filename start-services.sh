#!/bin/bash
set -e

# Function to handle shutdown
cleanup() {
    echo "Shutting down services..."
    kill $(jobs -p) 2>/dev/null || true
    exit 0
}

# Trap SIGTERM and SIGINT
trap cleanup SIGTERM SIGINT

# Start Backend API Server (port 8000)
echo "Starting Backend API Server on port 8000..."
cd /app
uvicorn server.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start MCP Server (port 9000, configurable via MCP_SERVER_PORT env var)
echo "Starting MCP Server on port ${MCP_SERVER_PORT:-9000}..."
cd /app
python3 -m server.mcp.http_server &
MCP_PID=$!

# Start Frontend Server (port 3000)
echo "Starting Frontend Server on port 3000..."
cd /app/frontend
npm run preview -- --host 0.0.0.0 --port 3000 &
FRONTEND_PID=$!

# Wait for all services to be ready
sleep 3

# Check if services are running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ Backend server failed to start"
    exit 1
fi

if ! kill -0 $MCP_PID 2>/dev/null; then
    echo "❌ MCP server failed to start"
    exit 1
fi

if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "❌ Frontend server failed to start"
    exit 1
fi

echo "✅ All services started successfully:"
echo "   - Backend API: http://localhost:8000"
echo "   - MCP Server: http://localhost:${MCP_SERVER_PORT:-9000}"
echo "   - Frontend: http://localhost:3000"

# Wait for all background processes
wait

