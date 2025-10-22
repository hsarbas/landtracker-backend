# app/admin.py
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
import os

from app.db.session import engine, SessionLocal
from app.models.user import User
from app.models.role import Role
from app.models.email_verify_token import EmailVerifyToken
from app.models.otp_code import OtpCode
from app.models.property import Property
from app.models.property_boundary import PropertyBoundary
from app.models.property_image import PropertyImage
from app.models.property_report import PropertyReport
from app.models.refresh_token import RefreshToken
from app.models.tie_point import TiePoint
from app.core.security import verify_password

ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", "3"))


# --- Auth backend (no template changes needed) ---
class AdminAuth(AuthenticationBackend):
    async def login(self, request):
        form = await request.form()
        email = (form.get("username") or "").strip().lower()
        password = form.get("password") or ""
        db = SessionLocal()
        try:
            user = db.execute(
                select(User).where(
                    User.email == email,
                    User.is_active == True,
                    User.role_id == ADMIN_ROLE_ID,
                )
            ).scalar_one_or_none()

            if user and verify_password(password, user.hashed_password):
                request.session["authenticated"] = True
                request.session["admin_user_id"] = user.id
                return True
            return False
        finally:
            db.close()

    async def authenticate(self, request):
        return bool(request.session.get("authenticated"))

    async def logout(self, request):
        request.session.clear()
        return True


