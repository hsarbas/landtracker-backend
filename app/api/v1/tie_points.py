from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from pydantic import ValidationError

from app.db.session import get_db
from app.models.tie_point import TiePoint
from app.schemas.tie_point import TiePointCreate, TiePointRead, TiePointImport
from app.utils.strings import norm_str, norm_upper
from app.core.deps import get_current_user

router = APIRouter(prefix="/v1/tie-points", tags=["TiePoints"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=TiePointRead)
def create_tie_point(payload: TiePointCreate, db: Session = Depends(get_db)):
    existing = db.query(TiePoint).filter(
        TiePoint.tie_point_name == payload.tie_point_name
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Tie point '{payload.tie_point_name}' already exists.",
        )

    tp = TiePoint(
        tie_point_name=payload.tie_point_name,
        description=payload.description,
        province=payload.province.upper(),
        municipality=payload.municipality.upper(),
        northing=payload.northing,
        easting=payload.easting,
    )
    db.add(tp)
    db.commit()
    db.refresh(tp)
    return tp


@router.get("", response_model=List[TiePointRead])
def list_tie_points(db: Session = Depends(get_db)):
    return db.query(TiePoint).order_by(TiePoint.tie_point_name.asc()).all()


# docker compose exec db psql -U landtracker -d landtracker_db -c "DROP TABLE IF EXISTS tie_points CASCADE;"
# curl -X POST http://127.0.0.1:8000/tie-points/import -F "file=@resources/tiepoints.json;type=application/json"
@router.post("/import")
async def import_tie_points(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if file.content_type not in ("application/json", "text/json"):
        raise HTTPException(400, "Please upload a JSON file.")

    raw = await file.read()
    try:
        payload = json.loads(raw)
    except Exception:
        raise HTTPException(400, "Invalid JSON.")

    if not isinstance(payload, list):
        raise HTTPException(400, "Top-level JSON must be an array of objects.")

    created = 0
    updated = 0
    errors = []

    for idx, item in enumerate(payload, start=1):
        try:
            row = TiePointImport.model_validate(item)
        except ValidationError as e:
            errors.append({"index": idx, "error": e.errors()})
            continue

        name = norm_str(row.tie_point_name)
        desc = norm_str(row.description)
        prov = norm_upper(row.province)
        muni = norm_upper(row.municipality)
        north = row.northing if row.northing is not None else None
        east = row.easting if row.easting is not None else None

        existing = db.query(TiePoint).filter(
            TiePoint.tie_point_name == name,
            TiePoint.description == desc,
            TiePoint.province == prov,
            TiePoint.municipality == muni,
        ).one_or_none()

        if existing:
            changed = False
            # Only update if a numeric value is provided
            if north is not None and existing.northing != north:
                existing.northing = north
                changed = True
            if east is not None and existing.easting != east:
                existing.easting = east
                changed = True

            # Text fields will already be normalized; update if different
            if existing.tie_point_name != name:
                existing.tie_point_name = name
                changed = True
            if existing.description != desc:
                existing.description = desc
                changed = True
            if existing.province != prov:
                existing.province = prov
                changed = True
            if existing.municipality != muni:
                existing.municipality = muni
                changed = True

            if changed:
                updated += 1
        else:
            db.add(TiePoint(
                tie_point_name=name,
                description=desc,
                province=prov,
                municipality=muni,
                northing=north,
                easting=east,
            ))
            created += 1

    db.commit()
    return {"created": created, "updated": updated, "errors": errors, "total": len(payload)}


@router.get("/provinces", response_model=List[Optional[str]])
def list_provinces(db: Session = Depends(get_db)):
    rows = (
        db.query(TiePoint.province)
        .distinct()
        .order_by(TiePoint.province.asc().nulls_last())
        .all()
    )

    return [r[0] for r in rows]


@router.get("/municipalities", response_model=List[Optional[str]])
def list_municipalities(province: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(TiePoint.municipality).distinct().order_by(TiePoint.municipality.asc().nulls_last())
    if province is None:
        q = q.filter(TiePoint.province.is_(None))
    else:
        q = q.filter(TiePoint.province == province.strip().upper())
    return [r[0] for r in q.all()]


@router.get("/descriptions", response_model=List[Optional[str]])
def list_descriptions(
    province: Optional[str] = Query(None),
    municipality: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(TiePoint.description).distinct()

    # province filter: NULL → IS NULL, else uppercase exact match
    if province is None:
        q = q.filter(TiePoint.province.is_(None))
    else:
        q = q.filter(TiePoint.province == province.strip().upper())

    # municipality filter: NULL → IS NULL, else uppercase exact match
    if municipality is None:
        q = q.filter(TiePoint.municipality.is_(None))
    else:
        q = q.filter(TiePoint.municipality == municipality.strip().upper())

    q = q.order_by(TiePoint.description.asc().nulls_last())
    rows = q.all()
    return [r[0] for r in rows]


@router.get("/by-description", response_model=TiePointRead)
def get_by_description(
    province: Optional[str] = Query(None),
    municipality: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(TiePoint)

    print(f'======== {province}, {municipality}, {description}')
    # province
    if province is None:
        q = q.filter(TiePoint.province.is_(None))
    else:
        q = q.filter(TiePoint.province == province.strip().upper())

    # municipality
    if municipality is None:
        q = q.filter(TiePoint.municipality.is_(None))
    else:
        q = q.filter(TiePoint.municipality == municipality.strip().upper())

    # description (keep original case; do exact match on trimmed string)
    if description is None:
        q = q.filter(TiePoint.description.is_(None))
    else:
        q = q.filter(TiePoint.description == description.strip())

    row = q.order_by(TiePoint.tie_point_name.asc()).first()
    if not row:
        raise HTTPException(status_code=404, detail="No matching tie point found.")
    return row


@router.get("/{tie_point_id}", response_model=TiePointRead)
def get_tie_point_by_id(tie_point_id: int, db: Session = Depends(get_db)):
    tp = db.get(TiePoint, tie_point_id)
    if not tp:
        raise HTTPException(status_code=404, detail=f"Tie point with id {tie_point_id} not found.")
    return tp

