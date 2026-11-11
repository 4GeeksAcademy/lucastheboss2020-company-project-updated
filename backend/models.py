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


class RegistrationResponse(BaseModel):
    """Minimal acknowledgement returned by the unauthenticated registration flow."""

    id: str
    is_active: bool
    role: Role
    created_at: datetime


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


class CurrentUserResponse(UserPublic):
    profile: ProfilePublic | None = None


class MessageResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


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


class CandidateNoteRead(BaseModel):
    id: str
    body: str
    createdAt: str


class CandidateRead(BaseModel):
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
    status: str
    stage: str
    assignedTo: str
    id: str
    notes: list[CandidateNoteRead] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class CandidateListItem(BaseModel):
    """Candidate fields needed for list views; notes stay on detail responses."""

    companyName: str
    contactPerson: str
    corporateEmail: EmailStr
    operatingCountry: str
    productType: str
    monthlyVolume: str
    servicesOfInterest: list[str]
    status: str
    stage: str
    id: str


class CandidateListRead(BaseModel):
    data: list[CandidateListItem]
    page: int
    pageSize: int
    total: int
    totalPages: int


class NoteCreate(BaseModel):
    body: str = Field(min_length=2)


class SupplierStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


TRACKFLOW_SERVICES = ["warehouse-management", "last-mile-delivery", "reverse-logistics"]
CURRENCIES = ["USD", "EUR"]
COUNTRIES = ["United States", "Spain"]


class SupplierInput(BaseModel):
    name: str = Field(min_length=2)
    country: str = Field(min_length=2)
    services: list[str] = Field(min_length=1)
    rate_per_shipment: float = Field(gt=0)
    currency: str = Field(min_length=3, default="USD")
    status: SupplierStatus = SupplierStatus.ACTIVE


class Supplier(SupplierInput):
    id: int
    updated_at: str


class RateUpdate(BaseModel):
    rate_per_shipment: float = Field(gt=0)


class StatusUpdate(BaseModel):
    status: SupplierStatus