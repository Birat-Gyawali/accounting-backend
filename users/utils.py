
from rest_framework_simplejwt.tokens import RefreshToken


def build_refresh_token(user, membership=None) -> RefreshToken:
    
    refresh = RefreshToken.for_user(user)
    refresh["email"] = user.email

    if membership is not None:
        refresh["organization_id"] = str(membership.organization_id)
        refresh["role"] = membership.role

    return refresh


def tokens_to_dict(refresh: RefreshToken) -> dict:
    
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }