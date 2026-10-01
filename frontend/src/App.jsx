import { useCallback, useEffect, useState } from "react";
import { api, auth, ago } from "./api";
import { Icon } from "./components/ui.jsx";
import Login from "./pages/Login.jsx";
import NewRequest from "./pages/NewRequest.jsx";
import RequestsList from "./pages/RequestsList.jsx";
import RequestDetail from "./pages/RequestDetail.jsx";
import DonorHome from "./pages/DonorHome.jsx";
import DonorProfile from "./pages/DonorProfile.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import DonorsList from "./pages/DonorsList.jsx";
import AdminUsers from "./pages/AdminUsers.jsx";
import Hospitals from "./pages/Hospitals.jsx";

const NAV = {
  requester: [["new", "New blood request", "plus"], ["mine", "My requests", "list"]],
  donor: [["incoming", "Requests for me", "inbox"], ["profile", "My donor profile", "user"]],
  coordinator: [["dashboard", "Dashboard", "chart"], ["queue", "Verification queue", "shield"],
    ["all", "All requests", "list"], ["donors", "Donors", "users"], ["new", "New request", "plus"]],
  admin: [["dashboard", "Dashboard & AI", "chart"], ["all", "All requests", "list"], ["flagged", "Flagged / suspicious", "flag"],
    ["users", "Users", "users"], ["donors", "Donors", "drop"], ["hospitals", "Hospitals", "hospital"]],
};
const TITLES = {
  new: ["New blood request", "AI checks urgency and duplicates while you type."],
  mine: ["My requests", "Track donor responses and request status."],
  incoming: ["Requests matched to you", "Only requests you are compatible with and close to."],
  profile: ["My donor profile", "Keep availability and last donation date up to date."],
  dashboard: ["Dashboard", "Live statistics, AI insights and demand forecast."],
  queue: ["Verification queue", "Verify new requests before donors are contacted."],
  all: ["All blood requests", "Search and filter every request."],
  flagged: ["Flagged requests", "Duplicates, reports and suspicious signals detected by AI."],
  donors: ["Donor registry", "Contact details stay private until a donor accepts a request."],
  users: ["Users", "Manage donors, requesters and staff accounts."],
  hospitals: ["Hospitals & blood banks", "Registered facilities."],
  detail: ["Request details", ""],
};

export default function App() {
  const [user, setUser] = useState(null);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(!!auth.token);
  const [route, setRoute] = useState({ page: null, id: null });
  const [notifs, setNotifs] = useState({ unread: 0, items: [] });
  const [showNotifs, setShowNotifs] = useState(false);
  const [tick, setTick] = useState(0); // bump to make pages refetch

  useEffect(() => { api("/meta").then(setMeta).catch(() => {}); }, []);
  useEffect(() => {
    if (!auth.token) return;
    api("/auth/me").then((u) => { setUser(u); setRoute({ page: NAV[u.role][0][0] }); })
      .catch(() => auth.clear()).finally(() => setLoading(false));
  }, []);

  const loadNotifs = useCallback(() => { if (auth.token) api("/notifications").then(setNotifs).catch(() => {}); }, []);
  useEffect(() => {
    if (!user) return;
    loadNotifs();
    // light polling so new notifications / donor responses appear without a refresh
    const t = setInterval(() => { loadNotifs(); setTick((x) => x + 1); }, 10000);
    return () => clearInterval(t);
  }, [user, loadNotifs]);

  const onLogin = (data) => { auth.set(data.token); setUser(data.user); setRoute({ page: NAV[data.user.role][0][0] }); };
  const logout = () => { auth.clear(); setUser(null); setNotifs({ unread: 0, items: [] }); };
  const go = (page, id = null) => { setRoute({ page, id }); setShowNotifs(false); window.scrollTo(0, 0); };
  const refreshUser = () => api("/auth/me").then(setUser);

  if (loading) return <div className="empty" style={{ paddingTop: 120 }}>Loading…</div>;
  if (!user) return <Login onLogin={onLogin} meta={meta} />;

  const props = { user, meta, go, tick, refreshUser, reloadNotifs: loadNotifs };
  const pages = {
    new: <NewRequest {...props} />,
    mine: <RequestsList {...props} mine />,
    all: <RequestsList {...props} />,
    queue: <RequestsList {...props} preset={{ status: "pending_verification" }} />,
    flagged: <RequestsList {...props} flagged />,
    detail: <RequestDetail {...props} id={route.id} />,
    incoming: <DonorHome {...props} />,
    profile: <DonorProfile {...props} />,
    dashboard: <Dashboard {...props} />,
    donors: <DonorsList {...props} />,
    users: <AdminUsers {...props} />,
    hospitals: <Hospitals {...props} />,
  };
  const [title, sub] = TITLES[route.page] || ["", ""];

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Icon name="drop" color="#fff" /></div>
          <div><div className="brand-name">BloodLink</div><div className="brand-sub">Emergency Donor Network</div></div>
        </div>
        {NAV[user.role].map(([key, text, icon]) => (
          <button key={key} className={"nav-btn" + (route.page === key ? " active" : "")} onClick={() => go(key)}>
            <Icon name={icon} size={17} /> {text}
          </button>
        ))}
        <div className="sidebar-foot">
          <div className="who">{user.name}</div>
          <div className="role">{user.role}{user.donor ? ` · ${user.donor.blood_group}` : ""}</div>
          <button className="nav-btn" style={{ padding: "8px 0", marginTop: 8 }} onClick={logout}>
            <Icon name="logout" size={16} /> Log out
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div><h1>{title}</h1>{sub && <p>{sub}</p>}</div>
          <div className="row">
            <button className="btn bell" onClick={() => { setShowNotifs(!showNotifs); if (!showNotifs) loadNotifs(); }}
              aria-label="Notifications">
              <Icon name="bell" size={17} /> Notifications
              {notifs.unread > 0 && <span className="dot">{notifs.unread}</span>}
            </button>
          </div>
        </div>

        {showNotifs && (
          <div className="drawer">
            <div className="row spread" style={{ marginBottom: 10 }}>
              <h3>Notifications</h3>
              <button className="btn sm" onClick={() => api("/notifications/read-all", { method: "POST" }).then(loadNotifs)}>
                Mark all read
              </button>
            </div>
            <div className="stack" style={{ display: "grid", gap: 8 }}>
              {notifs.items.length === 0 && <div className="empty">No notifications yet</div>}
              {notifs.items.map((n) => (
                <div key={n.id} className={"notif" + (n.read ? "" : " unread")}
                  style={{ cursor: n.request_id && user.role !== "donor" ? "pointer" : "default" }}
                  onClick={() => {
                    if (!n.request_id) return;
                    user.role === "donor" ? go("incoming") : go("detail", n.request_id);
                  }}>
                  <div className="row spread"><b>{n.title}</b><span className="small muted">{ago(n.created_at)}</span></div>
                  <div className="small" style={{ whiteSpace: "pre-line" }}>{n.body}</div>
                  <div className="small muted" style={{ marginTop: 4 }}>
                    via {n.channels.join(" · ")}{n.delivery_status !== "sent" && " · ⚠ delivery issue"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div key={route.page + (route.id || "")}>{pages[route.page]}</div>
      </main>
    </div>
  );
}
