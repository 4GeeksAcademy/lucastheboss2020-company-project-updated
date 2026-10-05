import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from .auth import create_access_token, get_current_user
from .candidates import router as candidates_router
from .config import get_settings
from .mailer import EmailDeliveryError, send_password_reset_email
from .models import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ProfileUpdate,
    ResetPasswordRequest,
    TokenResponse,
    UserCreate,
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
from passlib.hash import bcrypt
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

app = FastAPI(title="TrackFlow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(candidates_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    user = get_user_by_email(str(payload.email))
    if not user or not bcrypt.verify(payload.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.get("is_active", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return TokenResponse(access_token=create_access_token(user["id"]))


@app.get("/auth/me")
def me(user: dict = Depends(get_current_user)):
    profile = get_profile(user["id"])
    return {**public_user(user), "profile": profile}


@app.post("/users", status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate):
    try:
        user = create_user(payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    return public_user(user)


@app.put("/profiles/me")
def update_my_profile(payload: ProfileUpdate, user: dict = Depends(get_current_user)):
    return update_profile(user["id"], payload)


@app.post("/auth/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    user = get_user_by_email(str(payload.email))
    if user and user.get("is_active", False):
        token, _ = create_reset_token(user["id"])
        settings = get_settings()
        reset_url = (
            f"{settings['frontend_base_url']}/reset-password?"
            f"{urlencode({'token': token})}"
        )
        try:
            send_password_reset_email(str(payload.email), reset_url)
        except EmailDeliveryError:
            logger.error("Password reset email delivery failed")

    return {
        "message": "If that address is registered, you'll receive a reset link shortly."
    }


@app.post("/auth/reset-password")
def reset_password(payload: ResetPasswordRequest):
    try:
        redeem_reset_token(payload.token, payload.new_password)
    except InvalidPasswordResetToken:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token is invalid, expired, or has already been used",
        )
    return {"message": "Password reset successfully"}


@app.post("/auth/change-password")
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
    return {"message": "Password changed successfully"}