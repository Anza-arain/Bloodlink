"""Blood request endpoints: create, search/filter, verify, match, escalate, close."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from auth import current_user, require_roles
from database import get_db
from models import BloodRequest, Hospital, User, now
from schemas import RequestIn, AnalyzeIn, ReportIn
from serializers import request_out
from services import ai
from services.matching import rank_donors
from services import request_manager as rm
from services.notifications import notify

router = APIRouter(prefix="/api", tags=["requests"])
CLOSED = ["completed", "cancelled", "expired", "rejected"]


def _get(db: Session, rid: int) -> BloodRequest:
    r = db.get(BloodRequest, rid)
    if not r:
        raise HTTPException(404, "Request not found")
    return r


def _analyze(db: Session, data, requester_id: int) -> dict:
    hospital = db.get(Hospital, data.hospital_id) if data.hospital_id else None
    pr = ai.classify_priority(data.description, data.required_before, data.units_required)
    prio = ai.effective_priority(data.urgency, pr["priority"])
    summary = ai.summarize_request(data.blood_group, data.units_required,
                                   hospital.name if hospital else "selected hospital",
                                   data.required_before, prio, data.description)
    dups = []
    if hospital:
        open_recent = db.query(BloodRequest).filter(
            BloodRequest.request_status.notin_(CLOSED),
            BloodRequest.created_at >= now() - timedelta(hours=48)).all()
        dups = ai.find_duplicates({"hospital_id": hospital.id, "blood_group": data.blood_group,
                                   "patient_name": data.patient_name, "description": data.description,
                                   "requester_id": requester_id}, open_recent)
    return {"classification": pr, "effective_priority": prio, "summary": summary, "duplicates": dups}


@router.post("/ai/analyze")
def analyze(data: AnalyzeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Live AI preview while the requester is typing."""
    return _analyze(db, data, user.id)


@router.post("/requests")
def create_request(data: RequestIn, user: User = Depends(require_roles("requester", "coordinator", "admin")),
                   db: Session = Depends(get_db)):
    hospital = db.get(Hospital, data.hospital_id)
    if not hospital or not hospital.verified:
        raise HTTPException(400, "Please choose a registered hospital")
    if data.required_before <= now():
        raise HTTPException(400, "Required time must be in the future")

    a = _analyze(db, data, user.id)
    recent = db.query(BloodRequest).filter(BloodRequest.requester_id == user.id,
                                           BloodRequest.created_at >= now() - timedelta(hours=24)).count()
    flags = ai.suspicious_signals(data.model_dump(), recent, user.phone_verified or user.role != "requester")
    if a["duplicates"]:
        flags.append(f"possible duplicate of request #{a['duplicates'][0]['request_id']}")

    req = BloodRequest(
        requester_id=user.id, patient_name=data.patient_name.strip(), blood_group=data.blood_group,
        units_required=data.units_required, hospital_id=hospital.id, urgency=data.urgency,
        ai_priority=a["classification"]["priority"], ai_confidence=a["classification"]["confidence"],
        ai_reasons=ai.dumps(a["classification"]["reasons"]), ai_summary=a["summary"],
        required_before=data.required_before, description=data.description.strip(),
        contact_phone=data.contact_phone or user.phone,
        duplicate_of=a["duplicates"][0]["request_id"] if a["duplicates"] else None,
        suspicious_flags=ai.dumps(flags))
    db.add(req)
    db.flush()
    rm.log_event(db, req, f"Request created by {user.name} - AI priority: {req.ai_priority} "
                          f"({int(req.ai_confidence * 100)}% confidence)")

    if user.role in ("coordinator", "admin"):
        rm.verify(db, req, user)
    elif not flags and a["effective_priority"] == "critical":
        # life-critical + trusted requester: start matching immediately, staff review in parallel
        rm.log_event(db, req, "Auto-verified: critical priority from a phone-verified requester with no risk flags")
        req.verification_status = "verified"
        req.request_status = "active"
        rm.dispatch_next_wave(db, req, "critical fast-track")
    else:
        for staff in db.query(User).filter(User.role == "coordinator", User.account_status == "active").all():
            notify(db, staff, f"New request #{req.id} needs verification",
                   f"{req.ai_summary}. Flags: {', '.join(flags) if flags else 'none'}", req.id)
    db.commit()
    db.refresh(req)
    return {"request": request_out(req, user, detail=True), "warnings": flags}


