export type Subscription = {
  plan: string | null;
  status: string;
  is_active: boolean;
  cancel_at_period_end: boolean;
  current_period_end: string | null;
};
export type User = {
  id: number;
  email: string;
  full_name: string;
  hr_low_threshold: number;
  hr_high_threshold: number;
  created_at: string;
  subscription: Subscription | null;
};
export type Plan = {
  code: string;
  name: string;
  price_cents: number;
  max_devices: number;
  retention_days: number;
  features: string[];
};
export type Device = {
  id: number;
  name: string;
  model: string;
  api_key_prefix: string;
  is_active: boolean;
  created_at: string;
  last_seen_at: string | null;
};
export type Reading = {
  id: number;
  device_id: number;
  recorded_at: string;
  bpm: number;
  hrv_ms: number | null;
  signal_quality: number | null;
  irregular_rhythm: boolean;
};
export type DailySummary = {
  day: string;
  readings: number;
  avg_bpm: number;
  min_bpm: number;
  max_bpm: number;
  avg_hrv_ms: number | null;
};
export type Alert = {
  id: number;
  device_id: number;
  kind: "high_hr" | "low_hr" | "irregular_rhythm";
  bpm: number;
  message: string;
  reading_time: string;
  acknowledged: boolean;
};

const TOKEN_KEY = "pulsecloud.token";

export const tokenStore = {
  get: () => {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (t: string | null) => {
    try {
      if (t) localStorage.setItem(TOKEN_KEY, t);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* storage unavailable */
    }
  },
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof URLSearchParams)) headers.set("Content-Type", "application/json");

  const res = await fetch(`/api/v1${path}`, { ...init, headers });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.map((d: { msg: string }) => d.msg).join("; ") : body.detail;
    throw new ApiError(res.status, detail ?? res.statusText);
  }
  return body as T;
}

const json = (data: unknown) => JSON.stringify(data);

export const api = {
  register: (email: string, password: string, full_name: string) =>
    request<User>("/auth/register", { method: "POST", body: json({ email, password, full_name }) }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/token", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }),
    }),
  me: () => request<User>("/auth/me"),
  updateMe: (data: Partial<Pick<User, "full_name" | "hr_low_threshold" | "hr_high_threshold">>) =>
    request<User>("/auth/me", { method: "PATCH", body: json(data) }),

  plans: () => request<Plan[]>("/billing/plans"),
  billingMode: () => request<{ mode: "stripe" | "mock" }>("/billing/config"),
  checkout: (plan: string) => request<{ url: string }>("/billing/checkout", { method: "POST", body: json({ plan }) }),
  portal: () => request<{ url: string }>("/billing/portal", { method: "POST" }),
  cancel: () => request<Subscription>("/billing/cancel", { method: "POST" }),

  devices: () => request<Device[]>("/devices"),
  addDevice: (name: string, model: string) =>
    request<Device & { api_key: string }>("/devices", { method: "POST", body: json({ name, model }) }),
  rotateKey: (id: number) => request<Device & { api_key: string }>(`/devices/${id}/rotate-key`, { method: "POST" }),
  removeDevice: (id: number) => request<void>(`/devices/${id}`, { method: "DELETE" }),

  readings: (hours: number) => {
    const start = new Date(Date.now() - hours * 3600_000).toISOString();
    return request<Reading[]>(`/readings?start=${encodeURIComponent(start)}&limit=10000`);
  },
  summary: (days: number) => request<{ days: DailySummary[]; latest: Reading | null }>(`/readings/summary?days=${days}`),
  alerts: () => request<Alert[]>("/alerts?limit=20"),
  ackAlert: (id: number) => request<Alert>(`/alerts/${id}/ack`, { method: "POST" }),
};
