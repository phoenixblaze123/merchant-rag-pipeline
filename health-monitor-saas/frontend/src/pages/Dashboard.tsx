import { useCallback, useEffect, useState } from "react";
import { Alert, api, DailySummary, Reading } from "../api";
import { useAuth } from "../auth";
import PulseChart from "../components/PulseChart";

const RANGES = [
  { hours: 6, label: "6h" },
  { hours: 24, label: "24h" },
  { hours: 24 * 7, label: "7d" },
];

const ALERT_LABEL: Record<Alert["kind"], string> = {
  high_hr: "High heart rate",
  low_hr: "Low heart rate",
  irregular_rhythm: "Irregular rhythm",
};

function ago(iso: string) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  if (mins < 1440) return `${Math.round(mins / 60)} h ago`;
  return new Date(iso).toLocaleDateString();
}

export default function Dashboard() {
  const { user } = useAuth();
  const [hours, setHours] = useState(24);
  const [readings, setReadings] = useState<Reading[]>([]);
  const [days, setDays] = useState<DailySummary[]>([]);
  const [latest, setLatest] = useState<Reading | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [r, s, a] = await Promise.all([api.readings(hours), api.summary(7), api.alerts()]);
      setReadings(r);
      setDays(s.days);
      setLatest(s.latest);
      setAlerts(a);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [hours]);

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [load]);

  const ack = async (id: number) => {
    await api.ackAlert(id);
    setAlerts((xs) => xs.map((a) => (a.id === id ? { ...a, acknowledged: true } : a)));
  };

  const good = readings.filter((r) => r.signal_quality == null || r.signal_quality >= 0.5);
  const avg = good.length ? Math.round(good.reduce((s, r) => s + r.bpm, 0) / good.length) : null;
  const resting = days.length ? Math.min(...days.map((d) => d.min_bpm)) : null;
  const hrvs = good.map((r) => r.hrv_ms).filter((v): v is number => v != null);
  const hrv = hrvs.length ? Math.round(hrvs.reduce((s, v) => s + v, 0) / hrvs.length) : null;
  const openAlerts = alerts.filter((a) => !a.acknowledged).length;
  const rangeLabel = RANGES.find((r) => r.hours === hours)?.label;

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Hi{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}</h1>
        <div className="segmented" role="group" aria-label="Time range">
          {RANGES.map((r) => (
            <button key={r.hours} className={r.hours === hours ? "on" : ""} onClick={() => setHours(r.hours)}>
              {r.label}
            </button>
          ))}
        </div>
      </div>
      {error && <p className="error">{error}</p>}

      <section className="tiles">
        <div className="tile">
          <div className="tile-label">Latest pulse</div>
          <div className="tile-value">{latest ? latest.bpm : "—"}<span className="unit">bpm</span></div>
          <div className="tile-sub muted">{latest ? ago(latest.recorded_at) : "no data yet"}</div>
        </div>
        <div className="tile">
          <div className="tile-label">Average · {rangeLabel}</div>
          <div className="tile-value">{avg ?? "—"}<span className="unit">bpm</span></div>
          <div className="tile-sub muted">{good.length.toLocaleString()} samples</div>
        </div>
        <div className="tile">
          <div className="tile-label">Lowest · 7d</div>
          <div className="tile-value">{resting ?? "—"}<span className="unit">bpm</span></div>
          <div className="tile-sub muted">usually while asleep</div>
        </div>
        <div className="tile">
          <div className="tile-label">HRV · {rangeLabel}</div>
          <div className="tile-value">{hrv ?? "—"}<span className="unit">ms</span></div>
          <div className="tile-sub muted">RMSSD average</div>
        </div>
      </section>

      <section className="card">
        <h2>Heart rate</h2>
        <PulseChart
          readings={readings}
          hours={hours}
          low={user?.hr_low_threshold ?? 45}
          high={user?.hr_high_threshold ?? 120}
        />
      </section>

      <div className="two-col">
        <section className="card">
          <h2>Alerts {openAlerts > 0 && <span className="pill critical">{openAlerts} new</span>}</h2>
          {alerts.length === 0 ? (
            <p className="muted">No alerts. We'll flag readings outside your limits or an irregular rhythm.</p>
          ) : (
            <ul className="alerts">
              {alerts.map((a) => (
                <li key={a.id} className={a.acknowledged ? "done" : ""}>
                  <span className={`status-icon ${a.kind === "irregular_rhythm" ? "critical" : "serious"}`} aria-hidden>
                    {a.kind === "low_hr" ? "↓" : a.kind === "high_hr" ? "↑" : "⚠"}
                  </span>
                  <div className="alert-body">
                    <strong>{ALERT_LABEL[a.kind]}</strong>
                    <div className="muted small">{a.message} · {ago(a.reading_time)}</div>
                  </div>
                  {!a.acknowledged && (
                    <button className="btn ghost small" onClick={() => ack(a.id)}>Dismiss</button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <h2>Last 7 days</h2>
          {days.length === 0 ? (
            <p className="muted">Daily summaries appear once your device uploads data.</p>
          ) : (
            <table className="table">
              <thead>
                <tr><th>Day</th><th>Avg</th><th>Min</th><th>Max</th><th>HRV</th></tr>
              </thead>
              <tbody>
                {[...days].reverse().map((d) => (
                  <tr key={d.day}>
                    <td>{new Date(d.day + "T00:00:00Z").toLocaleDateString([], { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" })}</td>
                    <td>{Math.round(d.avg_bpm)}</td>
                    <td>{d.min_bpm}</td>
                    <td>{d.max_bpm}</td>
                    <td>{d.avg_hrv_ms != null ? Math.round(d.avg_hrv_ms) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="footnote muted">Days are grouped in UTC. Values in bpm; HRV in ms.</p>
        </section>
      </div>

      <p className="footnote muted">
        PulseCloud is a wellness monitor, not a medical device. If you feel unwell, contact a healthcare professional.
      </p>
    </div>
  );
}
