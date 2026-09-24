
from typing import Optional

from rest_framework.exceptions import PermissionDenied


def get_current_organization_id(request) -> Optional[str]:
    
    token = getattr(request, "auth", None)
    if token is None:
        return None
    return token.get("organization_id")


def get_current_role(request) -> Optional[str]:
    
    token = getattr(request, "auth", None)
    if token is None:
        return None
    return token.get("role")


def require_current_organization_id(request) -> str:
    
    organization_id = get_current_organization_id(request)
    if organization_id is None:
        raise PermissionDenied(
            "No organization selected for this session. "
            "Call /api/auth/select-organization/ first."
        )
    return organization_id