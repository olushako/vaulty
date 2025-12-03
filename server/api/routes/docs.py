"""API documentation endpoint"""
from fastapi import APIRouter

router = APIRouter(tags=["docs"])


@router.get("/api/docs")
def get_api_documentation():
    """
    Comprehensive API documentation with usage examples and best practices.
    """
    return {
        "title": "Vaulty Secrets Manager API Documentation",
        "version": "1.0.0",
        "description": "Complete guide to using the Vaulty Secrets Manager API",
        
        "authentication": {
            "method": "Bearer Token Authentication",
            "header": "Authorization: Bearer <token>",
            "token_types": {
                "master_token": {
                    "description": "Full access to all projects and operations",
                    "usage": "Use for administrative operations and managing multiple projects",
                    "example": "Authorization: Bearer <your-master-token>"
                },
                "project_token": {
                    "description": "Limited access to a specific project",
                    "usage": "Use for service/application access to a single project",
                    "example": "Authorization: Bearer <project_token>"
                }
            },
            "getting_tokens": {
                "master_token": "Set MASTER_TOKEN environment variable or create via /api/master-tokens",
                "project_token": "Create via POST /api/projects/{project_name}/tokens"
            }
        },
        
        "base_url": "http://localhost:8000",
        "interactive_docs": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_spec": "/openapi.json"
        },
        
        "endpoints": {
            "projects": {
                "list": {
                    "method": "GET",
                    "path": "/api/projects",
                    "description": "List all projects",
                    "auth": "master_token or project_token",
                    "response": "[{id, name, description, created_at}]",
                    "example": {
                        "request": "GET /api/projects\nAuthorization: Bearer <token>",
                        "response": {
                            "status": 200,
                            "body": [{"id": "...", "name": "MyProject", "description": "", "created_at": "2025-11-19T..."}]
                        }
                    }
                },
                "get": {
                    "method": "GET",
                    "path": "/api/projects/{project_name}",
                    "description": "Get project details",
                    "auth": "master_token or project_token (for own project)",
                    "response": "{id, name, description, created_at, auto_approval_tag_pattern}",
                    "example": {
                        "request": "GET /api/projects/MyProject\nAuthorization: Bearer <token>",
                        "response": {"status": 200, "body": {"id": "...", "name": "MyProject", "description": "", "created_at": "2025-11-19T..."}}
                    }
                },
                "create": {
                    "method": "POST",
                    "path": "/api/projects",
                    "description": "Create a new project",
                    "auth": "master_token only",
                    "request_body": {"name": "string", "description": "string (optional)"},
                    "response": "{id, name, description, created_at}",
                    "example": {
                        "request": "POST /api/projects\nAuthorization: Bearer <master_token>\nContent-Type: application/json\n\n{\"name\": \"NewProject\", \"description\": \"My new project\"}",
                        "response": {"status": 201, "body": {"id": "...", "name": "NewProject", "description": "My new project", "created_at": "2025-11-19T..."}}
                    }
                },
                "update": {
                    "method": "PATCH",
                    "path": "/api/projects/{project_name}",
                    "description": "Update project details",
                    "auth": "master_token or project_token (for own project)",
                    "request_body": {"description": "string (optional)", "auto_approval_tag_pattern": "string (optional)"},
                    "response": "{id, name, description, created_at, auto_approval_tag_pattern}",
                    "example": {
                        "request": "PATCH /api/projects/MyProject\nAuthorization: Bearer <token>\nContent-Type: application/json\n\n{\"description\": \"Updated description\"}",
                        "response": {"status": 200, "body": {"id": "...", "name": "MyProject", "description": "Updated description", "created_at": "2025-11-19T...", "auto_approval_tag_pattern": None}}
                    }
                }
            },
            
            "secrets": {
                "list": {
                    "method": "GET",
                    "path": "/api/projects/{project_name}/secrets",
                    "description": "List all secrets in a project (keys only, not values)",
                    "auth": "master_token or project_token (for own project)",
                    "response": "[{key, created_at, updated_at, note}]",
                    "note": "Secret values are NEVER returned. Use GET /api/projects/{project_name}/secrets/{key} to retrieve a value.",
                    "example": {
                        "request": "GET /api/projects/MyProject/secrets\nAuthorization: Bearer <token>",
                        "response": {
                            "status": 200,
                            "body": [{"key": "api_key", "created_at": "2025-11-19T...", "updated_at": "2025-11-19T...", "note": "Use REST API to retrieve secret values securely"}]
                        }
                    }
                },
                "get": {
                    "method": "GET",
                    "path": "/api/projects/{project_name}/secrets/{key}",
                    "description": "Get a secret value by key",
                    "auth": "master_token or project_token (for own project)",
                    "response": "{key, value, created_at, updated_at}",
                    "security_note": "This is the ONLY endpoint that returns secret values. Use with caution.",
                    "example": {
                        "request": "GET /api/projects/MyProject/secrets/api_key\nAuthorization: Bearer <token>",
                        "response": {
                            "status": 200,
                            "body": {"key": "api_key", "value": "actual_secret_value_here", "created_at": "...", "updated_at": "..."}
                        }
                    }
                },
                "create": {
                    "method": "POST",
                    "path": "/api/projects/{project_name}/secrets",
                    "description": "Create or update a secret",
                    "auth": "master_token or project_token (for own project)",
                    "request_body": {"key": "string", "value": "string"},
                    "response": "{key, created_at, updated_at}",
                    "note": "Secret value is NOT returned in response for security",
                    "example": {
                        "request": "POST /api/projects/MyProject/secrets\nAuthorization: Bearer <token>\nContent-Type: application/json\n\n{\"key\": \"api_key\", \"value\": \"my_secret_value\"}",
                        "response": {
                            "status": 201,
                            "body": {"key": "api_key", "created_at": "2025-11-19T...", "updated_at": "2025-11-19T..."}
                        }
                    }
                },
                "delete": {
                    "method": "DELETE",
                    "path": "/api/projects/{project_name}/secrets/{key}",
                    "description": "Delete a secret",
                    "auth": "master_token or project_token (for own project)",
                    "response": "204 No Content",
                    "example": {
                        "request": "DELETE /api/projects/MyProject/secrets/api_key\nAuthorization: Bearer <token>",
                        "response": {"status": 204}
                    }
                }
            },
            
            "tokens": {
                "list": {
                    "method": "GET",
                    "path": "/api/projects/{project_name}/tokens",
                    "description": "List all project tokens",
                    "auth": "master_token or project_token (for own project)",
                    "response": "[{id, project_id, name, created_at, last_used}]",
                    "note": "Token values are NEVER returned. Only metadata is shown.",
                    "example": {
                        "request": "GET /api/projects/MyProject/tokens\nAuthorization: Bearer <token>",
                        "response": {
                            "status": 200,
                            "body": [{"id": "...", "project_id": "...", "name": "ABC***XYZ", "created_at": "...", "last_used": None}]
                        }
                    }
                },
                "create": {
                    "method": "POST",
                    "path": "/api/projects/{project_name}/tokens",
                    "description": "Create a new project token",
                    "auth": "master_token or project_token (for own project)",
                    "request_body": {"name": "string (optional, ignored - token value is used as name)"},
                    "response": "{id, project_id, name, token, created_at}",
                    "important": "The token value is ONLY returned in this response. Store it securely immediately.",
                    "example": {
                        "request": "POST /api/projects/MyProject/tokens\nAuthorization: Bearer <token>\nContent-Type: application/json\n\n{\"name\": \"MyServiceToken\"}",
                        "response": {
                            "status": 201,
                            "body": {"id": "...", "project_id": "...", "name": "ABC***XYZ", "token": "full_token_value_here", "created_at": "..."}
                        }
                    }
                },
                "revoke": {
                    "method": "DELETE",
                    "path": "/api/tokens/{token_id}",
                    "description": "Revoke (delete) a project token",
                    "auth": "master_token or project_token (for own project)",
                    "note": "Path is /api/tokens/{token_id}, NOT /api/projects/{project_name}/tokens/{token_id}",
                    "response": "204 No Content (or 200 OK)",
                    "note": "DELETE operations typically return 204 No Content, but token deletion may return 200 OK",
                    "example": {
                        "request": "DELETE /api/tokens/abc123def456\nAuthorization: Bearer <token>",
                        "response": {"status": 204}
                    }
                }
            },
            
            "activities": {
                "list": {
                    "method": "GET",
                    "path": "/api/projects/{project_name}/activities",
                    "description": "Get activity history for a project",
                    "auth": "master_token or project_token (for own project)",
                    "query_params": {
                        "limit": "integer (optional, default: 100)",
                        "offset": "integer (optional, default: 0)"
                    },
                    "response": "{activities: [{id, method, action, path, status_code, created_at, ...}], total: integer, has_more: boolean}",
                    "example": {
                        "request": "GET /api/projects/MyProject/activities?limit=50\nAuthorization: Bearer <token>",
                        "response": {
                            "status": 200,
                            "body": {"activities": [{"id": "...", "method": "POST", "action": "create_secret", "path": "/api/projects/MyProject/secrets", "status_code": 201, "created_at": "2025-11-19T...", "execution_time_ms": 45}], "total": 1, "has_more": False}
                        }
                    }
                }
            },
            
            "auth": {
                "me": {
                    "method": "GET",
                    "path": "/api/auth/me",
                    "description": "Get current authentication information",
                    "auth": "Any valid token",
                    "response": "{token_type, token_name, is_master, project_id (if project token)}",
                    "example": {
                        "request": "GET /api/auth/me\nAuthorization: Bearer <token>",
                        "response": {
                            "status": 200,
                            "body": {"token_type": "master", "token_name": "ABC***XYZ", "is_master": True}
                        }
                    }
                }
            }
        },
        
        "common_patterns": {
            "create_and_store_secret": {
                "description": "Create a secret and store it securely",
                "steps": [
                    "1. POST /api/projects/{project_name}/secrets with {key, value}",
                    "2. Response contains key and metadata (NOT the value)",
                    "3. To retrieve value later: GET /api/projects/{project_name}/secrets/{key}"
                ]
            },
            "create_project_token": {
                "description": "Create a project token for service access",
                "steps": [
                    "1. POST /api/projects/{project_name}/tokens",
                    "2. Save the 'token' value from response immediately (only shown once)",
                    "3. Use this token for all future API calls to this project"
                ]
            },
            "list_and_retrieve_secrets": {
                "description": "List secrets and retrieve specific values",
                "steps": [
                    "1. GET /api/projects/{project_name}/secrets to list all keys",
                    "2. GET /api/projects/{project_name}/secrets/{key} to get a specific value"
                ]
            }
        },
        
        "error_handling": {
            "status_codes": {
                "200": "Success",
                "201": "Created",
                "204": "No Content (successful deletion)",
                "400": "Bad Request (invalid input)",
                "401": "Unauthorized (invalid or missing token)",
                "403": "Forbidden (token doesn't have required permissions)",
                "404": "Not Found (resource doesn't exist)",
                "500": "Internal Server Error"
            },
            "common_errors": {
                "401_unauthorized": {
                    "cause": "Invalid token or missing Authorization header",
                    "solution": "Check that token is correct and header format is: Authorization: Bearer <token>"
                },
                "403_forbidden": {
                    "cause": "Token doesn't have permission for this operation",
                    "solution": "Use master token for cross-project operations, or ensure project token is for the correct project"
                },
                "404_not_found": {
                    "cause": "Resource doesn't exist (project, secret, token, etc.)",
                    "solution": "Verify the resource name/ID is correct"
                }
            }
        },
        
        "security_best_practices": {
            "token_management": [
                "Never commit tokens to version control",
                "Store tokens in environment variables or secure secret managers",
                "Rotate tokens regularly",
                "Use project tokens for service access, not master tokens"
            ],
            "secret_handling": [
                "Secret values are NEVER returned in list operations",
                "Only GET /api/projects/{project_name}/secrets/{key} returns the actual value",
                "All API calls are logged in activity history",
                "Exposure detection automatically flags if secrets appear in responses"
            ],
            "authentication": [
                "Always use HTTPS in production",
                "Include Authorization header in every request",
                "Don't log or expose tokens in error messages"
            ]
        },
        
        "examples": {
            "curl": {
                "list_projects": "curl -H 'Authorization: Bearer <token>' http://localhost:8000/api/projects",
                "create_secret": "curl -X POST -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{\"key\":\"my_key\",\"value\":\"my_value\"}' http://localhost:8000/api/projects/MyProject/secrets",
                "get_secret": "curl -H 'Authorization: Bearer <token>' http://localhost:8000/api/projects/MyProject/secrets/my_key",
                "create_token": "curl -X POST -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{\"name\":\"MyToken\"}' http://localhost:8000/api/projects/MyProject/tokens"
            },
            "python": {
                "basic_usage": """
import requests

token = 'your_token_here'
base_url = 'http://localhost:8000'

headers = {'Authorization': f'Bearer {token}'}

# List projects
response = requests.get(f'{base_url}/api/projects', headers=headers)
projects = response.json()

# Create a secret
response = requests.post(
    f'{base_url}/api/projects/MyProject/secrets',
    headers={**headers, 'Content-Type': 'application/json'},
    json={'key': 'api_key', 'value': 'secret_value_123'}
)

# Get a secret value
response = requests.get(
    f'{base_url}/api/projects/MyProject/secrets/api_key',
    headers=headers
)
secret = response.json()
print(secret['value'])  # The actual secret value
"""
            },
            "javascript": {
                "basic_usage": """
const token = 'your_token_here';
const baseUrl = 'http://localhost:8000';

const headers = {
  'Authorization': `Bearer ${token}`,
  'Content-Type': 'application/json'
};

// List projects
const projects = await fetch(`${baseUrl}/api/projects`, { headers })
  .then(res => res.json());

// Create a secret
await fetch(`${baseUrl}/api/projects/MyProject/secrets`, {
  method: 'POST',
  headers,
  body: JSON.stringify({ key: 'api_key', value: 'secret_value_123' })
});

// Get a secret value
const secret = await fetch(
  `${baseUrl}/api/projects/MyProject/secrets/api_key`,
  { headers }
).then(res => res.json());
console.log(secret.value);  // The actual secret value
"""
            }
        },
        
        "notes": {
            "important": [
                "Token deletion uses /api/tokens/{token_id}, NOT /api/projects/{project_name}/tokens/{token_id}",
                "Secret values are only returned by GET /api/projects/{project_name}/secrets/{key}",
                "List operations (secrets, tokens) never return sensitive values",
                "All API calls are logged in activity history with exposure detection"
            ]
        },
        
        "mcp_integration": {
            "title": "MCP (Model Context Protocol) Integration",
            "description": "Vaulty provides MCP integration to expose secrets management functionality to AI assistants through the Model Context Protocol. All MCP operations use the REST API internally for consistency and automatic activity logging.",
            "endpoint": "http://localhost:8001/mcp/sse",
            "protocol": "HTTP/SSE (Server-Sent Events)",
            "authentication": {
                "method": "All MCP tools require a master_token or project_token parameter",
                "note": "The token is passed as a parameter to each tool call, not in HTTP headers"
            },
            "security": {
                "safe_mode": "Enabled by default (MCP_SAFE_MODE=1)",
                "features": [
                    "Secret VALUES are NEVER returned to prevent exposure to LLM servers",
                    "Only secret keys and metadata are exposed",
                    "All operations are logged in activity history",
                    "Exposure detection automatically flags sensitive data in responses",
                    "Client IP and user agent are captured for all MCP operations"
                ],
                "warning": "Set MCP_SAFE_MODE=0 to disable (NOT RECOMMENDED)"
            },
            "connection": {
                "description": "Connect to the MCP server via HTTP/SSE",
                "endpoint": "http://localhost:8001/mcp/sse",
                "method": "GET (for SSE connection), POST (for tool calls)",
                "example": "Connect using an MCP-compatible client (e.g., Cursor, Claude Desktop)"
            },
            "tools": {
                "list_projects": {
                    "description": "List all projects in vaulty",
                    "parameters": {
                        "master_token": {
                            "type": "string",
                            "required": True,
                            "description": "Master token for authentication"
                        }
                    },
                    "returns": "List of projects with id, name, description, created_at",
                    "example": {
                        "tool_call": "list_projects",
                        "arguments": {
                            "master_token": "<your-master-token>"
                        }
                    }
                },
                "get_project_info": {
                    "description": "Get detailed information about a specific project",
                    "parameters": {
                        "project_name": {
                            "type": "string",
                            "required": True,
                            "description": "Name of the project"
                        },
                        "master_token": {
                            "type": "string",
                            "required": True,
                            "description": "Master token or project token for authentication"
                        }
                    },
                    "returns": "Project details including id, name, description, created_at, auto_approval_tag_pattern",
                    "example": {
                        "tool_call": "get_project_info",
                        "arguments": {
                            "project_name": "MyProject",
                            "master_token": "<your-master-token>"
                        }
                    }
                },
                "list_secrets": {
                    "description": "List all secrets in a project (keys only, not values)",
                    "parameters": {
                        "project_name": {
                            "type": "string",
                            "required": True,
                            "description": "Name of the project"
                        },
                        "master_token": {
                            "type": "string",
                            "required": True,
                            "description": "Master token or project token for authentication"
                        }
                    },
                    "returns": "List of secrets with key, created_at, updated_at, note (NO VALUES)",
                    "security_note": "Secret values are NEVER returned. Use REST API GET /api/projects/{project_name}/secrets/{key} to retrieve values.",
                    "example": {
                        "tool_call": "list_secrets",
                        "arguments": {
                            "project_name": "MyProject",
                            "master_token": "<your-master-token>"
                        }
                    }
                },
                "check_secret_exists": {
                    "description": "Check if a secret exists in a project (returns existence status only, never the value)",
                    "parameters": {
                        "project_name": {
                            "type": "string",
                            "required": True,
                            "description": "Name of the project"
                        },
                        "key": {
                            "type": "string",
                            "required": True,
                            "description": "Secret key to check"
                        },
                        "master_token": {
                            "type": "string",
                            "required": True,
                            "description": "Master token or project token for authentication"
                        }
                    },
                    "returns": "Object with 'exists' boolean field",
                    "security_note": "This tool NEVER returns the secret value, only whether it exists",
                    "example": {
                        "tool_call": "check_secret_exists",
                        "arguments": {
                            "project_name": "MyProject",
                            "key": "api_key",
                            "master_token": "<your-master-token>"
                        }
                    }
                },
                "create_secret": {
                    "description": "Create or update a secret in a project. The secret value will be automatically generated by the server. The generated value will NEVER be returned to prevent exposure.",
                    "parameters": {
                        "project_name": {
                            "type": "string",
                            "required": True,
                            "description": "Name of the project"
                        },
                        "key": {
                            "type": "string",
                            "required": True,
                            "description": "Secret key"
                        },
                        "value_format": {
                            "type": "string",
                            "required": False,
                            "default": "random_string",
                            "description": "Format/type of value to generate",
                            "options": {
                                "uuid": "UUID v4",
                                "random_string": "32-char alphanumeric (default)",
                                "token": "32-char URL-safe token",
                                "hex": "64-char hex string",
                                "base64": "44-char base64 string",
                                "integer": "Random integer",
                                "float": "Random float",
                                "lowercase": "32-char lowercase",
                                "uppercase": "32-char uppercase",
                                "numeric": "32-char digits only",
                                "alphanumeric_lower": "32-char lowercase alphanumeric"
                            }
                        },
                        "value_length": {
                            "type": "integer",
                            "required": False,
                            "default": 32,
                            "description": "Length for string-based formats (1-256, ignored for uuid, integer, float)"
                        },
                        "integer_min": {
                            "type": "integer",
                            "required": False,
                            "default": 0,
                            "description": "Minimum value for integer format"
                        },
                        "integer_max": {
                            "type": "integer",
                            "required": False,
                            "default": 999999999,
                            "description": "Maximum value for integer format"
                        },
                        "float_min": {
                            "type": "number",
                            "required": False,
                            "default": 0.0,
                            "description": "Minimum value for float format"
                        },
                        "float_max": {
                            "type": "number",
                            "required": False,
                            "default": 999999.99,
                            "description": "Maximum value for float format"
                        },
                        "master_token": {
                            "type": "string",
                            "required": True,
                            "description": "Master token or project token for authentication"
                        }
                    },
                    "returns": "Object with key, created_at, updated_at (NO VALUE RETURNED)",
                    "security_note": "The generated secret value is NEVER returned. Store it via REST API if needed.",
                    "example": {
                        "tool_call": "create_secret",
                        "arguments": {
                            "project_name": "MyProject",
                            "key": "api_key",
                            "value_format": "token",
                            "value_length": 32,
                            "master_token": "<your-master-token>"
                        }
                    }
                },
                "delete_secret": {
                    "description": "Delete a secret from a project",
                    "parameters": {
                        "project_name": {
                            "type": "string",
                            "required": True,
                            "description": "Name of the project"
                        },
                        "key": {
                            "type": "string",
                            "required": True,
                            "description": "Secret key to delete"
                        },
                        "master_token": {
                            "type": "string",
                            "required": True,
                            "description": "Master token or project token for authentication"
                        }
                    },
                    "returns": "Success confirmation",
                    "example": {
                        "tool_call": "delete_secret",
                        "arguments": {
                            "project_name": "MyProject",
                            "key": "api_key",
                            "master_token": "<your-master-token>"
                        }
                    }
                },
                "get_documentation": {
                    "description": "Get comprehensive API and MCP documentation. Returns complete documentation including all API endpoints, MCP tools, authentication methods, examples, and usage instructions.",
                    "parameters": {
                        "master_token": {
                            "type": "string",
                            "required": False,
                            "description": "Master token (optional, documentation endpoint doesn't require auth but token is used for activity logging)"
                        }
                    },
                    "returns": "Complete API and MCP documentation as JSON object",
                    "example": {
                        "tool_call": "get_documentation",
                        "arguments": {
                            "master_token": "<your-master-token>"
                        }
                    }
                },
                "list_tokens": {
                    "description": "List all project tokens for a project",
                    "parameters": {
                        "project_name": {
                            "type": "string",
                            "required": True,
                            "description": "Name of the project"
                        },
                        "master_token": {
                            "type": "string",
                            "required": True,
                            "description": "Master token or project token for authentication"
                        }
                    },
                    "returns": "List of tokens with id, project_id, name (masked), created_at, last_used (NO TOKEN VALUES)",
                    "security_note": "Token values are NEVER returned. Only metadata is shown.",
                    "example": {
                        "tool_call": "list_tokens",
                        "arguments": {
                            "project_name": "MyProject",
                            "master_token": "<your-master-token>"
                        }
                    }
                },
                "test_expose_token": {
                    "description": "TEST TOOL: Returns the master token unmasked (for testing exposure detection)",
                    "note": "This is a test tool for development purposes only",
                    "parameters": {
                        "master_token": {
                            "type": "string",
                            "required": True,
                            "description": "Master token (will be exposed in response for testing)"
                        }
                    }
                },
                "test_expose_secret": {
                    "description": "TEST TOOL: Returns a secret value unmasked (for testing exposure detection)",
                    "note": "This is a test tool for development purposes only",
                    "parameters": {
                        "project_name": {
                            "type": "string",
                            "required": True,
                            "description": "Name of the project"
                        },
                        "key": {
                            "type": "string",
                            "required": True,
                            "description": "Secret key to retrieve"
                        },
                        "master_token": {
                            "type": "string",
                            "required": True,
                            "description": "Master token for authentication"
                        }
                    }
                },
                "test_expose_credentials": {
                    "description": "TEST TOOL: Returns credentials in response (for testing exposure detection)",
                    "note": "This is a test tool for development purposes only",
                    "parameters": {
                        "master_token": {
                            "type": "string",
                            "required": True,
                            "description": "Master token (will be exposed)"
                        }
                    }
                }
            },
            "usage_examples": {
                "cursor_config": {
                    "description": "Configure MCP in Cursor IDE",
                    "config_location": "~/.cursor/mcp.json or Cursor Settings > MCP",
                    "example_config": {
                        "mcpServers": {
                            "vaulty": {
                                "command": "python3",
                                "args": ["-m", "server.mcp.http_server"],
                                "env": {
                                    "VAULTY_API_URL": "http://localhost:8000"
                                }
                            }
                        }
                    },
                    "note": "Or connect via HTTP/SSE endpoint: http://localhost:8001/mcp/sse"
                },
                "common_workflows": {
                    "list_and_check": {
                        "description": "List projects and check for secrets",
                        "steps": [
                            "1. Call list_projects to see available projects",
                            "2. Call list_secrets for a project to see all secret keys",
                            "3. Call check_secret_exists to verify a specific secret exists",
                            "4. Use REST API to retrieve secret values if needed"
                        ]
                    },
                    "create_secret": {
                        "description": "Create a new secret with auto-generated value",
                        "steps": [
                            "1. Call create_secret with project_name, key, and value_format",
                            "2. Secret value is generated automatically",
                            "3. Value is NOT returned (security)",
                            "4. Use REST API GET /api/projects/{project_name}/secrets/{key} to retrieve value if needed"
                        ]
                    }
                }
            },
            "activity_logging": {
                "description": "All MCP tool calls are automatically logged in activity history",
                "features": [
                    "Client IP and user agent are captured",
                    "Tool name and arguments (masked) are logged",
                    "Response status and execution time are tracked",
                    "Exposure detection runs on all responses",
                    "Activities are visible in GET /api/projects/{project_name}/activities"
                ],
                "example": "MCP tool calls appear in activity logs with method='MCP' and source='mcp_llm'"
            },
            "api_relationship": {
                "description": "MCP tools use the REST API internally",
                "benefits": [
                    "Consistent behavior between MCP and REST API",
                    "Automatic activity logging for all operations",
                    "Same authentication and authorization rules",
                    "Unified exposure detection"
                ],
                "mapping": {
                    "list_projects": "GET /api/projects",
                    "get_project_info": "GET /api/projects/{project_name}",
                    "list_secrets": "GET /api/projects/{project_name}/secrets",
                    "check_secret_exists": "HEAD /api/projects/{project_name}/secrets/{key}",
                    "create_secret": "POST /api/projects/{project_name}/secrets",
                    "delete_secret": "DELETE /api/projects/{project_name}/secrets/{key}",
                    "list_tokens": "GET /api/projects/{project_name}/tokens"
                }
            }
        }
    }

