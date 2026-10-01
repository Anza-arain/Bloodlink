import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorBox, useToast } from "../components/ui.jsx";
import { EligibilityCard } from "./DonorHome.jsx";

export default function DonorProfile({ meta, refreshUser }) {
  const toast = useToast();
  const [d, setD] = useState(null);
  const [f, setF] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/donors/me").then((x) => {
      setD(x);
      setF({ blood_group: x.blood_group, age: x.age, city: x.city, area: x.area, available: x.available,
        last_donation_date: x.last_donation_date || "", unavailable_until: x.unavailable_until || "" });
    }).catch((e) => setError(e.message));
  }, []);
  if (!f) return <ErrorBox error={error} />;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const save = async (e) => {
    e.preventDefault(); setError("");
    try {
      const body = { ...f, age: Number(f.age), last_donation_date: f.last_donation_date || null,
        unavailable_until: f.unavailable_until || null, clear_unavailable: !f.unavailable_until };
      const x = await api("/donors/me", { method: "PUT", body });
      setD(x); refreshUser(); toast("Profile saved");
    } catch (err) { setError(err.message); }
  };

  return (
    <div className="stack">
      <EligibilityCard d={d} />
      <form className="card" onSubmit={save}>
        <h2 style={{ marginBottom: 14 }}>Donor details</h2>
        <div className="form-grid">
          <label className="field">Blood group
            <select value={f.blood_group} onChange={set("blood_group")}>{meta?.blood_groups.map((g) => <option key={g}>{g}</option>)}</select>
          </label>
          <label className="field">Age<input type="number" min={16} max={80} value={f.age} onChange={set("age")} /></label>
          <label className="field">City
            <select value={f.city} onChange={(e) => setF({ ...f, city: e.target.value, area: meta.areas[e.target.value][0] })}>
              {Object.keys(meta?.areas || {}).map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
          <label className="field">Area<span className="hint">Only your area is stored, never your home address</span>
            <select value={f.area} onChange={set("area")}>{(meta?.areas[f.city] || []).map((a) => <option key={a}>{a}</option>)}</select>
          </label>
          <label className="field">Last donation date<input type="date" value={f.last_donation_date} onChange={set("last_donation_date")} /></label>
          <label className="field">Temporarily unavailable until<span className="hint">e.g. travelling, illness, medication</span>
            <input type="date" value={f.unavailable_until} onChange={set("unavailable_until")} /></label>
          <label className="check full"><input type="checkbox" checked={f.available} onChange={set("available")} /> I am available to donate</label>
        </div>
        <div style={{ marginTop: 14 }}><ErrorBox error={error} /></div>
        <button className="btn primary" style={{ marginTop: 12 }}>Save profile</button>
      </form>
    </div>
  );
}
