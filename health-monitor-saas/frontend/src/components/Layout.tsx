import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";

export default function Layout() {
  const { user, logout } = useAuth();
  const sub = user?.subscription;

  return (
    <div className="shell">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-dot" aria-hidden /> PulseCloud
        </Link>
        <nav>
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/devices">Devices</NavLink>
          <NavLink to="/billing">Billing</NavLink>
          <NavLink to="/settings">Settings</NavLink>
        </nav>
        <div className="user">
          <span className="muted">{user?.email}</span>
          <button className="btn ghost" onClick={logout}>Sign out</button>
        </div>
      </header>

      {sub && !sub.is_active && (
        <div className="banner">
          Your subscription is <strong>{sub.status.replace("_", " ")}</strong>. Devices can't upload pulse data until
          you <Link to="/billing">choose a monthly plan</Link>.
        </div>
      )}

      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
