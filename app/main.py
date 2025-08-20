# app/main.py
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from app.core.config import settings, configure_cors
from app.core.exceptions import validation_exception_handler
from app.db.session import init_models
from app.api.v1 import ocr, geometry, parsing, tie_points, convert


app = FastAPI(title=settings.app_name)
configure_cors(app)

# Routers
app.include_router(ocr.router)
app.include_router(geometry.router)
app.include_router(parsing.router)
app.include_router(tie_points.router)
app.include_router(convert.router)


app.add_exception_handler(RequestValidationError, validation_exception_handler)


@app.on_event("startup")
def _startup():
    init_models()
