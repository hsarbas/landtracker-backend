# app/main.py
from __future__ import annotations
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from app.core.config import settings, configure_cors
from app.core.exceptions import validation_exception_handler
from app.db.session import init_models
from app.api.v1 import ocr, geometry, parsing, tie_points, convert, users

from app.db.session import SessionLocal
from app.models.user import User, Role
from app.core.security import hash_password
from app.core.config import ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_MOBILE

# Routers
from app.api.v1.auth import router as auth_router
from app.api.v1.admin import router as admin_router
from app.api.v1.convert import router as convert_router
from app.api.v1.geometry import router as geometry_router
from app.api.v1.ocr import router as ocr_router
from app.api.v1.parsing import router as parsing_router
from app.api.v1.tie_points import router as tie_points_router
from app.api.v1.users import router as users_router
from starlette.types import ASGIApp, Receive, Scope, Send


class CapacitorOriginFix:
    def __init__(self, app): self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = scope.get("headers") or []
            fixed = []
            for k, v in headers:
                if k == b'origin' and v == b'capacitor://localhost':
                    fixed.append((b'origin', b'http://localhost'))
                else:
                    fixed.append((k, v))
            scope = {**scope, "headers": fixed}
        await self.app(scope, receive, send)


app = FastAPI(title=settings.app_name)
app.add_middleware(CapacitorOriginFix)
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


# Ensure first admin on startup
@app.on_event("startup")
def ensure_admin():
    init_models()

    with SessionLocal() as db:
        exists = db.query(User).filter(User.role == Role.admin).first()
        if not exists:
            admin = User(
                mobile=ADMIN_MOBILE,  # <<< REQUIRED
                email=ADMIN_EMAIL.lower(),  # optional (can be None)
                hashed_password=hash_password(ADMIN_PASSWORD),
                first_name="Admin",
                last_name="Admin",
                role=Role.admin,
                is_verified=True,  # skip OTP for seeded admin
            )
            db.add(admin)
            db.commit()


# Mount API v1 routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(convert_router)
app.include_router(geometry_router)
app.include_router(ocr_router)
app.include_router(parsing_router)
app.include_router(tie_points_router)
app.include_router(users_router)


@app.middleware("http")
async def _log_login(request, call_next):
    if request.url.path.endswith("/api/v1/auth/login"):
        print("Method:", request.method,
              "| Origin:", request.headers.get("origin"),
              "| UA:", request.headers.get("user-agent"))
    return await call_next(request)
