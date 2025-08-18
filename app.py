import os
import re
import json
from pydantic import ValidationError
from sqlalchemy import and_

from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
from geographiclib.geodesic import Geodesic
from google.cloud import vision
from google.oauth2 import service_account

from typing import List, Optional

from db import Base, engine, get_db
from models.tie_point import TiePoint
from schemas import *

from settings import settings, configure_cors
from fastapi import Depends, Query
from sqlalchemy.orm import Session
from pyproj import Transformer
from fastapi.middleware.cors import CORSMiddleware

from utils import _unknown, _unknown_upper


# Initialize FastAPI with metadata
app = FastAPI(title=settings.app_name)

origins = [
    "capacitor://localhost",
    "http://localhost",
    "http://127.0.0.1",
    "http://192.168.1.20",  # if you ever load the UI from a dev server
    "http://192.168.1.5",  # if you ever load the UI from a dev server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,         # dev: you can use ["*"] if you prefer
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],           # or ["Authorization", "Content-Type"]
)

geod = Geodesic.WGS84  # uses the WGS84 ellipsoid
configure_cors(app)

# Initialize Vision client
if not os.path.isfile(settings.creds_path):
    raise RuntimeError(f"Credentials file not found at {settings.creds_path}")
creds = service_account.Credentials.from_service_account_file(settings.creds_path)
vision_client = vision.ImageAnnotatorClient(credentials=creds)

# OCR endpoint
default_allowed = {"image/png", "image/jpeg", "application/pdf"}


@app.on_event("startup")
def on_startup() -> None:
    # Create tables if they don't exist (use Alembic for real migrations)
    Base.metadata.create_all(bind=engine)


@app.post("/ocr")
async def ocr_image(file: UploadFile = File(...)):
    if file.content_type not in default_allowed:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")
    content = await file.read()
    image = vision.Image(content=content)
    response = vision_client.text_detection(image=image)
    if response.error.message:
        raise HTTPException(500, response.error.message)
    texts = response.text_annotations
    full_text = texts[0].description if texts else ""
    return {"text": full_text}


@app.post("/boundaries", response_model=List[List[float]])
def boundaries(payload: Payload):
    output: List[List[float]] = []
    curr_lat = payload.tie_lat
    curr_lon = payload.tie_lon

    for b in payload.boundaries:
        angle = b.deg + b.min / 60.0

        if b.ns == "N" and b.ew == "E":
            theta = angle
        elif b.ns == "N" and b.ew == "W":
            theta = 360 - angle
        elif b.ns == "S" and b.ew == "E":
            theta = 180 - angle
        else:
            theta = 180 + angle

        result = geod.Direct(
            curr_lat,
            curr_lon,
            theta,
            b.distance
        )

        output.append([result["lon2"], result["lat2"]])
        curr_lat = result['lat2']
        curr_lon = result['lon2']

    return output


#  ========== PARSE TECHNICAL DESCRIPTION =============

class DescriptionRequest(BaseModel):
    description: str


class BoundaryPoint(BaseModel):
    ns: str                # 'N' or 'S'
    degrees: int
    minutes: int
    seconds: Optional[float] = None
    ew: Optional[str] = None  # 'E' or 'W'
    distance_m: float


class ParseResponse(BaseModel):
    tie_point: str
    boundaries: List[BoundaryPoint]


# ——— Regex to handle both "°" and "deg.", minutes with or without apostrophe, optional seconds, optional EW ———
_BEARING_RX = re.compile(
    r'(?P<ns>[NS])\.?\s*'                   # N or S
    r'(?P<deg>\d+)(?:°|\s*deg\.?|-)\s*'       # degrees
    r'(?P<min>\d+)\'?\s*'                   # minutes (apostrophe optional)
    r'(?:\s*(?P<sec>\d+(?:\.\d+)?))?\"?\s*'  # optional seconds + quote
    r'(?P<ew>[EW])?\.?',                    # optional E or W
    flags=re.IGNORECASE
)


def _parse_segment(seg: str):
    seg_clean = seg.strip().rstrip(',:;.')

    # 1) bearing
    m_b = _BEARING_RX.search(seg_clean)
    # print(m_b)
    if not m_b:
        return None, None
    b = m_b.groupdict()
    # print(f'raw: {b}')
    ns  = b["ns"].upper()
    # print(f'ns: {ns}')
    deg = int(b["deg"])
    # print(f'deg: {deg}')
    mn  = int(b["min"])
    # print(f'mn: {mn}')
    sc  = float(b["sec"]) if b.get("sec") else None
    # print(f'sc: {sc}')
    ew  = b["ew"].upper() if b.get("ew") else None
    # print(f'ew: {ew}')

    # 2) distance after bearing
    post = seg_clean[m_b.end():]
    m_dist = re.search(r'(?P<dist>[\d\.]+)\s*m', post, flags=re.IGNORECASE)
    if not m_dist:
        raise ValueError(f"Could not parse distance in segment: {seg_clean!r}")
    dist = float(m_dist.group("dist"))
    # print(f'dist: {dist}')

    # print(f'parsed: {"ns": ns, "degrees": deg, "minutes": mn, "seconds": sc, "ew": ew}, f'{dist}')
    return {"ns": ns, "degrees": deg, "minutes": mn, "seconds": sc, "ew": ew}, dist


