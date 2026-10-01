import { useEffect, useState } from "react";
import { api } from "../api";
import { Empty, ErrorBox, useToast } from "../components/ui.jsx";

export default function Hospitals({ meta, user }) {
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [f, setF] = useState({ name: "", city: "Karachi", area: "Saddar", phone: "" });
  const load = () => api("/admin/hospitals").then(setRows).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const add = async (e) => {
    e.preventDefault(); setError("");
    try { await api("/admin/hospitals", { method: "POST", body: f }); toast("Hospital added"); setF({ ...f, name: "", phone: "" }); load(); }
    catch (err) { setError(err.message); }
  };

  return (
    <div className="stack">
      <div className="card">
        <ErrorBox error={error} />
        {!rows ? <Empty>Loading…</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Hospital / blood bank</th><th>City</th><th>Phone</th><th>Verified</th><th>Requests</th></tr></thead>
            <tbody>{rows.map((h) => (
              <tr key={h.id}><td><b>{h.name}</b></td><td>{h.city}</td><td className="small">{h.phone}</td>
                <td>{h.verified ? <span className="badge b-green">Verified</span> : <span className="badge b-amber">Pending</span>}</td>
                <td className="mono">{h.requests}</td></tr>))}
            </tbody>
          </table></div>
        )}
      </div>
      {user.role === "admin" && (
        <form className="card" onSubmit={add}>
          <h2 style={{ marginBottom: 12 }}>Add hospital or blood bank</h2>
          <div className="form-grid">
            <label className="field">Name<input required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
            <label className="field">Phone<input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></label>
            <label className="field">City<select value={f.city} onChange={(e) => setF({ ...f, city: e.target.value, area: meta.areas[e.target.value][0] })}>
              {Object.keys(meta?.areas || {}).map((c) => <option key={c}>{c}</option>)}</select></label>
            <label className="field">Area<select value={f.area} onChange={(e) => setF({ ...f, area: e.target.value })}>
              {(meta?.areas[f.city] || []).map((a) => <option key={a}>{a}</option>)}</select></label>
          </div>
          <button className="btn primary" style={{ marginTop: 14 }}>Add hospital</button>
        </form>
      )}
    </div>
  );
}
