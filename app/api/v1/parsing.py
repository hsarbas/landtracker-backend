from fastapi import APIRouter, HTTPException
from app.schemas.parsing import DescriptionRequest, ParseResponse, BoundaryPoint
from app.services.parsing import parse_land_title

router = APIRouter(prefix="/parse", tags=["Parsing"])


@router.post("", response_model=ParseResponse)
async def parse_description(req: DescriptionRequest):
    try:
        tie_point, boundaries = parse_land_title(req.description)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ParseResponse(
        tie_point=tie_point,
        boundaries=[
            BoundaryPoint(
                ns=b["ns"], degrees=b["degrees"], minutes=b["minutes"],
                seconds=b["seconds"], ew=b["ew"], distance_m=dist
            ) for b, dist in boundaries
        ]
    )
