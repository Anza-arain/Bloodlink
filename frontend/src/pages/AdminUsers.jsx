import { useEffect, useState } from "react";
import { api, fmtDate, label } from "../api";
import { Empty, ErrorBox, useToast } from "../components/ui.jsx";

export function AdminUsers({ user }) {
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const [role, setRole] = useState("");
  const [error, setError] = useState("");
  const load = () => api("/admin/users", { params: { role } }).then(setRows).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [role]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (u) => api(`/admin/users/${u.id}/${u.account_status === "active" ? "block" : "unblock"}`, { method: "POST" })
    .then(() => { toast(`${u.name} ${u.account_status === "active" ? "blocked" : "unblocked"}`); load(); })
    .catch((e) => setError(e.message));

  return (
    <div className="card">
      <div className="filters" style={{ maxWidth: 260 }}>
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">All roles</option><option value="donor">Donors</option><option value="requester">Requesters</option>
          <option value="coordinator">Coordinators</option><option value="admin">Admins</option>
        </select>
      </div>
      <ErrorBox error={error} />
      {!rows ? <Empty>Loading…</Empty> : (
        <div className="table-wrap"><table>
          <thead><tr><th>Name</th><th>Role</th><th>Email</th><th>Phone</th><th>Phone verified</th><th>Status</th><th>Joined</th><th></th></tr></thead>
          <tbody>{rows.map((u) => (
            <tr key={u.id} className={u.account_status === "blocked" ? "dim" : ""}>
              <td><b>{u.name}</b>{u.donor && <span className="small muted"> · {u.donor.blood_group}</span>}</td>
              <td>{label(u.role)}</td><td className="small">{u.email}</td><td className="small">{u.phone}</td>
              <td>{u.phone_verified ? <span className="badge b-green">Yes</span> : <span className="badge b-amber">No</span>}</td>
              <td>{u.account_status === "active" ? <span className="badge b-green">Active</span> : <span className="badge b-red">Blocked</span>}</td>
              <td className="small muted">{fmtDate(u.created_at)}</td>
              <td>{u.id !== user.id && <button className="btn sm" onClick={() => toggle(u)}>{u.account_status === "active" ? "Block" : "Unblock"}</button>}</td>
            </tr>))}
          </tbody>
        </table></div>
      )}
    </div>
  );
}
export default AdminUsers;
