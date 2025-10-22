from __future__ import annotations
import os
import re
import uuid
import base64
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload, joinedload

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db

from app.models.property import Property
from app.models.property_image import PropertyImage
from app.models.property_boundary import PropertyBoundary
from app.models.property_report import PropertyReport  # ensure this model file exists

from app.schemas.property import (
    PropertyCreate, PropertyOut,
    TitleImageCreate, BoundaryCreate, ReportCreate, ReportOut
)

router = APIRouter(
    prefix="/v1/properties",
    tags=["properties"],
    dependencies=[Depends(get_current_user)],
)

# --- Directories from settings ---
TITLE_IMG_DIR = settings.title_img_dir               # e.g., /data/uploads/properties
REPORT_DIR = getattr(settings, "report_dir", None) or os.path.join(os.path.dirname(TITLE_IMG_DIR), "reports")

# --- Helpers ---
DATA_URL_RE = re.compile(r"^data:(?P<mime>[\w\-\./\+]+);base64,(?P<b64>.+)$", re.I)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _save_data_url_strict(data_url: str, base_dir: str, subdir: str, *, allowed_mimes: set[str], filename_hint: str | None = None) -> str:
    m = DATA_URL_RE.match(data_url or "")
    if not m:
        raise HTTPException(status_code=422, detail="Invalid data URL")
    mime = (m.group("mime") or "").lower()
    if mime not in {x.lower() for x in allowed_mimes}:
        raise HTTPException(status_code=422, detail=f"Unsupported MIME type: {mime}")
    try:
        blob = base64.b64decode(m.group("b64"))
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid base64 payload")

    ext_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
    }
    ext = ext_map.get(mime, ".bin")

    folder = os.path.join(base_dir, subdir) if subdir else base_dir
    _ensure_dir(folder)
    fname = (filename_hint if filename_hint else f"{uuid.uuid4().hex}{ext}")
    fpath = os.path.join(folder, fname)
    with open(fpath, "wb") as fh:
        fh.write(blob)
    return fpath


def _load_full_property(db: Session, prop_id: int) -> Property:
    prop = db.get(
        Property,
        prop_id,
        options=(
            selectinload(Property.images),
            selectinload(Property.boundaries),
            selectinload(Property.reports),
            joinedload(Property.tie_point),
        ),
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


# --- Endpoints ---

@router.get("/my", response_model=list[PropertyOut])
def list_my_properties(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return (
        db.query(Property)
        .options(
            selectinload(Property.images),
            selectinload(Property.boundaries),
            selectinload(Property.reports),
            joinedload(Property.tie_point),
        )
        .filter(Property.user_id == user.id)
        .order_by(Property.created_at.desc())
        .all()
    )


@router.get("/{property_id}", response_model=PropertyOut)
def get_property(property_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    prop = _load_full_property(db, property_id)
    if prop.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your property")
    return prop


@router.post("", response_model=PropertyOut)
async def create_property(
    payload: PropertyCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # Security: only allow creating for self (adjust if you support admins)
    if payload.user_id != user.id:
        raise HTTPException(status_code=403, detail="Cannot create property for another user")

    prop = Property(
        user_id=payload.user_id,
        title_number=payload.title_number,
        owner=payload.owner,
        technical_description=payload.technical_description,
        tie_point_id=payload.tie_point_id,
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return _load_full_property(db, prop.id)


@router.put("/{property_id}/boundaries", response_model=PropertyOut)
async def replace_boundaries(
    property_id: int,
    boundaries: List[BoundaryCreate],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    prop = _load_full_property(db, property_id)
    if prop.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your property")

    # Replace-all semantics
    # Clear existing
    for b in list(prop.boundaries):
        db.delete(b)
    db.flush()

    # Insert new
    for b in boundaries or []:
        db.add(PropertyBoundary(
            property_id=prop.id,
            bearing=b.bearing,
            distance_m=b.distance_m,
        ))

    db.commit()
    return _load_full_property(db, prop.id)


@router.post("/{property_id}/images", response_model=PropertyOut)
async def add_images(
    property_id: int,
    images: List[TitleImageCreate],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    prop = _load_full_property(db, property_id)
    if prop.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your property")

    # Reject PDFs; allow image/* only
    allowed = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
    for img in images or []:
        # Save file
        saved_path = _save_data_url_strict(
            img.data_url,
            base_dir=TITLE_IMG_DIR,
            subdir=str(user.id),
            allowed_mimes=allowed,
            filename_hint=None,  # derive from MIME; you can pass a client filename if you add it later
        )
        # Store DB row
        db.add(PropertyImage(
            property_id=prop.id,
            file_path=saved_path,
            order_index=img.order_index,
        ))

    db.commit()
    return _load_full_property(db, prop.id)


@router.post("/{property_id}/reports", response_model=PropertyOut)
async def add_reports(
    property_id: int,
    reports: List[ReportCreate],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    prop = _load_full_property(db, property_id)
    if prop.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your property")

    # PDFs only
    allowed = {"application/pdf"}
    for rpt in reports or []:
        saved_path = _save_data_url_strict(
            rpt.data_url,
            base_dir=REPORT_DIR,
            subdir=str(user.id),
            allowed_mimes=allowed,
            filename_hint=None,  # can accept a filename in schema later if desired
        )
        db.add(PropertyReport(
            property_id=prop.id,
            report_type=rpt.report_type,
            file_path=saved_path,
        ))

    db.commit()
    return _load_full_property(db, prop.id)


@router.get("/{property_id}/reports", response_model=List[ReportOut])
def list_property_reports(property_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    prop = _load_full_property(db, property_id)
    if prop.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your property")
    return sorted(prop.reports, key=lambda r: (r.created_at, r.id), reverse=True)


@router.get("/{property_id}/reports/{report_id}/download")
def download_report(
    property_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # Verify property ownership
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if prop.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your property")

    rpt = (
        db.query(PropertyReport)
        .filter(
            PropertyReport.id == report_id,
            PropertyReport.property_id == property_id,
        )
        .first()
    )
    if not rpt:
        raise HTTPException(status_code=404, detail="Report not found")

    fpath = rpt.file_path
    if not fpath or not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="Report file missing")

    # Let browser display inline, but still downloadable
    return FileResponse(
        path=fpath,
        media_type="application/pdf",
        filename=os.path.basename(fpath),
    )
