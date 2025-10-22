from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.role import Role
from app.schemas.role import RoleRead, RoleCreate
from app.models.user import User

router = APIRouter(prefix="/v1/roles", tags=["roles"])


def require_admin(user: User):
    if not user.role or user.role.name != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")


@router.get("", response_model=list[RoleRead])
def list_roles(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # allow any authenticated user to list roles (or tighten if you want)
    return db.query(Role).order_by(Role.name).all()


@router.post("", response_model=RoleRead, status_code=201)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    exists = db.query(Role).filter(Role.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=400, detail="Role already exists")
    role = Role(name=payload.name, description=payload.description)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role
