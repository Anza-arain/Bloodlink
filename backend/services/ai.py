"""AI / intelligent features.

All models here are lightweight and explainable, and run fully offline
(no API key needed, so the demo works even on bad venue Wi-Fi):

1. classify_priority      - Normal / Urgent / Critical from text + time + units (with reasons)
2. summarize_request      - long description -> short donor-friendly message
3. find_duplicates        - repeated requests for same patient/hospital (fuzzy matching)
4. suspicious_signals     - spam / misuse heuristics for admin review
5. response_likelihood    - Bayesian estimate of whether a donor will accept
6. forecast_demand        - blood-group demand prediction + shortage risk
"""
import json
import re
from datetime import datetime, timedelta, timezone


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)
from difflib import SequenceMatcher

# ---------- 1. Priority classification ----------
CRITICAL_TERMS = {
    "accident": 3, "trauma": 3, "hemorrhage": 3, "haemorrhage": 3, "bleeding": 3, "unconscious": 3,
    "icu": 2, "emergency": 2, "critical": 3, "life threatening": 3, "dying": 3, "shock": 2,
    "gunshot": 3, "burn": 2, "postpartum": 3, "ventilator": 3, "hadsa": 3, "foran": 2,
}
URGENT_TERMS = {
    "surgery": 2, "operation": 2, "c-section": 2, "delivery": 2, "dengue": 2, "platelets": 1,
    "thalassemia": 1, "thalassaemia": 1, "anemia": 1, "anaemia": 1, "cancer": 1, "chemo": 1,
    "dialysis": 1, "urgent": 2, "asap": 2, "today": 1, "jaldi": 2, "low hb": 2, "transplant": 2,
}


def classify_priority(description: str, required_before: datetime, units: int,
                      now: datetime | None = None) -> dict:
    now = now or _utcnow()
    text = (description or "").lower()
    score, reasons = 0, []

    for term, w in CRITICAL_TERMS.items():
        if term in text:
            score += w * 2
            reasons.append(f"mentions '{term}'")
    for term, w in URGENT_TERMS.items():
        if term in text:
            score += w
            reasons.append(f"mentions '{term}'")

    hours = (required_before - now).total_seconds() / 3600
    if hours <= 6:
        score += 5
        reasons.append(f"needed within {max(hours, 0):.0f}h")
    elif hours <= 24:
        score += 3
        reasons.append("needed within 24h")
    elif hours > 72:
        score -= 2
        reasons.append("more than 3 days available")

    if units >= 4:
        score += 3
        reasons.append(f"{units} units is a large requirement")

    if score >= 9:
        level = "critical"
    elif score >= 4:
        level = "urgent"
    else:
        level = "normal"
    confidence = min(0.97, 0.55 + abs(score - (9 if level == "critical" else 4)) * 0.05 + len(reasons) * 0.03)
    return {"priority": level, "score": score, "confidence": round(confidence, 2),
            "reasons": reasons[:6] or ["no urgency signals found"]}


PRIORITY_RANK = {"normal": 0, "urgent": 1, "critical": 2}


def effective_priority(user_urgency: str, ai_priority: str) -> str:
    """Never downgrade what the requester said; AI may only upgrade."""
    return max([user_urgency or "normal", ai_priority or "normal"], key=lambda p: PRIORITY_RANK[p])


# ---------- 2. Donor-friendly summary ----------
CONDITION_TERMS = ["accident", "surgery", "operation", "c-section", "delivery", "dengue", "thalassemia",
                   "cancer", "dialysis", "transplant", "anemia", "burn", "trauma", "bleeding"]


def summarize_request(blood_group: str, units: int, hospital: str, required_before: datetime,
                      priority: str, description: str, now: datetime | None = None) -> str:
    now = now or _utcnow()
    hours = max(0, (required_before - now).total_seconds() / 3600)
    if hours <= 1:
        when = "needed within the hour"
    elif hours <= 24:
        when = f"needed within {round(hours)}h"
    else:
        when = f"needed within {round(hours / 24)} days"
    text = (description or "").lower()
    condition = next((c for c in CONDITION_TERMS if c in text), None)
    head = {"critical": "CRITICAL", "urgent": "URGENT", "normal": "Request"}[priority]
    unit_word = "unit" if units == 1 else "units"
    parts = [f"{head}: {blood_group} blood", f"{units} {unit_word}", hospital, when]
    if condition:
        parts.append(f"for {condition}")
    return " · ".join(parts)


