from __future__ import annotations
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from app.core.config import settings, configure_cors, ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_MOBILE, CapacitorOriginFix
from app.core.exceptions import validation_exception_handler
from app.db.session import init_models, SessionLocal

from app.models.user import User
from app.models.role import Role
from app.core.security import hash_password

# Routers (import once, include once)
from app.api.v1.auth import router as auth_router
from app.api.v1.admin import router as admin_router
from app.api.v1.convert import router as convert_router
from app.api.v1.geometry import router as geometry_router
from app.api.v1.ocr import router as ocr_router
from app.api.v1.parsing import router as parsing_router
from app.api.v1.tie_points import router as tie_points_router
from app.api.v1.users import router as users_router
# from app.api.v1.staticmap import router as map_router
from app.api.v1.report_pdf import router as report_pdf_router

app = FastAPI(title=settings.app_name)
configure_cors(app)
app.add_middleware(CapacitorOriginFix)

# Global exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)


def _get_or_create_role(db: Session, name: str, desc: str | None = None) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if not role:
        role = Role(name=name, description=desc)
        db.add(role)
        db.flush()  # get role.id
    return role


@app.on_event("startup")
def on_startup():
    """
    - Create tables
    - Seed roles (client/partner/admin)
    - Ensure a first admin user using ADMIN_* settings (idempotent)
    """
    init_models()

    with SessionLocal() as db:
        # Seed roles
        client_role = _get_or_create_role(db, "client", "Default role for new users")
        partner_role = _get_or_create_role(db, "partner", "Partner role")
        admin_role = _get_or_create_role(db, "admin", "Administrator role")

        # Ensure first admin (idempotent)
        admin_mobile = (ADMIN_MOBILE or "").strip()
        admin_email = (ADMIN_EMAIL or "").strip().lower() or None

        # Try to find an existing admin by mobile/email or by role_id
        admin_user = None
        if admin_mobile:
            admin_user = db.query(User).filter(User.mobile == admin_mobile).first()
        if not admin_user and admin_email:
            admin_user = db.query(User).filter(User.email == admin_email).first()
        if not admin_user:
            admin_user = db.query(User).filter(User.role_id == admin_role.id).first()

        if not admin_user:
            if not admin_mobile:
                # Minimal guard rail—don’t create a broken admin
                raise RuntimeError("ADMIN_MOBILE is required to seed the first admin user.")
            admin_user = User(
                mobile=admin_mobile,
                email=admin_email,
                hashed_password=hash_password(ADMIN_PASSWORD),
                first_name="Admin",
                last_name="Admin",
                role_id=admin_role.id,  # FK (no enum)
                is_verified=True,       # seed skips OTP
                is_active=True,
            )
            db.add(admin_user)

        db.commit()


# Mount API v1 routers (once)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(convert_router)
app.include_router(geometry_router)
app.include_router(ocr_router)
app.include_router(parsing_router)
app.include_router(tie_points_router)
app.include_router(users_router)
# app.include_router(map_router)
app.include_router(report_pdf_router)


# --- Optional request logging helpers you had before ---
@app.middleware("http")
async def _log_login(request, call_next):
    if request.url.path.endswith("/api/v1/auth/login"):
        print("Method:", request.method,
              "| Origin:", request.headers.get("origin"),
              "| UA:", request.headers.get("user-agent"))
    return await call_next(request)


@app.middleware("http")
async def _cors_probe(request, call_next):
    if request.headers.get("origin"):
        print(">> ORIGIN:", request.headers.get("origin"),
              "| METHOD:", request.method,
              "| PATH:", request.url.path,
              "| REQ-HDRS:", {k: v for k, v in request.headers.items()
                              if k.lower().startswith(("access-control","sec-")) or k.lower() in ("origin","referer")})
    resp = await call_next(request)
    cors_hdrs = {k: v for k, v in resp.headers.items() if k.lower().startswith("access-control")}
    if cors_hdrs:
        print("<< CORS RESP:", cors_hdrs)
    return resp