def parse_land_title(desc: str):
    # List of anchor phrases (just add more as needed)
    anchor_phrases = [
        r'beginning\s+at\s+a',
        r'beg.\s+at\s+a',
    ]

    # normalize & strip trailing punctuation
    desc = desc.strip().rstrip(':.')

    # Join them into a single regex with OR (|)
    pattern = r'(?:' + '|'.join(anchor_phrases) + r')'

    # anchor at the tie-line start
    m_anchor = re.search(pattern, desc, flags=re.IGNORECASE)
    if not m_anchor:
        raise ValueError("Could not find the 'Beginning at a pt. marked...' anchor")
    desc = desc[m_anchor.start():]

    # split on either ';' or the word 'thence'
    raw_parts = re.split(r'(?:;\s*|\bthence\b)', desc, flags=re.IGNORECASE)
    parts = [p for p in raw_parts if p.strip()]
    first_seg, *corner_segs = parts

    # isolate tie-line vs. tie-point
    split_td = re.split(r'\s+from\s+', first_seg, flags=re.IGNORECASE)
    if len(split_td) != 2:
        raise ValueError(f"Could not find tie-point in: {first_seg!r}")
    seg_td, tie_point = split_td

    # parse the tie-line
    tie_b, tie_d = _parse_segment(seg_td)

    # build boundaries, start with pt 1 = tie-line end
    boundaries = [
        BoundaryPoint(
            ns=tie_b["ns"],
            degrees=tie_b["degrees"],
            minutes=tie_b["minutes"],
            seconds=tie_b["seconds"],
            ew=tie_b["ew"],
            distance_m=tie_d
        )
    ]

    # parse each corner segment
    for seg in corner_segs:
        print(f'======== SEGMENT ==========: {seg}')
        bdict, dist = _parse_segment(seg)
        if bdict and dist:
            boundaries.append(
                BoundaryPoint(
                    ns=bdict["ns"],
                    degrees=bdict["degrees"],
                    minutes=bdict["minutes"],
                    seconds=bdict["seconds"],
                    ew=bdict["ew"],
                    distance_m=dist
                )
            )

    return tie_point.strip().rstrip(';'), boundaries


@app.post("/parse", response_model=ParseResponse)
async def parse_description(req: DescriptionRequest):
    tie_point, boundaries = parse_land_title(req.description)
    # try:
    #     tie_point, boundaries = parse_land_title(req.description)
    # except ValueError as e:
    #     raise HTTPException(status_code=400, detail=str(e))
    return ParseResponse(tie_point=tie_point, boundaries=boundaries)


def _norm_str(s: Optional[str]) -> Optional[str]:
    if isinstance(s, str):
        s = s.strip()
        return s or None
    return None


def _norm_upper(s: Optional[str]) -> Optional[str]:
    s = _norm_str(s)
    return s.upper() if s is not None else None


# docker compose exec db psql -U landtracker -d landtracker_db -c "DROP TABLE IF EXISTS tie_points CASCADE;"
# curl -X POST http://127.0.0.1:8000/tie-points/import -F "file=@resources/tiepoints.json;type=application/json"
@app.post("/tie-points/import")
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

        name = _norm_str(row.tie_point_name)
        desc = _norm_str(row.description)
        prov = _norm_upper(row.province)
        muni = _norm_upper(row.municipality)
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


# --- Dependent dropdown data ---

@app.get("/tie-points/provinces", response_model=List[Optional[str]])
def list_provinces(db: Session = Depends(get_db)):
    rows = (
        db.query(TiePoint.province)
        .distinct()
        .order_by(TiePoint.province.asc().nulls_last())
        .all()
    )
    return [r[0] for r in rows]


@app.get("/tie-points/municipalities", response_model=List[Optional[str]])
def list_municipalities(province: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(TiePoint.municipality).distinct().order_by(TiePoint.municipality.asc().nulls_last())
    if province is None:
        q = q.filter(TiePoint.province.is_(None))
    else:
        q = q.filter(TiePoint.province == province.strip().upper())
    return [r[0] for r in q.all()]


@app.get("/tie-points/descriptions", response_model=List[Optional[str]])
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


@app.get("/tie-points/by-description", response_model=TiePointRead)
def get_by_description(
    province: Optional[str] = Query(None),
    municipality: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(TiePoint)

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


# ---- Tie Points CRUD ----

@app.post("/tie-points", response_model=TiePointRead)
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


@app.get("/tie-points", response_model=List[TiePointRead])
def list_tie_points(db: Session = Depends(get_db)):
    return db.query(TiePoint).order_by(TiePoint.tie_point_name.asc()).all()


@app.get("/tie-points/{name}", response_model=TiePointRead)
def get_tie_point(name: str, db: Session = Depends(get_db)):
    tp = db.query(TiePoint).filter(TiePoint.tie_point_name == name).first()
    if not tp:
        raise HTTPException(status_code=404, detail=f"Tie point '{name}' not found.")
    return tp


@app.post("/convert/prs92-zone3", response_model=LonLatResponse)
def convert_prs92_zone3(req: NERequest):
    # PRS92 / Philippines zone 3 -> WGS84
    transformer = Transformer.from_crs("EPSG:3123", "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(req.easting, req.northing)
    return LonLatResponse(lon=lon, lat=lat)



from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    print("VALIDATION ERR:", exc.errors())
    return JSONResponse(status_code=HTTP_422_UNPROCESSABLE_ENTITY,
                        content={"detail": exc.errors()})
