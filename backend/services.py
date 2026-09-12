from datetime import datetime, timezone
from uuid import uuid4
from tinydb import Query
from passlib.hash import bcrypt
from .models import ProfileUpdate, Role, UserCreate, UserUpdate
from .storage import profiles_table, users_table


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_user(record: dict) -> dict:
    return {key: record[key] for key in ("id", "email", "is_active", "role", "created_at")}


def get_user_by_id(user_id: str) -> dict | None:
    return users_table.get(Query().id == user_id)


def get_user_by_email(email: str) -> dict | None:
    return users_table.get(Query().email == email.lower())


def create_user(payload: UserCreate) -> dict:
    if get_user_by_email(str(payload.email)):
        raise ValueError("Email is already registered")
    user_id = str(uuid4())
    record = {
        "id": user_id,
        "email": str(payload.email).lower(),
        "hashed_password": bcrypt.hash(payload.password),
        "is_active": True,
        "role": Role.user.value,
        "created_at": _now(),
    }
    users_table.insert(record)
    profiles_table.insert({"id": str(uuid4()), "user_id": user_id, "name": payload.name, "phone": payload.phone, "address": payload.address})
    return record


def update_user(user_id: str, payload: UserUpdate) -> dict | None:
    user = get_user_by_id(user_id)
    if not user:
        return None
    updates = payload.model_dump(exclude_none=True)
    if "email" in updates:
        existing = get_user_by_email(str(updates["email"]))
        if existing and existing["id"] != user_id:
            raise ValueError("Email is already registered")
        updates["email"] = str(updates["email"]).lower()
    if "role" in updates:
        updates["role"] = updates["role"].value if isinstance(updates["role"], Role) else updates["role"]
    if "password" in updates:
        updates["hashed_password"] = bcrypt.hash(updates.pop("password"))
    users_table.update(updates, Query().id == user_id)
    return get_user_by_id(user_id)


def delete_user(user_id: str) -> bool:
    removed = users_table.remove(Query().id == user_id)
    profiles_table.remove(Query().user_id == user_id)
    return bool(removed)


def get_profile(user_id: str) -> dict | None:
    return profiles_table.get(Query().user_id == user_id)


def update_profile(user_id: str, payload: ProfileUpdate) -> dict:
    profile = get_profile(user_id)
    if not profile:
        profile = {"id": str(uuid4()), "user_id": user_id}
        profiles_table.insert(profile)
    updates = payload.model_dump(exclude_unset=True)
    profiles_table.update(updates, Query().user_id == user_id)
    return get_profile(user_id) or profile
