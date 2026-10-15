from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from .config import get_settings
from .services import get_user_by_id
from .telemetry.auth_events import emit_session_expired

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=int(settings["expiry_minutes"]))
    return jwt.encode({"user_uuid": user_id, "exp": expires}, str(settings["secret"]), algorithm=str(settings["algorithm"]))


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        # Only reachable when the dependency is invoked outside the HTTP flow.
        emit_session_expired(reason="missing_token")
        raise credentials_error
    try:
        settings = get_settings()
        payload = jwt.decode(token, str(settings["secret"]), algorithms=[str(settings["algorithm"])])
    except ExpiredSignatureError:
        emit_session_expired(reason="token_expired")
        raise credentials_error
    except (JWTError, RuntimeError):
        emit_session_expired(reason="invalid_token")
        raise credentials_error
    user_id = payload.get("user_uuid")
    if not isinstance(user_id, str):
        emit_session_expired(reason="invalid_token")
        raise credentials_error
    user = get_user_by_id(user_id)
    if not user or not user.get("is_active", False):
        emit_session_expired(reason="user_inactive")
        raise credentials_error
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user