"""Activity management routes"""
import json
from fastapi import APIRouter, Depends, HTTPException, status, Security, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text, func, case, cast, Date, or_, and_
from typing import Optional
from datetime import datetime, timedelta

from ...models import Project, Activity
from ...schemas import ActivityListResponse
from ...auth import get_db, get_auth_context
from ..dependencies import get_project_with_access

router = APIRouter(tags=["activities"])


@router.get("/api/projects/{project_name}/activities", response_model=ActivityListResponse)
def get_project_activities(
    project: Project = Depends(get_project_with_access),
    db: Session = Depends(get_db),
    limit: int = Query(25, ge=1, le=100, description="Number of activities to return"),
    offset: int = Query(0, ge=0, description="Number of activities to skip"),
    method: Optional[str] = Query(None, description="Filter by HTTP method (e.g., 'MCP', 'GET', 'POST')"),
    exclude_ui: bool = Query(False, description="Exclude UI-initiated requests (source='ui')")
):
    """Get activity history for a project with pagination - requires master token or project token (own project only)"""
    
    # Get activities for this project (last 7 days)
    cutoff_date = datetime.utcnow() - timedelta(days=7)
    base_query = db.query(Activity).filter(
        Activity.project_name == project.name,
        Activity.created_at >= cutoff_date
    )
    
    # Apply method filter if provided
    if method:
        base_query = base_query.filter(Activity.method == method)
    
    # Get all matching activities (we'll filter exclude_ui in Python since it requires JSON parsing)
    # Debug: Check query before execution
    # print(f"DEBUG: Querying activities for project: {project.name}, method: {method}, exclude_ui: {exclude_ui}")
    all_activities = base_query.order_by(Activity.created_at.desc()).all()
    # Debug: Check results
    # print(f"DEBUG: Found {len(all_activities)} activities before exclude_ui filter")
    
    # Apply exclude_ui filter if requested (filter in Python for JSON field)
    if exclude_ui:
        filtered_activities = []
        for activity in all_activities:
            if activity.method == 'MCP':
                # Always include MCP activities
                filtered_activities.append(activity)
            elif activity.request_data:
                try:
                    request_data = json.loads(activity.request_data)
                    source = request_data.get("source")
                    # Exclude UI activities, include everything else
                    if source != 'ui':
                        filtered_activities.append(activity)
                except:
                    # If we can't parse, include it (assume not UI)
                    filtered_activities.append(activity)
            else:
                # No request_data, include it (assume not UI)
                filtered_activities.append(activity)
        all_activities = filtered_activities
    
    # Get total count after filtering
    total = len(all_activities)
    
    # Apply pagination
    paginated_activities = all_activities[offset:offset + limit + 1]
    
    # Check if there are more records
    has_more = len(paginated_activities) > limit
    if has_more:
        paginated_activities = paginated_activities[:limit]
    
    return ActivityListResponse(
        activities=paginated_activities,
        total=total,
        has_more=has_more
    )


@router.get("/api/activities/recent", response_model=ActivityListResponse)
def get_recent_activities(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    db: Session = Depends(get_db),
    limit: int = Query(25, ge=1, le=100, description="Number of activities to return")
):
    """Get recent activities (last 7 days) - supports both master and project tokens"""
    auth = get_auth_context(credentials, db)
    
    # Get all activities (last 7 days)
    cutoff_date = datetime.utcnow() - timedelta(days=7)
    
    if auth.is_master:
        base_query = db.query(Activity).filter(Activity.created_at >= cutoff_date)
    else:
        # For project tokens, only get activities for their project
        if not auth.token or not auth.project_id:
            return ActivityListResponse(activities=[], total=0, has_more=False)
        
        from ...models import Project
        project = db.query(Project).filter(Project.id == auth.project_id).first()
        if not project:
            return ActivityListResponse(activities=[], total=0, has_more=False)
        
        base_query = db.query(Activity).filter(
            Activity.created_at >= cutoff_date,
            Activity.project_name == project.name
        )
    
    # Get the most recent activities (ordered by created_at desc)
    activities = base_query.order_by(Activity.created_at.desc()).limit(limit).all()
    
    # Get total count
    total = base_query.count()
    
    return ActivityListResponse(
        activities=activities,
        total=total,
        has_more=False  # No pagination for recent activities
    )


