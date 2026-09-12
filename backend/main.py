from fastapi import Depends, FastAPI, HTTPException, status
from passlib.hash import bcrypt
from .auth import create_access_token, get_current_user
from .models import LoginRequest, ProfilePublic, ProfileUpdate, TokenResponse, UserCreate, UserPublic, UserUpdate
from .services import create_user, delete_user, get_profile, get_user_by_email, get_user_by_id, public_user, update_profile, update_user
from .candidates import router as candidates_router

app = FastAPI(title="TrackFlow API", version="1.0.0")
app.include_router(candidates_router)


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


@app.post("/users", response_model=UserPublic, status_code=201)
def register(payload: UserCreate):
    try:
        return public_user(create_user(payload))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/users", response_model=list[UserPublic])
def list_users(_: dict = Depends(get_current_user)):
    from .storage import users_table
    return [public_user(user) for user in users_table.all()]


@app.get("/users/{user_id}", response_model=UserPublic)
def read_user(user_id: str, current: dict = Depends(get_current_user)):
    if current["id"] != user_id and current.get("role") != "admin":
        raise HTTPException(status_code=403, detail="You do not own this resource")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return public_user(user)


@app.put("/users/{user_id}", response_model=UserPublic)
def edit_user(user_id: str, payload: UserUpdate, current: dict = Depends(get_current_user)):
    if current["id"] != user_id and current.get("role") != "admin":
        raise HTTPException(status_code=403, detail="You do not own this resource")
    if payload.role is not None and current.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admins can change roles")
    try:
        user = update_user(user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return public_user(user)


@app.delete("/users/{user_id}", status_code=204)
def remove_user(user_id: str, current: dict = Depends(get_current_user)):
    if current["id"] != user_id and current.get("role") != "admin":
        raise HTTPException(status_code=403, detail="You do not own this resource")
    if not delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    user = get_user_by_email(str(payload.email))
    if not user or not bcrypt.verify(payload.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    return TokenResponse(access_token=create_access_token(user["id"]))


@app.get("/auth/me")
def auth_me(current: dict = Depends(get_current_user)):
    return {"email": current["email"], "role": current["role"], "profile": get_profile(current["id"])}


def _owned_user(user_id: str, current: dict) -> None:
    if current["id"] != user_id and current.get("role") != "admin":
        raise HTTPException(status_code=403, detail="You do not own this resource")


@app.get("/profiles/me", response_model=ProfilePublic)
def my_profile(current: dict = Depends(get_current_user)):
    profile = get_profile(current["id"])
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.put("/profiles/me", response_model=ProfilePublic)
def edit_profile(payload: ProfileUpdate, current: dict = Depends(get_current_user)):
    return update_profile(current["id"], payload)


@app.get("/profiles/{user_id}", response_model=ProfilePublic)
def read_profile(user_id: str, current: dict = Depends(get_current_user)):
    _owned_user(user_id, current)
    profile = get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.put("/profiles/{user_id}", response_model=ProfilePublic)
def update_user_profile(user_id: str, payload: ProfileUpdate, current: dict = Depends(get_current_user)):
    _owned_user(user_id, current)
    return update_profile(user_id, payload)
