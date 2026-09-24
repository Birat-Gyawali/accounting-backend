from rest_framework.permissions import BasePermission

from .tenancy import require_current_organization_id


class IsTenantMember(BasePermission):
   

    message = "No organization selected for this session. Call /api/auth/select-organization/ first."

    def has_permission(self, request, view):
       
        require_current_organization_id(request)
        return True


class HasMinimumRole(BasePermission):


    ROLE_ORDER = ["STAFF", "MANAGER", "ACCOUNTANT", "ADMIN", "OWNER"]
    message = "Your role in this organization does not permit this action."

    def has_permission(self, request, view):
        from .tenancy import get_current_role

        required_role = self._resolve_required_role(view)
        if required_role is None:
            return True

        current_role = get_current_role(request)
        if current_role not in self.ROLE_ORDER:
            return False

        return self.ROLE_ORDER.index(current_role) >= self.ROLE_ORDER.index(required_role)

    @staticmethod
    def _resolve_required_role(view):
        action_roles = getattr(view, "action_required_roles", None)
        action = getattr(view, "action", None)
        if action_roles is not None and action in action_roles:
            return action_roles[action]
        return getattr(view, "required_role", None)


def draft_workflow_roles(post_actions, cancel_actions=(), create_role="STAFF", post_role="ACCOUNTANT"):
    
    roles = {
        "list": create_role, "retrieve": create_role,
        "create": create_role, "update": create_role,
        "partial_update": create_role, "destroy": create_role,
    }
    for action in post_actions:
        roles[action] = post_role
    for action in cancel_actions:
        roles[action] = post_role
    return roles