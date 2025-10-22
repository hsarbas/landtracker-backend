from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.schemas.user import SetRoleRequest, UserRead
from app.models.user import User
from app.models.role import Role
from app.core.deps import get_db, require_roles, get_current_user

router = APIRouter(
    prefix="/v1/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_user)],  # keeps all endpoints auth-protected
)


@router.patch("/users/{user_id}/role", response_model=UserRead)
def set_user_role(
    user_id: int,
    body: SetRoleRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),  # <- string-based role check
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    role = db.get(Role, body.role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    user.role_id = role.id
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),  # <- string-based role check
):
    # Eager-load roles so Pydantic can serialize UserRead.role cleanly
    users = (
        db.query(User)
        .options(joinedload(User.role))
        .order_by(User.id.asc())
        .all()
    )
    return users
