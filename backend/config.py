from functools import lru_cache
import os


@lru_cache
def get_settings() -> dict[str, str | int]:
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY must be configured")
    try:
        expiry = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    except ValueError as exc:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be an integer") from exc
    if expiry <= 0:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
    try:
        reset_expiry = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30"))
    except ValueError as exc:
        raise RuntimeError("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES must be an integer") from exc
    if reset_expiry <= 0:
        raise RuntimeError("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES must be positive")
    return {
        "secret": secret,
        "expiry_minutes": expiry,
        "reset_expiry_minutes": reset_expiry,
        "algorithm": "HS256",
        "resend_api_key": os.getenv("RESEND_API_KEY", ""),
        "password_reset_from_email": os.getenv(
            "PASSWORD_RESET_FROM_EMAIL", "TrackFlow <onboarding@resend.dev>"
        ),
        "frontend_base_url": os.getenv("FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/"),
    }