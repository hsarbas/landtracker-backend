from fastapi import APIRouter, HTTPException, Depends
from app.schemas.parsing import DescriptionRequest, ParseResponse, BoundaryPoint
from app.services.parsing import parse_land_title
from app.core.deps import get_current_user

router = APIRouter(prefix="/api/v1/parsing", tags=["Parsing"], dependencies=[Depends(get_current_user)])


@router.post("/description", response_model=ParseResponse)
async def parse_description(req: DescriptionRequest):
    """
    Parse a technical description text and return:
      - title_number (if found)
      - owner (if found)
      - technical_description (echo back the input)
      - tie_point
      - boundaries[]
    """
    try:
        title_number, owner, technical_description, tie_point, boundaries = parse_land_title(req.description)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ParseResponse(
        title_number=title_number,
        owner=owner,
        technical_description=technical_description,
        tie_point=tie_point,
        boundaries=[
            BoundaryPoint(
                ns=b["ns"],
                degrees=b["degrees"],
                minutes=b["minutes"],
                seconds=b.get("seconds"),
                ew=b.get("ew"),
                distance_m=dist,
            )
            for b, dist in boundaries
        ],
    )
