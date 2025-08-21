from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.services.vision import detect_text
from app.core.deps import get_current_user

router = APIRouter(prefix="/api/v1/ocr", tags=["OCR"], dependencies=[Depends(get_current_user)])
ALLOWED = {"image/png", "image/jpeg", "application/pdf"}


@router.post("")
async def ocr_image(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")
    try:
        text = detect_text(await file.read())
        return {"text": text}
    except RuntimeError as e:
        raise HTTPException(500, str(e))
