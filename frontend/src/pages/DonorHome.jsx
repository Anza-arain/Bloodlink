import { useEffect, useState } from "react";
import { api, ago, fmtDate, timeLeft } from "../api";
import { Blood, Empty, ErrorBox, Icon, Priority, Status, useToast } from "../components/ui.jsx";

export function EligibilityCard({ d, onToggle }) {
  if (!d) return null;
  return (
    <div className="card" style={{ borderLeft: `4px solid ${d.eligible ? "var(--green)" : "var(--amber)"}` }}>
      <div className="row spread">
        <div className="row" style={{ gap: 14 }}>
          <Blood g={d.blood_group} lg />
          <div>
            <h2>{d.eligible ? "You can donate" : "Not eligible right now"}</h2>
            <div className="small muted">
              {d.eligible ? "You will receive matching requests near " + d.area + "."
                : d.eligibility_reasons.join(" · ")}
              {d.next_eligible_date && ` · eligible again ${d.next_eligible_date}`}
            </div>
          </div>
        </div>
        <div className="row">
          <span className="small muted">{d.total_donations} donations</span>
          {onToggle && (
            <button className={"btn " + (d.available ? "" : "success")} onClick={onToggle}>
              {d.available ? "Pause (not available)" : "I'm available"}
            </button>
          )}
        </div>
      </div>
      <div className="small muted" style={{ marginTop: 10 }}>{d.disclaimer}</div>
    </div>
  );
}

export default function DonorHome({ tick, reloadNotifs }) {
  const toast = useToast();
  const [me, setMe] = useState(null);
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const load = () => {
    api("/donors/me").then(setMe).catch((e) => setError(e.message));
    api("/donors/me/requests").then(setItems).catch((e) => setError(e.message));
  };
  useEffect(load, [tick]);

  const respond = async (id, action) => {
    setError("");
    try {
      await api(`/responses/${id}/${action}`, { method: "POST" });
      toast(action === "accept" ? "Thank you! The requester can now contact you." : "Declined — we'll ask another donor.");
      load(); reloadNotifs();
    } catch (e) { setError(e.message); }
  };
  const toggle = () => api("/donors/me", { method: "PUT", body: { available: !me.available } }).then(setMe);

  const waiting = (items || []).filter((x) => x.response_status === "notified");
  const accepted = (items || []).filter((x) => x.response_status === "accepted");
  const history = (items || []).filter((x) => !["notified", "accepted"].includes(x.response_status));

  return (
    <div className="stack">
      <EligibilityCard d={me} onToggle={me && toggle} />
      <ErrorBox error={error} />

      <div className="card">
        <div className="card-head"><div><h2>Waiting for your answer</h2><p>You were chosen because you are compatible, eligible and close by.</p></div></div>
        {waiting.length === 0 ? <Empty>No new requests. We'll notify you when someone nearby needs your blood group.</Empty> : (
          <div className="grid g2">
            {waiting.map((x) => (
              <div key={x.response_id} className="card" style={{ margin: 0, borderColor: x.request.priority === "critical" ? "#f0a5b1" : undefined }}>
                <div className="row spread"><Priority p={x.request.priority} /><span className="small muted">{ago(x.notified_at)}</span></div>
                <div className="summary" style={{ marginTop: 8 }}>{x.request.summary}</div>
                <div className="row small muted">
                  <span><Icon name="hospital" size={13} /> {x.request.hospital}</span>
                  <span>~{x.distance_km} km away</span>
                  <span>{x.request.units_still_needed} unit(s) still needed</span>
                  <span>{timeLeft(x.request.required_before)}</span>
                </div>
                <div className="row" style={{ marginTop: 12 }}>
                  <button className="btn success" onClick={() => respond(x.response_id, "accept")}><Icon name="check" size={15} /> Accept</button>
                  <button className="btn" onClick={() => respond(x.response_id, "decline")}>Decline</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {accepted.length > 0 && (
        <div className="card">
          <h2 style={{ marginBottom: 12 }}>You accepted — please go to the hospital</h2>
          {accepted.map((x) => (
            <div key={x.response_id} className="alert ok" style={{ marginBottom: 8 }}>
              <b>{x.request.summary}</b>
              <div className="small" style={{ marginTop: 4 }}>
                Contact: {x.request.contact?.name} · <a href={`tel:${x.request.contact?.phone}`}>{x.request.contact?.phone}</a>
                {" · "}needed by {fmtDate(x.request.required_before)}
              </div>
              <button className="btn sm" style={{ marginTop: 8 }} onClick={() => respond(x.response_id, "decline")}>I can't make it anymore</button>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h2 style={{ marginBottom: 12 }}>Donation history</h2>
        {history.length === 0 ? <Empty>No history yet.</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Request</th><th>Hospital</th><th>Date</th><th>Your response</th></tr></thead>
            <tbody>{history.map((x) => (
              <tr key={x.response_id}>
                <td><Blood g={x.request.blood_group} /> <span className="small muted">#{x.request.id}</span></td>
                <td>{x.request.hospital}</td>
                <td className="small">{fmtDate(x.notified_at)}</td>
                <td><Status s={x.response_status} /></td>
              </tr>))}
            </tbody>
          </table></div>
        )}
      </div>
    </div>
  );
}
