import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Device } from "../api";
import { useAuth } from "../auth";

export default function Devices() {
  const { user } = useAuth();
  const [devices, setDevices] = useState<Device[]>([]);
  const [name, setName] = useState("");
  const [model, setModel] = useState("generic-wrist-ppg");
  const [newKey, setNewKey] = useState<{ name: string; key: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.devices().then(setDevices).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const d = await api.addDevice(name, model);
      setNewKey({ name: d.name, key: d.api_key });
      setName("");
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const rotate = async (d: Device) => {
    if (!confirm(`Issue a new key for "${d.name}"? The old key stops working immediately.`)) return;
    try {
      const r = await api.rotateKey(d.id);
      setNewKey({ name: r.name, key: r.api_key });
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const remove = async (d: Device) => {
    if (!confirm(`Remove "${d.name}"? It will stop uploading; past readings are kept.`)) return;
    await api.removeDevice(d.id);
    load();
  };

  const active = user?.subscription?.is_active;

  return (
    <div className="stack">
      <h1>Devices</h1>

      {newKey && (
        <div className="card key-card">
          <h2>Device key for “{newKey.name}”</h2>
          <p>Copy this key into the device (or simulator) now — it won't be shown again.</p>
          <code className="key">{newKey.key}</code>
          <div className="row">
            <button className="btn" onClick={() => navigator.clipboard?.writeText(newKey.key)}>Copy</button>
            <button className="btn ghost" onClick={() => setNewKey(null)}>Done</button>
          </div>
          <p className="muted small">
            Try it: <code>python device-simulator/simulate.py --key {newKey.key.slice(0, 10)}… --backfill-hours 24 --interval 5</code>
          </p>
        </div>
      )}

      <section className="card">
        <h2>Register a wrist device</h2>
        {active ? (
          <form className="row wrap" onSubmit={add}>
            <input placeholder="Name, e.g. Left wrist band" required value={name} onChange={(e) => setName(e.target.value)} />
            <input placeholder="Model" value={model} onChange={(e) => setModel(e.target.value)} />
            <button className="btn primary">Add device</button>
          </form>
        ) : (
          <p className="muted">
            You need an active subscription to connect devices. <Link to="/billing">See plans</Link>
          </p>
        )}
        {error && <p className="error">{error}</p>}
      </section>

      <section className="card">
        <h2>Your devices</h2>
        {devices.length === 0 ? (
          <p className="muted">No devices yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr><th>Name</th><th>Model</th><th>Key</th><th>Last upload</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {devices.map((d) => (
                <tr key={d.id} className={d.is_active ? "" : "muted"}>
                  <td>{d.name}</td>
                  <td>{d.model}</td>
                  <td><code>{d.api_key_prefix}…</code></td>
                  <td>{d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : "never"}</td>
                  <td>{d.is_active ? "Active" : "Removed"}</td>
                  <td className="actions">
                    {d.is_active && (
                      <>
                        <button className="btn ghost small" onClick={() => rotate(d)}>New key</button>
                        <button className="btn ghost small" onClick={() => remove(d)}>Remove</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
