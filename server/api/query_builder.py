"""Query builder utilities for activity filtering"""
from sqlalchemy.orm import Query
from sqlalchemy import text
from typing import Optional

from ...models import Activity


def build_activity_query(
    base_query: Query,
    project_name: Optional[str] = None,
    method: Optional[str] = None,
    source: Optional[str] = None,
    exposed_only: bool = False,
    breakdown: Optional[str] = None,
    breakdown_value: Optional[str] = None
) -> Query:
    """
    Build activity query with common filters.
    
    Args:
        base_query: Base SQLAlchemy query for Activity model
        project_name: Filter by project name
        method: Filter by HTTP method (e.g., 'MCP', 'GET', 'POST')
        source: Filter by source ('ui', 'api', 'mcp', 'root', 'project', 'exposed', 'ip', 'token', 'device')
        exposed_only: Filter to only activities with exposed confidential data
        breakdown: Filter by breakdown type ('project', 'secret', 'token', 'device', 'mcp_tool')
        breakdown_value: Filter by specific breakdown value
        
    Returns:
        Filtered query
    """
    # Apply project name filter
    if project_name:
        base_query = base_query.filter(Activity.project_name == project_name)
    
    # Apply method filter
    if method:
        base_query = base_query.filter(Activity.method == method)
    
    # Apply breakdown filters
    if breakdown:
        if breakdown == "secret":
            if breakdown_value:
                # Extract secret key from path
                base_query = base_query.filter(Activity.path.like(f'%/secrets/{breakdown_value}%'))
        elif breakdown == "token":
            if breakdown_value:
                # Filter by token ID in path
                base_query = base_query.filter(Activity.path.like(f'%/tokens/{breakdown_value}%'))
        elif breakdown == "device":
            if breakdown_value:
                # Filter by device ID in path
                base_query = base_query.filter(Activity.path.like(f'%/devices/{breakdown_value}%'))
        elif breakdown == "mcp_tool":
            if breakdown_value:
                # Filter by MCP tool name in path
                base_query = base_query.filter(Activity.path.like(f'%/mcp/tools/{breakdown_value}%'))
        elif breakdown == "project":
            if breakdown_value:
                # Filter by project name
                base_query = base_query.filter(Activity.project_name == breakdown_value)
            # Note: "project" breakdown without value doesn't make sense, so we don't filter
    
    # Apply source filter at SQL level (efficient filtering)
    if source:
        if source == "root":
            # Filter by activities without project name (project_name is null)
            base_query = base_query.filter(Activity.project_name.is_(None))
        elif source == "project":
            # Filter by activities with project name (project_name is not null)
            base_query = base_query.filter(Activity.project_name.isnot(None))
        elif source == "exposed":
            # Filter by exposed confidential data using SQLite JSON functions
            base_query = base_query.filter(
                Activity.response_data.isnot(None),
                text("json_valid(response_data) = 1"),
                text("json_extract(response_data, '$.exposed_confidential_data') = 1")
            )
        elif source == "ip":
            # IP filter: exclude UI events, only show API and MCP
            base_query = base_query.filter(
                Activity.request_data.isnot(None),
                text("json_valid(request_data) = 1"),
                text("json_extract(request_data, '$.source') != 'ui' OR json_extract(request_data, '$.source') IS NULL")
            )
        elif source == "token":
            # Token filter: only show activities with Bearer Authorization header
            base_query = base_query.filter(
                Activity.request_data.isnot(None),
                text("json_extract(request_data, '$.headers.authorization') LIKE 'Bearer %' OR json_extract(request_data, '$.headers.Authorization') LIKE 'Bearer %'")
            )
        elif source == "device":
            # Device filter: only show activities with /devices/ in path
            base_query = base_query.filter(Activity.path.like('%/devices/%'))
        else:
            # Filter by source (ui, api, mcp) using SQLite JSON functions
            base_query = base_query.filter(
                text("json_extract(request_data, '$.source') = :source")
            ).params(source=source)
    
    # Apply exposed_only filter if requested
    if exposed_only:
        try:
            base_query = base_query.filter(
                Activity.response_data.isnot(None),
                text("json_valid(response_data) = 1"),
                text("json_extract(response_data, '$.exposed_confidential_data') = 1")
            )
        except Exception:
            # Fallback if JSON functions fail
            pass
    
    return base_query

