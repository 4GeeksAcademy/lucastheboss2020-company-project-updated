import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from .auth import create_access_token, get_current_user
from .candidates import router as candidates_router
from .config import get_settings
from .error_handlers import install_api_error_handlers
from .mailer import send_password_reset_email
from .models import (
    ChangePasswordRequest,
    CurrentUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ProfilePublic,
    ProfileUpdate,
    RegistrationResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserCreate,
    UserPublic,
    UserUpdate,
)
from .password_resets import (
    InvalidPasswordResetToken,
    create_reset_token,
    invalidate_user_reset_tokens,
    redeem_reset_token,
)
from .services import (
    create_user,
    get_profile,
    get_user_by_email,
    public_user,
    update_profile,
    update_user,
)
from .telemetry.auth_events import (
    emit_login_failed,
    emit_login_succeeded,
    emit_password_changed,
    emit_password_reset_completed,
    emit_password_reset_requested,
    emit_registration_created,
    emit_registration_failed,
    emit_session_expired,
)
from .telemetry import install_telemetry
from passlib.hash import bcrypt
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

app = FastAPI(title="TrackFlow API")
install_api_error_handlers(app)

# Telemetry: request correlation + api_latency_recorded / api_error events.
# Replaces the original timing_middleware, preserving its exact log line, and is a
# no-op when TELEMETRY_ENABLED=0 (only correlation + logging remain).
install_telemetry(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(candidates_router)


@app.get("/health", response_model=dict[str, str])
def health():
    return {"status": "ok"}


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    user = get_user_by_email(str(payload.email))
    if not user or not bcrypt.verify(payload.password, user["hashed_password"]):
        # Sanitised failure event: never captures email/password (PII).
        emit_login_failed(reason="invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.get("is_active", False):
        emit_login_failed(reason="account_disabled")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    emit_login_succeeded(user_id=user["id"], role=user.get("role"))
    return TokenResponse(access_token=create_access_token(user["id"]))


@app.get("/auth/me", response_model=CurrentUserResponse)
def me(user: dict = Depends(get_current_user)):
    profile = get_profile(user["id"])
    return {**public_user(user), "profile": profile}


@app.post("/users", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate):
    try:
        user = create_user(payload)
    except ValueError as error:
        # Duplicate email conflict (sanitised; no email in the event).
        emit_registration_failed(reason="email_conflict")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    emit_registration_created(user_id=user["id"], role=user.get("role"))
    return public_user(user)


@app.put("/profiles/me", response_model=ProfilePublic)
def update_my_profile(payload: ProfileUpdate, user: dict = Depends(get_current_user)):
    return update_profile(user["id"], payload)


@app.post("/auth/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest):
    user = get_user_by_email(str(payload.email))
    # PII-safe: we never put the email in the event, and we always respond the
    # same way whether or not the address exists (no account enumeration).
    token_issued = False
    if user and user.get("is_active", False):
        try:
            token, _ = create_reset_token(user["id"])
            settings = get_settings()
            reset_url = (
                f"{settings['frontend_base_url']}/reset-password?"
                f"{urlencode({'token': token})}"
            )
            send_password_reset_email(str(payload.email), reset_url)
            token_issued = True
        except Exception:
            logger.error("Password reset request could not be completed.")
    emit_password_reset_requested(token_issued=token_issued)

    return {
        "message": "If that address is registered, you'll receive a reset link shortly."
    }


@app.post("/auth/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest):
    try:
        # NB: redeem_reset_token returns None; the reset event carries no
        # user_id by design (the token holder is anonymous to telemetry, and we
        # never log/emit the reset token itself).
        redeem_reset_token(payload.token, payload.new_password)
    except InvalidPasswordResetToken:
        emit_password_reset_completed(success=False, method="reset")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token is invalid, expired, or has already been used",
        )
    emit_password_reset_completed(success=True, method="reset")
    return {"message": "Password reset successfully"}


@app.post("/auth/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
):
    if not bcrypt.verify(payload.current_password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    updated = update_user(
        user["id"],
        UserUpdate(password=payload.new_password),
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid")
    invalidate_user_reset_tokens(user["id"])
    emit_password_changed(user_id=user["id"], source="profile")
    return {"message": "Password changed successfully"}
