from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from .config import get_settings
from .services import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=int(settings["expiry_minutes"]))
    return jwt.encode({"user_uuid": user_id, "exp": expires}, str(settings["secret"]), algorithm=str(settings["algorithm"]))


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        settings = get_settings()
        payload = jwt.decode(token, str(settings["secret"]), algorithms=[str(settings["algorithm"])])
        user_id = payload.get("user_uuid")
        if not isinstance(user_id, str):
            raise credentials_error
    except (JWTError, RuntimeError):
        raise credentials_error
    user = get_user_by_id(user_id)
    if not user or not user.get("is_active", False):
        raise credentials_error
    return user
