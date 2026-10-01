import { useCallback, useEffect, useState } from "react";
import { api, fmtDate, timeLeft, label } from "../api";
import { Blood, Empty, ErrorBox, Icon, Priority, Score, Status, StatusFlow, Verified, useToast } from "../components/ui.jsx";

const CLOSED = ["completed", "cancelled", "expired", "rejected"];

function FactorTip({ f }) {
  const text = Object.entries(f).map(([k, v]) => `${label(k)}: +${v}`).join("\n");
  return <span title={text} style={{ cursor: "help", borderBottom: "1px dotted var(--muted)" }} className="small muted">why?</span>;
}

export default function RequestDetail({ id, user, meta, go, tick, reloadNotifs }) {
  const toast = useToast();
  const [r, setR] = useState(null);
  const [cands, setCands] = useState(null);
  const [error, setError] = useState("");
  const staff = ["coordinator", "admin"].includes(user.role);

  const load = useCallback(() => {
    api(`/requests/${id}`).then(setR).catch((e) => setError(e.message));
    if (staff) api(`/requests/${id}/candidates`).then(setCands).catch(() => {});
  }, [id, staff]);
  useEffect(load, [load, tick]);

  const act = async (path, body, msg) => {
    setError("");
    try {
      const res = await api(`/requests/${id}/${path}`, { method: "POST", body });
      toast(path === "escalate" && res.notified === 0 ? "No more eligible donors within 50 km — contact the blood bank" : msg);
      load(); reloadNotifs();
    }
    catch (e) { setError(e.message); }
  };
  const confirm = async (respId) => {
    try { await api(`/responses/${respId}/confirm`, { method: "POST" }); toast("Donation confirmed"); load(); }
    catch (e) { setError(e.message); }
  };

  if (error && !r) return <ErrorBox error={error} />;
  if (!r) return <Empty>Loading…</Empty>;
  const open = !CLOSED.includes(r.request_status);
  const canManage = staff || r.is_owner;

  return (
    <div className="stack">
      <button className="btn ghost sm" onClick={() => go(user.role === "requester" ? "mine" : "all")}>← Back to requests</button>
      <ErrorBox error={error} />

      <div className="card">
        <div className="row spread" style={{ alignItems: "flex-start" }}>
          <div className="row" style={{ alignItems: "flex-start", gap: 14 }}>
            <Blood g={r.blood_group} lg />
            <div>
              <h2>Request #{r.id} · {r.hospital.name}</h2>
              <div className="row small muted" style={{ marginTop: 4 }}>
                <span>{r.hospital.city}</span>·<span>needed by {fmtDate(r.required_before)}</span>
                {open && <b style={{ color: "var(--red)" }}>({timeLeft(r.required_before)})</b>}
              </div>
              <div className="row" style={{ marginTop: 8 }}>
                <Priority p={r.priority} /><Status s={r.request_status} /><Verified v={r.verification_status} />
              </div>
            </div>
          </div>
          <div className="row">
            {staff && r.request_status === "pending_verification" && (
              <>
                <button className="btn success" onClick={() => act("verify", null, "Verified — matching donors now")}><Icon name="check" size={15} /> Verify & start matching</button>
                <button className="btn" onClick={() => { const reason = prompt("Reason for rejection?"); if (reason) act("reject", { reason }, "Request rejected"); }}>Reject</button>
              </>
            )}
            {canManage && ["active", "donors_contacted", "partially_fulfilled"].includes(r.request_status) && (
              <button className="btn" onClick={() => act("escalate", null, "Next wave of donors notified")}>Notify next wave</button>
            )}
            {canManage && open && r.request_status !== "pending_verification" && (
              <button className="btn primary" onClick={() => act("complete", null, "Request closed")}>Mark completed</button>
            )}
            {canManage && open && (
              <button className="btn ghost" onClick={() => confirm_cancel(() => act("cancel", null, "Request cancelled"))}>Cancel</button>
            )}
            {!canManage && open && (
              <button className="btn ghost" onClick={() => { const reason = prompt("Why is this request suspicious?"); if (reason) act("report", { reason }, "Reported to admin"); }}>
                <Icon name="flag" size={14} /> Report
              </button>
            )}
          </div>
        </div>
        <StatusFlow status={r.request_status} />

        <div className="grid g4" style={{ marginTop: 16 }}>
          <div><div className="small muted">Units arranged</div><div style={{ fontSize: 22, fontWeight: 800 }} className="mono">{r.units_arranged} / {r.units_required}</div>
            <div className="progress"><div style={{ width: `${(r.units_arranged / r.units_required) * 100}%` }} /></div></div>
          <div><div className="small muted">Donors notified</div><div style={{ fontSize: 22, fontWeight: 800 }} className="mono">{(r.responses || []).length}</div>
            <div className="small muted">wave {r.wave || 0} · radius {r.search_radius_km || 0} km</div></div>
          <div><div className="small muted">Accepted</div><div style={{ fontSize: 22, fontWeight: 800, color: "var(--green)" }} className="mono">{r.response_counts.accepted + r.response_counts.donated}</div>
            <div className="small muted">{r.response_counts.declined} declined</div></div>
          <div><div className="small muted">Still needed</div><div style={{ fontSize: 22, fontWeight: 800, color: r.units_still_needed ? "var(--red)" : "var(--green)" }} className="mono">{r.units_still_needed}</div>
            <div className="small muted">units not yet pledged</div></div>
        </div>
      </div>

      <div className="grid g-side">
        <div className="stack">
          {(staff || r.is_owner) && (
            <div className="card">
              <div className="card-head"><div><h2>Donor responses</h2><p>Names and phone numbers appear only after a donor accepts.</p></div></div>
              {!r.responses?.length ? <Empty>{r.request_status === "pending_verification" ? "Donors are contacted after verification." : "No donors contacted yet."}</Empty> : (
                <div className="table-wrap"><table>
                  <thead><tr><th>Donor</th><th>Group</th><th>Match</th><th>Distance</th><th>Wave</th><th>Status</th><th></th></tr></thead>
                  <tbody>
                    {r.responses.map((x) => (
                      <tr key={x.id} className={["cancelled", "no_response", "declined"].includes(x.response_status) ? "dim" : ""}>
                        <td><b>{x.donor_name}</b>{x.donor_phone && <div className="small"><a href={`tel:${x.donor_phone}`}>{x.donor_phone}</a></div>}</td>
                        <td><Blood g={x.blood_group} /></td>
                        <td><Score value={x.match_score} /></td>
                        <td className="mono">{x.distance_km} km</td>
                        <td className="mono">{x.wave}</td>
                        <td><Status s={x.response_status} /></td>
                        <td>{staff && x.response_status === "accepted" && <button className="btn sm success" onClick={() => confirm(x.id)}>Confirm donation</button>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table></div>
              )}
            </div>
          )}

        </div>

        <div className="stack">
          <div className="ai-box">
            <div className="ai-tag"><Icon name="spark" size={12} /> AI assessment</div>
            <div className="summary">{r.ai_summary}</div>
            <div className="row small"><span className="muted">AI priority</span><Priority p={r.ai_priority} />
              <span className="muted">{Math.round(r.ai_confidence * 100)}% confidence · requester said {r.urgency}</span></div>
            <ul className="small" style={{ margin: "8px 0 0", paddingLeft: 18 }}>{r.ai_reasons.map((x) => <li key={x}>{x}</li>)}</ul>
          </div>

          {staff && (r.suspicious_flags?.length > 0 || r.duplicate_of) && (
            <div className="alert warn">
              <b>Review flags</b>
              <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{r.suspicious_flags.map((x) => <li key={x}>{x}</li>)}</ul>
              {r.duplicate_of && <button className="btn sm" style={{ marginTop: 8 }} onClick={() => go("detail", r.duplicate_of)}>Open request #{r.duplicate_of}</button>}
            </div>
          )}

          {(staff || r.is_owner) && (
            <div className="card">
              <h3>Patient & requester</h3>
              <div className="small" style={{ marginTop: 8, display: "grid", gap: 4 }}>
                <div><span className="muted">Patient:</span> {r.patient_name}</div>
                <div><span className="muted">Requester:</span> {r.requester?.name} · {r.requester?.phone}</div>
                {r.description && <div><span className="muted">Description:</span> {r.description}</div>}
                <div><span className="muted">Created:</span> {fmtDate(r.created_at)}</div>
              </div>
            </div>
          )}

          <div className="card">
            <h3 style={{ marginBottom: 12 }}>Timeline</h3>
            <ul className="timeline">
              {r.events.map((e, i) => <li key={i}><div className="small">{e.message}</div><div className="small muted">{fmtDate(e.at)}</div></li>)}
            </ul>
          </div>
          <div className="small muted">{meta?.disclaimer}</div>
        </div>
      </div>

      {staff && (
        <div className="card">
          <div className="card-head"><div><h2>Smart donor ranking</h2>
            <p>All compatible donors within 60 km, scored on distance, response history, compatibility, rest period and speed.</p></div></div>
          {!cands ? <Empty>Loading…</Empty> : cands.length === 0 ? <Empty>No compatible donors registered nearby.</Empty> : (
            <div className="table-wrap" style={{ maxHeight: 420, overflowY: "auto" }}><table>
              <thead><tr><th>Rank</th><th>Donor</th><th>Group</th><th>Distance</th><th>Eligible</th><th>Reply odds</th><th>Match score</th></tr></thead>
              <tbody>
                {cands.map((d) => (
                  <tr key={d.donor_id} className={d.eligible ? "" : "dim"}>
                    <td className="mono muted">{d.rank}</td>
                    <td>{d.name}<div className="small muted">{d.area}{d.contact_status ? ` · ${label(d.contact_status)}` : ""}</div></td>
                    <td><Blood g={d.blood_group} /></td>
                    <td className="mono">{d.distance_km} km</td>
                    <td>{d.eligible ? <span className="badge b-green">Yes</span> : <span className="badge b-gray" title={d.eligibility_reasons.join("\n")}>No</span>}</td>
                    <td className="mono">{Math.round(d.response_likelihood * 100)}%</td>
                    <td><div className="row" style={{ gap: 6 }}><Score value={d.match_score} />{d.eligible && <FactorTip f={d.factors} />}</div></td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
        </div>
      )}
    </div>
  );
}

function confirm_cancel(fn) {
  if (window.confirm("Cancel this request? Notified donors will be told no action is needed.")) fn();
}
