"""
Confidential data tracking system - marks confidential fields at source.
This allows fast O(1) exposure detection without scanning the database.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from fastapi import Response


@dataclass
class ConfidentialField:
    """Represents a confidential field in a response"""
    path: str  # e.g., "body.value", "body.token"
    type: str  # "secret" or "token"
    details: Dict[str, Any] = field(default_factory=dict)  # Additional context


class ConfidentialTracker:
    """Tracks confidential fields in responses"""
    
    @staticmethod
    def mark_secret(response_data: Dict[str, Any], field_path: str, secret_key: str, project_name: str, secret_id: str = None):
        """Mark a secret field as confidential"""
        if "_confidential_fields" not in response_data:
            response_data["_confidential_fields"] = []
        
        response_data["_confidential_fields"].append({
            "path": field_path,
            "type": "secret",
            "details": {
                "secret_key": secret_key,
                "project_name": project_name,
                "secret_id": secret_id
            }
        })
    
    @staticmethod
    def mark_token(response_data: Dict[str, Any], field_path: str, token_type: str, token_name: str = None, token_id: str = None, project_name: str = None):
        """Mark a token field as confidential"""
        if "_confidential_fields" not in response_data:
            response_data["_confidential_fields"] = []
        
        response_data["_confidential_fields"].append({
            "path": field_path,
            "type": "token",
            "details": {
                "token_type": token_type,
                "token_name": token_name,
                "token_id": token_id,
                "project_name": project_name
            }
        })
    
    @staticmethod
    def get_confidential_fields(response_data: Dict[str, Any]) -> List[ConfidentialField]:
        """Get all confidential fields from response metadata"""
        if "_confidential_fields" not in response_data:
            return []
        
        return [
            ConfidentialField(
                path=field_data["path"],
                type=field_data["type"],
                details=field_data.get("details", {})
            )
            for field_data in response_data["_confidential_fields"]
        ]


def check_exposure_from_metadata(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fast O(1) exposure detection using metadata.
    Returns exposure report based on confidential fields metadata.
    """
    from .exposure_detector import ExposureReport, ExposureFinding
    
    report = ExposureReport()
    
    confidential_fields = ConfidentialTracker.get_confidential_fields(response_data)
    
    if not confidential_fields:
        return report.to_dict()
    
    # Convert confidential fields to exposure findings
    for field in confidential_fields:
        # Check if the field actually contains data (not already redacted)
        path_parts = field.path.split('.')
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
            
            # If field exists and has actual data (not redacted), it's exposed
            if current is not None and isinstance(current, str):
                # Skip if already redacted/masked
                # Also check for partial masking patterns (like "ABC***XYZ")
                is_already_redacted = (
                    current in ["***EXPOSED***", "***REDACTED***", "**** EXPOSED ****"] or
                    (current.count('*') > 3 and len(current) > 10)  # Heavily masked
                )
                if not is_already_redacted:
                    report.findings.append(ExposureFinding(
                        type=field.type,
                        location="response",
                        field_path=f"response.{field.path}",
                        details=field.details
                    ))
        except (KeyError, TypeError, AttributeError):
            # Field path doesn't exist or is invalid
            continue
    
    report.has_exposure = len(report.findings) > 0
    return report.to_dict()

