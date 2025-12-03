"""
Exposure detection utility for identifying confidential data in API requests/responses.
Checks for exposed secrets, tokens, and other sensitive information.
Returns detailed information about what was exposed, where, and how.
"""
import re
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from .models import Secret, Token, MasterToken, Project
from .encryption import decrypt_data
from .auth import hash_token


@dataclass
class ExposureFinding:
    """Represents a single finding of exposed confidential data"""
    type: str  # 'secret' or 'token'
    location: str  # 'request' or 'response'
    field_path: str  # e.g., 'body.value', 'body.token', 'headers.Authorization'
    details: Dict[str, Any] = field(default_factory=dict)  # Additional details (secret key, token type, etc.)


@dataclass
class ExposureReport:
    """Detailed report of all exposure findings"""
    has_exposure: bool = False
    findings: List[ExposureFinding] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "has_exposure": self.has_exposure,
            "findings": [
                {
                    "type": f.type,
                    "location": f.location,
                    "field_path": f.field_path,
                    "details": f.details
                }
                for f in self.findings
            ]
        }


def check_for_exposed_data(
    request_data: Optional[str] = None,
    response_data: Optional[str] = None,
    db: Optional[Session] = None,
    original_token: Optional[str] = None
) -> ExposureReport:
    """
    Check for exposed confidential information in both request and response data:
    - Secret values (actual secrets from the vault)
    - Token values (unmasked tokens: master tokens or project tokens)
    
    Args:
        request_data: JSON string of request data (checked for secrets, tokens expected)
        response_data: JSON string of response data (checked for secrets and tokens)
        db: Database session to query for actual secret/token values
        original_token: Original token used in the request (for comparison)
    
    Returns:
        ExposureReport with detailed findings about what was exposed and where
    """
    report = ExposureReport()
    
    # Check request data for exposed secrets (tokens in requests are expected, not exposure)
    # NOTE: We still check requests to track them, but they don't count as "exposure" 
    # since secrets in requests are expected (user is sending them to store)
    request_findings = []
    if request_data:
        try:
            request_obj = json.loads(request_data)
            _check_data_for_exposed_secrets(
                request_obj, 
                db, 
                report, 
                location="request",
                field_path="request"
            )
            # Track request findings separately (for logging, but not for exposure flag)
            request_findings = [f for f in report.findings if f.location == "request"]
        except (json.JSONDecodeError, TypeError):
            # Also check as plain text
            _check_text_for_exposed_secrets(
                request_data,
                db,
                report,
                location="request"
            )
            request_findings = [f for f in report.findings if f.location == "request"]
    
    # Check response data for exposed secrets and tokens
    # THIS is what counts as actual exposure - secrets/tokens in responses
    response_findings = []
    if response_data:
        try:
            response_obj = json.loads(response_data)
            _check_data_for_exposed_secrets(
                response_obj,
                db,
                report,
                location="response",
                field_path="response"
            )
            _check_data_for_exposed_tokens(
                response_obj,
                db,
                report,
                location="response",
                field_path="response",
                original_token=original_token
            )
            # Track response findings separately
            response_findings = [f for f in report.findings if f.location == "response"]
        except (json.JSONDecodeError, TypeError):
            # Also check as plain text
            _check_text_for_exposed_secrets(
                response_data,
                db,
                report,
                location="response"
            )
            _check_text_for_exposed_tokens(
                response_data,
                db,
                report,
                location="response",
                original_token=original_token
            )
            response_findings = [f for f in report.findings if f.location == "response"]
    
    # Only mark as exposure if response has findings (secrets in requests are expected)
    report.has_exposure = len(response_findings) > 0
    return report


def _check_data_for_exposed_secrets(
    data: Any,
    db: Optional[Session],
    report: ExposureReport,
    location: str,
    field_path: str
):
    """Recursively check data for exposed secret values"""
    if not db:
        return
    
    if isinstance(data, dict):
        # Check for 'value' field (common secret field)
        if 'value' in data and isinstance(data['value'], str):
            value = data['value']
            # Skip if already masked/redacted
            if '***' not in value and 'REDACTED' not in value and len(value) > 0:
                secret_info = _get_secret_info(value, db)
                if secret_info:
                    report.findings.append(ExposureFinding(
                        type="secret",
                        location=location,
                        field_path=f"{field_path}.value",
                        details=secret_info
                    ))
        
        # Check nested structures
        # Skip 'value' field in loop since it's already checked above
        for key, value in data.items():
            if key == 'value':
                continue  # Already checked above, skip to avoid duplicates
            if isinstance(value, (dict, list)):
                _check_data_for_exposed_secrets(
                    value,
                    db,
                    report,
                    location,
                    f"{field_path}.{key}"
                )
            elif isinstance(value, str) and len(value) > 10:
                # Check if this string matches a secret value
                if '***' not in value and 'REDACTED' not in value:
                    secret_info = _get_secret_info(value, db)
                    if secret_info:
                        report.findings.append(ExposureFinding(
                            type="secret",
                            location=location,
                            field_path=f"{field_path}.{key}",
                            details=secret_info
                        ))
    
    elif isinstance(data, list):
        for i, item in enumerate(data):
            _check_data_for_exposed_secrets(
                item,
                db,
                report,
                location,
                f"{field_path}[{i}]"
            )


