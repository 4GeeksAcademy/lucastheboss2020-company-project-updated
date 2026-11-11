from datetime import datetime, timedelta, timezone
from hashlib import sha256
from threading import Lock
from uuid import uuid4

from jose import JWTError, jwt
from passlib.hash import bcrypt
from tinydb import Query

from .config import get_settings
from .storage import password_reset_tokens_table, users_table

_reset_lock = Lock()


class InvalidPasswordResetToken(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def invalidate_user_reset_tokens(user_id: str) -> None:
    now = _now().isoformat()
    query = Query()
    with _reset_lock:
        for record in password_reset_tokens_table.search(query.user_id == user_id):
            if record.get("used_at") is None:
                password_reset_tokens_table.update(
                    {"used_at": now}, query.digest == record["digest"]
                )


def create_reset_token(user_id: str) -> tuple[str, datetime]:
    settings = get_settings()
    now = _now()
    expires_at = now + timedelta(minutes=int(settings["reset_expiry_minutes"]))
    token = jwt.encode(
        {
            "sub": user_id,
            "jti": str(uuid4()),
            "purpose": "password_reset",
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        },
        str(settings["secret"]),
        algorithm=str(settings["algorithm"]),
    )

    with _reset_lock:
        query = Query()
        for record in password_reset_tokens_table.search(query.user_id == user_id):
            if record.get("used_at") is None:
                password_reset_tokens_table.update(
                    {"used_at": now.isoformat()}, query.digest == record["digest"]
                )
        password_reset_tokens_table.insert(
            {
                "digest": _token_digest(token),
                "user_id": user_id,
                "expires_at": expires_at.isoformat(),
                "used_at": None,
            }
        )

    return token, expires_at


def redeem_reset_token(token: str, new_password: str) -> None:
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            str(settings["secret"]),
            algorithms=[str(settings["algorithm"])],
        )
    except JWTError as exc:
        raise InvalidPasswordResetToken("Invalid or expired reset token") from exc

    user_id = claims.get("sub")
    if claims.get("purpose") != "password_reset" or not isinstance(user_id, str):
        raise InvalidPasswordResetToken("Invalid or expired reset token")

    now = _now()
    digest = _token_digest(token)
    query = Query()

    with _reset_lock:
        record = password_reset_tokens_table.get(query.digest == digest)
        if not record or record.get("user_id") != user_id or record.get("used_at") is not None:
            raise InvalidPasswordResetToken("Invalid or expired reset token")

        try:
            expires_at = datetime.fromisoformat(record["expires_at"])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidPasswordResetToken("Invalid or expired reset token") from exc

        if expires_at <= now:
            password_reset_tokens_table.update({"used_at": now.isoformat()}, query.digest == digest)
            raise InvalidPasswordResetToken("Invalid or expired reset token")

        user_query = Query()
        user = users_table.get(user_query.id == user_id)
        if not user:
            raise InvalidPasswordResetToken("Invalid or expired reset token")

        users_table.update({"hashed_password": bcrypt.hash(new_password)}, user_query.id == user_id)
        for reset_record in password_reset_tokens_table.search(user_query.user_id == user_id):
            if reset_record.get("used_at") is None:
                password_reset_tokens_table.update(
                    {"used_at": now.isoformat()}, query.digest == reset_record["digest"]
                )
