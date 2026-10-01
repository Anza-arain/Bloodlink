"""Request bodies with input validation."""
from datetime import date, datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, field_validator

BloodGroup = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
Urgency = Literal["normal", "urgent", "critical"]


def to_naive_utc(v: datetime) -> datetime:
    """Store all datetimes as naive UTC."""
    if v.tzinfo is not None:
        v = v.astimezone(timezone.utc).replace(tzinfo=None)
    return v


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str = Field(min_length=10, max_length=15, pattern=r"^\+?[0-9]{10,14}$")
    password: str = Field(min_length=6, max_length=100)
    role: Literal["requester", "donor"]
    city: str = "Karachi"
    # donor-only fields
    blood_group: BloodGroup | None = None
    age: int | None = Field(default=None, ge=16, le=80)
    area: str | None = None
    last_donation_date: date | None = None


class LoginIn(BaseModel):
    email: str
    password: str


class OtpIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class RequestIn(BaseModel):
    patient_name: str = Field(min_length=2, max_length=80)
    blood_group: BloodGroup
    units_required: int = Field(ge=1, le=20)
    hospital_id: int
    urgency: Urgency = "normal"
    required_before: datetime
    description: str = Field(default="", max_length=1000)
    contact_phone: str = Field(default="", max_length=15)

    _utc = field_validator("required_before")(to_naive_utc)


class AnalyzeIn(BaseModel):
    blood_group: BloodGroup = "O+"
    units_required: int = Field(default=1, ge=1, le=20)
    hospital_id: int | None = None
    patient_name: str = ""
    required_before: datetime
    description: str = ""
    urgency: Urgency = "normal"

    _utc = field_validator("required_before")(to_naive_utc)


class DonorUpdate(BaseModel):
    blood_group: BloodGroup | None = None
    age: int | None = Field(default=None, ge=16, le=80)
    city: str | None = None
    area: str | None = None
    available: bool | None = None
    unavailable_until: date | None = None
    last_donation_date: date | None = None
    clear_unavailable: bool = False


class ReportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class HospitalIn(BaseModel):
    name: str = Field(min_length=3)
    city: str
    area: str
    phone: str = ""
