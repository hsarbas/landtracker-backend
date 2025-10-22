import os
from functools import lru_cache
from typing import List

from google.cloud import vision
from google.oauth2 import service_account
from app.core.config import settings


@lru_cache(maxsize=1)
def _cached_client() -> vision.ImageAnnotatorClient:
    if not os.path.isfile(settings.creds_path):
        raise RuntimeError(f"Credentials file not found at {settings.creds_path}")
    creds = service_account.Credentials.from_service_account_file(settings.creds_path)
    return vision.ImageAnnotatorClient(credentials=creds)


def get_vision_client() -> vision.ImageAnnotatorClient:
    # Keep public API but use cached client under the hood
    return _cached_client()


def detect_text(bytes_: bytes) -> str:
    """
    Single image OCR. Uses DOCUMENT_TEXT_DETECTION for better multi-line quality.
    """
    client = get_vision_client()
    image = vision.Image(content=bytes_)

    resp = client.annotate_image({
        "image": image,
        "features": [{"type": vision.Feature.Type.DOCUMENT_TEXT_DETECTION}]
    })

    if resp.error.message:
        raise RuntimeError(resp.error.message)

    # Prefer full_text_annotation if available
    if resp.full_text_annotation and resp.full_text_annotation.text:
        return resp.full_text_annotation.text.strip()

    if resp.text_annotations:
        return (resp.text_annotations[0].description or "").strip()

    return ""


def detect_text_many_image_bytes(payloads: List[bytes]) -> str:
    """
    Batch OCR for multiple images. Returns one concatenated string.
    """
    if not payloads:
        return ""

    client = get_vision_client()

    requests = []
    for content in payloads:
        image = vision.Image(content=content)
        requests.append(
            vision.AnnotateImageRequest(
                image=image,
                features=[vision.Feature(type=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)]
            )
        )

    batch_resp = client.batch_annotate_images(requests=requests)

    parts: List[str] = []
    for res in batch_resp.responses:
        if res.error.message:
            # Skip the failing image; you can choose to raise instead
            continue

        text = ""
        if res.full_text_annotation and res.full_text_annotation.text:
            text = res.full_text_annotation.text.strip()
        elif res.text_annotations:
            text = (res.text_annotations[0].description or "").strip()

        if text:
            parts.append(text)

    return "\n\n".join(parts)
