"""Demo data so the dashboard, matching and forecasting have something real to show.

Run manually with:  python seed.py --reset
(main.py also seeds automatically on first start when the database is empty.)
"""
import random
import sys
from datetime import date, timedelta

from database import Base, engine, SessionLocal
from models import User, Donor, Hospital, BloodRequest, DonorResponse, RequestEvent, now
from auth import hash_password
from services import ai
from services.compatibility import compatible_donor_groups
from services.locations import AREAS, haversine_km

DEMO_PASSWORD = "demo123"

HOSPITALS = [
    ("Civil Hospital Karachi", "Karachi", 24.8587, 67.0100, "021-99215740"),
    ("Jinnah Postgraduate Medical Centre", "Karachi", 24.8517, 67.0447, "021-99201300"),
    ("Aga Khan University Hospital", "Karachi", 24.8920, 67.0745, "021-34930051"),
    ("Indus Hospital Korangi", "Karachi", 24.8406, 67.1427, "021-35112709"),
    ("Abbasi Shaheed Hospital", "Karachi", 24.9205, 67.0300, "021-99260400"),
    ("Liaquat University Hospital", "Hyderabad", 25.3960, 68.3690, "022-9210213"),
]

FIRST = ["Ahmed", "Ali", "Hassan", "Usman", "Bilal", "Hamza", "Fahad", "Zain", "Imran", "Saad", "Ayesha", "Fatima",
         "Sana", "Hira", "Maryam", "Zainab", "Amna", "Iqra", "Noor", "Kashif", "Rizwan", "Danish", "Sameer", "Farah",
         "Mehwish", "Asad", "Junaid", "Kiran", "Tariq", "Sobia"]
LAST = ["Khan", "Siddiqui", "Qureshi", "Shaikh", "Memon", "Baloch", "Ansari", "Raza", "Abbasi", "Soomro", "Jamali",
        "Malik", "Hussain", "Mirza", "Butt"]
# approximate blood group distribution in Pakistan
GROUP_WEIGHTS = {"B+": 30, "O+": 27, "A+": 22, "AB+": 8, "B-": 4, "O-": 4, "A-": 3, "AB-": 2}
DESCRIPTIONS = [
    ("Patient admitted after a road accident, heavy bleeding", "critical"),
    ("Scheduled surgery tomorrow morning", "urgent"),
    ("Thalassemia patient needs regular transfusion", "normal"),
    ("C-section delivery, doctor asked to arrange blood", "urgent"),
    ("Dengue patient with low platelets", "urgent"),
    ("Cancer patient on chemo, low hb", "normal"),
    ("Open heart operation planned", "urgent"),
    ("Postpartum hemorrhage in ICU", "critical"),
    ("Dialysis patient, anemia", "normal"),
    ("Burn victim in emergency ward", "critical"),
]


def pick_group(rng):
    return rng.choices(list(GROUP_WEIGHTS), weights=list(GROUP_WEIGHTS.values()))[0]


