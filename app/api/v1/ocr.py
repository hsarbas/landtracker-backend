# app/api/v1/ocr.py
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.core.deps import get_current_user
from app.services.vision import detect_text_many_image_bytes

router = APIRouter(prefix="/api/v1/ocr", tags=["OCR"], dependencies=[Depends(get_current_user)])
ALLOWED = {"image/png", "image/jpeg"}  # keep this images-only for now


@router.post("", summary="OCR multiple images → single string")
async def ocr_images(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "No files uploaded")

    # Validate types
    for f in files:
        if f.content_type not in ALLOWED:
            raise HTTPException(400, f"Unsupported file type: {f.content_type}")

    try:
        payloads = [await f.read() for f in files]
        text = detect_text_many_image_bytes(payloads)
        return {"text": text}
    except Exception as e:
        raise HTTPException(500, f"OCR failed: {e}")
