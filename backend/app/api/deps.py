"""API dependencies: authentication and role-based authorization.

Roles: admin (everything), recruiter (upload/process/search/match/manage jobs),
viewer (read-only). Permissions are configurable via ROLE_PERMISSIONS.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.utils.security import decode_access_token

bearer = HTTPBearer(auto_error=False)

#: Cookie name used as an alternative token transport.
ACCESS_COOKIE = "access_token"
#: Custom header fallback — used when a hosting proxy consumes Authorization.
TOKEN_HEADER = "X-Access-Token"

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        "read", "upload", "process", "delete", "manage_users", "manage_skills",
        "manage_aliases", "manage_thresholds", "review", "retry", "audit_view",
        "manage_jobs", "match", "file_download",
    },
    "recruiter": {
        "read", "upload", "process", "review", "retry", "manage_jobs", "match",
        "file_download",
    },
    "viewer": {"read"},
}

# Map of route "scopes" -> required permission
PERMISSION_FOR_SCOPE: dict[str, str] = {
    "read": "read",
    "upload": "upload",
    "process": "process",
    "delete": "delete",
    "manage_users": "manage_users",
    "manage_skills": "manage_skills",
    "manage_aliases": "manage_aliases",
    "review": "review",
    "retry": "retry",
    "manage_jobs": "manage_jobs",
    "audit_view": "audit_view",
    "manage_thresholds": "manage_thresholds",
    "match": "match",
    "file_download": "file_download",
}


def _extract_token(
    request: Request, credentials: HTTPAuthorizationCredentials | None
) -> str | None:
    """Resolve the token from three transports, in priority order.

    ``Authorization`` is the primary channel. Some hosting proxies strip or
    consume it, so the SPA also authenticates via an HttpOnly cookie set at
    login and (as a last resort) a custom ``X-Access-Token`` header.
    """
    if credentials is not None:
        return credentials.credentials
    cookie = request.cookies.get(ACCESS_COOKIE)
    if cookie:
        return cookie.removeprefix("Bearer ")
    custom = request.headers.get(TOKEN_HEADER)
    if custom:
        return custom.removeprefix("Bearer ")
    return None


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_token(request, credentials)
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NOT_AUTHENTICATED", "message": "Authentication required."},
        )
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or expired token."},
        )
    user = db.query(User).filter(User.email == payload["sub"]).first()
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "USER_NOT_FOUND", "message": "Token subject not found."},
        )
    return user


def require_permission(scope: str):
    """Dependency factory enforcing role-based authorization."""

    permission = PERMISSION_FOR_SCOPE[scope]

    def checker(user: User = Depends(get_current_user)) -> User:
        allowed = ROLE_PERMISSIONS.get(user.role, set())
        if permission not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": f"Role '{user.role}' lacks the '{permission}' permission.",
                },
            )
        return user

    return checker
