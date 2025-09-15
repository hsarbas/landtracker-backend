from fastapi import APIRouter, Depends
from typing import List
from app.schemas.geometry import Payload
from app.services.geodesy import next_point
from app.core.deps import get_current_user

router = APIRouter(prefix="/api/v1/geometry", tags=["Geometry"], dependencies=[Depends(get_current_user)])


@router.post("/boundaries", response_model=List[List[float]])
def boundaries(payload: Payload):
    out: List[List[float]] = []
    curr_lat, curr_lon = payload.tie_lat, payload.tie_lon

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

        lat2, lon2 = next_point(curr_lat, curr_lon, theta, b.distance)
        out.append([lon2, lat2])
        curr_lat, curr_lon = lat2, lon2
    return out