def seed(db, rng=None):
    rng = rng or random.Random(42)
    pw = hash_password(DEMO_PASSWORD)  # one hash reused for speed; every demo account uses demo123
    t = now()
    today = date.today()

    hospitals = [Hospital(name=n, city=c, lat=la, lng=lo, phone=p) for n, c, la, lo, p in HOSPITALS]
    db.add_all(hospitals)
    db.flush()
    civil = hospitals[0]

    admin = User(name="System Admin", email="admin@demo.com", phone="03001110000", password_hash=pw,
                 role="admin", phone_verified=True)
    coord = User(name="Dr. Sara Coordinator", email="coordinator@demo.com", phone="03002220000",
                 password_hash=pw, role="coordinator", phone_verified=True, hospital_id=civil.id)
    requester = User(name="Kamran Requester", email="requester@demo.com", phone="03003330000",
                     password_hash=pw, role="requester", phone_verified=True)
    demo_donor_user = User(name="Ahmed Donor", email="donor@demo.com", phone="03004440000", password_hash=pw,
                           role="donor", phone_verified=True)
    demo_donor_user.donor = Donor(blood_group="B+", age=27, area="Saddar", city="Karachi",
                                  lat=AREAS["Karachi"]["Saddar"][0], lng=AREAS["Karachi"]["Saddar"][1],
                                  last_donation_date=today - timedelta(days=200), total_donations=6,
                                  requests_received=14, requests_accepted=12, avg_response_minutes=6)
    db.add_all([admin, coord, requester, demo_donor_user])

    # second coordinator in Hyderabad + a few more requesters
    db.add(User(name="Dr. Imran Hyderabad", email="coordinator.hyd@demo.com", phone="03005550000",
                password_hash=pw, role="coordinator", phone_verified=True, hospital_id=hospitals[5].id, city="Hyderabad"))
    requesters = [requester]
    for i in range(6):
        u = User(name=f"{rng.choice(FIRST)} {rng.choice(LAST)}", email=f"family{i}@demo.com",
                 phone=f"0310{rng.randint(1000000, 9999999)}", password_hash=pw, role="requester",
                 phone_verified=rng.random() > 0.3)
        db.add(u)
        requesters.append(u)

    donors = [demo_donor_user.donor]
    for i in range(80):
        city = "Hyderabad" if rng.random() < 0.15 else "Karachi"
        area = rng.choice(list(AREAS[city]))
        lat, lng = AREAS[city][area]
        lat += rng.uniform(-0.008, 0.008)  # spread donors around the area centre
        lng += rng.uniform(-0.008, 0.008)
        received = rng.randint(0, 15)
        u = User(name=f"{rng.choice(FIRST)} {rng.choice(LAST)}", email=f"donor{i}@demo.com",
                 phone=f"0300{rng.randint(1000000, 9999999)}", password_hash=pw, role="donor",
                 phone_verified=True, city=city)
        last = None if rng.random() < 0.25 else today - timedelta(days=rng.randint(10, 420))
        u.donor = Donor(
            blood_group=pick_group(rng), age=rng.choice([rng.randint(18, 60)] * 9 + [rng.choice([17, 67])]),
            area=area, city=city, lat=lat, lng=lng, available=rng.random() > 0.12,
            unavailable_until=today + timedelta(days=rng.randint(2, 20)) if rng.random() < 0.06 else None,
            last_donation_date=last, total_donations=rng.randint(0, 12) if last else 0,
            requests_received=received, requests_accepted=int(received * rng.uniform(0.1, 0.95)),
            avg_response_minutes=round(rng.uniform(3, 90), 1) if received else 0)
        db.add(u)
        donors.append(u.donor)
    db.flush()

    # ---- historical requests (last 28 days) so analytics + forecasting are meaningful ----
    for i in range(85):
        age_days = int(rng.triangular(0, 28, 2))  # more recent activity
        created = t - timedelta(days=age_days, hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        group = rng.choices(list(GROUP_WEIGHTS), weights=[38 if g == "B+" and age_days < 7 else w
                                                          for g, w in GROUP_WEIGHTS.items()])[0]
        h = rng.choices(hospitals, weights=[30, 20, 15, 15, 10, 10])[0]
        desc, urg = rng.choice(DESCRIPTIONS)
        units = rng.choice([1, 1, 2, 2, 2, 3, 4])
        needed_by = created + timedelta(hours=rng.choice([4, 6, 12, 24, 48]))
        cls = ai.classify_priority(desc, needed_by, units, now=created)
        prio = ai.effective_priority(urg, cls["priority"])
        req = BloodRequest(
            requester_id=rng.choice(requesters).id, patient_name=f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            blood_group=group, units_required=units, hospital_id=h.id, urgency=urg,
            ai_priority=cls["priority"], ai_confidence=cls["confidence"], ai_reasons=ai.dumps(cls["reasons"]),
            ai_summary=ai.summarize_request(group, units, h.name, needed_by, prio, desc, now=created),
            required_before=needed_by, description=desc, verification_status="verified",
            created_at=created, wave=rng.randint(1, 3), search_radius_km=rng.choice([5, 10, 25]),
            last_wave_at=created + timedelta(minutes=5))
        if age_days == 0 and needed_by > t:
            continue  # keep "today" clean for the live demo; open demo requests are added below
        outcome = rng.choices(["completed", "fulfilled", "expired", "cancelled", "rejected"],
                              weights=[62, 14, 10, 8, 6])[0]
        req.request_status = outcome
        if outcome == "rejected":
            req.verification_status = "rejected"
        db.add(req)
        db.flush()
        db.add(RequestEvent(request_id=req.id, message="Request created", created_at=created))

        compatible = [d for d in donors if d.blood_group in compatible_donor_groups(group)
                      and d.city == h.city]
        rng.shuffle(compatible)
        contacted = compatible[:rng.randint(units + 1, units + 6)]
        donated = 0
        for d in contacted:
            notified = created + timedelta(minutes=rng.randint(2, 30))
            dist = round(haversine_km(h.lat, h.lng, d.lat, d.lng), 1)
            if outcome in ("completed", "fulfilled") and donated < units:
                st, donated = "donated", donated + 1
            elif outcome == "rejected":
                continue
            else:
                st = rng.choice(["declined", "no_response", "cancelled", "declined"])
            rt = notified + timedelta(minutes=rng.randint(2, 75)) if st in ("donated", "declined") else None
            db.add(DonorResponse(request_id=req.id, donor_id=d.id, match_score=rng.randint(55, 96), distance_km=dist,
                                 wave=1, response_status=st, notified_at=notified, response_time=rt,
                                 donation_confirmed=st == "donated"))
        if outcome in ("completed", "fulfilled"):
            req.units_arranged = units
            hours = rng.uniform(0.7, 4) if prio == "critical" else rng.uniform(1.5, 20)
            req.fulfilled_at = created + timedelta(hours=hours)
        elif outcome == "expired":
            req.units_arranged = rng.randint(0, units - 1) if units > 1 else 0

    # ---- a couple of open requests so every screen has content ----
    # 1. pending verification, from an unverified phone (shows in coordinator queue with flags)
    open1_deadline = t + timedelta(hours=30)
    d1 = "Scheduled operation, doctor asked to arrange blood"
    c1 = ai.classify_priority(d1, open1_deadline, 2)
    r1 = BloodRequest(requester_id=requesters[1].id, patient_name="Nadia Hussain", blood_group="A+", units_required=2,
                      hospital_id=hospitals[2].id, urgency="normal", ai_priority=c1["priority"],
                      ai_confidence=c1["confidence"], ai_reasons=ai.dumps(c1["reasons"]),
                      ai_summary=ai.summarize_request("A+", 2, hospitals[2].name, open1_deadline,
                                                      ai.effective_priority("normal", c1["priority"]), d1),
                      required_before=open1_deadline, description=d1, created_at=t - timedelta(minutes=40),
                      suspicious_flags=ai.dumps(["requester phone not verified"]))
    db.add(r1)
    db.flush()
    db.add(RequestEvent(request_id=r1.id, message="Request created by family - waiting for verification",
                        created_at=r1.created_at))
    db.commit()
    return {"hospitals": len(hospitals), "donors": len(donors)}


def reset_and_seed():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        return seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    if "--reset" in sys.argv:
        print("Reset + seeded:", reset_and_seed())
    else:
        print("Usage: python seed.py --reset   (drops ALL data and loads demo data)")
