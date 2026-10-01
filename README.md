# BloodLink — Smart Blood & Emergency Donor Network

A complete platform that takes a blood request from **"person needs blood"** to **"request fulfilled → statistics updated"**:

```
Blood Request → Verification → Compatibility Check → Smart Donor Ranking → Notification Waves
→ Donor Accept/Decline → Donation Confirmed → Request Completed → Dashboard & AI Forecast
```

**Stack:** Python FastAPI · SQLite (SQLAlchemy) · React (Vite) · JWT auth · offline explainable AI (no API key needed)

---

## 1. Run it locally (5 minutes)

**Requirements:** Python 3.10+ and Node.js 18+.

```bash
# 1) Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate      Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```
The database is created and filled with demo data automatically on first start.
API docs: http://localhost:8000/docs

```bash
# 2) Frontend (new terminal)
cd frontend
npm install
npm run dev
```
Open **http://localhost:5173**.

> **Shortcut:** the `frontend/dist` folder is already built. If you only run the backend, open **http://localhost:8000** — FastAPI serves the React app too. (Re-run `npm run build` after changing frontend code.)

### Demo accounts (password `demo123`, or one-click buttons on the login page)
| Role | Email |
|---|---|
| Requester (patient's family) | requester@demo.com |
| Donor (Ahmed, B+, Saddar) | donor@demo.com |
| Hospital coordinator (Civil Hospital) | coordinator@demo.com |
| Administrator | admin@demo.com |

### Reset demo data between rehearsals
After a demo, Ahmed has "donated" and is ineligible for 90 days. Reset with:
- Admin dashboard → **Reset demo data** button, or
- `cd backend && python seed.py --reset`

### Run tests
```bash
cd backend && python -m pytest -q      # 6 tests incl. the full end-to-end workflow
```

---

## 2. Live demo script (≈4 minutes — use this for the video too)

| # | Who | Do this | Say this |
|---|---|---|---|
| 1 | Login page | Show the flow chips | "Families today search through WhatsApp groups. BloodLink finds the *right* donor, not just any donor." |
| 2 | **Requester** | New blood request → **Fill example request** (B+, Civil Hospital, 2 units, 6 h) | Point at the **AI analysis** box: priority, confidence, reasons, and the short donor-friendly summary. |
| 3 | Requester | Submit | Status flow shows **Pending verification**. Fake requests can't reach donors. |
| 4 | **Coordinator** | Dashboard → Verification queue → open the request | Show AI flags (unverified phone, duplicates). |
| 5 | Coordinator | **Verify & start matching** | "Only the top 5 donors within 5 km are notified — not everyone." Show **Smart donor ranking**: match scores, *why?* tooltip, ineligible donors greyed out. Names are hidden. |
| 6 | **Donor** | Requests for me → **Accept** | Donor sees only the summary + approx distance. After accepting they see the family's contact. |
| 7 | **Requester** | My requests → open | Ahmed's name and phone now appear (privacy: shared only after acceptance). |
| 8 | **Coordinator** | **Confirm donation** | Units 1/2 → Partially fulfilled. Ahmed becomes ineligible for 90 days automatically. Click **Notify next wave** to show radius expansion (5 → 10 → 25 → 50 km). |
| 9 | **Admin** | Dashboard & AI | KPIs, 14-day trend, **AI insights**, **demand forecast with shortage risk**, flagged requests, users (block), hospitals. |
| 10 | Bonus | As requester, create a request with *"road accident, heavy bleeding"* needed in 3 h | AI classifies **Critical** and a phone-verified requester is **fast-tracked** — matching starts instantly. |

**Extra talking points:** accepting enough donors auto-cancels pending notifications; a decline triggers the next wave immediately if pending donors can't cover the need; a background scheduler escalates unanswered waves (10 min critical / 30 min urgent / 2 h normal) and expires overdue requests.

---

## 3. What judges asked for → where it is

| Requirement | Implementation |
|---|---|
| 4 user roles | Requester, Donor, Coordinator, Admin — JWT + role checks on every endpoint |
| Real compatibility rules | `services/compatibility.py` — full ABO/Rh red-cell table (O− universal donor, AB+ universal recipient) |
| Eligibility | Age 18–65, 90-day donation gap, availability, temporary unavailability; disclaimer that staff confirm final eligibility |
| Smart matching | `services/matching.py` — 0–100 score from distance, response history, compatibility (conserves O−), rest period, response speed; weights change with urgency |
| Notification & escalation | `services/request_manager.py` — waves 5/10/10/15 donors at 5/10/25/50 km, auto-stop when enough accept, in-app + email/SMS/push (simulated, SMTP optional) |
| Statuses | Pending Verification → Active → Donors Contacted → Partially Fulfilled → Fulfilled → Completed, plus Cancelled / Expired / Rejected |
| AI features | Priority classification (with reasons), request summarization, duplicate detection, misuse heuristics, donor response prediction, demand forecasting + shortage risk, auto-generated insights |
| Privacy | Only area stored (no home address); names/phones hidden until acceptance; donor registry hides phones |
| Security | PBKDF2 passwords, JWT, role checks, Pydantic validation, OTP phone verification, request reporting, admin block, graceful DB/notification error handling, secrets via env vars |
| Search & dashboard | Filters by blood group, city, hospital, status, date, urgency, verification; dashboard with all requested statistics |

---

## 4. Deploy (get a public link for judges)

**Render.com (free):**
1. Push this folder to a GitHub repo (see below).
2. Render → **New + → Blueprint** → select the repo. `render.yaml` builds both frontend and backend into one service.
3. Wait ~5 min → open the `.onrender.com` link. Demo data loads automatically.

*(Free instances sleep after inactivity — open the link 1 minute before judging.)*

**Push to GitHub:**
```bash
git init && git add . && git commit -m "BloodLink - Smart Blood & Emergency Donor Network"
git branch -M main
git remote add origin https://github.com/<your-username>/bloodlink.git
git push -u origin main
```

### Environment variables (optional)
| Variable | Purpose |
|---|---|
| `SECRET_KEY` | JWT signing key (set in production) |
| `DATABASE_URL` | e.g. a PostgreSQL URL; defaults to SQLite |
| `DEMO_MODE` | `true` shows OTP codes on screen and allows demo reset |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` | Send real emails |
| `MAINTENANCE_SECONDS` | Scheduler interval (default 60) |

---

## 5. Project structure
See `Project_Explanation.pdf` (submission document). Short version:

```
backend/
  main.py              starts the app, scheduler, serves frontend
  database.py          database connection
  models.py            tables: users, donors, hospitals, requests, responses, events, notifications
  schemas.py           input validation
  auth.py              password hashing, JWT, roles
  serializers.py       JSON output + privacy rules
  seed.py              demo data
  routers/             API endpoints (auth, requests, donors, admin/analytics)
  services/            compatibility, matching, request_manager, notifications, ai, locations
  tests/               unit + end-to-end tests
frontend/
  src/App.jsx          layout, navigation per role, notifications
  src/api.js           API client
  src/pages/           Login, NewRequest, RequestsList, RequestDetail, DonorHome, DonorProfile, Dashboard, ...
  src/components/ui.jsx  badges, charts, icons
```

> Medical note: BloodLink is a coordination tool. Final medical eligibility must be confirmed by qualified healthcare staff or the receiving blood facility.
