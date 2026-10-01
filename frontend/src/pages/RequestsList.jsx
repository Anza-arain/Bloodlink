import { useEffect, useState } from "react";
import { api, ago, label, timeLeft } from "../api";
import { Blood, Empty, ErrorBox, Icon, Priority, Status } from "../components/ui.jsx";

export default function RequestsList({ user, meta, go, tick, mine, preset = {}, flagged }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [f, setF] = useState({ q: "", blood_group: "", city: "", hospital_id: "", status: "", priority: "",
    verification: "", date_from: "", date_to: "", ...preset });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  useEffect(() => {
    const t = setTimeout(() => {
      const p = flagged ? api("/admin/flagged") : api("/requests", { params: { ...f, mine: mine || undefined } });
      p.then(setRows).catch((e) => setError(e.message));
    }, 250);
    return () => clearTimeout(t);
  }, [f, tick, mine, flagged]);

  return (
    <div className="card">
      {!flagged && (
        <div className="filters">
          <input placeholder="Search patient, hospital…" value={f.q} onChange={set("q")} />
          <select value={f.blood_group} onChange={set("blood_group")}>
            <option value="">All blood groups</option>{meta?.blood_groups.map((g) => <option key={g}>{g}</option>)}
          </select>
          <select value={f.city} onChange={set("city")}>
            <option value="">All cities</option>{Object.keys(meta?.areas || {}).map((c) => <option key={c}>{c}</option>)}
          </select>
          <select value={f.hospital_id} onChange={set("hospital_id")}>
            <option value="">All hospitals</option>{meta?.hospitals.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
          </select>
          <select value={f.status} onChange={set("status")}>
            <option value="">All statuses</option><option value="open">Open (any)</option>
            {meta?.statuses.map((s) => <option key={s} value={s}>{label(s)}</option>)}
          </select>
          <select value={f.priority} onChange={set("priority")}>
            <option value="">All urgency</option><option value="critical">Critical</option>
            <option value="urgent">Urgent</option><option value="normal">Normal</option>
          </select>
          <select value={f.verification} onChange={set("verification")}>
            <option value="">Any verification</option><option value="pending">Pending</option>
            <option value="verified">Verified</option><option value="rejected">Rejected</option>
          </select>
          <input type="date" title="Created from" value={f.date_from} onChange={set("date_from")} />
          <input type="date" title="Created until" value={f.date_to} onChange={set("date_to")} />
        </div>
      )}
      <ErrorBox error={error} />
      {rows && rows.length === 0 && (
        <Empty>
          No requests found.
          {mine && <div style={{ marginTop: 10 }}><button className="btn primary" onClick={() => go("new")}><Icon name="plus" size={15} /> Create a request</button></div>}
        </Empty>
      )}
      {rows && rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr>
              <th>#</th><th>Blood</th><th>Hospital</th><th>Units</th><th>Priority</th><th>Status</th>
              <th>{flagged ? "Flags" : "Needed by"}</th><th>Created</th>
            </tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="clickable" onClick={() => go("detail", r.id)}>
                  <td className="muted mono">{r.id}</td>
                  <td><Blood g={r.blood_group} /></td>
                  <td><b>{r.hospital.name}</b><div className="small muted">{r.hospital.city}{r.patient_name ? ` · ${r.patient_name}` : ""}</div></td>
                  <td style={{ minWidth: 90 }}>
                    <div className="mono small">{r.units_arranged}/{r.units_required}</div>
                    <div className="progress"><div style={{ width: `${(r.units_arranged / r.units_required) * 100}%` }} /></div>
                  </td>
                  <td><Priority p={r.priority} /></td>
                  <td><Status s={r.request_status} />{r.verification_status === "verified" && <span title="Verified" style={{ color: "var(--green)", marginLeft: 4 }}>✓</span>}</td>
                  <td className="small">
                    {flagged ? (r.suspicious_flags || []).join("; ") || (r.duplicate_of ? `duplicate of #${r.duplicate_of}` : "reported")
                      : ["completed", "cancelled", "expired", "rejected", "fulfilled"].includes(r.request_status)
                        ? <span className="muted">—</span> : timeLeft(r.required_before)}
                  </td>
                  <td className="small muted">{ago(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!rows && !error && <Empty>Loading…</Empty>}
    </div>
  );
}
