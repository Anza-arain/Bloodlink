"""Blood-group compatibility and donor eligibility rules.

Red-cell compatibility (who can GIVE to a patient):
  O-  -> universal donor            AB+ -> universal recipient
Eligibility rules are a screening aid only. Final medical eligibility
must be confirmed by qualified healthcare staff at the blood facility.
"""
from datetime import date, timedelta

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

# recipient blood group -> donor blood groups that can safely give red cells
COMPATIBLE_DONORS = {
    "O-":  ["O-"],
    "O+":  ["O+", "O-"],
    "A-":  ["A-", "O-"],
    "A+":  ["A+", "A-", "O+", "O-"],
    "B-":  ["B-", "O-"],
    "B+":  ["B+", "B-", "O+", "O-"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "AB+": ["AB+", "AB-", "A+", "A-", "B+", "B-", "O+", "O-"],
}

MIN_AGE, MAX_AGE = 18, 65
DONATION_GAP_DAYS = 90  # minimum gap between whole-blood donations (3 months)

MEDICAL_DISCLAIMER = ("Final medical eligibility must be confirmed by qualified healthcare "
                      "staff or the receiving blood facility.")


def compatible_donor_groups(recipient_group: str) -> list[str]:
    if recipient_group not in COMPATIBLE_DONORS:
        raise ValueError(f"Unknown blood group: {recipient_group}")
    return COMPATIBLE_DONORS[recipient_group]


def can_donate_to(donor_group: str, recipient_group: str) -> bool:
    return donor_group in COMPATIBLE_DONORS.get(recipient_group, [])


def check_eligibility(age: int, last_donation: date | None, available: bool,
                      unavailable_until: date | None, today: date | None = None) -> dict:
    """Returns {eligible, reasons[], next_eligible_date}."""
    today = today or date.today()
    reasons = []
    next_date = None
    if age < MIN_AGE:
        reasons.append(f"Under minimum age ({MIN_AGE})")
    if age > MAX_AGE:
        reasons.append(f"Over maximum age ({MAX_AGE})")
    if last_donation:
        gap_end = last_donation + timedelta(days=DONATION_GAP_DAYS)
        if gap_end > today:
            reasons.append(f"Donated {(today - last_donation).days} days ago (needs {DONATION_GAP_DAYS})")
            next_date = gap_end
    if unavailable_until and unavailable_until >= today:
        reasons.append(f"Temporarily unavailable until {unavailable_until.isoformat()}")
        next_date = max(next_date or unavailable_until, unavailable_until + timedelta(days=1))
    if not available:
        reasons.append("Marked as not available")
    return {"eligible": not reasons, "reasons": reasons,
            "next_eligible_date": next_date.isoformat() if next_date else None}
