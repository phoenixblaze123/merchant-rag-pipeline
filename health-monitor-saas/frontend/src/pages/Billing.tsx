import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, Plan } from "../api";
import { useAuth } from "../auth";

const money = (cents: number) => `$${(cents / 100).toFixed(2)}`;

export default function Billing() {
  const { user, refresh } = useAuth();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [mode, setMode] = useState<"stripe" | "mock">("mock");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [params] = useSearchParams();
  const sub = user?.subscription;

  useEffect(() => {
    api.plans().then(setPlans);
    api.billingMode().then((r) => setMode(r.mode));
    // Returning from Stripe Checkout: the webhook may land a moment later.
    if (params.get("checkout") === "success") {
      refresh();
      const id = setTimeout(refresh, 3000);
      return () => clearTimeout(id);
    }
  }, [params, refresh]);

  const go = async (action: () => Promise<{ url: string }>, key: string) => {
    setBusy(key);
    setError(null);
    try {
      const { url } = await action();
      if (url.startsWith(window.location.origin)) {
        await refresh();
        window.history.replaceState(null, "", new URL(url).pathname + new URL(url).search);
      } else {
        window.location.href = url;
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const cancel = async () => {
    if (!confirm("Cancel your subscription at the end of this billing period?")) return;
    try {
      await api.cancel();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="stack">
      <h1>Billing</h1>
      {params.get("checkout") === "success" && <div className="notice">Thanks! Your monthly subscription is set up.</div>}
      {params.get("checkout") === "cancelled" && <div className="notice">Checkout cancelled — no charge was made.</div>}
      {mode === "mock" && (
        <div className="notice muted">
          Demo mode: Stripe keys aren't configured, so choosing a plan activates it instantly without payment.
        </div>
      )}

      {sub && (
        <section className="card">
          <h2>Current subscription</h2>
          <dl className="facts">
            <dt>Plan</dt><dd>{sub.plan ? plans.find((p) => p.code === sub.plan)?.name ?? sub.plan : "None"}</dd>
            <dt>Status</dt><dd className="cap">{sub.status.replace("_", " ")}{sub.cancel_at_period_end && " · cancels at period end"}</dd>
            <dt>{sub.cancel_at_period_end ? "Ends" : "Renews"}</dt>
            <dd>{sub.current_period_end ? new Date(sub.current_period_end).toLocaleDateString() : "—"}</dd>
          </dl>
          <div className="row">
            {mode === "stripe" && sub.plan && (
              <button className="btn" disabled={busy === "portal"} onClick={() => go(api.portal, "portal")}>
                Manage payment & invoices
              </button>
            )}
            {sub.is_active && !sub.cancel_at_period_end && (
              <button className="btn ghost" onClick={cancel}>Cancel subscription</button>
            )}
          </div>
        </section>
      )}

      <section className="plans">
        {plans.map((p) => {
          const current = sub?.is_active && sub.plan === p.code;
          return (
            <div key={p.code} className={`card plan ${current ? "current" : ""}`}>
              <h2>{p.name}</h2>
              <div className="price">{money(p.price_cents)}<span className="muted"> / month</span></div>
              <ul>
                {p.features.map((f) => <li key={f}>{f}</li>)}
              </ul>
              <button
                className="btn primary"
                disabled={current || busy === p.code}
                onClick={() =>
                  // With Stripe, plan changes are prorated in the customer portal.
                  mode === "stripe" && sub?.is_active ? go(api.portal, p.code) : go(() => api.checkout(p.code), p.code)
                }
              >
                {current ? "Current plan" : busy === p.code ? "Redirecting…" : sub?.is_active ? `Switch to ${p.name}` : `Subscribe`}
              </button>
            </div>
          );
        })}
      </section>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
