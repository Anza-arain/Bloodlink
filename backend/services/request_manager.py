"""Blood Request Manager: status lifecycle, staged notification waves, escalation, auto-stop.

Lifecycle:
  pending_verification -> active -> donors_contacted -> partially_fulfilled -> fulfilled -> completed
  side exits: cancelled | expired | rejected

Escalation (never spam every donor at once):
  wave 1: top 5 donors within 5 km -> wait -> wave 2: next 10 within 10 km
  -> wave 3: next 10 within 25 km -> wave 4: next 15 within 50 km
  Waiting time depends on priority. A decline triggers the next wave immediately
  when the remaining accepted/pending donors can no longer cover the units.
  Once enough donors accept, outstanding notifications are cancelled automatically.
"""
from datetime import date, timedelta
from sqlalchemy.orm import Session

from models import BloodRequest, DonorResponse, Donor, RequestEvent, User, now
from services.matching import rank_donors
from services.notifications import notify
from services.ai import effective_priority

WAVES = [(5, 5.0), (10, 10.0), (10, 25.0), (15, 50.0)]  # (donors to notify, radius km)
WAVE_TIMEOUT_MIN = {"critical": 10, "urgent": 30, "normal": 120}
OPEN_STATUSES = ["active", "donors_contacted", "partially_fulfilled"]
ALL_STATUSES = ["pending_verification", "active", "donors_contacted", "partially_fulfilled",
                "fulfilled", "completed", "cancelled", "expired", "rejected"]


def log_event(db: Session, req: BloodRequest, message: str):
    db.add(RequestEvent(request_id=req.id, message=message))


def counts(req: BloodRequest) -> dict:
    c = {"notified": 0, "accepted": 0, "declined": 0, "donated": 0, "cancelled": 0, "no_response": 0}
    for r in req.responses:
        c[r.response_status] = c.get(r.response_status, 0) + 1
    return c


def units_still_needed(req: BloodRequest) -> int:
    """Units not yet covered by a confirmed donation or an accepted (pledged) donor."""
    c = counts(req)
    return max(0, req.units_required - req.units_arranged - c["accepted"])


def dispatch_next_wave(db: Session, req: BloodRequest, reason: str = "") -> int:
    """Notify the next batch of best-ranked eligible donors. Returns number notified."""
    if req.request_status not in OPEN_STATUSES or units_still_needed(req) <= 0:
        return 0
    already = {r.donor_id for r in req.responses}
    ranked = [d for d in rank_donors(db, req, include_ineligible=False) if d["donor_id"] not in already]
    priority = effective_priority(req.urgency, req.ai_priority)

    already_exhausted = req.wave >= len(WAVES)
    wave_idx = min(req.wave, len(WAVES) - 1) if already_exhausted else req.wave
    while wave_idx < len(WAVES):
        size, radius = WAVES[wave_idx]
        batch = [d for d in ranked if d["distance_km"] <= radius][:size]
        wave_idx += 1
        if batch:
            break
        if not already_exhausted:
            log_event(db, req, f"No new eligible donors within {radius:g} km - expanding search radius")
    else:
        batch = []

    req.wave = wave_idx
    req.search_radius_km = WAVES[min(wave_idx, len(WAVES)) - 1][1]
    req.last_wave_at = now()

    if not batch:
        if already_exhausted:
            return 0  # coordinators were already alerted once
        log_event(db, req, "All search radii exhausted - coordinators alerted")
        for u in db.query(User).filter(User.role.in_(["coordinator", "admin"])).all():
            notify(db, u, f"No donors left for request #{req.id}",
                   f"{req.blood_group} at {req.hospital.name} still needs {units_still_needed(req)} unit(s). "
                   "Consider contacting the blood bank directly.", req.id)
        return 0

    for d in batch:
        donor = db.get(Donor, d["donor_id"])
        db.add(DonorResponse(request_id=req.id, donor_id=donor.id, match_score=d["match_score"],
                             distance_km=d["distance_km"], wave=wave_idx))
        donor.requests_received += 1
        notify(db, donor.user, f"{priority.upper()}: {req.blood_group} blood needed",
               f"{req.ai_summary}\nApproximately {d['distance_km']} km away. Open the app to accept or decline.",
               req.id, urgent=priority != "normal")
    if req.request_status == "active":
        req.request_status = "donors_contacted"
    why = f" ({reason})" if reason else ""
    log_event(db, req, f"Wave {wave_idx}: notified {len(batch)} donor(s) within {req.search_radius_km:g} km{why}")
    return len(batch)