@router.get("/requests")
def list_requests(
    blood_group: str | None = None, city: str | None = None, hospital_id: int | None = None,
    status: str | None = None, priority: str | None = None, verification: str | None = None,
    date_from: datetime | None = None, date_to: datetime | None = None, q: str | None = None,
    mine: bool = False, limit: int = Query(100, le=500),
    user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(BloodRequest).join(Hospital)
    if user.role in ("requester", "donor") or mine:
        query = query.filter(BloodRequest.requester_id == user.id)
    if blood_group:
        query = query.filter(BloodRequest.blood_group == blood_group)
    if city:
        query = query.filter(Hospital.city == city)
    if hospital_id:
        query = query.filter(BloodRequest.hospital_id == hospital_id)
    if status == "open":
        query = query.filter(BloodRequest.request_status.in_(rm.OPEN_STATUSES + ["pending_verification"]))
    elif status:
        query = query.filter(BloodRequest.request_status == status)
    if priority:
        query = query.filter(or_(BloodRequest.ai_priority == priority, BloodRequest.urgency == priority))
    if verification:
        query = query.filter(BloodRequest.verification_status == verification)
    if date_from:
        query = query.filter(BloodRequest.created_at >= date_from)
    if date_to:
        query = query.filter(BloodRequest.created_at <= date_to)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(BloodRequest.patient_name.ilike(like), BloodRequest.description.ilike(like),
                                 Hospital.name.ilike(like)))
    rows = query.order_by(BloodRequest.created_at.desc()).limit(limit).all()
    return [request_out(r, user) for r in rows]


@router.get("/requests/{rid}")
def get_request(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _get(db, rid)
    if user.role in ("requester",) and r.requester_id != user.id:
        raise HTTPException(403, "You can only view your own requests")
    return request_out(r, user, detail=True)


@router.get("/requests/{rid}/candidates")
def candidates(rid: int, user: User = Depends(require_roles("coordinator", "admin")),
               db: Session = Depends(get_db)):
    """Ranked list of compatible donors with explainable match score (names hidden until acceptance)."""
    r = _get(db, rid)
    contacted = {resp.donor_id: resp.response_status for resp in r.responses}
    out = []
    for i, d in enumerate(rank_donors(db, r, max_km=60)[:40], start=1):
        d["rank"] = i
        d["contact_status"] = contacted.get(d["donor_id"])
        if d["contact_status"] not in ("accepted", "donated"):
            d["name"] = f"Donor #{d['donor_id']}"
        out.append(d)
    return out


@router.post("/requests/{rid}/verify")
def verify(rid: int, user: User = Depends(require_roles("coordinator", "admin")), db: Session = Depends(get_db)):
    r = _get(db, rid)
    if r.request_status != "pending_verification":
        raise HTTPException(400, f"Request is already {r.request_status}")
    rm.verify(db, r, user)
    db.commit()
    return request_out(r, user, detail=True)


@router.post("/requests/{rid}/reject")
def reject(rid: int, data: ReportIn, user: User = Depends(require_roles("coordinator", "admin")),
           db: Session = Depends(get_db)):
    r = _get(db, rid)
    r.verification_status, r.request_status = "rejected", "rejected"
    for resp in r.responses:
        if resp.response_status == "notified":
            resp.response_status = "cancelled"
    rm.log_event(db, r, f"Rejected by {user.name}: {data.reason}")
    notify(db, r.requester, f"Request #{r.id} rejected", data.reason, r.id)
    db.commit()
    return request_out(r, user, detail=True)


@router.post("/requests/{rid}/escalate")
def escalate(rid: int, user: User = Depends(require_roles("coordinator", "admin", "requester")),
             db: Session = Depends(get_db)):
    r = _get(db, rid)
    if user.role == "requester" and r.requester_id != user.id:
        raise HTTPException(403, "Not your request")
    if r.request_status not in rm.OPEN_STATUSES:
        raise HTTPException(400, "Only active requests can be escalated")
    n = rm.dispatch_next_wave(db, r, f"manual escalation by {user.name}")
    db.commit()
    return {"notified": n, "request": request_out(r, user, detail=True)}


@router.post("/requests/{rid}/cancel")
def cancel(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _get(db, rid)
    if r.requester_id != user.id and user.role not in ("coordinator", "admin"):
        raise HTTPException(403, "Not your request")
    if r.request_status in CLOSED:
        raise HTTPException(400, f"Request is already {r.request_status}")
    r.request_status = "cancelled"
    for resp in r.responses:
        if resp.response_status in ("notified", "accepted"):
            notify(db, resp.donor.user, f"Request #{r.id} cancelled", "No action needed. Thank you!", r.id)
            resp.response_status = "cancelled"
    rm.log_event(db, r, f"Cancelled by {user.name}")
    db.commit()
    return request_out(r, user, detail=True)


@router.post("/requests/{rid}/complete")
def complete(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Requester marks request completed / coordinator closes a fulfilled request."""
    r = _get(db, rid)
    if r.requester_id != user.id and user.role not in ("coordinator", "admin"):
        raise HTTPException(403, "Not your request")
    if r.request_status in CLOSED:
        raise HTTPException(400, f"Request is already {r.request_status}")
    r.request_status = "completed"
    r.fulfilled_at = r.fulfilled_at or now()
    for resp in r.responses:
        if resp.response_status == "notified":
            resp.response_status = "cancelled"
    rm.log_event(db, r, f"Closed as completed by {user.name}")
    db.commit()
    return request_out(r, user, detail=True)


@router.post("/requests/{rid}/report")
def report(rid: int, data: ReportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _get(db, rid)
    r.report_count += 1
    flags = ai.loads(r.suspicious_flags)
    flags.append(f"reported by user: {data.reason}")
    r.suspicious_flags = ai.dumps(flags)
    rm.log_event(db, r, "Reported as suspicious - sent to admin review")
    db.commit()
    return {"ok": True}
