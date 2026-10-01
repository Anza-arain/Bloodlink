"""Database models: users, donors, hospitals, blood requests, donor responses, notifications."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # requester | donor | coordinator | admin
    city = Column(String, default="Karachi")
    phone_verified = Column(Boolean, default=False)
    account_status = Column(String, default="active")  # active | blocked
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True)  # for coordinators
    created_at = Column(DateTime, default=now)

    donor = relationship("Donor", back_populates="user", uselist=False)


class Hospital(Base):
    __tablename__ = "hospitals"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    phone = Column(String, default="")
    verified = Column(Boolean, default=True)


class Donor(Base):
    __tablename__ = "donors"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    blood_group = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    area = Column(String, nullable=False)
    city = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    available = Column(Boolean, default=True)
    unavailable_until = Column(Date, nullable=True)  # temporary unavailable status
    last_donation_date = Column(Date, nullable=True)
    total_donations = Column(Integer, default=0)
    # response behaviour (used by the AI response-likelihood model)
    requests_received = Column(Integer, default=0)
    requests_accepted = Column(Integer, default=0)
    avg_response_minutes = Column(Float, default=0)

    user = relationship("User", back_populates="donor")


class BloodRequest(Base):
    __tablename__ = "blood_requests"
    id = Column(Integer, primary_key=True)
    requester_id = Column(Integer, ForeignKey("users.id"))
    patient_name = Column(String, nullable=False)
    blood_group = Column(String, nullable=False)
    units_required = Column(Integer, nullable=False)
    units_arranged = Column(Integer, default=0)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"))
    urgency = Column(String, default="normal")  # set by requester
    ai_priority = Column(String, default="normal")  # set by AI classifier
    ai_confidence = Column(Float, default=0)
    ai_reasons = Column(Text, default="[]")  # JSON list
    ai_summary = Column(Text, default="")
    required_before = Column(DateTime, nullable=False)
    description = Column(Text, default="")
    contact_phone = Column(String, default="")
    verification_status = Column(String, default="pending")  # pending | verified | rejected
    request_status = Column(String, default="pending_verification")
    duplicate_of = Column(Integer, nullable=True)
    suspicious_flags = Column(Text, default="[]")  # JSON list
    report_count = Column(Integer, default=0)
    search_radius_km = Column(Float, default=0)
    wave = Column(Integer, default=0)
    last_wave_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now)
    fulfilled_at = Column(DateTime, nullable=True)

    hospital = relationship("Hospital")
    requester = relationship("User")
    responses = relationship("DonorResponse", back_populates="request", cascade="all, delete-orphan")
    events = relationship("RequestEvent", back_populates="request", cascade="all, delete-orphan",
                          order_by="RequestEvent.created_at")


class DonorResponse(Base):
    __tablename__ = "donor_responses"
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("blood_requests.id"))
    donor_id = Column(Integer, ForeignKey("donors.id"))
    match_score = Column(Float, default=0)
    distance_km = Column(Float, default=0)
    wave = Column(Integer, default=1)
    # notified | accepted | declined | no_response | cancelled | donated
    response_status = Column(String, default="notified")
    notified_at = Column(DateTime, default=now)
    response_time = Column(DateTime, nullable=True)
    donation_confirmed = Column(Boolean, default=False)

    request = relationship("BloodRequest", back_populates="responses")
    donor = relationship("Donor")


class RequestEvent(Base):
    """Timeline of everything that happened to a request (shown in the UI)."""
    __tablename__ = "request_events"
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("blood_requests.id"))
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=now)
    request = relationship("BloodRequest", back_populates="events")


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    request_id = Column(Integer, nullable=True)
    channels = Column(String, default="in_app")  # e.g. "in_app,sms,email,push"
    title = Column(String, nullable=False)
    body = Column(Text, default="")
    read = Column(Boolean, default=False)
    delivery_status = Column(String, default="sent")  # sent | failed
    created_at = Column(DateTime, default=now)