def stop_extra_notifications(db: Session, req: BloodRequest):
    """Enough donors have accepted -> cancel pending notifications so nobody travels for nothing."""
    if units_still_needed(req) > 0:
        return
    stopped = 0
    for r in req.responses:
        if r.response_status == "notified":
            r.response_status = "cancelled"
            stopped += 1
            notify(db, r.donor.user, f"Request #{req.id} is covered - thank you!",
                   "Enough donors have accepted this request. No action is needed.", req.id)
    if stopped:
        log_event(db, req, f"Enough donors accepted - stopped {stopped} pending notification(s)")


def refresh_status(req: BloodRequest):
    if req.request_status not in OPEN_STATUSES + ["fulfilled"]:
        return
    if req.units_arranged >= req.units_required:
        req.request_status = "fulfilled"
        req.fulfilled_at = req.fulfilled_at or now()
    elif req.units_arranged > 0:
        req.request_status = "partially_fulfilled"


def verify(db: Session, req: BloodRequest, by: User):
    req.verification_status = "verified"
    req.request_status = "active"
    log_event(db, req, f"Verified by {by.name} ({by.role})")
    notify(db, req.requester, f"Request #{req.id} verified",
           "Your request is verified. We are contacting the best-matched donors now.", req.id)
    dispatch_next_wave(db, req, "initial matching")


def respond(db: Session, resp: DonorResponse, accept: bool):
    req = resp.request
    donor = resp.donor
    t = now()
    minutes = (t - resp.notified_at).total_seconds() / 60
    # exponential moving average of response time (recent behaviour matters more)
    prev = donor.avg_response_minutes or 0
    donor.avg_response_minutes = round(minutes if not prev else 0.7 * prev + 0.3 * minutes, 1)
    resp.response_time = t
    if accept:
        resp.response_status = "accepted"
        donor.requests_accepted += 1
        log_event(db, req, f"{donor.user.name} ({donor.blood_group}) accepted - {resp.distance_km} km away")
        notify(db, req.requester, f"A donor accepted request #{req.id}",
               f"{donor.user.name} ({donor.blood_group}) accepted. Contact: {donor.user.phone}. "
               f"{donor.user.name} is about {resp.distance_km} km from {req.hospital.name}.", req.id)
        stop_extra_notifications(db, req)
    else:
        resp.response_status = "declined"
        log_event(db, req, f"A donor declined (wave {resp.wave})")
        pending = sum(1 for r in req.responses if r.response_status == "notified")
        if units_still_needed(req) > pending:
            dispatch_next_wave(db, req, "decline received, not enough pending donors")


def confirm_donation(db: Session, resp: DonorResponse, by: User):
    req = resp.request
    donor = resp.donor
    resp.response_status = "donated"
    resp.donation_confirmed = True
    req.units_arranged += 1
    donor.total_donations += 1
    donor.last_donation_date = date.today()
    log_event(db, req, f"Donation by {donor.user.name} confirmed by {by.name} "
                       f"({req.units_arranged}/{req.units_required} units)")
    notify(db, donor.user, "Thank you for donating!",
           f"Your donation for request #{req.id} is confirmed. You can donate again after "
           f"{(date.today() + timedelta(days=90)).isoformat()}.", req.id)
    refresh_status(req)
    if req.request_status == "fulfilled":
        log_event(db, req, "All units arranged - request fulfilled")
        notify(db, req.requester, f"Request #{req.id} fulfilled", "All required units are arranged.", req.id)


def maintain(db: Session) -> dict:
    """Runs periodically: expire overdue requests and escalate waves whose wait time has passed."""
    t = now()
    expired = escalated = 0
    for req in db.query(BloodRequest).filter(
            BloodRequest.request_status.in_(OPEN_STATUSES + ["pending_verification"])).all():
        if req.required_before < t and req.units_arranged < req.units_required:
            req.request_status = "expired"
            for r in req.responses:
                if r.response_status == "notified":
                    r.response_status = "no_response"
            log_event(db, req, "Required time passed - request expired")
            expired += 1
            continue
        if req.request_status in OPEN_STATUSES and req.last_wave_at:
            prio = effective_priority(req.urgency, req.ai_priority)
            if t - req.last_wave_at >= timedelta(minutes=WAVE_TIMEOUT_MIN[prio]) and units_still_needed(req) > 0 \
                    and req.wave < len(WAVES):
                if dispatch_next_wave(db, req, f"no answer after {WAVE_TIMEOUT_MIN[prio]} min"):
                    escalated += 1
    db.commit()
    return {"expired": expired, "escalated": escalated}