@router.get("/api/activities", response_model=ActivityListResponse)
def get_all_activities(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    db: Session = Depends(get_db),
    limit: int = Query(25, ge=1, le=100, description="Number of activities to return"),
    offset: int = Query(0, ge=0, description="Number of activities to skip"),
    method: Optional[str] = Query(None, description="Filter by HTTP method (e.g., 'MCP', 'GET', 'POST')"),
    exposed_only: bool = Query(False, description="Filter to only activities with exposed confidential data"),
    breakdown: Optional[str] = Query(None, description="Filter by breakdown type: project, secret, token, device, mcp_tool"),
    breakdown_value: Optional[str] = Query(None, description="Filter by specific breakdown value (e.g., project name, secret key, etc.)"),
    source: Optional[str] = Query(None, description="Filter by source: 'ui', 'api', or 'mcp'. Omit to show all.")
):
    """Get all activities across all projects (master token) or project-specific (project token)"""
    auth = get_auth_context(credentials, db)
    
    # Get all activities (last 7 days)
    cutoff_date = datetime.utcnow() - timedelta(days=7)
    
    if auth.is_master:
        base_query = db.query(Activity).filter(Activity.created_at >= cutoff_date)
    else:
        # For project tokens, only get activities for their project
        if not auth.token or not auth.project_id:
            return ActivityListResponse(activities=[], total=0, has_more=False)
        
        from ...models import Project
        project = db.query(Project).filter(Project.id == auth.project_id).first()
        if not project:
            return ActivityListResponse(activities=[], total=0, has_more=False)
        
        base_query = db.query(Activity).filter(
            Activity.created_at >= cutoff_date,
            Activity.project_name == project.name
        )
    
    # Apply method filter if provided
    if method:
        base_query = base_query.filter(Activity.method == method)
    
    # Apply breakdown filter if provided
    if breakdown:
        if breakdown_value:
            # Filter by specific breakdown value
            if breakdown == "project":
                base_query = base_query.filter(Activity.project_name == breakdown_value)
            elif breakdown == "secret":
                # Filter by secret key in path or request_data
                base_query = base_query.filter(
                    or_(
                        Activity.path.like(f'%/secrets/{breakdown_value}%'),
                        and_(
                            Activity.action == 'create_secret',
                            or_(
                                text(f"json_extract(request_data, '$.body.key') = '{breakdown_value}'"),
                                text(f"json_extract(request_data, '$.key') = '{breakdown_value}'")
                            )
                        )
                    )
                )
            elif breakdown == "token":
                # Filter by token ID in path
                base_query = base_query.filter(Activity.path.like(f'%/tokens/{breakdown_value}%'))
            elif breakdown == "device":
                # Filter by device ID in path
                base_query = base_query.filter(Activity.path.like(f'%/devices/{breakdown_value}%'))
            elif breakdown == "mcp_tool":
                # Filter by MCP tool name in action
                base_query = base_query.filter(Activity.action == f'mcp_{breakdown_value}')
        else:
            # Filter by breakdown type only (show all activities of this type)
            if breakdown == "secret":
                # Filter to show all secret-related activities
                base_query = base_query.filter(
                    or_(
                        Activity.path.like('%/secrets/%'),
                        Activity.action.in_(['create_secret', 'get_secret', 'delete_secret', 'check_secret_exists'])
                    )
                )
            elif breakdown == "token":
                # Filter to show all token-related activities
                base_query = base_query.filter(Activity.path.like('%/tokens/%'))
            elif breakdown == "device":
                # Filter to show all device-related activities
                base_query = base_query.filter(Activity.path.like('%/devices/%'))
            elif breakdown == "mcp_tool":
                # Filter to show all MCP-related activities
                base_query = base_query.filter(Activity.method == 'MCP')
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
            # Fallback: if JSON functions fail, filter in Python
            all_activities = base_query.order_by(Activity.created_at.desc()).all()
            filtered_activities = []
            for activity in all_activities:
                if activity.response_data:
                    try:
                        response_data = json.loads(activity.response_data)
                        if response_data.get('exposed_confidential_data', False):
                            filtered_activities.append(activity)
                    except:
                        pass
            
            # Get total count
            total = len(filtered_activities)
            
            # Apply pagination
            paginated_activities = filtered_activities[offset:offset + limit + 1]
            
            # Check if there are more records
            has_more = len(paginated_activities) > limit
            if has_more:
                paginated_activities = paginated_activities[:limit]
            
            return ActivityListResponse(
                activities=paginated_activities,
                total=total,
                has_more=has_more
            )
    
    # Get total count
    total = base_query.count()
    
    # Get paginated results
    activities = base_query.order_by(Activity.created_at.desc()).offset(offset).limit(limit + 1).all()
    
    # Check if there are more records
    has_more = len(activities) > limit
    if has_more:
        activities = activities[:limit]
    
    return ActivityListResponse(
        activities=activities,
        total=total,
        has_more=has_more
    )


@router.delete("/api/activities", status_code=status.HTTP_200_OK)
def flush_all_activities(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """Flush all activities across all projects (master token only)"""
    # Only allow master tokens
    auth = get_auth_context(credentials, db)
    if not auth.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires a master token"
        )
    
    # Delete all activities
    deleted_count = db.query(Activity).delete()
    db.commit()
    
    return {"deleted": deleted_count, "message": f"Flushed {deleted_count} activities"}


@router.delete("/api/projects/{project_name}/activities", status_code=status.HTTP_200_OK)
def flush_project_activities(
    project: Project = Depends(get_project_with_access),
    db: Session = Depends(get_db)
):
    """Flush all activities for a project - requires master token or project token (own project only)"""
    
    # Delete all activities for this project
    deleted_count = db.query(Activity).filter(
        Activity.project_name == project.name
    ).delete()
    db.commit()
    
    return {"deleted": deleted_count, "message": f"Flushed {deleted_count} activities"}


