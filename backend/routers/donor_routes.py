"""Donor endpoints: profile, availability, incoming requests, accept/decline, history; donation confirmation."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import current_user, require_roles
from database import get_db
from models import Donor, DonorResponse, User, Notification
from schemas import DonorUpdate
from serializers import donor_out, iso, notification_out, request_out
from services.locations import area_coords
from services import request_manager as rm
from services.compatibility import check_eligibility

router = APIRouter(prefix="/api", tags=["donors"])


def _me(user: User) -> Donor:
    if not user.donor:
        raise HTTPException(400, "This account has no donor profile")
    return user.donor


@router.get("/donors/me")
def my_profile(user: User = Depends(require_roles("donor"))):
    return donor_out(_me(user), private=True)


@router.put("/donors/me")
def update_profile(data: DonorUpdate, user: User = Depends(require_roles("donor")), db: Session = Depends(get_db)):
    d = _me(user)
    fields = data.model_dump(exclude_unset=True)
    if "city" in fields or "area" in fields:
        city, area = fields.get("city", d.city), fields.get("area", d.area)
        try:
            d.lat, d.lng = area_coords(city, area)
        except ValueError as e:
            raise HTTPException(400, str(e))
        d.city, d.area = city, area
    for k in ("blood_group", "age", "available", "unavailable_until", "last_donation_date"):
        if k in fields:
            setattr(d, k, fields[k])
    if data.clear_unavailable:
        d.unavailable_until = None
    db.commit()
    return donor_out(d, private=True)


@router.get("/donors/me/requests")
def my_incoming(user: User = Depends(require_roles("donor")), db: Session = Depends(get_db)):
    """Requests this donor was matched to. Shows only donor-friendly info (no patient private data)."""
    d = _me(user)
    rows = db.query(DonorResponse).filter(DonorResponse.donor_id == d.id).order_by(DonorResponse.notified_at.desc()).all()
    out = []
    for r in rows:
        req = r.request
        item = {"response_id": r.id, "response_status": r.response_status, "match_score": r.match_score,
                "distance_km": r.distance_km, "notified_at": iso(r.notified_at), "wave": r.wave,
                "donation_confirmed": r.donation_confirmed,
                "request": {"id": req.id, "summary": req.ai_summary, "blood_group": req.blood_group,
                            "units_required": req.units_required, "units_still_needed": rm.units_still_needed(req),
                            "hospital": req.hospital.name, "required_before": iso(req.required_before),
                            "priority": request_out(req, user)["priority"], "status": req.request_status}}
        if r.response_status in ("accepted", "donated"):
            item["request"]["contact"] = {"name": req.requester.name, "phone": req.contact_phone or req.requester.phone}
        out.append(item)
    return out


def _my_response(db: Session, rid: int, user: User) -> DonorResponse:
    resp = db.get(DonorResponse, rid)
    if not resp or resp.donor_id != _me(user).id:
        raise HTTPException(404, "Not found")
    return resp


@router.post("/responses/{rid}/accept")
def accept(rid: int, user: User = Depends(require_roles("donor")), db: Session = Depends(get_db)):
    resp = _my_response(db, rid, user)
    if resp.response_status != "notified":
        raise HTTPException(400, f"This request is no longer waiting for you ({resp.response_status})")
    if resp.request.request_status not in rm.OPEN_STATUSES:
        raise HTTPException(400, "This request is no longer active")
    elig = check_eligibility(resp.donor.age, resp.donor.last_donation_date, True, resp.donor.unavailable_until)
    if not elig["eligible"]:
        raise HTTPException(400, "You are not currently eligible: " + "; ".join(elig["reasons"]))
    rm.respond(db, resp, accept=True)
    db.commit()
    return {"ok": True}


@router.post("/responses/{rid}/decline")
def decline(rid: int, user: User = Depends(require_roles("donor")), db: Session = Depends(get_db)):
    resp = _my_response(db, rid, user)
    if resp.response_status not in ("notified", "accepted"):
        raise HTTPException(400, "Nothing to decline")
    was_accepted = resp.response_status == "accepted"
    if was_accepted:
        resp.donor.requests_accepted = max(0, resp.donor.requests_accepted - 1)
    rm.respond(db, resp, accept=False)
    db.commit()
    return {"ok": True}


@router.post("/responses/{rid}/confirm")
def confirm(rid: int, user: User = Depends(require_roles("coordinator", "admin")), db: Session = Depends(get_db)):
    resp = db.get(DonorResponse, rid)
    if not resp:
        raise HTTPException(404, "Not found")
    if resp.response_status != "accepted":
        raise HTTPException(400, "Only accepted donors can be confirmed")
    rm.confirm_donation(db, resp, user)
    db.commit()
    return request_out(resp.request, user, detail=True)


@router.get("/donors")
def search_donors(blood_group: str | None = None, city: str | None = None, available: bool | None = None,
                  eligible: bool | None = None, user: User = Depends(require_roles("coordinator", "admin")),
                  db: Session = Depends(get_db)):
    q = db.query(Donor).join(User).filter(User.account_status == "active")
    if blood_group:
        q = q.filter(Donor.blood_group == blood_group)
    if city:
        q = q.filter(Donor.city == city)
    if available is not None:
        q = q.filter(Donor.available.is_(available))
    rows = [dict(donor_out(d), name=d.user.name) for d in q.order_by(Donor.id).all()]
    if eligible is not None:
        rows = [r for r in rows if r["eligible"] == eligible]
    return rows


@router.get("/notifications")
def my_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = (db.query(Notification).filter(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc()).limit(50).all())
    return {"unread": sum(1 for n in rows if not n.read), "items": [notification_out(n) for n in rows]}


@router.post("/notifications/read-all")
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.user_id == user.id).update({"read": True})
    db.commit()
    return {"ok": True}
