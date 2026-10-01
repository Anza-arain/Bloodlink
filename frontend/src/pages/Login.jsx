import { useState } from "react";
import { api } from "../api";
import { ErrorBox, Icon } from "../components/ui.jsx";

const DEMOS = [
  ["requester@demo.com", "Requester", "Patient's family"],
  ["donor@demo.com", "Donor", "Ahmed · B+ · Saddar"],
  ["coordinator@demo.com", "Coordinator", "Civil Hospital"],
  ["admin@demo.com", "Administrator", "Dashboard & AI"],
];

export default function Login({ onLogin, meta }) {
  const [tab, setTab] = useState("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [f, setF] = useState({ email: "", password: "", name: "", phone: "", role: "donor", city: "Karachi",
    blood_group: "B+", age: 25, area: "", last_donation_date: "" });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e, demoEmail) => {
    e?.preventDefault();
    setError(""); setBusy(true);
    try {
      if (demoEmail || tab === "login") {
        onLogin(await api("/auth/login", { method: "POST",
          body: { email: demoEmail || f.email, password: demoEmail ? "demo123" : f.password } }));
      } else {
        const body = { name: f.name, email: f.email, phone: f.phone, password: f.password, role: f.role, city: f.city };
        if (f.role === "donor") Object.assign(body, { blood_group: f.blood_group, age: Number(f.age),
          area: f.area || meta?.areas[f.city][0], last_donation_date: f.last_donation_date || null });
        onLogin(await api("/auth/register", { method: "POST", body }));
      }
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };

  return (
    <div className="auth">
      <section className="auth-hero">
        <div className="row"><div className="brand-mark" style={{ background: "#fff" }}><Icon name="drop" color="#c8102e" /></div>
          <b style={{ fontSize: 18 }}>BloodLink</b></div>
        <div>
          <h1>Find the right donor,<br />not just any donor.</h1>
          <p>Smart Blood & Emergency Donor Network connects patients with compatible, eligible donors nearby —
            ranked by AI, notified in waves, tracked until every unit is arranged.</p>
          <div className="flow">
            {["Request", "Compatibility check", "Smart matching", "Notification waves", "Donor response",
              "Donation confirmed", "Analytics"].map((s) => <span key={s}>{s}</span>)}
          </div>
        </div>
        <small style={{ color: "#fecdd3" }}>Final medical eligibility is always confirmed by qualified healthcare staff.</small>
      </section>

      <section className="auth-panel">
        <div className="auth-box">
          <div className="tabs">
            <button className={tab === "login" ? "on" : ""} onClick={() => setTab("login")}>Log in</button>
            <button className={tab === "register" ? "on" : ""} onClick={() => setTab("register")}>Create account</button>
          </div>

          <form onSubmit={submit} className="stack" style={{ display: "grid", gap: 12 }}>
            {tab === "register" && (
              <>
                <div className="tabs" style={{ marginBottom: 0 }}>
                  <button type="button" className={f.role === "donor" ? "on" : ""} onClick={() => setF({ ...f, role: "donor" })}>I want to donate</button>
                  <button type="button" className={f.role === "requester" ? "on" : ""} onClick={() => setF({ ...f, role: "requester" })}>I need blood</button>
                </div>
                <label className="field">Full name<input required value={f.name} onChange={set("name")} /></label>
                <label className="field">Phone<input required placeholder="03001234567" value={f.phone} onChange={set("phone")} /></label>
              </>
            )}
            <label className="field">Email<input required type="email" value={f.email} onChange={set("email")} /></label>
            <label className="field">Password<input required type="password" minLength={6} value={f.password} onChange={set("password")} /></label>
            {tab === "register" && (
              <div className="form-grid">
                <label className="field">City
                  <select value={f.city} onChange={(e) => setF({ ...f, city: e.target.value, area: "" })}>
                    {Object.keys(meta?.areas || {}).map((c) => <option key={c}>{c}</option>)}
                  </select>
                </label>
                {f.role === "donor" && (
                  <>
                    <label className="field">Area<span className="hint">No exact address needed</span>
                      <select value={f.area} onChange={set("area")}>
                        {(meta?.areas[f.city] || []).map((a) => <option key={a}>{a}</option>)}
                      </select>
                    </label>
                    <label className="field">Blood group
                      <select value={f.blood_group} onChange={set("blood_group")}>
                        {(meta?.blood_groups || []).map((g) => <option key={g}>{g}</option>)}
                      </select>
                    </label>
                    <label className="field">Age<input type="number" min={16} max={80} value={f.age} onChange={set("age")} /></label>
                    <label className="field full">Last donation date (optional)
                      <input type="date" value={f.last_donation_date} onChange={set("last_donation_date")} /></label>
                  </>
                )}
              </div>
            )}
            <ErrorBox error={error} />
            <button className="btn primary lg" disabled={busy}>{busy ? "Please wait…" : tab === "login" ? "Log in" : "Create account"}</button>
          </form>

          <div style={{ marginTop: 26 }}>
            <div className="small muted" style={{ marginBottom: 8, fontWeight: 600 }}>DEMO ACCOUNTS · one click (password demo123)</div>
            <div className="demo-grid">
              {DEMOS.map(([email, role, sub]) => (
                <button key={email} className="demo-btn" disabled={busy} onClick={(e) => submit(e, email)}>
                  <b>{role}</b><small>{sub}</small>
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
