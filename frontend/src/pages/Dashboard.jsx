import { useEffect, useState } from "react";
import { api, label } from "../api";
import { Bars, Blood, Empty, ErrorBox, Icon, useToast } from "../components/ui.jsx";

const Kpi = ({ label: l, value, hint, accent }) => (
  <div className={"card kpi" + (accent ? " accent" : "")} style={{ margin: 0 }}>
    <div className="label">{l}</div><div className="value">{value}</div>{hint && <div className="hint">{hint}</div>}
  </div>
);
const riskClass = { high: "b-red", medium: "b-amber", low: "b-green" };

export default function Dashboard({ tick, go, user }) {
  const toast = useToast();
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const load = () => api("/analytics/dashboard").then(setD).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [tick]);

  if (error) return <ErrorBox error={error} />;
  if (!d) return <Empty>Loading dashboard…</Empty>;
  const k = d.kpis;
  const maxDay = Math.max(1, ...d.daily_trend.map((x) => Math.max(x.created, x.fulfilled)));

  return (
    <div className="stack">
      <div className="grid g4">
        <Kpi accent label="Active requests" value={k.active_requests} hint={`${k.pending_verification} awaiting verification`} />
        <Kpi label="Critical requests" value={k.critical_requests} hint="all time" />
        <Kpi label="Fulfillment rate" value={`${k.fulfillment_rate}%`} hint={`${k.completed_requests} of closed requests`} />
        <Kpi label="Avg. fulfillment time" value={`${k.avg_fulfillment_hours}h`} hint="request → all units arranged" />
        <Kpi label="Total requests" value={k.total_requests} />
        <Kpi label="Registered donors" value={k.registered_donors} hint={`${k.available_donors} available & eligible now`} />
        <Kpi label="Donations completed" value={k.donations_completed} />
        <Kpi label="Avg. donor response" value={`${k.avg_response_minutes}m`} hint={`${k.acceptance_rate}% acceptance`} />
      </div>

      <div className="grid g-side">
        <div className="card">
          <div className="card-head"><div><h2>Requests vs fulfilled · last 14 days</h2></div>
            <div className="legend"><span><i style={{ background: "#cbd5e1" }} />Created</span><span><i style={{ background: "var(--red)" }} />Fulfilled</span></div></div>
          <div className="cols">
            {d.daily_trend.map((x) => (
              <div className="col" key={x.date} title={`${x.date}: ${x.created} created, ${x.fulfilled} fulfilled`}>
                <div className="pair">
                  <div className="c1" style={{ height: `${(x.created / maxDay) * 100}%` }} />
                  <div className="c2" style={{ height: `${(x.fulfilled / maxDay) * 100}%` }} />
                </div>
                <span className="lbl">{new Date(x.date).getDate()}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="ai-box">
          <div className="ai-tag"><Icon name="spark" size={12} /> AI insights</div>
          <div style={{ marginTop: 6 }}>
            {d.insights.map((s) => <div className="insight small" key={s}><span style={{ color: "var(--red)" }}>●</span><span>{s}</span></div>)}
          </div>
        </div>
      </div>

      <div className="grid g2">
        <div className="card">
          <div className="card-head"><div><h2>AI demand forecast · next 7 days</h2>
            <p>Exponentially-weighted daily demand vs. eligible compatible donors.</p></div></div>
          <div className="table-wrap"><table>
            <thead><tr><th>Group</th><th>Last 7d</th><th>Predicted</th><th>Trend</th><th>Supply</th><th>Shortage risk</th></tr></thead>
            <tbody>{d.forecast.map((f) => (
              <tr key={f.blood_group}>
                <td><Blood g={f.blood_group} /></td>
                <td className="mono">{f.last_7_days} u</td>
                <td className="mono"><b>{f.predicted_next_7_days} u</b></td>
                <td className="mono" style={{ color: f.trend_pct > 0 ? "var(--red)" : "var(--green)" }}>{f.trend_pct > 0 ? "▲" : f.trend_pct < 0 ? "▼" : "–"} {Math.abs(f.trend_pct)}%</td>
                <td className="mono">{f.eligible_supply}</td>
                <td><span className={"badge " + riskClass[f.shortage_risk]}>{label(f.shortage_risk)}</span></td>
              </tr>))}
            </tbody>
          </table></div>
        </div>
        <div className="card">
          <div className="card-head"><div><h2>Demand by blood group</h2><p>Units requested (red) vs eligible donors of that group (grey)</p></div></div>
          <Bars rows={d.demand_by_blood_group} labelKey="blood_group" valueKey="units" altKey="eligible_donors" unit=" u" />
        </div>
      </div>

      <div className="grid g3">
        <div className="card"><h2 style={{ marginBottom: 12 }}>Requests by hospital</h2>
          <Bars rows={d.requests_by_hospital} labelKey="name" valueKey="count" /></div>
        <div className="card"><h2 style={{ marginBottom: 12 }}>Requests by city</h2>
          <Bars rows={d.requests_by_city} labelKey="name" valueKey="count" />
          <h3 style={{ margin: "18px 0 10px" }}>By priority</h3>
          <Bars rows={Object.entries(d.priority_breakdown).map(([k, v]) => ({ name: label(k), count: v }))} labelKey="name" valueKey="count" />
        </div>
        <div className="card"><h2 style={{ marginBottom: 12 }}>Status breakdown</h2>
          <Bars rows={Object.entries(d.status_breakdown).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ name: label(k), count: v }))} labelKey="name" valueKey="count" />
          <button className="btn sm" style={{ marginTop: 16 }} onClick={() => api("/maintenance/run", { method: "POST" })
            .then((r) => { toast(`Scheduler ran: ${r.escalated} escalated, ${r.expired} expired`); load(); })}>
            Run escalation scheduler now
          </button>
          <button className="btn sm ghost" style={{ marginTop: 8 }} onClick={() => go("all")}>Open all requests →</button>
          {user.role === "admin" && (
            <button className="btn sm ghost" style={{ marginTop: 8 }} onClick={() => {
              if (window.confirm("Delete ALL data and reload the demo data?"))
                api("/demo/reset", { method: "POST" }).then(() => { toast("Demo data reset"); load(); }).catch((e) => setError(e.message));
            }}>Reset demo data</button>
          )}
        </div>
      </div>
    </div>
  );
}
