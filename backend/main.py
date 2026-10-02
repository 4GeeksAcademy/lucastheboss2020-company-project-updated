from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from .auth import create_access_token, get_current_user
from .candidates import router as candidates_router
from .models import LoginRequest, ProfileUpdate, TokenResponse, UserCreate
from .services import create_user, get_profile, get_user_by_email, public_user, update_profile
from passlib.hash import bcrypt

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