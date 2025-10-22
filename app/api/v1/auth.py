from __future__ import annotations
from datetime import datetime, timezone, timedelta
import uuid, secrets
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi.responses import RedirectResponse

from app.schemas.user import (
    UserCreate, UserLogin, UserRead, TokenPair, LogoutResponse,
    EmailVerifyRequest, EmailVerifyConfirm, normalize_ph_mobile
)
from app.schemas.otp import OtpRequest, OtpConfirm, OtpStatus
from app.models.user import User
from app.models.role import Role
from app.models.refresh_token import RefreshToken
from app.models.email_verify_token import EmailVerifyToken
from app.models.otp_code import OtpCode, OtpPurpose
from app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token, TokenPayload
)
from app.core.deps import get_current_user
from app.core.config import (
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH, REFRESH_COOKIE_SAMESITE,
    REFRESH_COOKIE_SECURE, REFRESH_COOKIE_HTTPONLY,
    OTP_LENGTH, OTP_TTL_MINUTES, OTP_MAX_ATTEMPTS, OTP_RESEND_COOLDOWN_SECONDS, APP_FRONTEND_URL, APP_BACKEND_URL
)
from app.services.sms import send_sms
from app.services.email import send_email
from app.services.email_templates import build_verification_email

from app.db.session import get_db

from app.schemas.otp import MobileChangeRequest, MobileChangeConfirm


router = APIRouter(prefix="/v1/auth", tags=["auth"])

EMAIL_TOKEN_TTL_MINUTES = 60 * 24


def _gen_email_token() -> str:
    # short opaque token (url-safe)
    return secrets.token_urlsafe(32)


def _create_email_verify_token(db: Session, user: User) -> EmailVerifyToken:
    # Invalidate previous, unused tokens
    db.query(EmailVerifyToken).filter(
        EmailVerifyToken.user_id == user.id,
        EmailVerifyToken.is_used == False
    ).update({EmailVerifyToken.is_used: True})

    token = _gen_email_token()
    row = EmailVerifyToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=EMAIL_TOKEN_TTL_MINUTES),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _send_verification_email(user, token: str):
    verify_link = f"{APP_BACKEND_URL}/v1/auth/verify/email?token={token}"
    html = build_verification_email(user.email, verify_link)
    send_email(
        to=user.email,
        subject="Verify your Land Tracker account",
        html=html
    )


# ----------------- Cookie helpers -----------------
def _set_refresh_cookie(resp: Response, refresh_token: str, expires: datetime):
    resp.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=REFRESH_COOKIE_HTTPONLY,
        secure=REFRESH_COOKIE_SECURE,
        samesite=REFRESH_COOKIE_SAMESITE,
        path=REFRESH_COOKIE_PATH,
        expires=expires,
        max_age=int((expires - datetime.now(timezone.utc)).total_seconds()),
    )


def _clear_refresh_cookie(resp: Response):
    resp.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


def _read_refresh_cookie(req: Request) -> str | None:
    return req.cookies.get(REFRESH_COOKIE_NAME)


# ----------------- OTP helpers -----------------
_otp_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _gen_otp_code(length: int = OTP_LENGTH) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def _hash_otp(code: str) -> str:
    return _otp_ctx.hash(code)


def _verify_otp(code: str, code_hash: str) -> bool:
    return _otp_ctx.verify(code, code_hash)


def _create_or_replace_otp(db: Session, user: User) -> OtpCode:
    db.query(OtpCode).filter(
        OtpCode.user_id == user.id,
        OtpCode.purpose == OtpPurpose.REGISTER,
        OtpCode.is_used == False
    ).update({OtpCode.is_used: True})
    code = _gen_otp_code()
    row = OtpCode(
        user_id=user.id,
        code_hash=_hash_otp(code),
        purpose=OtpPurpose.REGISTER,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES),
        max_attempts=OTP_MAX_ATTEMPTS,
        last_sent_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    send_sms(user.mobile, f"Your OTP code is {code}. It expires in {OTP_TTL_MINUTES} minutes.")
    return row


