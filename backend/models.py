from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Role(str, Enum):
    admin = "admin"
    manager = "manager"
    user = "user"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    role: Role | None = None
    password: str | None = Field(default=None, min_length=8)


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    is_active: bool
    role: Role
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class ProfilePublic(BaseModel):
    id: str
    user_id: str
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CandidateWrite(BaseModel):
    companyName: str
    contactPerson: str
    corporateEmail: EmailStr
    phone: str
    companyWebsite: str | None = None
    operatingCountry: str
    productType: str
    monthlyVolume: str
    servicesOfInterest: list[str]
    current3pl: str
    comments: str | None = None
    privacyAccepted: bool
    status: str = "new"
    stage: str = "intake"
    assignedTo: str = "Commercial Desk"


class CandidatePatch(BaseModel):
    status: str | None = None
    stage: str | None = None


class NoteCreate(BaseModel):
    body: str = Field(min_length=2)
