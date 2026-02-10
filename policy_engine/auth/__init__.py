"""Authentication and authorization modules"""

from policy_engine.auth.api_key import verify_api_key, get_current_agent
from policy_engine.auth.rbac import (
    get_current_user,
    require_role,
    require_permission,
    get_admin_user,
    get_analyst_or_admin
)
from policy_engine.auth.jwt_utils import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    get_token_expiration_time
)

__all__ = [
    "verify_api_key",
    "get_current_agent",
    "get_current_user",
    "require_role",
    "require_permission",
    "get_admin_user",
    "get_analyst_or_admin",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "decode_access_token",
    "get_token_expiration_time"
]
