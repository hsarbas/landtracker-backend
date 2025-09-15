# app/api/v1/staticmap.py
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from urllib.parse import urlsplit, unquote, parse_qsl, urlencode, urlunsplit
from app.core.deps import get_current_user
import httpx

router = APIRouter(prefix="/api/v1/staticmap", tags=["staticmap"], dependencies=[Depends(get_current_user)])
ALLOWED_HOST = "maps.googleapis.com"
ALLOWED_PATH_PREFIX = "/maps/api/staticmap"


def _redact_key(u: str) -> str:
    # avoid logging your API key
    sp = urlsplit(u)
    qs = dict(parse_qsl(sp.query, keep_blank_values=True))
    if "key" in qs:
        qs["key"] = "REDACTED"
    return urlunsplit((sp.scheme, sp.netloc, sp.path, urlencode(qs, doseq=True), sp.fragment))


@router.get("/staticmap-proxy")
async def staticmap_proxy(url: str = Query(..., description="Full Google Static Maps URL")):
    # Decode once (your logs show %2F etc., which is normal for query encoding)
    decoded = unquote(url)

    sp = urlsplit(decoded)
    if sp.scheme != "https" or sp.netloc != ALLOWED_HOST or not sp.path.startswith(ALLOWED_PATH_PREFIX):
        raise HTTPException(status_code=400, detail="Invalid Static Maps URL")

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(decoded)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Upstream request error") from e

    if r.status_code != 200:
        # bubble up upstream status but keep message generic
        raise HTTPException(status_code=r.status_code, detail="Upstream Static Maps error")

    media_type = r.headers.get("content-type", "image/png").split(";")[0]
    headers = {"Cache-Control": "private, max-age=300"}
    # (Optional) debug:
    # print("StaticMap OK:", _redact_key(decoded))
    return StreamingResponse(r.aiter_bytes(), media_type=media_type, headers=headers)
