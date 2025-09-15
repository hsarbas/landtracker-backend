from __future__ import annotations
import os
import uuid
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import select, delete
from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.property import Property
from app.models.property_image import PropertyImage
from app.models.property_boundary import PropertyBoundary
from app.schemas.property import PropertyCreate, PropertyUpdate, PropertyOut

# Where to save uploads (adjust to your liking / settings.py)
TITLE_IMG_DIR = settings.title_img_dir

router = APIRouter(prefix="/api/v1/properties", tags=["properties"], dependencies=[Depends(get_current_user)])


def _ensure_dirs():
    os.makedirs(TITLE_IMG_DIR, exist_ok=True)


def _save_upload(file: UploadFile, subdir: str = "") -> str:
    _ensure_dirs()
    stem = str(uuid.uuid4())
    base, ext = os.path.splitext(file.filename or "")
    fname = f"{stem}{ext or ''}"
    dir_path = os.path.join(TITLE_IMG_DIR, subdir) if subdir else TITLE_IMG_DIR
    os.makedirs(dir_path, exist_ok=True)
    fpath = os.path.join(dir_path, fname)
    with open(fpath, "wb") as out:
        out.write(file.file.read())
    return fpath


def _load_full_property(db: Session, prop_id: int) -> Property:
    stmt = (
        select(Property)
        .where(Property.id == prop_id)
        .options(
            selectinload(Property.images),
            selectinload(Property.boundaries),
            selectinload(Property.reports),
            joinedload(Property.tie_point),
        )
    )
    prop = db.execute(stmt).scalars().first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


@router.get("/my", response_model=list[PropertyOut])
def list_my_properties(db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = (
        select(Property)
        .where(Property.user_id == user.id, Property.is_archived == False)  # noqa: E712
        .options(
            selectinload(Property.images),
            selectinload(Property.boundaries),
            selectinload(Property.reports),
            joinedload(Property.tie_point),
        )
        .order_by(Property.created_at.desc())
    )
    props = db.execute(stmt).scalars().all()
    return props


@router.get("/{property_id}", response_model=PropertyOut)
def get_property(property_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    prop = _load_full_property(db, property_id)
    if prop.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your property")
    return prop


# Accept multipart form with (A) JSON payload + (B) zero/one/many files
@router.post("", response_model=PropertyOut)
async def create_property(
    payload: str = Form(..., description="JSON string for PropertyCreate"),
    title_image: Optional[UploadFile] = File(None, description="(legacy) single image"),
    title_images: Optional[List[UploadFile]] = File(None, description="one or many images"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        data = PropertyCreate.model_validate_json(payload)
    except Exception:
        # fallback for old clients sending raw JSON string without quotes escaping
        data = PropertyCreate(**json.loads(payload))

    prop = Property(
        user_id=user.id,
        title_number=data.title_number,
        owner=data.owner,
        technical_description=data.technical_description,
        ocr_raw=data.ocr_raw,
        tie_point_id=data.tie_point_id,
        tie_point_province=data.tie_point_province,
        tie_point_municipality=data.tie_point_municipality,
        tie_point_name=data.tie_point_name,
    )
    db.add(prop)
    db.flush()  # so we have prop.id

    # Boundaries
    for b in data.boundaries:
        db.add(
            PropertyBoundary(
                property_id=prop.id,
                idx=b.idx,
                bearing=b.bearing,
                distance_m=b.distance_m,
                start_lat=b.start_lat,
                start_lng=b.start_lng,
                end_lat=b.end_lat,
                end_lng=b.end_lng,
                raw_text=b.raw_text,
            )
        )

    # Images: support both the single `title_image` and the future `title_images`
    files: List[UploadFile] = []
    if title_images:
        files.extend(title_images)
    if title_image:
        files.append(title_image)

    for i, f in enumerate(files):
        if not f:
            continue
        fpath = _save_upload(f, subdir=str(user.id))
        db.add(
            PropertyImage(
                property_id=prop.id,
                file_path=fpath,
                original_name=f.filename or "",
                order_index=i,
                page_number=1,
            )
        )

    db.commit()
    return _load_full_property(db, prop.id)


@router.patch("/{property_id}", response_model=PropertyOut)
async def update_property(
    property_id: int,
    payload: str = Form(..., description="JSON string for PropertyUpdate"),
    # optionally append more images
    title_images: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    prop = db.get(Property, property_id)
    if not prop or prop.user_id != user.id:
        raise HTTPException(status_code=404, detail="Property not found")

    try:
        data = PropertyUpdate.model_validate_json(payload)
    except Exception:
        data = PropertyUpdate(**json.loads(payload))

    for field, value in data.model_dump(exclude_unset=True).items():
        if field != "boundaries":
            setattr(prop, field, value)

    # Replace-all semantics for boundaries if provided
    if data.boundaries is not None:
        db.execute(delete(PropertyBoundary).where(PropertyBoundary.property_id == prop.id))
        for b in data.boundaries:
            db.add(
                PropertyBoundary(
                    property_id=prop.id,
                    idx=b.idx,
                    bearing=b.bearing,
                    distance_m=b.distance_m,
                    start_lat=b.start_lat,
                    start_lng=b.start_lng,
                    end_lat=b.end_lat,
                    end_lng=b.end_lng,
                    raw_text=b.raw_text,
                )
            )

    # New images (append)
    if title_images:
        start = len(prop.images)
        for i, f in enumerate(title_images):
            if not f:
                continue
            fpath = _save_upload(f, subdir=str(user.id))
            db.add(
                PropertyImage(
                    property_id=prop.id,
                    file_path=fpath,
                    original_name=f.filename or "",
                    order_index=start + i,
                    page_number=1,
                )
            )

    db.commit()
    return _load_full_property(db, prop.id)
