"""Tests for compatibility rules, AI helpers and the full request workflow.

Run from the backend folder:  python -m pytest -q
"""
import os
from datetime import date, datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite:///./test_bloodlink.db"
if os.path.exists("test_bloodlink.db"):
    os.remove("test_bloodlink.db")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from services.compatibility import can_donate_to, check_eligibility, compatible_donor_groups  # noqa: E402
from services import ai  # noqa: E402


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------- unit tests ----------
def test_compatibility_rules():
    assert compatible_donor_groups("O-") == ["O-"]
    assert len(compatible_donor_groups("AB+")) == 8
    assert can_donate_to("O-", "B+")
    assert not can_donate_to("A+", "B+")
    assert not can_donate_to("AB+", "O+")
    assert set(compatible_donor_groups("B+")) == {"B+", "B-", "O+", "O-"}


def test_eligibility():
    today = date(2026, 10, 1)
    assert check_eligibility(25, None, True, None, today)["eligible"]
    recent = check_eligibility(25, today - timedelta(days=30), True, None, today)
    assert not recent["eligible"] and recent["next_eligible_date"] == "2026-11-30"
    assert not check_eligibility(17, None, True, None, today)["eligible"]
    assert not check_eligibility(30, None, False, None, today)["eligible"]
    assert not check_eligibility(30, None, True, today + timedelta(days=3), today)["eligible"]


def test_priority_classifier():
    t = utcnow()
    assert ai.classify_priority("road accident heavy bleeding", t + timedelta(hours=3), 2, t)["priority"] == "critical"
    assert ai.classify_priority("scheduled surgery", t + timedelta(hours=20), 1, t)["priority"] == "urgent"
    assert ai.classify_priority("thalassemia transfusion", t + timedelta(days=4), 1, t)["priority"] == "normal"
    # AI can upgrade but never downgrade the requester's urgency
    assert ai.effective_priority("critical", "normal") == "critical"
    assert ai.effective_priority("normal", "urgent") == "urgent"


def test_response_likelihood():
    assert ai.response_likelihood(0, 0) == 0.5
    assert ai.response_likelihood(10, 9) > 0.8


# ---------- end-to-end workflow ----------
def login(c, email):
    r = c.post("/api/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_full_workflow():
    with TestClient(main.app) as c:
        req_h, coord_h, donor_h = (login(c, "requester@demo.com"), login(c, "coordinator@demo.com"),
                                   login(c, "donor@demo.com"))
        civil = next(h for h in c.get("/api/meta").json()["hospitals"] if h["name"].startswith("Civil"))

        # 1. requester submits a normal request -> pending verification
        body = {"patient_name": "Test Patient", "blood_group": "B+", "units_required": 2, "hospital_id": civil["id"],
                "urgency": "urgent", "description": "Patient needs surgery today",
                "required_before": (utcnow() + timedelta(hours=6)).isoformat() + "Z"}
        r = c.post("/api/requests", json=body, headers=req_h)
        assert r.status_code == 200, r.text
        rid = r.json()["request"]["id"]
        assert r.json()["request"]["request_status"] == "pending_verification"

        # duplicate detection on a second, near-identical request
        r2 = c.post("/api/requests", json=dict(body, patient_name="Test Patiant"), headers=req_h)
        assert any("duplicate" in w for w in r2.json()["warnings"])

        # 2. coordinator verifies -> wave 1 notifies max 5 donors within 5 km
        r = c.post(f"/api/requests/{rid}/verify", headers=coord_h).json()
        assert r["request_status"] == "donors_contacted"
        assert 0 < len(r["responses"]) <= 5
        assert all(x["distance_km"] <= 5 for x in r["responses"])
        # privacy: no names/phones before acceptance
        assert all("donor_phone" not in x for x in r["responses"])

        # candidates are ranked and only compatible groups appear
        cands = c.get(f"/api/requests/{rid}/candidates", headers=coord_h).json()
        assert all(x["blood_group"] in ("B+", "B-", "O+", "O-") for x in cands)

        # 3. demo donor (close by, reliable) is in the first wave and accepts
        inbox = c.get("/api/donors/me/requests", headers=donor_h).json()
        mine = next(x for x in inbox if x["request"]["id"] == rid)
        assert c.post(f"/api/responses/{mine['response_id']}/accept", headers=donor_h).status_code == 200

        detail = c.get(f"/api/requests/{rid}", headers=req_h).json()
        accepted = [x for x in detail["responses"] if x["response_status"] == "accepted"]
        assert accepted and accepted[0]["donor_phone"] == "03004440000"  # contact revealed after accept

        # 4. coordinator confirms donation -> partially fulfilled
        r = c.post(f"/api/responses/{accepted[0]['id']}/confirm", headers=coord_h).json()
        assert r["request_status"] == "partially_fulfilled" and r["units_arranged"] == 1

        # donor is now ineligible for 90 days
        me = c.get("/api/donors/me", headers=donor_h).json()
        assert not me["eligible"]

        # 5. manual escalation expands the search
        r = c.post(f"/api/requests/{rid}/escalate", headers=coord_h).json()
        assert r["request"]["wave"] >= 2

        # 6. requester closes the request
        r = c.post(f"/api/requests/{rid}/complete", headers=req_h).json()
        assert r["request_status"] == "completed"

        # dashboard works
        d = c.get("/api/analytics/dashboard", headers=coord_h).json()
        assert d["kpis"]["total_requests"] > 0 and d["insights"]


def test_permissions():
    with TestClient(main.app) as c:
        donor_h = login(c, "donor@demo.com")
        assert c.get("/api/analytics/dashboard", headers=donor_h).status_code == 403
        assert c.get("/api/admin/users", headers=login(c, "coordinator@demo.com")).status_code == 403
        assert c.get("/api/requests").status_code == 401
