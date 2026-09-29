import { FormEvent, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";

export default function Settings() {
  const { user, refresh } = useAuth();
  const [name, setName] = useState(user?.full_name ?? "");
  const [low, setLow] = useState(user?.hr_low_threshold ?? 45);
  const [high, setHigh] = useState(user?.hr_high_threshold ?? 120);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.updateMe({ full_name: name, hr_low_threshold: low, hr_high_threshold: high });
      await refresh();
      setMsg({ ok: true, text: "Saved." });
    } catch (err) {
      setMsg({ ok: false, text: (err as Error).message });
    }
  };

  return (
    <div className="stack narrow">
      <h1>Settings</h1>
      <form className="card stack" onSubmit={save}>
        <label>
          Full name
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <h2>Alert limits</h2>
        <p className="muted small">You'll get an alert when your pulse goes outside this range (15-minute cooldown per alert type).</p>
        <div className="row">
          <label>
            Low (bpm)
            <input type="number" min={25} max={100} value={low} onChange={(e) => setLow(+e.target.value)} />
          </label>
          <label>
            High (bpm)
            <input type="number" min={80} max={220} value={high} onChange={(e) => setHigh(+e.target.value)} />
          </label>
        </div>
        <div className="row">
          <button className="btn primary">Save</button>
          {msg && <span className={msg.ok ? "muted" : "error"}>{msg.text}</span>}
        </div>
      </form>
    </div>
  );
}