def _check_data_for_exposed_tokens(
    data: Any,
    db: Optional[Session],
    report: ExposureReport,
    location: str,
    field_path: str,
    original_token: Optional[str] = None
):
    """Recursively check data for exposed token values (only in responses)"""
    if not db:
        return
    
    if isinstance(data, dict):
        # Check for token fields
        token_fields = ['token', 'master_token', 'api_token', 'access_token', 'bearer_token', 'auth_token']
        for field_name in token_fields:
            if field_name in data and isinstance(data[field_name], str):
                token = data[field_name]
                # Check if it's unmasked (not containing masking patterns)
                if '***' not in token and '...' not in token and len(token) > 8:
                    token_info = _get_token_info(token, db)
                    if token_info:
                        report.findings.append(ExposureFinding(
                            type="token",
                            location=location,
                            field_path=f"{field_path}.{field_name}",
                            details=token_info
                        ))
        
        # Check Authorization header if present
        if 'headers' in data and isinstance(data['headers'], dict):
            auth_header = data['headers'].get('Authorization') or data['headers'].get('authorization')
            if auth_header and isinstance(auth_header, str):
                # Extract token from Bearer header
                token = None
                if auth_header.startswith('Bearer '):
                    token = auth_header[7:].strip()
                elif auth_header.startswith('Bearer'):
                    token = auth_header[6:].strip()
                
                if token and '***' not in token and '...' not in token and len(token) > 8:
                    token_info = _get_token_info(token, db)
                    if token_info:
                        report.findings.append(ExposureFinding(
                            type="token",
                            location=location,
                            field_path=f"{field_path}.headers.Authorization",
                            details=token_info
                        ))
        
        # Check nested structures
        # Skip token fields and headers in loop since they're already checked above
        for key, value in data.items():
            # Skip fields already checked above to avoid duplicates
            if key in ['token', 'master_token', 'api_token', 'access_token', 'bearer_token', 'auth_token', 'headers']:
                continue
            if isinstance(value, (dict, list)):
                _check_data_for_exposed_tokens(
                    value,
                    db,
                    report,
                    location,
                    f"{field_path}.{key}",
                    original_token
                )
            elif isinstance(value, str) and len(value) > 10:
                # Check if this string matches a token value
                if '***' not in value and '...' not in value:
                    token_info = _get_token_info(value, db)
                    if token_info:
                        report.findings.append(ExposureFinding(
                            type="token",
                            location=location,
                            field_path=f"{field_path}.{key}",
                            details=token_info
                        ))
    
    elif isinstance(data, list):
        for i, item in enumerate(data):
            _check_data_for_exposed_tokens(
                item,
                db,
                report,
                location,
                f"{field_path}[{i}]",
                original_token
            )


def _check_text_for_exposed_secrets(
    text: str,
    db: Optional[Session],
    report: ExposureReport,
    location: str
):
    """Check plain text for exposed secret values"""
    if not text or not db:
        return
    
    # Check for secret value patterns in JSON responses
    if '"value"' in text.lower() or "'value'" in text.lower():
        value_pattern = r'["\']value["\']\s*:\s*["\']([^"\']+)["\']'
        matches = re.findall(value_pattern, text, re.IGNORECASE)
        for match in matches:
            # Skip if it's already masked/redacted
            if '***' in match or 'REDACTED' in match:
                continue
            # Check if it's an actual secret value from the database
            secret_info = _get_secret_info(match, db)
            if secret_info:
                report.findings.append(ExposureFinding(
                    type="secret",
                    location=location,
                    field_path="response.value",
                    details=secret_info
                ))


def _check_text_for_exposed_tokens(
    text: str,
    db: Optional[Session],
    report: ExposureReport,
    location: str,
    original_token: Optional[str] = None
):
    """Check plain text for exposed token values"""
    if not text or not db:
        return
    
    # Check for unmasked token patterns in JSON responses
    if '"token"' in text.lower() or "'token'" in text.lower():
        token_pattern = r'["\']token["\']\s*:\s*["\']([^"\']+)["\']'
        matches = re.findall(token_pattern, text, re.IGNORECASE)
        for match in matches:
            # Skip if it's already masked
            if '***' not in match and '...' not in match and len(match) > 8:
                token_info = _get_token_info(match, db)
                if token_info:
                    report.findings.append(ExposureFinding(
                        type="token",
                        location=location,
                        field_path="response.token",
                        details=token_info
                    ))


def _get_secret_info(value: str, db: Session) -> Optional[Dict[str, Any]]:
    """Get information about a secret value if it matches a secret in the database"""
    try:
        # Query all secrets and check if the value matches
        secrets = db.query(Secret).all()
        for secret in secrets:
            try:
                decrypted = decrypt_data(secret.encrypted_value)
                if decrypted == value:
                    # Get project name
                    from .models import Project
                    project = db.query(Project).filter(Project.id == secret.project_id).first()
                    return {
                        "secret_key": secret.key,
                        "project_name": project.name if project else None,
                        "secret_id": secret.id
                    }
            except Exception:
                # Skip if decryption fails
                continue
    except Exception:
        pass
    return None


def _get_token_info(value: str, db: Session) -> Optional[Dict[str, Any]]:
    """Get information about a token value if it matches a token in the database"""
    try:
        # Hash the value and check against stored hashes
        value_hash = hash_token(value)
        
        # Check master tokens
        master_token = db.query(MasterToken).filter(
            MasterToken.token_hash == value_hash
        ).first()
        if master_token:
            return {
                "token_type": "master",
                "token_id": master_token.id,
                "token_name": master_token.name
            }
        
        # Check project tokens
        project_token = db.query(Token).filter(
            Token.token_hash == value_hash
        ).first()
        if project_token:
            # Get project name
            from .models import Project
            project = db.query(Project).filter(Project.id == project_token.project_id).first()
            return {
                "token_type": "project",
                "token_id": project_token.id,
                "token_name": project_token.name,
                "project_name": project.name if project else None
            }
        
        # Also check environment variable master token
        from .config import MASTER_TOKEN
        if value == MASTER_TOKEN:
            return {
                "token_type": "master",
                "token_name": "Environment Variable Master Token",
                "source": "environment"
            }
            
    except Exception:
        pass
    return None

