"""Authentication endpoints: register, login, me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import ACCESS_COOKIE, get_current_user, require_permission
from app.config import settings
from app.database.session import get_db
from app.models.user import User
from app.models.document import AuditLog
from app.schemas.api import LoginRequest, PasswordChange, RegisterRequest, TokenResponse
from app.schemas.common import APIResponse
from app.utils.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookie(response: Response, token: str, secure: bool) -> None:
    """HttpOnly cookie transport (works where proxies strip Authorization).

    SameSite=Lax; Secure only when the request itself is HTTPS — plain-HTTP
    origins (local dev) silently drop Secure cookies. The JS-accessible
    localStorage copy remains the primary transport.
    """
    response.set_cookie(
        ACCESS_COOKIE,
        f"Bearer {token}",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def _user_payload(user: User) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


@router.post(
    "/register",
    summary="Register a new user",
    description="Creates a local account. The first registered user becomes admin; "
    "subsequent self-registrations are viewers unless an admin assigns a role.",
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> APIResponse:
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_TAKEN", "message": "A user with this email already exists."},
        )
    is_first = db.query(User).count() == 0
    role = "admin" if is_first else (payload.role if payload.role in ("viewer",) else "viewer")
    user = User(
        name=payload.name.strip(),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return APIResponse(data=_user_payload(user), message="User registered successfully.")


@router.post("/login", summary="Obtain a JWT access token")
def login(
    payload: LoginRequest, request: Request, response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "BAD_CREDENTIALS", "message": "Incorrect email or password."},
        )
    token = create_access_token(subject=user.email, role=user.role)
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    _set_auth_cookie(response, token, secure=secure)
    return TokenResponse(access_token=token, user=_user_payload(user))


@router.post("/logout", summary="Clear the auth cookie")
def logout(response: Response) -> APIResponse:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    return APIResponse(message="Logged out.")


@router.get("/me", summary="Current authenticated user")
def me(user: User = Depends(get_current_user)) -> APIResponse:
    return APIResponse(data=_user_payload(user))


@router.post("/change-password", summary="Change the current user's password")
def change_password(
    payload: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "BAD_CREDENTIALS", "message": "Current password is incorrect."},
        )
    user.password_hash = hash_password(payload.new_password)
    db.add(AuditLog(user_id=user.id, action="change_password", entity="user",
                    entity_id=user.id))
    db.commit()
    return APIResponse(message="Password changed successfully.")


@router.get(
    "/users",
    summary="List users (admin)",
    dependencies=[Depends(require_permission("manage_users"))],
)
def list_users(db: Session = Depends(get_db)) -> APIResponse:
    users = db.query(User).order_by(User.id).all()
    return APIResponse(data=[_user_payload(u) for u in users])


@router.put(
    "/users/{user_id}/role",
    summary="Change a user's role (admin)",
    dependencies=[Depends(require_permission("manage_users"))],
)
def set_role(user_id: int, role: str, db: Session = Depends(get_db)) -> APIResponse:
    if role not in ("admin", "recruiter", "viewer"):
        raise HTTPException(400, detail={"code": "BAD_ROLE", "message": "Unknown role."})
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "User not found."})
    user.role = role
    db.commit()
    return APIResponse(data=_user_payload(user), message="Role updated.")
