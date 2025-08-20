from fastapi import APIRouter
from pyproj import Transformer
from app.schemas.geometry import NERequest, LonLatResponse

router = APIRouter(prefix="/convert", tags=["Convert"])


@router.post("/prs92-zone3", response_model=LonLatResponse)
def convert_prs92_zone3(req: NERequest):
    # PRS92 / Philippines zone 3 -> WGS84
    transformer = Transformer.from_crs("EPSG:3123", "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(req.easting, req.northing)
    return LonLatResponse(lon=lon, lat=lat)
