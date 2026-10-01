"""Smart Donor Matcher: ranks compatible donors with an explainable 0-100 match score."""
from datetime import date
from sqlalchemy.orm import Session

from models import Donor, User, BloodRequest
from services.compatibility import compatible_donor_groups, check_eligibility
from services.locations import haversine_km
from services.ai import response_likelihood, effective_priority

# weights per priority (each row sums to 100)
WEIGHTS = {
    "critical": {"distance": 45, "response": 20, "compatibility": 15, "rest": 10, "speed": 10},
    "urgent":   {"distance": 40, "response": 25, "compatibility": 15, "rest": 10, "speed": 10},
    "normal":   {"distance": 30, "response": 30, "compatibility": 15, "rest": 15, "speed": 10},
}
DISTANCE_FALLOFF_KM = 30.0


def compatibility_factor(donor_group: str, recipient_group: str) -> float:
    if donor_group == recipient_group:
        return 1.0
    if donor_group == "O-":
        return 0.6  # conserve universal donors for patients who have no other option
    return 0.8


def score_donor(donor: Donor, req: BloodRequest, today: date | None = None) -> dict:
    today = today or date.today()
    h = req.hospital
    dist = haversine_km(h.lat, h.lng, donor.lat, donor.lng)
    elig = check_eligibility(donor.age, donor.last_donation_date, donor.available,
                             donor.unavailable_until, today)
    likelihood = response_likelihood(donor.requests_received, donor.requests_accepted)
    priority = effective_priority(req.urgency, req.ai_priority)
    w = WEIGHTS[priority]

    f_distance = max(0.0, 1 - dist / DISTANCE_FALLOFF_KM)
    f_compat = compatibility_factor(donor.blood_group, req.blood_group)
    if donor.last_donation_date:
        days = (today - donor.last_donation_date).days
        f_rest = max(0.0, min(1.0, (days - 90) / 270))
    else:
        f_rest = 1.0
    f_speed = 0.5 if not donor.avg_response_minutes else max(0.0, 1 - donor.avg_response_minutes / 120)

    raw = (w["distance"] * f_distance + w["response"] * likelihood + w["compatibility"] * f_compat
           + w["rest"] * f_rest + w["speed"] * f_speed)
    factors = {
        "distance": round(w["distance"] * f_distance, 1),
        "response_history": round(w["response"] * likelihood, 1),
        "compatibility": round(w["compatibility"] * f_compat, 1),
        "rested": round(w["rest"] * f_rest, 1),
        "response_speed": round(w["speed"] * f_speed, 1),
    }
    return {
        "donor_id": donor.id,
        "name": donor.user.name,
        "blood_group": donor.blood_group,
        "area": donor.area,
        "distance_km": round(dist, 1),
        "available": donor.available,
        "eligible": elig["eligible"],
        "eligibility_reasons": elig["reasons"],
        "response_likelihood": likelihood,
        "match_score": round(raw) if elig["eligible"] else 0,
        "factors": factors,
        "priority_used": priority,
    }


def rank_donors(db: Session, req: BloodRequest, include_ineligible: bool = True,
                max_km: float | None = None) -> list[dict]:
    groups = compatible_donor_groups(req.blood_group)
    donors = (db.query(Donor).join(User)
              .filter(Donor.blood_group.in_(groups), User.account_status == "active").all())
    results = [score_donor(d, req) for d in donors]
    if max_km is not None:
        results = [r for r in results if r["distance_km"] <= max_km]
    if not include_ineligible:
        results = [r for r in results if r["eligible"]]
    results.sort(key=lambda r: (not r["eligible"], -r["match_score"], r["distance_km"]))
    return results