@router.get("/api/activities/stats")
def get_activity_stats(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    db: Session = Depends(get_db),
    project_name: Optional[str] = Query(None, description="Filter by project name (optional)")
):
    """Get activity statistics including exposed data counts - uses efficient SQL queries"""
    # Check authentication
    auth = get_auth_context(credentials, db)
    
    # Get cutoff date (last 7 days)
    cutoff_date = datetime.utcnow() - timedelta(days=7)
    
    # Build base query
    base_query = db.query(Activity).filter(Activity.created_at >= cutoff_date)
    
    # If project_name is provided and user is not master, verify access
    if project_name:
        if not auth.is_master:
            # Verify user has access to this project
            project = db.query(Project).filter(Project.name == project_name).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            # For project tokens, verify they belong to this project
            # This is handled by the auth context - if they can call this endpoint, they have access
        base_query = base_query.filter(Activity.project_name == project_name)
    elif not auth.is_master:
        # Non-master tokens can only query their own project
        # Get project from token (if it's a project token)
        # For now, if no project_name specified and not master, return empty stats
        return {
            "total_activities": 0,
            "mcp_activities": 0,
            "exposed_data_count": 0,
            "mcp_exposed_data_count": 0
        }
    
    # Count total activities
    total_activities = base_query.count()
    
    # Count MCP activities
    mcp_activities = base_query.filter(Activity.method == 'MCP').count()
    
    # Count activities with exposed data using SQLite JSON functions
    # SQLite 3.38+ supports json_extract() function
    # We check if response_data contains "exposed_confidential_data": true
    # json_extract returns 1 for true, NULL for missing/invalid JSON
    # Use json_valid() to filter out malformed JSON first
    try:
        # Use json_valid() to ensure we only check valid JSON
        # This prevents errors from malformed JSON in response_data
        exposed_query = base_query.filter(
            Activity.response_data.isnot(None),
            text("json_valid(response_data) = 1"),
            text("json_extract(response_data, '$.exposed_confidential_data') = 1")
        )
        exposed_data_count = exposed_query.count()
    except Exception:
        # Fallback: if JSON functions fail, return 0
        exposed_data_count = 0
    
    # Count MCP activities with exposed data
    try:
        mcp_exposed_query = base_query.filter(
            Activity.method == 'MCP',
            Activity.response_data.isnot(None),
            text("json_valid(response_data) = 1"),
            text("json_extract(response_data, '$.exposed_confidential_data') = 1")
        )
        mcp_exposed_data_count = mcp_exposed_query.count()
    except Exception:
        # Fallback: if JSON functions fail, return 0
        mcp_exposed_data_count = 0
    
    return {
        "total_activities": total_activities,
        "mcp_activities": mcp_activities,
        "exposed_data_count": exposed_data_count,
        "mcp_exposed_data_count": mcp_exposed_data_count
    }


def extract_secret_key_from_path(path: str) -> Optional[str]:
    """Extract secret key from path like /projects/{project}/secrets/{key}"""
    if '/secrets/' in path:
        parts = path.split('/secrets/')
        if len(parts) > 1:
            secret_part = parts[1].split('/')[0].split('?')[0]  # Remove query params
            return secret_part if secret_part else None
    return None

def extract_secret_key_from_action(action: str, request_data: Optional[str]) -> Optional[str]:
    """Extract secret key from action and request data"""
    if action in ['get_secret', 'create_secret', 'delete_secret', 'check_secret_exists']:
        if request_data:
            import json
            try:
                data = json.loads(request_data)
                if isinstance(data, dict):
                    # Check body.key or key
                    body = data.get('body', {})
                    if isinstance(body, dict):
                        return body.get('key') or body.get('secret_key')
                    return data.get('key') or data.get('secret_key')
            except:
                pass
    return None

def extract_token_id_from_path(path: str) -> Optional[str]:
    """Extract token ID from path like /tokens/{id}"""
    if '/tokens/' in path:
        parts = path.split('/tokens/')
        if len(parts) > 1:
            token_part = parts[1].split('/')[0].split('?')[0]
            return token_part if token_part else None
    return None

def extract_mcp_tool_from_action(action: str) -> Optional[str]:
    """Extract MCP tool name from action like mcp_get_secret"""
    if action.startswith('mcp_'):
        return action[4:]  # Remove 'mcp_' prefix
    return None

def extract_device_id_from_path(path: str) -> Optional[str]:
    """Extract device ID from path"""
    if '/devices/' in path:
        parts = path.split('/devices/')
        if len(parts) > 1:
            device_part = parts[1].split('/')[0].split('?')[0]
            return device_part if device_part else None
    return None


