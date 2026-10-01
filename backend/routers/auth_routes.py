"""Auth, account and reference-data endpoints."""
import os
import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import hash_password, verify_password, create_token, current_user
from database import get_db
from models import User, Donor, Hospital
from schemas import RegisterIn, LoginIn, OtpIn
from serializers import user_out
from services.compatibility import BLOOD_GROUPS, COMPATIBLE_DONORS, MEDICAL_DISCLAIMER
from services.locations import AREAS, area_coords
from services.notifications import _send_sms
from services.request_manager import ALL_STATUSES

router = APIRouter(prefix="/api", tags=["auth"])
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
_otp_codes: dict[int, str] = {}


@router.post("/auth/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = data.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "An account with this email already exists")
    if data.city not in AREAS:
        raise HTTPException(400, "Unsupported city")
    user = User(name=data.name.strip(), email=email, phone=data.phone, role=data.role,
                password_hash=hash_password(data.password), city=data.city)
    if data.role == "donor":
        if not (data.blood_group and data.age and data.area):
            raise HTTPException(400, "Donors must provide blood group, age and area")
        try:
            lat, lng = area_coords(data.city, data.area)
        except ValueError as e:
            raise HTTPException(400, str(e))
        user.donor = Donor(blood_group=data.blood_group, age=data.age, area=data.area, city=data.city,
                           lat=lat, lng=lng, last_donation_date=data.last_donation_date)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": create_token(user), "user": user_out(user)}


@router.post("/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower().strip()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    if user.account_status != "active":
        raise HTTPException(403, "This account has been blocked by an administrator")
    return {"token": create_token(user), "user": user_out(user)}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.post("/auth/send-otp")
def send_otp(user: User = Depends(current_user)):
    code = f"{secrets.randbelow(1_000_000):06d}"
    _otp_codes[user.id] = code
    _send_sms(user.phone, f"Your BloodLink verification code is {code}")
    # in demo mode the code is returned so judges can test without a real SMS gateway
    return {"sent": True, "dev_code": code if DEMO_MODE else None}


@router.post("/auth/verify-otp")
def verify_otp(data: OtpIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if _otp_codes.get(user.id) != data.code:
        raise HTTPException(400, "Incorrect code")
    user.phone_verified = True
    _otp_codes.pop(user.id, None)
    db.commit()
    return user_out(user)


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    hospitals = db.query(Hospital).filter(Hospital.verified.is_(True)).order_by(Hospital.city, Hospital.name).all()
    return {
        "blood_groups": BLOOD_GROUPS,
        "compatibility": COMPATIBLE_DONORS,
        "areas": {city: list(areas.keys()) for city, areas in AREAS.items()},
        "hospitals": [{"id": h.id, "name": h.name, "city": h.city} for h in hospitals],
        "statuses": ALL_STATUSES,
        "disclaimer": MEDICAL_DISCLAIMER,
    }