# ---------- 3. Duplicate detection ----------
def _sim(a: str, b: str) -> float:
    a, b = (a or "").lower().strip(), (b or "").lower().strip()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def find_duplicates(candidate: dict, existing: list) -> list[dict]:
    """candidate: dict of the new request. existing: list of BloodRequest (open, recent)."""
    hits = []
    for r in existing:
        if r.hospital_id != candidate["hospital_id"] or r.blood_group != candidate["blood_group"]:
            continue
        name_sim = _sim(r.patient_name, candidate["patient_name"])
        desc_sim = _sim(r.description, candidate["description"])
        same_requester = r.requester_id == candidate["requester_id"]
        score = name_sim * 0.6 + desc_sim * 0.25 + (0.15 if same_requester else 0)
        if name_sim >= 0.8 or score >= 0.7:
            hits.append({"request_id": r.id, "similarity": round(score, 2),
                         "reason": f"same hospital + blood group, patient name {int(name_sim * 100)}% similar"})
    return sorted(hits, key=lambda h: -h["similarity"])


# ---------- 4. Misuse heuristics ----------
def suspicious_signals(candidate: dict, recent_by_requester: int, phone_verified: bool) -> list[str]:
    flags = []
    if recent_by_requester >= 3:
        flags.append(f"requester created {recent_by_requester} requests in 24h")
    if candidate["units_required"] > 8:
        flags.append("unusually high number of units")
    if not phone_verified:
        flags.append("requester phone not verified")
    desc = candidate.get("description") or ""
    if re.search(r"(https?://|bit\.ly|send money|jazzcash|easypaisa|payment)", desc, re.I):
        flags.append("description contains links or payment requests")
    if len(desc.strip()) < 10:
        flags.append("very short description")
    return flags


# ---------- 5. Donor response prediction ----------
def response_likelihood(received: int, accepted: int) -> float:
    """Bayesian (Laplace-smoothed) acceptance rate; new donors start at 50%."""
    return round((accepted + 1) / (received + 2), 2)


# ---------- 6. Demand forecasting ----------
def forecast_demand(requests: list, donors_by_group: dict, groups: list[str], compat: dict,
                    now: datetime | None = None) -> list[dict]:
    """Exponentially-weighted daily demand per blood group for the last 28 days -> next 7 days.

    shortage_risk compares predicted units against eligible donors who can give to that group.
    """
    now = now or _utcnow()
    out = []
    for g in groups:
        daily = [0.0] * 28
        for r in requests:
            if r.blood_group != g:
                continue
            age = (now - r.created_at).days
            if 0 <= age < 28:
                daily[27 - age] += r.units_required
        alpha, level = 0.3, daily[0]
        for v in daily[1:]:
            level = alpha * v + (1 - alpha) * level
        last7, prev7 = sum(daily[-7:]), sum(daily[-14:-7])
        trend = ((last7 - prev7) / prev7 * 100) if prev7 else (100.0 if last7 else 0.0)
        predicted = round(level * 7, 1)
        supply = sum(donors_by_group.get(d, 0) for d in compat[g])
        ratio = predicted / supply if supply else (9 if predicted else 0)
        risk = "high" if ratio > 0.8 else "medium" if ratio > 0.4 else "low"
        out.append({"blood_group": g, "last_7_days": last7, "predicted_next_7_days": predicted,
                    "trend_pct": round(trend), "eligible_supply": supply, "shortage_risk": risk})
    return sorted(out, key=lambda x: -x["predicted_next_7_days"])


def dumps(x) -> str:
    return json.dumps(x)


def loads(s: str):
    try:
        return json.loads(s or "[]")
    except json.JSONDecodeError:
        return []