@router.get("/api/dashboard/daily-stats")
def get_daily_activity_stats(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    db: Session = Depends(get_db),
    project_name: Optional[str] = Query(None, description="Filter by project name (optional)"),
    source: Optional[str] = Query(None, description="Filter by source: 'ui', 'api', or 'mcp'. Omit to show all.")
):
    """Get daily activity counts for the last 7 days with optional source filtering"""
    from ...auth import get_auth_context
    from sqlalchemy import case, text
    
    # Check authentication
    auth = get_auth_context(credentials, db)
    
    # Get cutoff date (last 7 days)
    cutoff_date = datetime.utcnow() - timedelta(days=7)
    
    # Build base query
    if auth.is_master:
        base_query = db.query(Activity).filter(Activity.created_at >= cutoff_date)
        # Filter by project if provided
        if project_name:
            base_query = base_query.filter(Activity.project_name == project_name)
    else:
        # For project tokens, only get activities for their project
        # Get project name from token
        if not auth.token or not auth.project_id:
            return {"daily_stats": [], "source": source, "avg_response_time_ms": None}
        
        from ...models import Project
        project = db.query(Project).filter(Project.id == auth.project_id).first()
        if not project:
            return {"daily_stats": [], "source": source, "avg_response_time_ms": None}
        
        # Filter activities for this project only
        base_query = db.query(Activity).filter(
            Activity.created_at >= cutoff_date,
            Activity.project_name == project.name
        )
    
    # Use SQL aggregation for efficient counting (instead of loading all activities)
    # Apply filters at SQL level where possible
    # Initialize variables
    daily_path_counts = {}
    avg_response_time_ms = None
    
    # Apply source filters BEFORE grouping
    if source == "root":
        base_query = base_query.filter(Activity.project_name.is_(None))
    elif source == "project":
        base_query = base_query.filter(Activity.project_name.isnot(None))
    elif source == "exposed":
        # For exposed filter, check response_data JSON
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
    elif source == "ui":
        # Filter by source='ui' using SQLite JSON functions
        base_query = base_query.filter(
            Activity.request_data.isnot(None),
            text("json_valid(request_data) = 1"),
            text("json_extract(request_data, '$.source') = 'ui'")
        )
    elif source in ["api", "mcp"]:
        # Filter by source using SQLite JSON functions
        base_query = base_query.filter(
            Activity.request_data.isnot(None),
            text("json_valid(request_data) = 1"),
            text("json_extract(request_data, '$.source') = :source")
        ).params(source=source)
    
    # For UI, API, MCP, ROOT filters: group by path
    # For PROJECT filter: group by project_name
    # For IP filter: group by client_ip
    # For EXPOSED filter: group by source (ui, api, mcp)
    # For TOKEN filter: group by token
    # For DEVICE filter: group by device_id
    if source in ["ui", "api", "mcp", "root"]:
        # Group by date and path using SQL (get raw path, process in Python)
        path_query = base_query.with_entities(
            func.date(Activity.created_at).label('date'),
            Activity.path,
            func.count(Activity.id).label('count')
        ).group_by(
            func.date(Activity.created_at),
            Activity.path
        ).all()
        
        # Get daily totals and avg response time
        daily_totals = base_query.with_entities(
            func.date(Activity.created_at).label('date'),
            func.count(Activity.id).label('count'),
            func.avg(Activity.execution_time_ms).label('avg_time')
        ).group_by(
            func.date(Activity.created_at)
        ).all()
        
        # Build dictionaries from SQL results
        daily_path_counts = {}
        daily_counts = {}
        total_response_time = 0
        response_time_count = 0
        
        for row in path_query:
            date_key = row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date)
            # Process path: remove /api prefix, handle empty paths
            path = row.path if row.path else ''
            if path.startswith('/api'):
                path = path[4:]  # Remove /api prefix
            if not path:
                path = '/'
            if date_key not in daily_path_counts:
                daily_path_counts[date_key] = {}
            daily_path_counts[date_key][path] = row.count
    elif source == "project":
        # Group by date and project_name using SQL
        path_query = base_query.with_entities(
            func.date(Activity.created_at).label('date'),
            Activity.project_name,
            func.count(Activity.id).label('count')
        ).group_by(
            func.date(Activity.created_at),
            Activity.project_name
        ).all()
        
        # Get daily totals and avg response time
        daily_totals = base_query.with_entities(
            func.date(Activity.created_at).label('date'),
            func.count(Activity.id).label('count'),
            func.avg(Activity.execution_time_ms).label('avg_time')
        ).group_by(
            func.date(Activity.created_at)
        ).all()
        
        # Build dictionaries from SQL results (using project_name as key)
        daily_path_counts = {}
        daily_counts = {}
        total_response_time = 0
        response_time_count = 0
        
        for row in path_query:
            date_key = row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date)
            # Use project_name as the key (or "Global" if None)
            project_key = row.project_name if row.project_name else "Global"
            if date_key not in daily_path_counts:
                daily_path_counts[date_key] = {}
            daily_path_counts[date_key][project_key] = row.count
    elif source == "ip":
        # Group by date, client_ip, and source using SQL (extract from request_data JSON)
        # Exclude UI events - only show API and MCP
        from sqlalchemy import cast, String
        path_query = base_query.filter(
            Activity.request_data.isnot(None),
            text("json_valid(request_data) = 1"),
            text("json_extract(request_data, '$.source') != 'ui' OR json_extract(request_data, '$.source') IS NULL")
        ).with_entities(
            func.date(Activity.created_at).label('date'),
            cast(text("COALESCE(json_extract(request_data, '$.client_ip'), 'unknown')"), String).label('client_ip'),
            cast(text("COALESCE(json_extract(request_data, '$.source'), 'unknown')"), String).label('source'),
            func.count(Activity.id).label('count')
        ).group_by(
            func.date(Activity.created_at),
            text("COALESCE(json_extract(request_data, '$.client_ip'), 'unknown')"),
            text("COALESCE(json_extract(request_data, '$.source'), 'unknown')")
        ).all()
        
        # Get daily totals and avg response time (also exclude UI events)
        daily_totals = base_query.filter(
            Activity.request_data.isnot(None),
            text("json_valid(request_data) = 1"),
            text("json_extract(request_data, '$.source') != 'ui' OR json_extract(request_data, '$.source') IS NULL")
        ).with_entities(
            func.date(Activity.created_at).label('date'),
            func.count(Activity.id).label('count'),
            func.avg(Activity.execution_time_ms).label('avg_time')
        ).group_by(
            func.date(Activity.created_at)
        ).all()
        
        # Build dictionaries from SQL results (using "IP @ source" as key)
        daily_path_counts = {}
        daily_counts = {}
        total_response_time = 0
        response_time_count = 0
        
        for row in path_query:
            date_key = row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date)
            # Get client_ip and source
            ip_key = getattr(row, 'client_ip', 'unknown')
            source_key = getattr(row, 'source', 'unknown')
            
            if not ip_key or ip_key == 'null':
                ip_key = 'unknown'
            if not source_key or source_key == 'null' or source_key not in ['ui', 'api', 'mcp']:
                source_key = 'unknown'
            
            # Handle special case: MCP server sets client_ip to "MCP @ IP" format
            # Extract the actual IP if it's in that format
            if ip_key.startswith('MCP @ '):
                ip_key = ip_key.replace('MCP @ ', '')
            elif ip_key == 'MCP':
                # If it's just "MCP", use localhost as default
                ip_key = '127.0.0.1'
            
            # Create combined key: "SOURCE @ IP" or just "IP" if source is unknown
            if source_key == 'unknown':
                combined_key = ip_key
            else:
                combined_key = f"{source_key.upper()} @ {ip_key}"
            
            if date_key not in daily_path_counts:
                daily_path_counts[date_key] = {}
            daily_path_counts[date_key][combined_key] = row.count
        
        for row in daily_totals:
            date_key = row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date)
            daily_counts[date_key] = row.count
            if row.avg_time:
                total_response_time += row.avg_time * row.count
                response_time_count += row.count
        
        avg_response_time_ms = round(total_response_time / response_time_count) if response_time_count > 0 else None
    elif source == "token":
        # Group by date and masked Bearer token from request_data using SQL aggregation
        # Extract the masked token from Authorization header using SQLite JSON and string functions
        from sqlalchemy import cast, String
        
        # Extract token from Authorization header: json_extract gets "Bearer TOKEN", then REPLACE removes "Bearer "
        # Handle case-insensitive header lookup by checking both 'authorization' and 'Authorization'
        path_query = base_query.filter(
            Activity.request_data.isnot(None),
            text("json_extract(request_data, '$.headers.authorization') LIKE 'Bearer %' OR json_extract(request_data, '$.headers.Authorization') LIKE 'Bearer %'")
        ).with_entities(
            func.date(Activity.created_at).label('date'),
            cast(
                text("""
                    COALESCE(
                        REPLACE(json_extract(request_data, '$.headers.authorization'), 'Bearer ', ''),
                        REPLACE(json_extract(request_data, '$.headers.Authorization'), 'Bearer ', ''),
                        ''
                    )
                """),
                String
            ).label('token'),
            func.count(Activity.id).label('count')
        ).group_by(
            func.date(Activity.created_at),
            text("""
                COALESCE(
                    REPLACE(json_extract(request_data, '$.headers.authorization'), 'Bearer ', ''),
                    REPLACE(json_extract(request_data, '$.headers.Authorization'), 'Bearer ', ''),
                    ''
                )
            """)
        ).all()
        
        # Get daily totals and avg response time (using SQL)
        daily_totals = base_query.filter(
            Activity.request_data.isnot(None),
            text("json_extract(request_data, '$.headers.authorization') LIKE 'Bearer %' OR json_extract(request_data, '$.headers.Authorization') LIKE 'Bearer %'")
        ).with_entities(
            func.date(Activity.created_at).label('date'),
            func.count(Activity.id).label('count'),
            func.avg(Activity.execution_time_ms).label('avg_time')
        ).group_by(
            func.date(Activity.created_at)
        ).all()
        
        # Build dictionaries from SQL results
        daily_path_counts = {}
        daily_counts = {}
        total_response_time = 0
        response_time_count = 0
        
        for row in path_query:
            date_key = row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date)
            token_key = getattr(row, 'token', '').strip()
            # Only process non-empty tokens
            if token_key:
                if date_key not in daily_path_counts:
                    daily_path_counts[date_key] = {}
                daily_path_counts[date_key][token_key] = row.count
        
        # Process daily totals
        for row in daily_totals:
            date_key = row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date)
            daily_counts[date_key] = row.count
            if row.avg_time:
                total_response_time += row.avg_time * row.count
                response_time_count += row.count
        
        avg_response_time_ms = round(total_response_time / response_time_count) if response_time_count > 0 else None
    elif source == "device":
        # Group by date and device ID using SQL aggregation
        # Extract device ID from path like /projects/{project}/devices/{device_id} using SQL string functions
        from sqlalchemy import cast, String
        
        # Extract device ID from path using SQL:
        # Path format: /api/projects/{project}/devices/{device_id} or /projects/{project}/devices/{device_id}
        # We need to extract the part after /devices/ and before the next / or end of string
        # Use a simpler approach: extract substring after /devices/ up to next / or end
        path_query = base_query.filter(
            Activity.path.like('%/devices/%')
        ).with_entities(
            func.date(Activity.created_at).label('date'),
            cast(
                text("""
                    SUBSTR(
                        path,
                        INSTR(path, '/devices/') + 9,
                        CASE 
                            WHEN INSTR(SUBSTR(path, INSTR(path, '/devices/') + 9), '/') > 0 
                            THEN INSTR(SUBSTR(path, INSTR(path, '/devices/') + 9), '/') - 1
                            WHEN INSTR(SUBSTR(path, INSTR(path, '/devices/') + 9), '?') > 0 
                            THEN INSTR(SUBSTR(path, INSTR(path, '/devices/') + 9), '?') - 1
                            ELSE LENGTH(path) - INSTR(path, '/devices/') - 8
                        END
                    )
                """),
                String
            ).label('device_id'),
            func.count(Activity.id).label('count')
        ).group_by(
            func.date(Activity.created_at),
            text("""
                SUBSTR(
                    path,
                    INSTR(path, '/devices/') + 9,
                    CASE 
                        WHEN INSTR(SUBSTR(path, INSTR(path, '/devices/') + 9), '/') > 0 
                        THEN INSTR(SUBSTR(path, INSTR(path, '/devices/') + 9), '/') - 1
                        WHEN INSTR(SUBSTR(path, INSTR(path, '/devices/') + 9), '?') > 0 
                        THEN INSTR(SUBSTR(path, INSTR(path, '/devices/') + 9), '?') - 1
                        ELSE LENGTH(path) - INSTR(path, '/devices/') - 8
                    END
                )
            """)
        ).having(
            text("device_id IS NOT NULL AND device_id != ''")
        ).all()
        
        # Get daily totals and avg response time (only for device-related paths)
        daily_totals = base_query.filter(
            Activity.path.like('%/devices/%')
        ).with_entities(
            func.date(Activity.created_at).label('date'),
            func.count(Activity.id).label('count'),
            func.avg(Activity.execution_time_ms).label('avg_time')
        ).group_by(
            func.date(Activity.created_at)
        ).all()
        
        # Build dictionaries from SQL results
        daily_path_counts = {}
        daily_counts = {}
        total_response_time = 0
        response_time_count = 0
        
        for row in path_query:
            date_key = row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date)
            device_id = getattr(row, 'device_id', '').strip()
            if device_id:
                # Use device ID (show first 8 chars for readability)
                device_key = f"Device {device_id[:8]}"
                if date_key not in daily_path_counts:
                    daily_path_counts[date_key] = {}
                daily_path_counts[date_key][device_key] = row.count
        
        # Process daily totals
        for row in daily_totals:
            date_key = row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date)
            daily_counts[date_key] = row.count
            if row.avg_time:
                total_response_time += row.avg_time * row.count
                response_time_count += row.count
        
        avg_response_time_ms = round(total_response_time / response_time_count) if response_time_count > 0 else None
    elif source == "exposed":
        # For EXPOSED filter: group by date and source (ui, api, mcp)
        from sqlalchemy import cast, String
        path_query = base_query.with_entities(
            func.date(Activity.created_at).label('date'),
            cast(text("COALESCE(json_extract(request_data, '$.source'), 'unknown')"), String).label('source'),
            func.count(Activity.id).label('count')
        ).group_by(
            func.date(Activity.created_at),
            text("COALESCE(json_extract(request_data, '$.source'), 'unknown')")
        ).all()
        
        # Get daily totals and avg response time
        daily_totals = base_query.with_entities(
            func.date(Activity.created_at).label('date'),
            func.count(Activity.id).label('count'),
            func.avg(Activity.execution_time_ms).label('avg_time')
        ).group_by(
            func.date(Activity.created_at)
        ).all()
        
        # Build dictionaries from SQL results (using source as key)
        daily_path_counts = {}
        daily_counts = {}
        total_response_time = 0
        response_time_count = 0
        
        for row in path_query:
            date_key = row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date)
            # Use source as the key (ui, api, mcp, unknown)
            source_key = getattr(row, 'source', 'unknown')
            if source_key not in ['ui', 'api', 'mcp']:
                source_key = 'unknown'
            if date_key not in daily_path_counts:
                daily_path_counts[date_key] = {}
            daily_path_counts[date_key][source_key] = row.count
        
        for row in daily_totals:
            date_key = row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date)
            daily_counts[date_key] = row.count
            if row.avg_time:
                total_response_time += row.avg_time * row.count
                response_time_count += row.count
        
        avg_response_time_ms = round(total_response_time / response_time_count) if response_time_count > 0 else None
    else:
        # For "All" filter (no source filter), use SQL aggregation for daily counts
        # This handles the case when source is None or not in the special filter list
        daily_results = base_query.with_entities(
            func.date(Activity.created_at).label('date'),
            func.count(Activity.id).label('count'),
            func.avg(Activity.execution_time_ms).label('avg_time')
        ).group_by(
            func.date(Activity.created_at)
        ).all()
        
        daily_counts = {}
        total_response_time = 0
        response_time_count = 0
        daily_path_counts = {}
        
        for row in daily_results:
            # Convert date to string - handle both date objects and strings from SQLite
            # SQLite func.date() returns a date object, but we need to ensure consistent formatting
            if hasattr(row.date, 'isoformat'):
                date_key = row.date.isoformat()
            elif hasattr(row.date, 'strftime'):
                date_key = row.date.strftime('%Y-%m-%d')
            elif isinstance(row.date, str):
                # If it's already a string, use it directly (but ensure format)
                date_key = row.date[:10] if len(row.date) >= 10 else row.date
            else:
                # Fallback: convert to string and extract date part
                date_str = str(row.date)
                date_key = date_str[:10] if len(date_str) >= 10 else date_str
            # Ensure date_key is exactly in YYYY-MM-DD format (10 characters)
            if len(date_key) > 10:
                date_key = date_key[:10]
            daily_counts[date_key] = row.count
            if row.avg_time:
                total_response_time += row.avg_time * row.count
                response_time_count += row.count
        
        avg_response_time_ms = round(total_response_time / response_time_count) if response_time_count > 0 else None
    
    # Generate list for last 7 days
    result = []
    all_paths = set()
    
    # Collect all unique paths/categories
    if source in ["ui", "api", "mcp", "root", "token", "device", "exposed", "project", "ip"] and daily_path_counts:
        # For UI/API/MCP/ROOT/TOKEN/DEVICE/EXPOSED/PROJECT/IP: collect paths/categories
        for date_paths in daily_path_counts.values():
            all_paths.update(date_paths.keys())
    elif source == "project" and daily_path_counts:
        # For PROJECT: collect project names
        for date_paths in daily_path_counts.values():
            all_paths.update(date_paths.keys())
    elif source == "ip" and daily_path_counts:
        # For IP: collect client IPs
        for date_paths in daily_path_counts.values():
            all_paths.update(date_paths.keys())
    elif source == "exposed" and daily_path_counts:
        # For EXPOSED: collect sources (ui, api, mcp)
        for date_paths in daily_path_counts.values():
            all_paths.update(date_paths.keys())
        # Ensure we have all three sources even if count is 0
        all_paths.update(["ui", "api", "mcp"])
    elif source == "token" and daily_path_counts:
        # For TOKEN: collect masked token values
        for date_paths in daily_path_counts.values():
            all_paths.update(date_paths.keys())
    elif source == "device" and daily_path_counts:
        # For DEVICE: collect device IDs
        for date_paths in daily_path_counts.values():
            all_paths.update(date_paths.keys())
    all_paths = sorted(list(all_paths))  # Sort for consistent ordering
    
    # Debug: Print daily_counts for troubleshooting (remove in production)
    # print(f"DEBUG: daily_counts = {daily_counts}")
    # print(f"DEBUG: source = {source}")
    
    for i in range(6, -1, -1):  # Last 7 days, most recent last
        date = (datetime.utcnow() - timedelta(days=i)).date()
        date_key = date.isoformat()
        
        # Calculate total: if we have path breakdown, sum all paths; otherwise use daily_counts
        total = daily_counts.get(date_key, 0)
        if source in ["ui", "api", "mcp", "root", "project", "ip", "token", "device", "exposed"] and date_key in daily_path_counts:
            # Sum all path/source/project/IP/token/device counts for this day
            total = sum(daily_path_counts[date_key].values())
        
        day_obj = {
            "date": date_key,
            "day": date.strftime("%a"),  # Mon, Tue, etc.
            "total": total
        }
        
        # Add path/source/project/IP/token/device breakdown
        if source in ["ui", "api", "mcp", "root", "project", "ip", "token", "device", "exposed"] and date_key in daily_path_counts:
            for path in all_paths:
                day_obj[path] = daily_path_counts[date_key].get(path, 0)
        # For "All" (no filter), just use total - no path breakdown needed
        
        result.append(day_obj)
    
    return {
        "daily_stats": result,
        "source": source,
        "avg_response_time_ms": avg_response_time_ms,
        "paths": all_paths if source in ["ui", "api", "mcp", "root", "project", "ip", "token", "device", "exposed"] else []  # Return paths/sources/projects/IPs/tokens/devices for filters
    }


