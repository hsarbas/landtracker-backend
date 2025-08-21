from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.user import SetRoleRequest, UserRead
from app.models.user import User, Role
from app.core.deps import get_db, require_roles, get_current_user

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(get_current_user)],)


@router.patch("/users/{user_id}/role", response_model=UserRead)
def set_user_role(
    user_id: int,
    body: SetRoleRequest,
    _: User = Depends(require_roles(Role.admin)),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = body.role
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserRead])
def list_users(_: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    return db.query(User).all()
