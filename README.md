# Vaulty Secrets Manager

A secure secrets management system with MCP (Model Context Protocol) integration, featuring a RESTful API, MCP server, web frontend, and CLI client.

## Architecture

- **Backend API** (Port 8000): FastAPI REST server
- **MCP Server** (Port 9000): Model Context Protocol server for AI assistants
- **Frontend** (Port 3000): React + TypeScript web interface

## Quick Start

### Docker (Recommended)

1. **Generate a master token**:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

2. **Set MASTER_TOKEN** in `docker-compose.yml` or as environment variable:
```bash
export MASTER_TOKEN="your-generated-token-here"
```

3. **Deploy**:
```bash
docker-compose up -d --build
```

4. **Access services**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - MCP Server: http://localhost:9000/mcp/sse

### Local Development

**Backend & MCP**:
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export MASTER_TOKEN="your-token-here"

# Terminal 1: Backend API
uvicorn server.main:app --host 0.0.0.0 --port 8000

# Terminal 2: MCP Server
uvicorn server.mcp.http_server:app --host 0.0.0.0 --port 9000
```

**Frontend**:
```bash
cd frontend && npm install && npm run dev
```

**CLI Client**:
```bash
# Install system-wide
pip install -e .

# Use from any directory
vaulty --help
```

## Client CLI

### Installation

Install the CLI system-wide (recommended):
```bash
pip install -e .
```

After installation, use the `vaulty` command from any directory:
```bash
vaulty --help
```

### Usage

**Device Management**:
```bash
vaulty token                    # Get device token
vaulty id                       # Get device ID
vaulty register <project> [name] # Register device
vaulty device-status            # Check device status
vaulty list-devices             # List all devices
```

**Secret Management**:
```bash
vaulty list-secrets             # List all secrets
vaulty check-secret <key>       # Check if secret exists
vaulty get-secret <key>         # Get secret value
vaulty create-secret <key>      # Create/update secret
vaulty delete-secret <key>      # Delete secret
```

**Project Management**:
```bash
vaulty list-projects            # List all projects
vaulty get-project              # Get project info
vaulty list-tokens              # List project tokens
vaulty list-activities          # List activity history
vaulty get-docs                 # Get API documentation
```

### JSON Output

All commands support `--json` flag for structured output:
```bash
vaulty list-secrets --json
vaulty get-project --json
vaulty device-status --json
```

### Configuration

**API URL** (saved locally in `.vaulty` file):
```bash
# Set once - saved automatically
vaulty list-secrets --api-url http://custom-server:8000

# Future commands use saved URL automatically
vaulty list-secrets  # Uses saved URL
```

**Environment Variables** (highest priority):
```bash
export VAULTY_API_URL="http://localhost:8000"  # Overrides config file
export VAULTY_DEVICE_ID="your-device-id"        # Override device ID
```

**Priority Order**:
1. Environment variable `VAULTY_API_URL`
2. Local config file `.vaulty` (in current directory)
3. Default: `http://localhost:8000`

## MCP Integration

**Endpoint**: `http://localhost:9000/mcp/sse`

**Available Tools**: `list-projects`, `get-project`, `list-secrets`, `check-secret`, `create-secret`, `delete-secret`, `list-tokens`, `list-devices`, `device-status`, `register`, `list-activities`

Authenticate using `master_token`, `project_token`, or `device_token` in tool calls.

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MASTER_TOKEN` | Yes | - | Administrative token (required on first run) |
| `MASTER_KEY` | No | dev key | 64 hex chars for encryption |
| `DATABASE_PATH` | No | `server/data/vaulty.db` | SQLite database path |
| `MCP_SERVER_PORT` | No | `9000` | MCP server port |

## Features

- Project-based secrets management with encrypted storage
- Token-based authentication (master, project, device tokens)
- Device registration and approval workflow
- Activity logging with exposure detection
- MCP integration for AI assistants
- RESTful API with OpenAPI documentation
- Web frontend and CLI client
- System-wide CLI installation (`vaulty` command)
- JSON output support for all commands
- Local config storage for API URL persistence

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **API Docs**: http://localhost:8000/api/docs

## Project Structure

```
vaulty/
├── server/          # Backend API and MCP server
│   ├── api/        # REST API routes
│   ├── mcp/        # MCP server implementation
│   ├── models/     # Database models
│   └── schemas/    # Pydantic schemas
├── frontend/       # React frontend
├── client/         # CLI client
├── pyproject.toml  # Python package configuration
├── Dockerfile      # Container definition
└── docker-compose.yml
```

## Security Notes

- Keep `MASTER_TOKEN` secure - it provides full administrative access
- Use a strong `MASTER_KEY` in production (64 hex characters)
- Device tokens are derived from device IDs and working directories
- Use HTTPS and restrict network access in production
