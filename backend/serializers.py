"""Convert DB objects to JSON, applying privacy rules.

Privacy rule: a donor's phone/email is only visible to the requester and
hospital staff AFTER that donor has accepted the request. Before that,
everyone only sees "Compatible donor ~4 km away". Exact home addresses are
never stored - only an area.
"""
from models import BloodRequest, User, Donor, Notification
from services.ai import loads, effective_priority
from services.compatibility import check_eligibility, MEDICAL_DISCLAIMER
from services.request_manager import counts, units_still_needed


def iso(dt):
    return dt.isoformat() + "Z" if dt else None


def user_out(u: User) -> dict:
    d = {"id": u.id, "name": u.name, "email": u.email, "phone": u.phone, "role": u.role, "city": u.city,
         "phone_verified": u.phone_verified, "account_status": u.account_status, "created_at": iso(u.created_at)}
    if u.donor:
        d["donor"] = donor_out(u.donor, private=True)
    return d


def donor_out(d: Donor, private: bool = False) -> dict:
    elig = check_eligibility(d.age, d.last_donation_date, d.available, d.unavailable_until)
    out = {"id": d.id, "blood_group": d.blood_group, "area": d.area, "city": d.city, "available": d.available,
           "eligible": elig["eligible"], "eligibility_reasons": elig["reasons"],
           "next_eligible_date": elig["next_eligible_date"], "total_donations": d.total_donations,
           "last_donation_date": d.last_donation_date.isoformat() if d.last_donation_date else None,
           "disclaimer": MEDICAL_DISCLAIMER}
    if private:
        out.update({"age": d.age,
                    "unavailable_until": d.unavailable_until.isoformat() if d.unavailable_until else None,
                    "requests_received": d.requests_received, "requests_accepted": d.requests_accepted,
                    "avg_response_minutes": d.avg_response_minutes})
    return out


def request_out(r: BloodRequest, viewer: User, detail: bool = False) -> dict:
    staff = viewer.role in ("coordinator", "admin")
    owner = viewer.id == r.requester_id
    c = counts(r)
    out = {
        "id": r.id, "blood_group": r.blood_group, "units_required": r.units_required,
        "units_arranged": r.units_arranged, "units_still_needed": units_still_needed(r),
        "hospital": {"id": r.hospital.id, "name": r.hospital.name, "city": r.hospital.city},
        "urgency": r.urgency, "ai_priority": r.ai_priority, "ai_confidence": r.ai_confidence,
        "priority": effective_priority(r.urgency, r.ai_priority), "ai_reasons": loads(r.ai_reasons),
        "ai_summary": r.ai_summary, "required_before": iso(r.required_before),
        "verification_status": r.verification_status, "request_status": r.request_status,
        "created_at": iso(r.created_at), "fulfilled_at": iso(r.fulfilled_at),
        "search_radius_km": r.search_radius_km, "wave": r.wave, "response_counts": c,
        "is_owner": owner,
    }
    if staff or owner:
        out.update({"patient_name": r.patient_name, "description": r.description,
                    "requester": {"id": r.requester.id, "name": r.requester.name,
                                  "phone": r.contact_phone or r.requester.phone}})
    if staff:
        out.update({"duplicate_of": r.duplicate_of, "suspicious_flags": loads(r.suspicious_flags),
                    "report_count": r.report_count})
    if detail:
        out["events"] = [{"message": e.message, "at": iso(e.created_at)} for e in r.events]
        if staff or owner:
            rs = []
            for resp in sorted(r.responses, key=lambda x: -x.match_score):
                item = {"id": resp.id, "match_score": resp.match_score, "distance_km": resp.distance_km,
                        "wave": resp.wave, "response_status": resp.response_status,
                        "notified_at": iso(resp.notified_at), "response_time": iso(resp.response_time),
                        "donation_confirmed": resp.donation_confirmed, "blood_group": resp.donor.blood_group}
                if resp.response_status in ("accepted", "donated"):
                    # contact details shared only after the donor accepted
                    item.update({"donor_name": resp.donor.user.name, "donor_phone": resp.donor.user.phone})
                else:
                    item["donor_name"] = "Compatible donor (hidden)"
                rs.append(item)
            out["responses"] = rs
    return out


def notification_out(n: Notification) -> dict:
    return {"id": n.id, "title": n.title, "body": n.body, "request_id": n.request_id, "read": n.read,
            "channels": n.channels.split(","), "delivery_status": n.delivery_status, "created_at": iso(n.created_at)}
