from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserRead, UserUpdate, PasswordChange, SetRoleRequest
from app.core.security import verify_password, hash_password

router = APIRouter(prefix="/v1/users", tags=["users"], dependencies=[Depends(get_current_user)])


def require_admin(user: User):
    if not user.role or user.role.name != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    # email uniqueness (if provided)
    if payload.email is not None:
        exists = db.query(User).filter(
            User.email == payload.email.lower(),
            User.id != current_user.id
        ).first()
        if exists:
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.email = payload.email.lower()

    if payload.first_name is not None:
        current_user.first_name = payload.first_name
    if payload.last_name is not None:
        current_user.last_name = payload.last_name

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.patch("/me/password", response_model=dict)
def change_password(
    body: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(body.new_password)
    db.add(current_user)
    db.commit()
    return {"ok": True}


# ---- ADMIN: set a user's role ----
@router.patch("/{user_id}/role", response_model=UserRead)
def set_user_role(
    user_id: int = Path(..., ge=1),
    body: SetRoleRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    role = db.get(Role, body.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    user.role_id = role.id
    db.add(user)
    db.commit()
    db.refresh(user)
    return user