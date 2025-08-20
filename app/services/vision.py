import os
from google.cloud import vision
from google.oauth2 import service_account
from app.core.config import settings


def get_vision_client() -> vision.ImageAnnotatorClient:
    if not os.path.isfile(settings.creds_path):
        raise RuntimeError(f"Credentials file not found at {settings.creds_path}")
    creds = service_account.Credentials.from_service_account_file(settings.creds_path)
    return vision.ImageAnnotatorClient(credentials=creds)


def detect_text(bytes_: bytes) -> str:
    client = get_vision_client()
    image = vision.Image(content=bytes_)
    resp = client.text_detection(image=image)
    if resp.error.message:
        raise RuntimeError(resp.error.message)
    texts = resp.text_annotations
    return texts[0].description if texts else ""
