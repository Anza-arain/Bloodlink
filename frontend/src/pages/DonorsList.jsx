import { useEffect, useState } from "react";
import { api } from "../api";
import { Blood, Empty, ErrorBox } from "../components/ui.jsx";

export default function DonorsList({ meta }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [f, setF] = useState({ blood_group: "", city: "", available: "", eligible: "" });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  useEffect(() => { api("/donors", { params: f }).then(setRows).catch((e) => setError(e.message)); }, [f]);

  return (
    <div className="card">
      <div className="filters">
        <select value={f.blood_group} onChange={set("blood_group")}><option value="">All blood groups</option>{meta?.blood_groups.map((g) => <option key={g}>{g}</option>)}</select>
        <select value={f.city} onChange={set("city")}><option value="">All cities</option>{Object.keys(meta?.areas || {}).map((c) => <option key={c}>{c}</option>)}</select>
        <select value={f.available} onChange={set("available")}><option value="">Any availability</option><option value="true">Available</option><option value="false">Not available</option></select>
        <select value={f.eligible} onChange={set("eligible")}><option value="">Any eligibility</option><option value="true">Eligible</option><option value="false">Not eligible</option></select>
      </div>
      <ErrorBox error={error} />
      {!rows ? <Empty>Loading…</Empty> : rows.length === 0 ? <Empty>No donors match these filters.</Empty> : (
        <>
          <div className="small muted" style={{ marginBottom: 8 }}>{rows.length} donors · phone numbers are hidden (privacy)</div>
          <div className="table-wrap"><table>
            <thead><tr><th>Donor</th><th>Group</th><th>Area</th><th>Available</th><th>Eligible</th><th>Last donation</th><th>Donations</th></tr></thead>
            <tbody>{rows.map((d) => (
              <tr key={d.id}>
                <td><b>{d.name}</b></td><td><Blood g={d.blood_group} /></td><td>{d.area}, {d.city}</td>
                <td>{d.available ? "Yes" : "No"}</td>
                <td>{d.eligible ? <span className="badge b-green">Eligible</span> : <span className="badge b-gray" title={d.eligibility_reasons.join("\n")}>{d.eligibility_reasons[0]}</span>}</td>
                <td className="small">{d.last_donation_date || "Never"}</td><td className="mono">{d.total_donations}</td>
              </tr>))}
            </tbody>
          </table></div>
        </>
      )}
    </div>
  );
}
