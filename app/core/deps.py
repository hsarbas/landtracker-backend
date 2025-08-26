from __future__ import annotations
from typing import Annotated, Iterable
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload
from jose import jwt, JWTError

from app.db.session import get_db
from app.models.user import User
from app.core.config import SECRET_KEY, ALGORITHM
from app.core.security import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """
    Decode access token, fetch the user, ensure active.
    We eager-load role to avoid lazy-load issues in dependencies.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        data = TokenPayload(**payload)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if data.type != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token required")

    user = (
        db.query(User)
        .options(joinedload(User.role))  # eager-load role
        .get(int(data.sub))
    )
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing user")
    return user


# ---------- Role helpers (string-based) ----------

def _has_any_role(user: User, allowed_names: Iterable[str]) -> bool:
    """
    Check if user's role name matches any of the provided allowed names.
    Case-sensitive by default; make .lower() both sides if you prefer case-insensitive.
    """
    if not user.role:
        return False
    return user.role.name in set(allowed_names)


def ensure_role(user: User, *allowed_role_names: str) -> None:
    """
    Low-level guard you can call inside route handlers.
    """
    if not _has_any_role(user, allowed_role_names):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")


def require_roles(*allowed_role_names: str):
    """
    FastAPI dependency: require that the current user has ANY of the given roles.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_roles("admin"))])
        def admin_only(...):
            ...
    """
    def _checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        ensure_role(current_user, *allowed_role_names)
        return current_user
    return _checker


# Optional alias with a friendlier name
def require_any_role(*allowed_role_names: str):
    return require_roles(*allowed_role_names)