def mount_admin(app):
    # Use default SQLAdmin templates by NOT passing templates_dir
    auth_backend = AdminAuth(secret_key=os.getenv("ADMIN_SECRET", "super-secret-key"))

    admin = Admin(
        app=app,
        engine=engine,
        authentication_backend=auth_backend,
    )

    # --- Users ---
    class UserAdmin(ModelView, model=User):
        name = "User"
        name_plural = "Users"
        icon = "fa-solid fa-user"
        column_list = [
            User.id, User.email, User.first_name, User.last_name,
            User.role_id, User.is_active, User.is_verified, User.created_at
        ]
        form_excluded_columns = ["hashed_password"]

    # --- Roles ---
    class RoleAdmin(ModelView, model=Role):
        name = "Role"
        name_plural = "Roles"
        icon = "fa-solid fa-users"
        column_list = [Role.id, Role.name, Role.description]

    # --- EmailVerifyToken (read-only) ---
    class EmailVerifyTokenAdmin(ModelView, model=EmailVerifyToken):
        name = "Email Verify Token"
        name_plural = "Email Verify Tokens"
        icon = "fa-solid fa-envelope-circle-check"
        category = "Auth"
        column_list = [
            EmailVerifyToken.id,
            EmailVerifyToken.user_id,
            EmailVerifyToken.token,
            EmailVerifyToken.is_used,
            EmailVerifyToken.created_at,
            EmailVerifyToken.expires_at,
            EmailVerifyToken.used_at,
        ]
        column_searchable_list = [EmailVerifyToken.token]
        column_sortable_list = [
            EmailVerifyToken.id,
            EmailVerifyToken.created_at,
            EmailVerifyToken.expires_at,
            EmailVerifyToken.is_used,
        ]
        column_formatters = {
            EmailVerifyToken.user_id: lambda m, a: f"{m.user_id} ({getattr(m.user, 'email', '')})"
        }
        can_create = False
        can_edit = False
        can_delete = False

    # --- TiePoint ---
    class TiePointAdmin(ModelView, model=TiePoint):
        name = "Tie Point"
        name_plural = "Tie Points"
        icon = "fa-solid fa-location-dot"
        category = "Land"
        column_list = [
            TiePoint.id,
            TiePoint.tie_point_name,
            TiePoint.province,
            TiePoint.municipality,
            TiePoint.northing,
            TiePoint.easting,
        ]
        column_searchable_list = [TiePoint.tie_point_name, TiePoint.province, TiePoint.municipality]
        column_sortable_list = [TiePoint.id, TiePoint.tie_point_name, TiePoint.province, TiePoint.municipality]

    # --- Property ---
    class PropertyAdmin(ModelView, model=Property):
        name = "Property"
        name_plural = "Properties"
        icon = "fa-solid fa-house-chimney"
        category = "Land"
        column_list = [
            Property.id,
            Property.title_number,
            Property.owner,
            Property.user_id,
            Property.tie_point_id,
            Property.created_at,
            Property.updated_at,
        ]
        column_searchable_list = [Property.title_number, Property.owner]
        column_sortable_list = [Property.id, Property.created_at, Property.updated_at]
        form_excluded_columns = ["images", "boundaries", "reports", "user"]
        column_details_list = [
            Property.id,
            Property.title_number,
            Property.owner,
            Property.technical_description,
            Property.user_id,
            Property.tie_point_id,
            Property.created_at,
            Property.updated_at,
        ]
        column_formatters = {
            Property.user_id: lambda m, a: f"{m.user_id} ({getattr(m.user, 'email', '')})",
            Property.tie_point_id: lambda m, a: f"{m.tie_point_id} ({getattr(m.tie_point, 'tie_point_name', '')})",
        }

    # --- PropertyBoundary ---
    class PropertyBoundaryAdmin(ModelView, model=PropertyBoundary):
        name = "Property Boundary"
        name_plural = "Property Boundaries"
        icon = "fa-solid fa-draw-polygon"
        category = "Land"
        column_list = [
            PropertyBoundary.id,
            PropertyBoundary.property_id,
            PropertyBoundary.bearing,
            PropertyBoundary.distance_m,
        ]
        column_searchable_list = [PropertyBoundary.bearing]
        column_sortable_list = [PropertyBoundary.id, PropertyBoundary.property_id, PropertyBoundary.distance_m]

    # --- PropertyImage ---
    class PropertyImageAdmin(ModelView, model=PropertyImage):
        name = "Property Image"
        name_plural = "Property Images"
        icon = "fa-regular fa-image"
        category = "Land"
        column_list = [
            PropertyImage.id,
            PropertyImage.property_id,
            PropertyImage.file_path,
            PropertyImage.order_index,
            PropertyImage.created_at,
        ]
        column_searchable_list = [PropertyImage.file_path]
        column_sortable_list = [
            PropertyImage.id,
            PropertyImage.property_id,
            PropertyImage.order_index,
            PropertyImage.created_at,
        ]

    # --- PropertyReport ---
    class PropertyReportAdmin(ModelView, model=PropertyReport):
        name = "Property Report"
        name_plural = "Property Reports"
        icon = "fa-regular fa-file-pdf"
        category = "Land"
        column_list = [
            PropertyReport.id,
            PropertyReport.property_id,
            PropertyReport.report_type,
            PropertyReport.file_path,
            PropertyReport.created_at,
        ]
        column_searchable_list = [PropertyReport.report_type, PropertyReport.file_path]
        column_sortable_list = [PropertyReport.id, PropertyReport.property_id, PropertyReport.created_at]

    # --- RefreshToken (read-only) ---
    class RefreshTokenAdmin(ModelView, model=RefreshToken):
        name = "Refresh Token"
        name_plural = "Refresh Tokens"
        icon = "fa-solid fa-key"
        category = "Auth"
        column_list = [
            RefreshToken.id,
            RefreshToken.jti,
            RefreshToken.user_id,
            RefreshToken.is_revoked,
            RefreshToken.expires_at,
            RefreshToken.created_at,
            RefreshToken.user_agent,
            RefreshToken.ip_addr,
            RefreshToken.rotated_at,
            RefreshToken.reused_at,
        ]
        column_searchable_list = [RefreshToken.jti, RefreshToken.user_agent, RefreshToken.ip_addr]
        column_sortable_list = [
            RefreshToken.id,
            RefreshToken.expires_at,
            RefreshToken.created_at,
            RefreshToken.is_revoked,
        ]
        column_formatters = {
            RefreshToken.user_id: lambda m, a: f"{m.user_id} ({getattr(m.user, 'email', '')})"
        }
        can_create = False
        can_edit = False
        can_delete = False

    # --- OtpCode (read-only) ---
    class OtpCodeAdmin(ModelView, model=OtpCode):
        name = "OTP Code"
        name_plural = "OTP Codes"
        icon = "fa-solid fa-mobile-screen-button"
        category = "Auth"
        column_list = [
            OtpCode.id,
            OtpCode.user_id,
            OtpCode.purpose,
            OtpCode.expires_at,
            OtpCode.attempts_used,
            OtpCode.max_attempts,
            OtpCode.is_used,
            OtpCode.last_sent_at,
            OtpCode.resend_count,
            OtpCode.created_at,
            OtpCode.context_mobile,
        ]
        column_searchable_list = [OtpCode.purpose, OtpCode.context_mobile]
        column_sortable_list = [
            OtpCode.id,
            OtpCode.expires_at,
            OtpCode.created_at,
            OtpCode.is_used,
            OtpCode.resend_count,
        ]
        column_formatters = {
            OtpCode.user_id: lambda m, a: f"{m.user_id} ({getattr(m.user, 'email', '')})"
        }
        form_excluded_columns = ["code_hash"]
        can_create = False
        can_edit = False
        can_delete = False

    # Register all views
    admin.add_view(UserAdmin)
    admin.add_view(RoleAdmin)
    admin.add_view(PropertyAdmin)
    admin.add_view(PropertyBoundaryAdmin)
    admin.add_view(PropertyReportAdmin)
    admin.add_view(PropertyImageAdmin)
    admin.add_view(EmailVerifyTokenAdmin)
    admin.add_view(RefreshTokenAdmin)
    admin.add_view(TiePointAdmin)
    # admin.add_view(OtpCodeAdmin)
