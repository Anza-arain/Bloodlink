import { createContext, useCallback, useContext, useState } from "react";
import { label } from "../api";

// ---------- toast ----------
const ToastCtx = createContext(() => {});
export function ToastProvider({ children }) {
  const [msg, setMsg] = useState(null);
  const show = useCallback((m) => { setMsg(m); setTimeout(() => setMsg(null), 3200); }, []);
  return (
    <ToastCtx.Provider value={show}>
      {children}
      {msg && <div className="toast" role="status">{msg}</div>}
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);

// ---------- icons (inline, no dependency) ----------
const paths = {
  drop: "M12 3s-7 8.2-7 13a7 7 0 0 0 14 0c0-4.8-7-13-7-13z",
  plus: "M12 5v14M5 12h14",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  chart: "M3 3v18h18M7 15l4-4 3 3 5-6",
  user: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  users: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
  bell: "M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  check: "M20 6 9 17l-5-5",
  inbox: "M22 12h-6l-2 3h-4l-2-3H2M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.1z",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  hospital: "M3 21h18M5 21V7l7-4 7 4v14M9 21v-4h6v4M10 10h4M12 8v4",
  spark: "M12 3l1.9 5.8L20 10l-6.1 1.2L12 17l-1.9-5.8L4 10l6.1-1.2z",
  flag: "M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7",
};
export function Icon({ name, size = 18, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={paths[name]} />
    </svg>
  );
}

// ---------- badges ----------
export const Blood = ({ g, lg }) => <span className={"blood" + (lg ? " lg" : "")}>{g}</span>;

const prioClass = { critical: "b-red", urgent: "b-amber", normal: "b-gray" };
export const Priority = ({ p }) => <span className={"badge " + (prioClass[p] || "b-gray")}>{label(p)}</span>;

const statusClass = {
  pending_verification: "b-amber", active: "b-blue", donors_contacted: "b-blue", partially_fulfilled: "b-amber",
  fulfilled: "b-green", completed: "b-green", cancelled: "b-gray", expired: "b-gray", rejected: "b-red",
  notified: "b-blue", accepted: "b-green", declined: "b-gray", donated: "b-green", no_response: "b-gray",
};
export const Status = ({ s }) => <span className={"badge " + (statusClass[s] || "b-gray")}>{label(s)}</span>;

export const Verified = ({ v }) =>
  v === "verified" ? <span className="badge b-green"><Icon name="check" size={12} /> Verified Blood Request</span>
    : v === "rejected" ? <span className="badge b-red">Rejected</span>
      : <span className="badge b-amber">Awaiting verification</span>;

export function Score({ value }) {
  if (!value) return <span className="badge b-gray">Not eligible</span>;
  return (
    <span className="score mono">
      <b>{Math.round(value)}%</b>
      <span className="score-bar"><div style={{ width: `${value}%` }} /></span>
    </span>
  );
}

const FLOW = ["pending_verification", "active", "donors_contacted", "partially_fulfilled", "fulfilled", "completed"];
export function StatusFlow({ status }) {
  const idx = FLOW.indexOf(status);
  if (idx === -1) return <div className="status-flow"><span className="now">{label(status)}</span></div>;
  return (
    <div className="status-flow">
      {FLOW.map((s, i) => <span key={s} className={i < idx ? "done" : i === idx ? "now" : ""}>{label(s)}</span>)}
    </div>
  );
}

export function Bars({ rows, valueKey, labelKey, altKey, unit = "" }) {
  const max = Math.max(1, ...rows.map((r) => Math.max(r[valueKey], altKey ? r[altKey] : 0)));
  return (
    <div className="bars">
      {rows.map((r) => (
        <div className="bar-row" key={r[labelKey]}>
          <span title={r[labelKey]} style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r[labelKey]}</span>
          <div>
            <div className="track"><div className="fill" style={{ width: `${(r[valueKey] / max) * 100}%` }} /></div>
            {altKey && <div className="track" style={{ marginTop: 3, height: 6 }}><div className="fill alt" style={{ width: `${(r[altKey] / max) * 100}%` }} /></div>}
          </div>
          <b className="mono" style={{ textAlign: "right" }}>{r[valueKey]}{unit}</b>
        </div>
      ))}
    </div>
  );
}

export const Empty = ({ children }) => <div className="empty">{children}</div>;
export const ErrorBox = ({ error }) => (error ? <div className="alert err">{error}</div> : null);