@router.get("/api/dashboard/project-stats")
def get_project_activity_stats(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """Get activity counts per project for the last 7 days"""
    from ...auth import get_auth_context
    
    # Check authentication
    auth = get_auth_context(credentials, db)
    
    # Get cutoff date (last 7 days)
    cutoff_date = datetime.utcnow() - timedelta(days=7)
    
    # Build base query
    if auth.is_master:
        # Use SQL aggregation to count activities per project
        project_counts_query = db.query(
            Activity.project_name.label('project_name'),
            func.count(Activity.id).label('total'),
            func.sum(case((Activity.method == 'MCP', 1), else_=0)).label('mcp_count')
        ).filter(
            Activity.created_at >= cutoff_date
        ).group_by(
            Activity.project_name
        ).all()
        
        # Convert to list
        result = []
        for row in project_counts_query:
            project_name = row.project_name or "Global"
            total = row.total or 0
            mcp_count = int(row.mcp_count or 0)
            result.append({
                "project_name": project_name,
                "total": total,
                "mcp": mcp_count,
                "api": total - mcp_count
            })
        
        # Sort by total descending
        result.sort(key=lambda x: x["total"], reverse=True)
        
        return {"project_stats": result}
    else:
        # For project tokens, only get activities for their project
        return {"project_stats": []}


@router.get("/api/dashboard/stats")
def get_dashboard_stats(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    db: Session = Depends(get_db)
):
    """Get comprehensive dashboard statistics in a single request - uses efficient SQL queries"""
    from ...models import Secret, Token, Device
    
    # Check authentication
    auth = get_auth_context(credentials, db)
    
    # Get cutoff date (last 7 days) for activities
    cutoff_date = datetime.utcnow() - timedelta(days=7)
    
    if auth.is_master:
        # Master token: get stats for all projects
        projects_count = db.query(Project).count()
        
        # Count secrets across all projects
        secrets_count = db.query(Secret).count()
        
        # Count tokens across all projects
        tokens_count = db.query(Token).count()
        
        # Count authorized devices across all projects
        authorized_devices_count = db.query(Device).filter(Device.status == 'authorized').count()
        
        # Activity stats (all activities)
        base_activity_query = db.query(Activity).filter(Activity.created_at >= cutoff_date)
        total_activities = base_activity_query.count()
        mcp_activities = base_activity_query.filter(Activity.method == 'MCP').count()
        
        # Count exposed data
        try:
            exposed_data_count = base_activity_query.filter(
                Activity.response_data.isnot(None),
                text("json_valid(response_data) = 1"),
                text("json_extract(response_data, '$.exposed_confidential_data') = 1")
            ).count()
        except Exception:
            exposed_data_count = 0
        
        # Count MCP exposed data
        try:
            mcp_exposed_data_count = base_activity_query.filter(
                Activity.method == 'MCP',
                Activity.response_data.isnot(None),
                text("json_valid(response_data) = 1"),
                text("json_extract(response_data, '$.exposed_confidential_data') = 1")
            ).count()
        except Exception:
            mcp_exposed_data_count = 0
        
        # Calculate average response time using SQL aggregation
        result = db.query(func.avg(Activity.execution_time_ms)).filter(
            Activity.created_at >= cutoff_date,
            Activity.execution_time_ms.isnot(None)
        ).scalar()
        
        avg_response_time = round(result) if result is not None else None
        
    else:
        # Project token: get stats for the project this token belongs to
        # Get project from token
        from ...auth import hash_token
        token_hash = hash_token(credentials.credentials)
        project_token = db.query(Token).filter(Token.token_hash == token_hash).first()
        
        if not project_token:
            raise HTTPException(status_code=403, detail="Invalid token")
        
        project = db.query(Project).filter(Project.id == project_token.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        projects_count = 1
        
        # Count secrets for this project
        secrets_count = db.query(Secret).filter(Secret.project_id == project.id).count()
        
        # Count tokens for this project
        tokens_count = db.query(Token).filter(Token.project_id == project.id).count()
        
        # Count authorized devices for this project
        authorized_devices_count = db.query(Device).filter(
            Device.project_id == project.id,
            Device.status == 'authorized'
        ).count()
        
        # Activity stats (for this project)
        base_activity_query = db.query(Activity).filter(
            Activity.project_name == project.name,
            Activity.created_at >= cutoff_date
        )
        total_activities = base_activity_query.count()
        mcp_activities = base_activity_query.filter(Activity.method == 'MCP').count()
        
        # Count exposed data
        try:
            exposed_data_count = base_activity_query.filter(
                Activity.response_data.isnot(None),
                text("json_valid(response_data) = 1"),
                text("json_extract(response_data, '$.exposed_confidential_data') = 1")
            ).count()
        except Exception:
            exposed_data_count = 0
        
        # Count MCP exposed data
        try:
            mcp_exposed_data_count = base_activity_query.filter(
                Activity.method == 'MCP',
                Activity.response_data.isnot(None),
                text("json_valid(response_data) = 1"),
                text("json_extract(response_data, '$.exposed_confidential_data') = 1")
            ).count()
        except Exception:
            mcp_exposed_data_count = 0
        
        # Calculate average response time using SQL aggregation
        result = db.query(func.avg(Activity.execution_time_ms)).filter(
            Activity.project_name == project.name,
            Activity.created_at >= cutoff_date,
            Activity.execution_time_ms.isnot(None)
        ).scalar()
        
        avg_response_time = round(result) if result is not None else None
    
    return {
        "projects": projects_count,
        "secrets": secrets_count,
        "tokens": tokens_count,
        "authorized_devices": authorized_devices_count,
        "events_last_week": total_activities,
        "mcp_activities": mcp_activities,
        "exposed_data_count": exposed_data_count,
        "mcp_exposed_data_count": mcp_exposed_data_count,
        "avg_response_time_ms": avg_response_time
    }