def _create_change_mobile_otp(db: Session, user: User, new_mobile_norm: str) -> OtpCode:
    # Invalidate older active change_mobile codes
    db.query(OtpCode).filter(
        OtpCode.user_id == user.id,
        OtpCode.purpose == OtpPurpose.CHANGE_MOBILE,
        OtpCode.is_used is False,
    ).update({OtpCode.is_used: True})

    code = _gen_otp_code()
    row = OtpCode(
        user_id=user.id,
        code_hash=_hash_otp(code),
        purpose=OtpPurpose.CHANGE_MOBILE,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES),
        max_attempts=OTP_MAX_ATTEMPTS,
        last_sent_at=datetime.now(timezone.utc),
        context_mobile=new_mobile_norm,  # bind new target mobile
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # Send OTP to the NEW number
    send_sms(new_mobile_norm, f"Your LandTracker code is {code}. Valid for {OTP_TTL_MINUTES} minutes.")
    return row


# --- NEW: helper used by login when the account is unverified ---
def _issue_otp_respecting_cooldown(db: Session, user: User) -> None:
    """Send a fresh OTP unless the last one was just sent within the cooldown window."""
    last = (
        db.query(OtpCode)
        .filter(OtpCode.user_id == user.id, OtpCode.purpose == OtpPurpose.REGISTER)
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    now = datetime.now(timezone.utc)
    if last and last.last_sent_at and (now - last.last_sent_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
        # Re-send the same (still-valid) code without rotating it
        # (Optional) You could also choose to silently do nothing.
        send_sms(user.mobile, f"Your verification code is valid. It expires at {last.expires_at.isoformat()}.")
        return

    # Otherwise, rotate (invalidate old) and send a brand-new code
    _create_or_replace_otp(db, user)


# ----------------- Role helpers (NEW) -----------------
def _get_role_or_bootstrap(db: Session, name: str) -> Role:
    """Fetch a role by name; if missing, create it (keeps environments resilient)."""
    role = db.query(Role).filter(Role.name == name).first()
    if not role:
        role = Role(name=name, description=f"{name} role")
        db.add(role)
        db.flush()  # get role.id without full commit
    return role


def _user_role_name(user: User) -> str:
    """Always return a string role name for JWTs."""
    # relationship may be lazy; make sure role is present
    return user.role.name if getattr(user, "role", None) else "client"


# ----------------- Endpoints -----------------
@router.post("/register", response_model=UserRead, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    # Enforce unique email manually for clearer error (DB also enforces)
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    mobile_norm = normalize_ph_mobile(payload.mobile) if payload.mobile else None
    if mobile_norm and db.query(User).filter(User.mobile == mobile_norm).first():
        raise HTTPException(status_code=400, detail="Mobile already registered")

    role = _get_role_or_bootstrap(db, "client")
    user = User(
        email=payload.email,
        mobile=mobile_norm,
        hashed_password=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role_id=role.id,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    tok = _create_email_verify_token(db, user)
    _send_verification_email(user, tok.token)
    return user


# ---------- RESEND verification email ----------
@router.post("/verify/email/request", response_model=OtpStatus)  # reuse your OtpStatus(ok,message)
def email_verify_request(body: EmailVerifyRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        return OtpStatus(ok=True, message="Already verified")

    tok = _create_email_verify_token(db, user)
    _send_verification_email(user, tok.token)
    return OtpStatus(ok=True, message="Verification email sent")


# ---------- One-click VERIFY endpoint (clicked from email) ----------
@router.get("/verify/email")
def email_verify_confirm(token: str, db: Session = Depends(get_db)):
    row = db.query(EmailVerifyToken).filter(EmailVerifyToken.token == token).first()
    if not row or row.is_used:
        raise HTTPException(status_code=400, detail="Invalid or used token")

    now = datetime.now(timezone.utc)
    if now > row.expires_at:
        row.is_used = True
        db.commit()
        raise HTTPException(status_code=400, detail="Token expired")

    user = row.user
    user.is_verified = True
    user.verified_at = now
    row.is_used = True
    row.used_at = now
    db.commit()

    web_fallback = f"{APP_FRONTEND_URL}/auth/verify-success?email={user.email}"

    return RedirectResponse(url=web_fallback, status_code=302)



@router.post("/verify/request", response_model=OtpStatus)
def request_verification(body: OtpRequest, db: Session = Depends(get_db)):
    mobile = normalize_ph_mobile(body.mobile)
    user = db.query(User).filter(User.mobile == mobile).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        return OtpStatus(ok=True, message="Already verified")

    # resend cooldown
    row = db.query(OtpCode).filter(
        OtpCode.user_id == user.id,
        OtpCode.purpose == OtpPurpose.REGISTER
    ).order_by(OtpCode.created_at.desc()).first()
    now = datetime.now(timezone.utc)
    if row and row.last_sent_at and (now - row.last_sent_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
        raise HTTPException(status_code=429, detail="Please wait before requesting another code")

    _create_or_replace_otp(db, user)
    return OtpStatus(ok=True, message="OTP sent")


@router.post("/verify/confirm", response_model=OtpStatus)
def confirm_verification(body: OtpConfirm, db: Session = Depends(get_db)):
    mobile = normalize_ph_mobile(body.mobile)
    user = db.query(User).filter(User.mobile == mobile).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        return OtpStatus(ok=True, message="Already verified")

    row = db.query(OtpCode).filter(
        OtpCode.user_id == user.id,
        OtpCode.purpose == OtpPurpose.REGISTER,
        OtpCode.is_used == False
    ).order_by(OtpCode.created_at.desc()).first()
    if not row:
        raise HTTPException(status_code=400, detail="No active OTP")

    now = datetime.now(timezone.utc)
    if now > row.expires_at:
        row.is_used = True
        db.commit()
        raise HTTPException(status_code=400, detail="OTP expired")

    if row.attempts_used >= row.max_attempts:
        row.is_used = True
        db.commit()
        raise HTTPException(status_code=400, detail="Too many attempts")

    ok = _verify_otp(body.code, row.code_hash)
    row.attempts_used += 1
    if ok:
        row.is_used = True
        user.is_verified = True
        user.verified_at = now
        db.commit()
        return OtpStatus(ok=True, message="Verified")
    else:
        db.commit()
        raise HTTPException(status_code=400, detail="Incorrect code")


@router.post("/verify/change-mobile/request", response_model=OtpStatus)
def request_change_mobile(
    body: MobileChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    new_mobile_norm = normalize_ph_mobile(body.new_mobile)

    # No-op if same as current (optional: still force verify)
    if current_user.mobile == new_mobile_norm:
        return OtpStatus(ok=True, message="Mobile is unchanged")

    # Enforce uniqueness
    exists = db.query(User).filter(User.mobile == new_mobile_norm).first()
    if exists:
        raise HTTPException(status_code=400, detail="Mobile already in use")

    # Cooldown on last change_mobile OTP
    last = db.query(OtpCode).filter(
        OtpCode.user_id == current_user.id,
        OtpCode.purpose == OtpPurpose.CHANGE_MOBILE
    ).order_by(OtpCode.created_at.desc()).first()

    now = datetime.now(timezone.utc)
    if last and last.last_sent_at and (now - last.last_sent_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
        raise HTTPException(status_code=429, detail="Please wait before requesting another code")

    _create_change_mobile_otp(db, current_user, new_mobile_norm)
    return OtpStatus(ok=True, message="OTP sent to new mobile")


@router.post("/verify/change-mobile/confirm", response_model=OtpStatus)
def confirm_change_mobile(
    body: MobileChangeConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    new_mobile_norm = normalize_ph_mobile(body.new_mobile)

    # Load latest active change_mobile OTP
    row = db.query(OtpCode).filter(
        OtpCode.user_id == current_user.id,
        OtpCode.purpose == OtpPurpose.CHANGE_MOBILE,
        OtpCode.is_used == False
    ).order_by(OtpCode.created_at.desc()).first()

    if not row:
        raise HTTPException(status_code=400, detail="No active OTP. Request a new code.")

    # Ensure code was issued for this specific target mobile
    if row.context_mobile != new_mobile_norm:
        raise HTTPException(status_code=400, detail="Mobile does not match OTP request")

    now = datetime.now(timezone.utc)
    if now > row.expires_at:
        row.is_used = True
        db.commit()
        raise HTTPException(status_code=400, detail="OTP expired")

    if row.attempts_used >= row.max_attempts:
        row.is_used = True
        db.commit()
        raise HTTPException(status_code=400, detail="Too many attempts")

    ok = _verify_otp(body.code, row.code_hash)
    row.attempts_used += 1

    if not ok:
        db.commit()
        raise HTTPException(status_code=400, detail="Incorrect code")

    # Final uniqueness check in case race conditions
    exists = db.query(User).filter(User.mobile == new_mobile_norm, User.id != current_user.id).first()
    if exists:
        row.is_used = True
        db.commit()
        raise HTTPException(status_code=400, detail="Mobile already in use")

    # Commit the change
    current_user.mobile = new_mobile_norm
    current_user.is_verified = True
    current_user.verified_at = now
    row.is_used = True

    db.add(current_user)
    db.add(row)
    db.commit()
    db.refresh(current_user)

    return OtpStatus(ok=True, message="Mobile updated and verified")


@router.post("/login", response_model=TokenPair)
def login(payload: UserLogin, response: Response, request: Request, db: Session = Depends(get_db)):
    print(payload)
    email = payload.email
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    if not user.is_verified:
        # issue (or rotate) email token and tell client to check email
        tok = _create_email_verify_token(db, user)
        _send_verification_email(user, tok.token)
        raise HTTPException(
            status_code=403,
            detail={
                "code": "EMAIL_VERIFICATION_REQUIRED",
                "message": "Email not verified. We sent you a verification link.",
                "next": {"endpoint": "/v1/auth/verify/email?token=<token-from-email>", "method": "GET"},
            },
        )

    # ★ Use string role name from related Role
    role_name = _user_role_name(user)

    access = create_access_token(user.id, role_name)
    jti = uuid.uuid4().hex
    refresh = create_refresh_token(user.id, role_name, jti=jti)

    rt = RefreshToken(
        jti=jti,
        user_id=user.id,
        is_revoked=False,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        user_agent=request.headers.get("user-agent"),
        ip_addr=request.client.host if request.client else None,
    )
    db.add(rt)
    db.commit()

    _set_refresh_cookie(response, refresh, rt.expires_at)

    return TokenPair(
        access_token=access,
        refresh_token="",  # keep refresh only in HttpOnly cookie
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenPair)
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    cookie = _read_refresh_cookie(request)
    if not cookie:
        raise HTTPException(status_code=401, detail="Missing refresh cookie")

    try:
        payload = jwt.decode(cookie, SECRET_KEY, algorithms=[ALGORITHM])
        data = TokenPayload(**payload)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if data.type != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token required")

    token_row: RefreshToken | None = db.query(RefreshToken).filter(RefreshToken.jti == data.jti).first()
    if not token_row or token_row.is_revoked:
        if token_row:
            token_row.reused_at = datetime.now(timezone.utc)
            db.commit()
        raise HTTPException(status_code=401, detail="Refresh token revoked or unknown")

    token_row.is_revoked = True
    token_row.rotated_at = datetime.now(timezone.utc)

    user = db.get(User, int(data.sub))
    if not user or not user.is_active:
        db.rollback()
        raise HTTPException(status_code=401, detail="Inactive or missing user")

    # ★ Use role name string again
    role_name = _user_role_name(user)

    new_jti = uuid.uuid4().hex
    new_refresh = create_refresh_token(user.id, role_name, jti=new_jti)
    new_row = RefreshToken(
        jti=new_jti,
        user_id=user.id,
        is_revoked=False,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        user_agent=request.headers.get("user-agent"),
        ip_addr=request.client.host if request.client else None,
    )
    db.add(new_row)
    db.commit()

    _set_refresh_cookie(response, new_refresh, new_row.expires_at)

    access = create_access_token(user.id, role_name)
    return TokenPair(access_token=access, refresh_token="", expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Idempotent logout:
    - If refresh cookie is present and valid, revoke that refresh token (jti) in DB.
    - Always clear the refresh cookie with the same `path`/flags you set on login/refresh.
    """
    cookie = _read_refresh_cookie(request)
    if cookie:
        try:
            payload = jwt.decode(cookie, SECRET_KEY, algorithms=[ALGORITHM])
            data = TokenPayload(**payload)

            # revoke just this token (common case)
            row = db.query(RefreshToken).filter(RefreshToken.jti == data.jti).first()
            if row and not row.is_revoked:
                row.is_revoked = True
                db.commit()

            # OPTIONAL hardening: revoke all tokens for this user on logout
            db.query(RefreshToken).filter(
                RefreshToken.user_id == int(data.sub),
                RefreshToken.is_revoked == False
            ).update({RefreshToken.is_revoked: True})
            db.commit()

        except JWTError:
            # invalid/expired cookie is fine—we still clear it below
            pass

    # Clear cookie using the SAME attributes you used to set it
    _clear_refresh_cookie(response)

    from app.schemas.user import LogoutResponse as LR
    return LR()
