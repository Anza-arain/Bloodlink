import { useEffect, useState } from "react";
import { api, isoToLocalInput, localToIso } from "../api";
import { ErrorBox, Icon, Priority, useToast } from "../components/ui.jsx";

function PhoneVerify({ user, refreshUser }) {
  const [sent, setSent] = useState(null);
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");
  if (user.phone_verified) return null;
  return (
    <div className="alert warn" style={{ marginBottom: 16 }}>
      <div className="row spread">
        <span><b>Verify your phone</b> — verified requesters are trusted for critical fast-track matching.</span>
        {!sent ? (
          <button className="btn sm" onClick={() => api("/auth/send-otp", { method: "POST" }).then(setSent).catch((e) => setErr(e.message))}>Send code</button>
        ) : (
          <span className="row">
            <input style={{ width: 110 }} placeholder="6-digit code" value={code} onChange={(e) => setCode(e.target.value)} />
            <button className="btn sm primary" onClick={() => api("/auth/verify-otp", { method: "POST", body: { code } })
              .then(refreshUser).catch((e) => setErr(e.message))}>Verify</button>
          </span>
        )}
      </div>
      {sent?.dev_code && <div className="small" style={{ marginTop: 6 }}>Demo mode: SMS is simulated, your code is <b>{sent.dev_code}</b></div>}
      {err && <div className="small" style={{ marginTop: 6 }}>{err}</div>}
    </div>
  );
}

export default function NewRequest({ user, meta, go, refreshUser }) {
  const toast = useToast();
  const inSix = new Date(Date.now() + 6 * 3600e3);
  const [f, setF] = useState({ patient_name: "", blood_group: "B+", units_required: 2, hospital_id: "",
    urgency: "urgent", required_before: isoToLocalInput(inSix), description: "", contact_phone: "" });
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  useEffect(() => {
    if (!f.hospital_id && meta?.hospitals?.length) setF((x) => ({ ...x, hospital_id: meta.hospitals[0].id }));
  }, [meta]); // eslint-disable-line react-hooks/exhaustive-deps

  // live AI analysis while typing (debounced)
  useEffect(() => {
    if (!f.required_before) return;
    const t = setTimeout(() => {
      api("/ai/analyze", { method: "POST", body: { ...f, units_required: Number(f.units_required) || 1,
        hospital_id: Number(f.hospital_id) || null, required_before: localToIso(f.required_before) } })
        .then(setAnalysis).catch(() => {});
    }, 450);
    return () => clearTimeout(t);
  }, [f]);

  const example = () => setF({ ...f, patient_name: "Rashid Ali", blood_group: "B+", units_required: 2, urgency: "urgent",
    hospital_id: meta.hospitals.find((h) => h.name.startsWith("Civil"))?.id || f.hospital_id,
    required_before: isoToLocalInput(inSix),
    description: "B+ blood urgently required at Civil Hospital. Two units required within six hours. Patient admitted in ward 5, doctor asked the family to arrange blood." });

  const submit = async (e) => {
    e.preventDefault();
    setError(""); setBusy(true);
    try {
      const res = await api("/requests", { method: "POST", body: { ...f, units_required: Number(f.units_required),
        hospital_id: Number(f.hospital_id), required_before: localToIso(f.required_before) } });
      toast(res.request.request_status === "pending_verification"
        ? "Request submitted — waiting for hospital verification" : "Request verified — donors are being notified");
      go("detail", res.request.id);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };

  const c = analysis?.classification;
  return (
    <>
      {user.role === "requester" && <PhoneVerify user={user} refreshUser={refreshUser} />}
      <div className="grid g-side">
        <form className="card" onSubmit={submit}>
          <div className="card-head">
            <h2>Request details</h2>
            <button type="button" className="btn sm" onClick={example}>Fill example request</button>
          </div>
          <div className="form-grid">
            <label className="field">Patient name<input required value={f.patient_name} onChange={set("patient_name")} /></label>
            <label className="field">Blood group needed
              <select value={f.blood_group} onChange={set("blood_group")}>
                {meta?.blood_groups.map((g) => <option key={g}>{g}</option>)}
              </select>
            </label>
            <label className="field">Units required<input type="number" min={1} max={20} required value={f.units_required} onChange={set("units_required")} /></label>
            <label className="field">Urgency
              <select value={f.urgency} onChange={set("urgency")}>
                <option value="normal">Normal</option><option value="urgent">Urgent</option><option value="critical">Critical</option>
              </select>
            </label>
            <label className="field">Hospital / blood bank
              <select value={f.hospital_id} onChange={set("hospital_id")}>
                {meta?.hospitals.map((h) => <option key={h.id} value={h.id}>{h.name} — {h.city}</option>)}
              </select>
            </label>
            <label className="field">Required before<input type="datetime-local" required value={f.required_before} onChange={set("required_before")} /></label>
            <label className="field full">Description<span className="hint">Condition, ward, anything donors should know. AI reads this to set priority.</span>
              <textarea value={f.description} onChange={set("description")} maxLength={1000} />
            </label>
            <label className="field full">Contact phone (optional)<span className="hint">Shared only with donors who accept. Defaults to your account phone.</span>
              <input value={f.contact_phone} onChange={set("contact_phone")} placeholder={user.phone} />
            </label>
          </div>
          <div style={{ marginTop: 16 }}><ErrorBox error={error} /></div>
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn primary lg" disabled={busy}><Icon name="drop" size={16} /> {busy ? "Submitting…" : "Submit blood request"}</button>
          </div>
        </form>

        <div className="stack">
          <div className="ai-box">
            <div className="ai-tag"><Icon name="spark" size={12} /> AI analysis · live</div>
            {!c ? <p className="muted">Start typing to see the AI assessment.</p> : (
              <>
                <div className="row" style={{ marginTop: 10 }}>
                  <span className="muted small">AI priority</span><Priority p={c.priority} />
                  <span className="small muted">{Math.round(c.confidence * 100)}% confidence</span>
                </div>
                {analysis.effective_priority !== f.urgency && (
                  <div className="small" style={{ marginTop: 6 }}>Effective priority will be <b>{analysis.effective_priority}</b> (AI only ever upgrades, never downgrades your choice).</div>
                )}
                <ul className="small" style={{ margin: "8px 0", paddingLeft: 18 }}>{c.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                <div className="small muted" style={{ marginTop: 10 }}>What donors will see:</div>
                <div className="summary">{analysis.summary}</div>
              </>
            )}
          </div>
          {analysis?.duplicates?.length > 0 && (
            <div className="alert warn">
              <b>Possible duplicate.</b> Request #{analysis.duplicates[0].request_id} looks similar ({analysis.duplicates[0].reason}).
              You can still submit; staff will review it.
            </div>
          )}
          <div className="card small">
            <h3 style={{ marginBottom: 6 }}>What happens next</h3>
            <ol style={{ margin: 0, paddingLeft: 18, color: "var(--ink-2)" }}>
              <li>Hospital coordinator verifies the request (critical + verified phone is fast-tracked).</li>
              <li>Compatible, eligible donors are ranked by match score.</li>
              <li>The top 5 nearby donors are notified first; the radius expands only if needed.</li>
              <li>You see each donor's response and get their contact once they accept.</li>
            </ol>
          </div>
        </div>
      </div>
    </>
  );
}
