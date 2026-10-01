"""Admin and analytics endpoints."""
from collections import Counter, defaultdict
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import require_roles
from database import get_db
from models import BloodRequest, Donor, DonorResponse, Hospital, User, now
from schemas import HospitalIn
from serializers import user_out, request_out
from services import ai
from services.compatibility import BLOOD_GROUPS, COMPATIBLE_DONORS, check_eligibility
from services.locations import area_coords
from services.request_manager import OPEN_STATUSES

router = APIRouter(prefix="/api", tags=["admin"])
staff = require_roles("coordinator", "admin")
admin_only = require_roles("admin")


# ---------------- analytics ----------------
def _eligible_supply(db: Session) -> dict:
    supply = Counter()
    for d in db.query(Donor).join(User).filter(User.account_status == "active").all():
        if check_eligibility(d.age, d.last_donation_date, d.available, d.unavailable_until)["eligible"]:
            supply[d.blood_group] += 1
    return supply


@router.get("/analytics/dashboard")
def dashboard(user: User = Depends(staff), db: Session = Depends(get_db)):
    reqs = db.query(BloodRequest).all()
    responses = db.query(DonorResponse).all()
    donors = db.query(Donor).join(User).filter(User.account_status == "active").all()
    supply = _eligible_supply(db)
    t = now()

    status_counts = Counter(r.request_status for r in reqs)
    done = [r for r in reqs if r.request_status in ("fulfilled", "completed")]
    closed = [r for r in reqs if r.request_status not in OPEN_STATUSES + ["pending_verification"]]
    fulfil_hours = [(r.fulfilled_at - r.created_at).total_seconds() / 3600 for r in done if r.fulfilled_at]
    resp_minutes = [(x.response_time - x.notified_at).total_seconds() / 60 for x in responses if x.response_time]
    answered = [x for x in responses if x.response_status in ("accepted", "declined", "donated")]
    accepted = [x for x in responses if x.response_status in ("accepted", "donated")]

    demand = Counter()
    for r in reqs:
        demand[r.blood_group] += r.units_required
    by_hospital = Counter(r.hospital.name for r in reqs)
    by_city = Counter(r.hospital.city for r in reqs)
    by_priority = Counter(ai.effective_priority(r.urgency, r.ai_priority) for r in reqs)

    days = [(t - timedelta(days=i)).date() for i in range(13, -1, -1)]
    created_per_day = Counter(r.created_at.date() for r in reqs)
    fulfilled_per_day = Counter(r.fulfilled_at.date() for r in done if r.fulfilled_at)
    trend = [{"date": d.isoformat(), "created": created_per_day.get(d, 0), "fulfilled": fulfilled_per_day.get(d, 0)}
             for d in days]

    forecast = ai.forecast_demand(reqs, supply, BLOOD_GROUPS, COMPATIBLE_DONORS, t)

    kpis = {
        "total_requests": len(reqs),
        "active_requests": sum(status_counts[s] for s in OPEN_STATUSES),
        "pending_verification": status_counts["pending_verification"],
        "completed_requests": len(done),
        "critical_requests": by_priority["critical"],
        "registered_donors": len(donors),
        "available_donors": sum(supply.values()),
        "donations_completed": sum(1 for x in responses if x.donation_confirmed),
        "avg_fulfillment_hours": round(sum(fulfil_hours) / len(fulfil_hours), 1) if fulfil_hours else 0,
        "avg_response_minutes": round(sum(resp_minutes) / len(resp_minutes), 1) if resp_minutes else 0,
        "fulfillment_rate": round(len(done) / len(closed) * 100) if closed else 0,
        "acceptance_rate": round(len(accepted) / len(answered) * 100) if answered else 0,
    }

    # ---- human-readable insights: patterns, not just raw numbers ----
    insights = []
    if demand:
        g, units = demand.most_common(1)[0]
        insights.append(f"{g} has the highest demand ({units} units, {round(units / sum(demand.values()) * 100)}% of all units requested).")
    rising = [f for f in forecast if f["trend_pct"] >= 25 and f["last_7_days"] >= 2]
    if rising:
        f = max(rising, key=lambda x: x["trend_pct"])
        insights.append(f"{f['blood_group']} demand rose {f['trend_pct']}% this week compared with last week.")
    risky = [f["blood_group"] for f in forecast if f["shortage_risk"] == "high"]
    if risky:
        insights.append(f"Shortage risk next week for {', '.join(risky)} - consider a targeted donor drive.")
    if by_hospital:
        h, n = by_hospital.most_common(1)[0]
        insights.append(f"{h} generates the most requests ({n}).")
    if kpis["acceptance_rate"]:
        insights.append(f"{kpis['acceptance_rate']}% of donors who respond accept; average reply time is "
                        f"{kpis['avg_response_minutes']} minutes.")
    crit_done = [((r.fulfilled_at - r.created_at).total_seconds() / 3600) for r in done
                 if r.fulfilled_at and ai.effective_priority(r.urgency, r.ai_priority) == "critical"]
    if crit_done:
        insights.append(f"Critical requests are fulfilled in {round(sum(crit_done) / len(crit_done), 1)}h on average.")

    return {
        "kpis": kpis,
        "status_breakdown": dict(status_counts),
        "demand_by_blood_group": [{"blood_group": g, "units": demand.get(g, 0), "eligible_donors": supply.get(g, 0)}
                                  for g in BLOOD_GROUPS],
        "requests_by_hospital": [{"name": k, "count": v} for k, v in by_hospital.most_common(8)],
        "requests_by_city": [{"name": k, "count": v} for k, v in by_city.most_common()],
        "priority_breakdown": dict(by_priority),
        "daily_trend": trend,
        "forecast": forecast,
        "insights": insights,
    }


# ---------------- admin ----------------
@router.get("/admin/users")
def users(role: str | None = None, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    return [user_out(u) for u in q.order_by(User.created_at.desc()).all()]


@router.post("/admin/users/{uid}/{action}")
def set_user_status(uid: int, action: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    if action not in ("block", "unblock"):
        raise HTTPException(400, "Unknown action")
    target = db.get(User, uid)
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == user.id:
        raise HTTPException(400, "You cannot block yourself")
    target.account_status = "blocked" if action == "block" else "active"
    db.commit()
    return user_out(target)


@router.get("/admin/flagged")
def flagged(user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = db.query(BloodRequest).filter(
        (BloodRequest.suspicious_flags != "[]") | (BloodRequest.duplicate_of.isnot(None))
        | (BloodRequest.report_count > 0)).order_by(BloodRequest.created_at.desc()).limit(50).all()
    return [request_out(r, user) for r in rows]


@router.get("/admin/hospitals")
def hospitals(user: User = Depends(staff), db: Session = Depends(get_db)):
    counts = defaultdict(int)
    for r in db.query(BloodRequest).all():
        counts[r.hospital_id] += 1
    return [{"id": h.id, "name": h.name, "city": h.city, "phone": h.phone, "verified": h.verified,
             "requests": counts[h.id]} for h in db.query(Hospital).order_by(Hospital.city, Hospital.name).all()]


@router.post("/admin/hospitals")
def add_hospital(data: HospitalIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    try:
        lat, lng = area_coords(data.city, data.area)
    except ValueError as e:
        raise HTTPException(400, str(e))
    h = Hospital(name=data.name, city=data.city, lat=lat, lng=lng, phone=data.phone, verified=True)
    db.add(h)
    db.commit()
    return {"id": h.id, "name": h.name, "city": h.city}
